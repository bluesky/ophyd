#!/usr/bin/env python2
#
# Parses areaDetector documentation into Python
# Started off simple, but as is usually the case with this type of
# project, it gets cryptic pretty quickly...

import os
import re
import sys

import lxml
import lxml.html

try:
    DOC_PATH = sys.argv[1]
except IndexError:
    DOC_PATH = "html"

# PV$(N) (N=1-10)
n_regex = re.compile(
    r"^([a-z0-9_]+\$\(N\)[a-z0-9_]*)\s+\(N=(\d+)-(\d+)\)$", flags=re.IGNORECASE
)

# PV(1-10)
n1_regex = re.compile(
    r"^[a-z0-9_]+([\(\[](\d+)-(\d+)[\]\)])[a-z0-9_]*$", flags=re.IGNORECASE
)

# PV     PV_RBV
rbv_re = re.compile(r"^(.*)\s+(.*)_RBV$", flags=re.IGNORECASE)


class DocRow(object):
    __slots__ = [
        "param_idx_var",
        "asyn_interface",
        "access",
        "description",
        "drvinfo",
        "record",
        "record_type",
    ]

    def __init__(self, row):
        for attr, data in zip(self.__slots__, row):
            setattr(self, attr, data)

        self.record = self.record.replace("$(P)$(R)", "")
        self.record = self.record.replace("(P)$(R)", "")
        m = rbv_re.match(self.record)
        if m and (m.groups()[0] == m.groups()[1]):
            pv = m.groups()[0]
            self.record = [pv]
        else:
            self.record = [s.strip() for s in self.record.split("\n")]

        self.record_type = [s.strip() for s in self.record_type.split("\n")]

        # Couple quick fixes:
        self.record[0] = self.record[0].replace("ThresholdN", "Threshold$(N)")
        self.record[0] = self.record[0].replace(
            "ThresholdActualN", "ThresholdActual$(N)"
        )

        if len(self.record_type) < len(self.record) and len(self.record_type) == 1:
            self.record_type = self.record_type * len(self.record)

    @property
    def multiple(self):
        r0 = self.record[0]

        m = n_regex.match(r0)
        if m:
            pv_base, n_low, n_high = m.groups()
            n_low = int(n_low)
            n_high = int(n_high)

            return [pv_base.replace("$(N)", str(n)) for n in range(n_low, n_high + 1)]

        m = n1_regex.match(r0)
        if m:
            full_str, low, high = m.groups()
            low = int(low)
            high = int(high)
            return [r0.replace(full_str, str(n)) for n in range(low, high + 1)]

        return None

    def python_source(self):
        def get_doc(pv, type_):
            if not pv.strip():
                return ""

            if "\n" in self.description:
                quotes = "'''"
            else:
                quotes = "'"

            lines = self.description.split("\n")
            line_count = len(lines)
            if line_count > 1:
                m = re.match(r"^(\s+)", lines[1])
                if m:
                    whitespace = m.groups()[0]
                    self.description = "\n%s%s" % (
                        whitespace,
                        self.description.lstrip(),
                    )

            top_info = [pv]

            if self.access:
                top_info.append(self.access)

            if type_:
                top_info.append(type_)

            top_line = " ".join(top_info)
            return "{0}=u{3}[{1}] {2.description}{3},".format(
                pv, top_line, self, quotes
            )

        m = self.multiple
        if m is not None:
            record_type = self.record_type[0]
            return [get_doc(pv, record_type) for pv in m]

        return [
            get_doc(rec, type_) for rec, type_ in zip(self.record, self.record_type)
        ]

    def __iter__(self):
        for attr in self.__slots__:
            yield getattr(self, attr)

    @property
    def is_valid(self):
        if self.record[0].startswith("N/A"):
            return False

        if not self.multiple and any(" " in record for record in self.record):
            return False

        return True


def parse_doc(fn):
    with open(fn, "rt") as f:
        tree = lxml.html.fromstring(f.read())

    rows = tree.xpath("//tr")
    skip_header = False
    ret = []
    past_rows = []
    last_header = None
    for row in rows:
        row_text = [child.text_content().strip() for child in row.getchildren()]
        # all_text = '\n'.join(row_text)

        if row.xpath("th"):
            skip_header = row_text[0] == "ImageMode"
            last_header = row_text
        elif skip_header:
            print("(skip header)", row_text, file=sys.stderr)
        elif row.xpath("td"):
            row = None
            if len(row_text) == 3:
                # Per-detector additional information
                # TODO: grab missing information
                if last_header == [
                    "Parameter index variable",
                    "EPICS record name",
                    "Description",
                ]:
                    if row_text[1].startswith("$(P)$(R)"):
                        fake_row = [
                            row_text[0],
                            "",
                            "",
                            row_text[2],
                            "",
                            row_text[1],
                            "",
                        ]
                        row = DocRow(fake_row)

            elif len(row_text) == 7:
                row = DocRow(row_text)

            if row is not None:
                if row.is_valid:
                    if list(row) not in past_rows and row.record[0] not in past_rows:
                        ret.append(row)
                        past_rows.append(list(row))
                        past_rows.append(row.record[0])
                else:
                    print("invalid row", row_text, file=sys.stderr)
        else:
            print("(skipping)", row_text)

    return ret


print("#!/usr/bin/env python")
print("# -*- coding: utf-8 -*-")
print("# Autogenerated area detector documentation")
print("# (see ophyd.git/docs/area_detector)")
print()
print("docs = {")
for fn in os.listdir(DOC_PATH):
    full_fn = os.path.join(DOC_PATH, fn)
    if full_fn.endswith(".html") or fn in ("NDFileMagick",):
        rows = parse_doc(full_fn)
        if rows:
            print("-------------", fn, file=sys.stderr)
            print("    '%s': dict(" % fn)
            for row in rows:
                for line in row.python_source():
                    if line.lstrip().startswith("$(PROPERTY"):
                        continue
                    elif line.lstrip().startswith("$(FEATURE"):
                        continue
                    print(" " * 8 + line.encode("utf-8"))
            print(" " * 8 + "),  # end of %s" % fn)
            print()
            print()

print("}")
