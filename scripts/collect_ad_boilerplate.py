#!/usr/bin/env python3

import argparse
import logging
import os

import inflection


def write_detector_class(boilerplate_file, dev_name, det_name, cam_name):
    """
    Writes boilerplate 'Detector' class for ophyd/areadetector/detectors.

    This script automates the creation of ophyd classes for areaDetector
    drivers by scraping their *.template files. It is called by developers as
    needed.

    Parameters
    ----------
    boilerplate_file : io.TextIOWrapper
        Open temporary file for writing boilerplate
    dev_name : str
        Name of device type/make. Ex. PICam, Eiger, etc.
    det_name : str
        Name of detector class, ex. PICamDetector, EigerDetector, etc.
    cam_name : str
        Name of cam class, ex. PICamDetectorCam, EigerDetectorCam, etc.
    """

    boilerplate_file.write(
        f"""
class {det_name}(DetectorBase):
    _html_docs = ['{dev_name}Doc.html']
    cam = C(cam.{cam_name}, 'cam1:')
"""
    )


def parse_pv_structure(driver_dir):
    """
    Reads all .template files in the specified driver directory and maps them
    to the appropriate EPICS signal class in ophyd

    Also determines if the Cam class should extend the FileBase class as well.

    Parameters
    ----------
    driver_dir : PathLike
        Path to the areaDetector driver

    Returns
    -------
    pv_to_signal_mapping : dict
        Dict mapping PVs to the EPICS signal they fall under
    include_file_base : bool
        True if the NDFile.template file is included, otherwise False
    """

    # Find the template directory following the standard areaDetector project format
    template_dir = driver_dir
    for dir in os.listdir(driver_dir):
        if os.path.isdir(os.path.join(driver_dir, dir)) and dir.endswith("App"):
            template_dir = os.path.join(template_dir, dir, "Db")
            break
    logging.debug(f"Found template dir: {template_dir}")

    # Create a list of file paths to all template files.
    template_files = []
    for file in os.listdir(template_dir):
        file_path = os.path.join(template_dir, file)
        if os.path.isfile(file_path) and file.endswith(".template"):
            template_files.append(file_path)
            logging.debug(f"Found template file {file}")

    # Dict mapping pv name to appropriate EPICS signal, based on typical
    # PV and PV_RBV format for areaDetector
    pv_to_signal_mapping = {}
    include_file_base = False

    for file in template_files:
        logging.debug(f"Collecting pv info from {os.path.basename(file)}")
        with open(file, "r") as fp:

            lines = fp.readlines()
            for line in lines:

                # If NDFile.template is included, we need to extend FileBase as well.
                if line.startswith('include "NDFile.template"'):
                    logging.debug(f"Driver AD{dev_name} uses the NDFile.template file.")
                    include_file_base = True

                # identify any lines that start with 'record'
                if line.startswith("record"):
                    # Get the name of the PV.
                    # Ex:
                    # record(stringin, "$(P)$(R)Description_RBV") Splits into
                    # ['record(stringin, "$(P', '$(R', 'Description_RBV"', '']
                    # The PV name is the 3rd element, so array index 2, and we remove the last character, '"'
                    pv_name = line.split(")")[2][:-1]

                    # Check if it is a readback PV
                    if pv_name.endswith("_RBV"):

                        pv_name_without_rbv = pv_name[: -len("_RBV")]
                        # If it has a partner PV, switch the signal to SignalWithRBV
                        if pv_name_without_rbv in pv_to_signal_mapping.keys():
                            logging.debug(
                                f"Identified {pv_name_without_rbv} as a record w/ RBV"
                            )
                            pv_to_signal_mapping[pv_name_without_rbv] = "SignalWithRBV"
                        # Otherwise, it is a read only PV, so use EpicsSignalRO
                        else:
                            logging.debug(f"Identified read-only record {pv_name}")
                            pv_to_signal_mapping[pv_name] = "EpicsSignalRO"
                    else:
                        # Otherwise, use the default EpicsSignal
                        logging.debug(f"Found record {pv_name}")
                        pv_to_signal_mapping[pv_name] = "EpicsSignal"

    return pv_to_signal_mapping, include_file_base


def write_cam_class(
    boilerplate_file,
    pv_to_signal_mapping,
    include_file_base,
    dev_name,
    det_name,
    cam_name,
):
    """
    Function that writes the boilerplate cam class. This includes the default configuration
    attributes, along with all the attributes extracted from the template file.

    This function uses the inflection library's `underscore` function to convert a PV name
    into an attribute name

    Examples:

    EnableCallbacks -> enable_callbacks
    EVTLoadGainFile -> evt_load_gain_file

    Parameters
    ----------
    boilerplate_file : io.TextIOWrapper
        Open boilerplate file
    pv_to_signal_mapping : dict
        Dictionary mapping PVs to the EPICS signal they fall under
    include_file_base : bool
        If true, we extend the FileBase class, otherwise we don't
    dev_name : str
        Name of device type/make. Ex. PICam, Eiger, etc.
    det_name : str
        Name of detector class, ex. PICamDetector, EigerDetector, etc.
    cam_name : str
        Name of cam class, ex. PICamDetectorCam, EigerDetectorCam, etc.
    """

    # Extend from FileBase class as well if necessary
    file_base = ""
    if include_file_base:
        file_base = ", FileBase"

    # Write class boilerplate
    boilerplate_file.write(
        f"""
class {cam_name}(CamBase{file_base}):
    _html_docs = ['{dev_name}Doc.html']
    _default_configuration_attrs = (
        CamBase._default_configuration_attrs
    )
"""
    )

    # Write attribute for each discovered PV, with appropriate EPICS signal class
    for pv in pv_to_signal_mapping.keys():
        pv_name = pv
        if pv_name.endswith("_RBV"):
            pv_name = pv[: -len("_RBV")]

        # Generate attribute name from PV name. Uses inflection library
        attribute_name = inflection.underscore(pv_name)
        # attribute_name = re.sub('(?<!^)(?=[A-Z])', '_', pv_name).lower()
        boilerplate_file.write(
            f"    {attribute_name} = ADCpt({pv_to_signal_mapping[pv]}, '{pv}')\n"
        )


def parse_args():
    """
    usage: collect_ad_boilerplate.py [-h] [-t TARGET] [-d]

    Utility for creating boilerplate areaDetector ophyd classes

    optional arguments:
      -h, --help            show this help message and exit
      -t TARGET, --target TARGET
                            Location of locally installed areaDetector driver
                            folder structure.
      -d, --debug           Enable debug logging for the script.
    """

    parser = argparse.ArgumentParser(
        description="Utility for creating boilerplate areaDetector ophyd classes"
    )
    parser.add_argument(
        "-t",
        "--target",
        help="Location of locally installed areaDetector driver folder structure.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging for the script.",
    )

    args = vars(parser.parse_args())

    # Set logging level
    log_level = logging.ERROR
    if args["debug"]:
        log_level = logging.DEBUG

    if args["target"] is None:
        return os.path.abspath("."), log_level
    else:
        return args["target"], log_level


if __name__ == "__main__":

    # Check if input is valid
    driver_dir, log_level = parse_args()
    if not os.path.exists(driver_dir) or not os.path.isdir(driver_dir):
        logging.error(f"Input {driver_dir} does not exist or is not a directory!")
        exit(1)

    logging.basicConfig(level=log_level)

    # Check if specified target is an areaDetector driver
    driver_name = os.path.basename(driver_dir)
    if not driver_name.startswith("AD"):
        logging.error(
            f"Specified driver directory {driver_name} could not be identified as an areaDetector driver!"
        )
        exit(1)

    # Collect device, detector, and cam names
    dev_name = driver_name[2:]
    det_name = f"{dev_name}Detector"
    cam_name = f"{det_name}Cam"
    logging.debug(
        f"Creating boilerplate for {dev_name}, with classes {det_name} and {cam_name}"
    )

    # Create boilerplate file with .py extension for syntax highlighting
    boilerplate_file_name = f"{det_name}_boilerplate.py"

    # Create boilerplate temp file
    with open(boilerplate_file_name, "w") as boilerplate_file:

        # Create the detector class for ophyd/areadetector/detectors
        write_detector_class(boilerplate_file, dev_name, det_name, cam_name)

        # Collect PV information from detector driver
        driver_template, include_file_base = parse_pv_structure(driver_dir)

        # Create boilerplate cam class for ophyd/areadetector/cam
        write_cam_class(
            boilerplate_file,
            driver_template,
            include_file_base,
            dev_name,
            det_name,
            cam_name,
        )

    print(f"Done. Temporary boilerplate file saved to {boilerplate_file_name}")
