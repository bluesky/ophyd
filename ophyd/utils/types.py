from typing import List, Literal, Tuple, TypedDict


class Hints(TypedDict, total=False):
    """A dictionary of optional hints for visualization"""

    #: A list of the interesting fields to plot
    fields: List[str]
    #: Partition fields (and their stream name) into dimensions for plotting
    #:
    #: ``'dimensions': [(fields, stream_name), (fields, stream_name), ...]``
    dimensions: List[Tuple[List[str], str]]
    #: Include this if scan data is sampled on a regular rectangular grid
    gridding: Literal["rectilinear", "rectilinear_nonsequential"]
