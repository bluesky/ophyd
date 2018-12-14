from .. import (Component as Cpt, FormattedComponent as FCpt, EpicsSignal,
                EpicsSignalRO, Device)
from .plugins import (PluginBase, Overlay, ColorConvPlugin, FilePlugin,
                      HDF5Plugin, ImagePlugin, JPEGPlugin, MagickPlugin,
                      NetCDFPlugin, NexusPlugin, OverlayPlugin, ProcessPlugin,
                      ROIPlugin, StatsPlugin, TIFFPlugin, TransformPlugin)
from .base import (DDC_EpicsSignal, DDC_EpicsSignalRO, DDC_SignalWithRBV)
from . import (EpicsSignalWithRBV as SignalWithRBV)


# --- NDPluginBase ---

class PluginBase_V20(PluginBase, version=(2, 0), version_of=PluginBase):
    epics_ts_sec = Cpt(EpicsSignalRO, "EpicsTSSec_RBV")
    epics_ts_nsec = Cpt(EpicsSignalRO, "EpicsTSNsec_RBV")


class PluginBase_V22(PluginBase_V20, version=(2, 2), version_of=PluginBase):
    ad_core_version = Cpt(EpicsSignalRO, "ADCoreVersion_RBV", string=True)
    array_callbacks = Cpt(SignalWithRBV, "ArrayCallbacks", string=True, doc="0='Disable' 1='Enable'")
    array_size_int = Cpt(EpicsSignalRO, "ArraySize_RBV")
    color_mode = Cpt(
        SignalWithRBV, "ColorMode", string=True,
        doc="0=Mono 1=Bayer 2=RGB1 3=RGB2 4=RGB3 5=YUV444 6=YUV422 7=YUV421",
    )
    data_type = Cpt(
        SignalWithRBV, "DataType", string=True,
        doc="0=Int8 1=UInt8 2=Int16 3=UInt16 4=Int32 5=UInt32 6=Float32 7=Float64",
    )
    array_size_xyz = DDC_EpicsSignalRO(
        ("array_size_x", "ArraySizeX_RBV"),
        ("array_size_y", "ArraySizeY_RBV"),
        ("array_size_z", "ArraySizeZ_RBV"),
    )


class PluginBase_V26(PluginBase_V22, version=(2, 6), version_of=PluginBase):
    queue_size = Cpt(SignalWithRBV, 'QueueSize')
    dimensions = Cpt(SignalWithRBV, "Dimensions")
    driver_version = Cpt(EpicsSignalRO, "DriverVersion_RBV", string=True)
    execution_time = Cpt(EpicsSignalRO, "ExecutionTime_RBV", string=True)
    ndimensions = Cpt(SignalWithRBV, "NDimensions", string=True)
    array_size_all = DDC_SignalWithRBV(
        ("array_size0", "ArraySize0"),
        ("array_size1", "ArraySize1"),
        ("array_size2", "ArraySize2"),
        ("array_size3", "ArraySize3"),
        ("array_size4", "ArraySize4"),
        ("array_size5", "ArraySize5"),
        ("array_size6", "ArraySize6"),
        ("array_size7", "ArraySize7"),
        ("array_size8", "ArraySize8"),
        ("array_size9", "ArraySize9"),
        doc="array_size",
    )
    dim_sa = DDC_SignalWithRBV(
        ("dim0_sa", "Dim0SA"),
        ("dim1_sa", "Dim1SA"),
        ("dim2_sa", "Dim2SA"),
        ("dim3_sa", "Dim3SA"),
        ("dim4_sa", "Dim4SA"),
        ("dim5_sa", "Dim5SA"),
        ("dim6_sa", "Dim6SA"),
        ("dim7_sa", "Dim7SA"),
        ("dim8_sa", "Dim8SA"),
        ("dim9_sa", "Dim9SA"),
        doc="dim_sa",
    )


class PluginBase_V31(PluginBase_V26, version=(3, 1), version_of=PluginBase):
    disordered_arrays = Cpt(SignalWithRBV, "DisorderedArrays")
    dropped_output_arrays = Cpt(SignalWithRBV, "DroppedOutputArrays")
    max_threads = Cpt(EpicsSignalRO, "MaxThreads_RBV")
    nd_attributes_macros = Cpt(EpicsSignal, "NDAttributesMacros")
    nd_attributes_status = Cpt(
        EpicsSignal, "NDAttributesStatus", string=True,
        doc="0='Attributes file OK' 1='File not found' 2='XML syntax error' 3='Macro substitution error'",
    )
    num_threads = Cpt(SignalWithRBV, "NumThreads")
    process_plugin = Cpt(EpicsSignal, "ProcessPlugin", string=True)
    sort_free = Cpt(EpicsSignal, "SortFree")
    sort_free_low = Cpt(EpicsSignal, "SortFreeLow")
    sort_mode = Cpt(SignalWithRBV, "SortMode", string=True,
                    doc="0=Unsorted 1=Sorted")
    sort_size = Cpt(SignalWithRBV, "SortSize")
    sort_time = Cpt(SignalWithRBV, "SortTime")


class PluginBase_V33(PluginBase_V31, version=(3, 3), version_of=PluginBase):
    empty_free_list = Cpt(EpicsSignal, "EmptyFreeList", string=True)
    num_queued_arrays = Cpt(EpicsSignal, "NumQueuedArrays", string=True)
    pool_max_buffers = None  # REMOVED


class PluginBase_V34(PluginBase_V33, version=(3, 4), version_of=PluginBase):
    max_array_rate = Cpt(SignalWithRBV, "MaxArrayRate")
    max_array_rate_cout = Cpt(EpicsSignal, "MaxArrayRate_COUT")
    max_byte_rate = Cpt(SignalWithRBV, "MaxByteRate")
    min_callback_time = Cpt(SignalWithRBV, "MinCallbackTime")


# --- NDFile ---

class FilePlugin_V20(PluginBase_V20, FilePlugin, version=(2, 0), version_of=FilePlugin):
    ...


class FilePlugin_V21(FilePlugin_V20, version=(2, 1), version_of=FilePlugin):
    lazy_open = Cpt(SignalWithRBV, "LazyOpen", string=True, doc="0='No' 1='Yes'")


class FilePlugin_V22(PluginBase_V22, FilePlugin_V21, version=(2, 2), version_of=FilePlugin):
    create_directory = Cpt(SignalWithRBV, "CreateDirectory")
    file_number = Cpt(SignalWithRBV, "FileNumber")
    file_number_sync = None  # REMOVED
    file_number_write = None  # REMOVED
    temp_suffix = Cpt(SignalWithRBV, "TempSuffix", string=True)


class FilePlugin_V26(PluginBase_V26, FilePlugin_V22, version=(2, 6), version_of=FilePlugin):
    ...


class FilePlugin_V31(PluginBase_V31, FilePlugin_V26, version=(3, 1), version_of=FilePlugin):
    ...


class FilePlugin_V33(PluginBase_V33, FilePlugin_V31, version=(3, 3), version_of=FilePlugin):
    ...


class FilePlugin_V34(PluginBase_V34, FilePlugin_V33, version=(3, 4), version_of=FilePlugin):
    ...


# --- ColorConvPlugin ---

class ColorConvPlugin_V20(PluginBase_V20, ColorConvPlugin, version=(2, 0), version_of=ColorConvPlugin):
    ...


class ColorConvPlugin_V22(PluginBase_V22, ColorConvPlugin_V20, version=(2, 2), version_of=ColorConvPlugin):
    ...


class ColorConvPlugin_V26(PluginBase_V26, ColorConvPlugin_V22, version=(2, 6), version_of=ColorConvPlugin):
    ...


class ColorConvPlugin_V31(PluginBase_V31, ColorConvPlugin_V26, version=(3, 1), version_of=ColorConvPlugin):
    ...


class ColorConvPlugin_V33(PluginBase_V33, ColorConvPlugin_V31, version=(3, 3), version_of=ColorConvPlugin):
    ...


class ColorConvPlugin_V34(PluginBase_V34, ColorConvPlugin_V33, version=(3, 4), version_of=ColorConvPlugin):
    ...


# --- NDFileHDF5 ---

class HDF5Plugin_V20(FilePlugin_V20, HDF5Plugin, version=(2, 0), version_of=HDF5Plugin):
    # data_bits_offset = Cpt(SignalWithRBV, 'DataBitsOffset')
    # io_speed = Cpt(EpicsSignal, 'IOSpeed')
    # num_data_bits = Cpt(SignalWithRBV, 'NumDataBits')
    # num_frames_flush = Cpt(SignalWithRBV, 'NumFramesFlush')
    # run_time = Cpt(EpicsSignal, 'RunTime')
    # szip_num_pixels = Cpt(SignalWithRBV, 'SZipNumPixels')
    # store_attr = Cpt(SignalWithRBV, 'StoreAttr', string=True, doc="0='No' 1='Yes'")
    # store_perform = Cpt(SignalWithRBV, 'StorePerform', string=True, doc="0='No' 1='Yes'")
    # zlevel = Cpt(SignalWithRBV, 'ZLevel')
    ...


class HDF5Plugin_V21(FilePlugin_V21, HDF5Plugin_V20, version=(2, 1), version_of=HDF5Plugin):
    xml_error_msg = Cpt(EpicsSignalRO, "XMLErrorMsg_RBV")
    xml_file_name = Cpt(SignalWithRBV, "XMLFileName")
    xml_valid = Cpt(EpicsSignalRO, "XMLValid_RBV", string=True, doc="0='No' 1='Yes'")


class HDF5Plugin_V22(FilePlugin_V22, HDF5Plugin_V21, version=(2, 2), version_of=HDF5Plugin):
    nd_attribute_chunk = Cpt(SignalWithRBV, "NDAttributeChunk")


class HDF5Plugin_V25(HDF5Plugin_V22, version=(2, 5), version_of=HDF5Plugin):
    dim_att_datasets = Cpt(SignalWithRBV, "DimAttDatasets", string=True,
                           doc="0='No' 1='Yes'")
    fill_value = Cpt(SignalWithRBV, "FillValue")
    position_mode = Cpt(SignalWithRBV, "PositionMode", string=True,
                        doc="0='Off' 1='On'")
    swmr_active = Cpt(EpicsSignalRO, "SWMRActive_RBV", string=True,
                      doc="0='Off' 1='Active'")
    swmr_cb_counter = Cpt(EpicsSignalRO, "SWMRCbCounter_RBV")
    swmr_mode = Cpt(SignalWithRBV, "SWMRMode", string=True,
                    doc="0='Off' 1='On'")
    swmr_supported = Cpt(EpicsSignalRO, "SWMRSupported_RBV", string=True,
                         doc="0='Not Supported' 1='Supported'")
    extra_dim_chunk = DDC_SignalWithRBV(
        ("chunk_3", "ExtraDimChunk3"),
        ("chunk_4", "ExtraDimChunk4"),
        ("chunk_5", "ExtraDimChunk5"),
        ("chunk_6", "ExtraDimChunk6"),
        ("chunk_7", "ExtraDimChunk7"),
        ("chunk_8", "ExtraDimChunk8"),
        ("chunk_9", "ExtraDimChunk9"),
        ("chunk_x", "ExtraDimChunkX"),
        ("chunk_y", "ExtraDimChunkY"),
        doc="extra_dim_chunk",
    )
    extra_dim_name = DDC_EpicsSignalRO(
        ("name_3", "ExtraDimName3_RBV"),
        ("name_4", "ExtraDimName4_RBV"),
        ("name_5", "ExtraDimName5_RBV"),
        ("name_6", "ExtraDimName6_RBV"),
        ("name_7", "ExtraDimName7_RBV"),
        ("name_8", "ExtraDimName8_RBV"),
        ("name_9", "ExtraDimName9_RBV"),

        ("name_x", "ExtraDimNameX_RBV"),
        ("name_y", "ExtraDimNameY_RBV"),
        ("name_n", "ExtraDimNameN_RBV"),
        doc="extra_dim_name",
    )
    extra_dim_size = DDC_SignalWithRBV(
        ("size_3", "ExtraDimSize3"),
        ("size_4", "ExtraDimSize4"),
        ("size_5", "ExtraDimSize5"),
        ("size_6", "ExtraDimSize6"),
        ("size_7", "ExtraDimSize7"),
        ("size_8", "ExtraDimSize8"),
        ("size_9", "ExtraDimSize9"),

        ("size_x", "ExtraDimSizeX"),
        ("size_y", "ExtraDimSizeY"),
        ("size_n", "ExtraDimSizeN"),
        doc="extra_dim_size",
    )
    pos_index_dim = DDC_SignalWithRBV(
        ("dim_3", "PosIndexDim3"),
        ("dim_4", "PosIndexDim4"),
        ("dim_5", "PosIndexDim5"),
        ("dim_6", "PosIndexDim6"),
        ("dim_7", "PosIndexDim7"),
        ("dim_8", "PosIndexDim8"),
        ("dim_9", "PosIndexDim9"),
        ("dim_x", "PosIndexDimX"),
        ("dim_y", "PosIndexDimY"),
        ("dim_n", "PosIndexDimN"),
        doc="pos_index_dim",
    )
    pos_name_dim = DDC_SignalWithRBV(
        ("dim_3", "PosNameDim3"),
        ("dim_4", "PosNameDim4"),
        ("dim_5", "PosNameDim5"),
        ("dim_6", "PosNameDim6"),
        ("dim_7", "PosNameDim7"),
        ("dim_8", "PosNameDim8"),
        ("dim_9", "PosNameDim9"),
        ("dim_x", "PosNameDimX"),
        ("dim_y", "PosNameDimY"),
        ("dim_n", "PosNameDimN"),
        doc="pos_name_dim",
    )


class HDF5Plugin_V26(FilePlugin_V26, HDF5Plugin_V25, version=(2, 6), version_of=HDF5Plugin):
    ...


class HDF5Plugin_V31(FilePlugin_V31, HDF5Plugin_V26, version=(3, 1), version_of=HDF5Plugin):
    ...


class HDF5Plugin_V32(HDF5Plugin_V31, version=(3, 2), version_of=HDF5Plugin):
    blosc_compressor = Cpt(SignalWithRBV, "BloscCompressor", string=True,
                           doc="0=blosclz 1=lz4 2=lz4hc 3=snappy 4=zlib 5=zstd")
    blosc_level = Cpt(SignalWithRBV, "BloscLevel")
    blosc_shuffle = Cpt(SignalWithRBV, "BloscShuffle", string=True,
                        doc="0=None 1=ByteShuffle 2=BitShuffle")
    compression = Cpt(SignalWithRBV, 'Compression', string=True,
                      doc="0=None 1=N-bit 2=szip 3=zlib 4=blosc")


class HDF5Plugin_V33(FilePlugin_V33, HDF5Plugin_V32, version=(3, 3), version_of=HDF5Plugin):
    ...


class HDF5Plugin_V34(FilePlugin_V34, HDF5Plugin_V33, version=(3, 4), version_of=HDF5Plugin):
    ...


# --- NDStdArrays ---


class ImagePlugin_V20(PluginBase_V20, ImagePlugin, version=(2, 0), version_of=ImagePlugin):
    ...


class ImagePlugin_V22(PluginBase_V22, ImagePlugin_V20, version=(2, 2), version_of=ImagePlugin):
    ...


class ImagePlugin_V26(PluginBase_V26, ImagePlugin_V22, version=(2, 6), version_of=ImagePlugin):
    ...


class ImagePlugin_V31(PluginBase_V31, ImagePlugin_V26, version=(3, 1), version_of=ImagePlugin):
    ...


class ImagePlugin_V33(PluginBase_V33, ImagePlugin_V31, version=(3, 3), version_of=ImagePlugin):
    ...


class ImagePlugin_V34(PluginBase_V34, ImagePlugin_V33, version=(3, 4), version_of=ImagePlugin):
    ...


# --- NDFileJPEG ---


class JPEGPlugin_V20(FilePlugin_V20, JPEGPlugin, version=(2, 0), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V21(FilePlugin_V21, JPEGPlugin_V20, version=(2, 1), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V22(FilePlugin_V22, JPEGPlugin_V21, version=(2, 2), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V26(FilePlugin_V26, JPEGPlugin_V22, version=(2, 6), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V31(FilePlugin_V31, JPEGPlugin_V26, version=(3, 1), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V33(FilePlugin_V33, JPEGPlugin_V31, version=(3, 3), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V34(FilePlugin_V34, JPEGPlugin_V33, version=(3, 4), version_of=JPEGPlugin):
    ...


# --- NDFileMagick ---


class MagickPlugin_V20(FilePlugin_V20, MagickPlugin, version=(2, 0), version_of=MagickPlugin):
    ...


class MagickPlugin_V21(FilePlugin_V21, MagickPlugin_V20, version=(2, 1), version_of=MagickPlugin):
    ...


class MagickPlugin_V22(FilePlugin_V22, MagickPlugin_V21, version=(2, 2), version_of=MagickPlugin):
    ...


class MagickPlugin_V26(FilePlugin_V26, MagickPlugin_V22, version=(2, 6), version_of=MagickPlugin):
    ...


class MagickPlugin_V31(FilePlugin_V31, MagickPlugin_V26, version=(3, 1), version_of=MagickPlugin):
    bit_depth = Cpt(SignalWithRBV, 'BitDepth', string=True, doc="1=1 8=8 16=16 32=32")


class MagickPlugin_V33(FilePlugin_V33, MagickPlugin_V31, version=(3, 3), version_of=MagickPlugin):
    ...


class MagickPlugin_V34(FilePlugin_V34, MagickPlugin_V33, version=(3, 4), version_of=MagickPlugin):
    ...


# --- NDFileNetCDF ---


class NetCDFPlugin_V20(FilePlugin_V20, NetCDFPlugin, version=(2, 0), version_of=NetCDFPlugin):
    ...


class NetCDFPlugin_V21(FilePlugin_V21, NetCDFPlugin_V20, version=(2, 1), version_of=NetCDFPlugin):
    ...


class NetCDFPlugin_V22(FilePlugin_V22, NetCDFPlugin_V21, version=(2, 2), version_of=NetCDFPlugin):
    ...


class NetCDFPlugin_V26(FilePlugin_V26, NetCDFPlugin_V22, version=(2, 6), version_of=NetCDFPlugin):
    ...


class NetCDFPlugin_V31(FilePlugin_V31, NetCDFPlugin_V26, version=(3, 1), version_of=NetCDFPlugin):
    ...


class NetCDFPlugin_V33(FilePlugin_V33, NetCDFPlugin_V31, version=(3, 3), version_of=NetCDFPlugin):
    ...


class NetCDFPlugin_V34(FilePlugin_V34, NetCDFPlugin_V33, version=(3, 4), version_of=NetCDFPlugin):
    ...


# --- NDFileNexus ---


class NexusPlugin_V20(FilePlugin_V20, NexusPlugin, version=(2, 0), version_of=NexusPlugin):
    ...


class NexusPlugin_V21(FilePlugin_V21, NexusPlugin_V20, version=(2, 1), version_of=NexusPlugin):
    ...


class NexusPlugin_V22(FilePlugin_V22, NexusPlugin_V21, version=(2, 2), version_of=NexusPlugin):
    ...


class NexusPlugin_V26(FilePlugin_V26, NexusPlugin_V22, version=(2, 6), version_of=NexusPlugin):
    ...


class NexusPlugin_V31(FilePlugin_V31, NexusPlugin_V26, version=(3, 1), version_of=NexusPlugin):
    ...


class NexusPlugin_V33(FilePlugin_V33, NexusPlugin_V31, version=(3, 3), version_of=NexusPlugin):
    ...


class NexusPlugin_V34(FilePlugin_V34, NexusPlugin_V33, version=(3, 4), version_of=NexusPlugin):
    ...


# --- NDOverlayN ---


class Overlay_V21(Overlay, version=(2, 1), version_of=Overlay):
    display_text = Cpt(SignalWithRBV, "DisplayText")
    font = Cpt(SignalWithRBV, "Font", string=True,
               doc="0=6x13 1='6x13 Bold' 2=9x15 3='9x15 Bold'")
    shape = Cpt(SignalWithRBV, 'Shape', string=True,
                doc="0=Cross 1=Rectangle 2=Text")
    time_stamp_format = Cpt(SignalWithRBV, "TimeStampFormat", string=True)
    width = DDC_SignalWithRBV(
        ("x", "WidthX"),
        ("y", "WidthY"),
        doc="width"
    )
    width_link = DDC_EpicsSignal(
        ("x", "WidthXLink"),
        ("y", "WidthYLink"),
        doc="width_link"
    )


class Overlay_V26(Overlay_V21, version=(2, 6), version_of=Overlay):
    shape = Cpt(SignalWithRBV, 'Shape', string=True, doc="0=Cross 1=Rectangle 2=Text 3=Ellipse ")
    center = DDC_SignalWithRBV(
        ("x", "CenterX"),
        ("y", "CenterY"),
        doc="center"
    )
    center_link = DDC_EpicsSignal(
        ("x", "CenterXLink"),
        ("y", "CenterYLink"),
        doc="center_link"
    )
    position_ = DDC_SignalWithRBV(
        ("x", "PositionX"),
        ("y", "PositionY"),
        doc="position"
    )
    set_hopr = DDC_EpicsSignal(
        ("x", "SetXHOPR"),
        ("y", "SetYHOPR"),
        doc="set_hopr"
    )


class Overlay_V31(Overlay_V26, version=(3, 1), version_of=Overlay):
    ...


# --- NDOverlay ---


class OverlayPlugin_V20(PluginBase_V20, OverlayPlugin, version=(2, 0), version_of=OverlayPlugin):
    ...


class OverlayPlugin_V22(PluginBase_V22, OverlayPlugin_V20, version=(2, 2), version_of=OverlayPlugin):
    ...


class OverlayPlugin_V26(PluginBase_V26, OverlayPlugin_V22, version=(2, 6), version_of=OverlayPlugin):
    ...


class OverlayPlugin_V31(PluginBase_V31, OverlayPlugin_V26, version=(3, 1), version_of=OverlayPlugin):
    ...


class OverlayPlugin_V33(PluginBase_V33, OverlayPlugin_V31, version=(3, 3), version_of=OverlayPlugin):
    ...


class OverlayPlugin_V34(PluginBase_V34, OverlayPlugin_V33, version=(3, 4), version_of=OverlayPlugin):
    ...


# --- NDProcess ---


class ProcessPlugin_V20(PluginBase_V20, ProcessPlugin, version=(2, 0), version_of=ProcessPlugin):
    ...


class ProcessPlugin_V22(PluginBase_V22, ProcessPlugin_V20, version=(2, 2), version_of=ProcessPlugin):
    ...


class ProcessPlugin_V26(PluginBase_V26, ProcessPlugin_V22, version=(2, 6), version_of=ProcessPlugin):
    ...


class ProcessPlugin_V31(PluginBase_V31, ProcessPlugin_V26, version=(3, 1), version_of=ProcessPlugin):
    ...


class ProcessPlugin_V33(PluginBase_V33, ProcessPlugin_V31, version=(3, 3), version_of=ProcessPlugin):
    port_backup = Cpt(EpicsSignal, "PortBackup", string=True)
    read_background_tiffs_eq = Cpt(EpicsSignal, "ReadBackgroundTIFFSeq")
    read_flat_field_tiffs_eq = Cpt(EpicsSignal, "ReadFlatFieldTIFFSeq")


class ProcessPlugin_V34(PluginBase_V34, ProcessPlugin_V33, version=(3, 4), version_of=ProcessPlugin):
    ...


# --- NDROI ---


class ROIPlugin_V20(PluginBase_V20, ROIPlugin, version=(2, 0), version_of=ROIPlugin):
    array_size_xyz = DDC_EpicsSignalRO(
        ("x", "ArraySizeX_RBV"),
        ("y", "ArraySizeY_RBV"),
        ("z", "ArraySizeZ_RBV"),
    )
    array_size_012 = DDC_EpicsSignalRO(
        ("size0", "ArraySize0_RBV"),
        ("size1", "ArraySize1_RBV"),
        ("size2", "ArraySize2_RBV"),
    )


class ROIPlugin_V22(PluginBase_V22, ROIPlugin_V20, version=(2, 2), version_of=ROIPlugin):
    ...


class ROIPlugin_V26(PluginBase_V26, ROIPlugin_V22, version=(2, 6), version_of=ROIPlugin):
    collapse_dims = Cpt(SignalWithRBV, "CollapseDims", string=True, doc="0='Disable' 1='Enable'")


class ROIPlugin_V31(PluginBase_V31, ROIPlugin_V26, version=(3, 1), version_of=ROIPlugin):
    ...


class ROIPlugin_V33(PluginBase_V33, ROIPlugin_V31, version=(3, 3), version_of=ROIPlugin):
    ...


class ROIPlugin_V34(PluginBase_V34, ROIPlugin_V33, version=(3, 4), version_of=ROIPlugin):
    ...


# --- NDROIStat ---


class ROIStatPlugin(Device):
    "Serves as a base class for other versions"
    ...


class ROIStatPlugin_V22(PluginBase_V22, ROIStatPlugin, version=(2, 2), version_of=ROIStatPlugin):
    reset_all = Cpt(EpicsSignal, "ResetAll", string=True, doc="")


class ROIStatPlugin_V23(ROIStatPlugin_V22, version=(2, 3), version_of=ROIStatPlugin):
    ts_acquiring = Cpt(EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'")
    ts_control = Cpt(EpicsSignal, "TSControl", string=True, doc="0=Erase/Start 1=Start 2=Stop 3=Read")
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints")
    ts_read = Cpt(EpicsSignal, "TSRead")


class ROIStatPlugin_V26(PluginBase_V26, ROIStatPlugin_V23, version=(2, 6), version_of=ROIStatPlugin):
    ...


class ROIStatPlugin_V31(PluginBase_V31, ROIStatPlugin_V26, version=(3, 1), version_of=ROIStatPlugin):
    ...


class ROIStatPlugin_V33(PluginBase_V33, ROIStatPlugin_V31, version=(3, 3), version_of=ROIStatPlugin):
    ...


class ROIStatPlugin_V34(PluginBase_V34, ROIStatPlugin_V33, version=(3, 4), version_of=ROIStatPlugin):
    ...


# --- NDROIStatN ---


class ROIStatNPlugin(Device):
    "Serves as a base class for other versions"
    ...


class ROIStatNPlugin_V22(ROIStatNPlugin, version=(2, 2), version_of=ROIStatNPlugin):
    bgd_width = Cpt(SignalWithRBV, "BgdWidth")
    max_value = Cpt(EpicsSignalRO, "MaxValue_RBV")
    mean_value = Cpt(EpicsSignalRO, "MeanValue_RBV")
    min_value = Cpt(EpicsSignalRO, "MinValue_RBV")
    name_ = Cpt(EpicsSignal, "Name", string=True)
    net = Cpt(EpicsSignalRO, "Net_RBV")
    reset = Cpt(EpicsSignal, "Reset", string=True, doc="")
    total = Cpt(EpicsSignalRO, "Total_RBV")
    use = Cpt(SignalWithRBV, "Use", string=True, doc="0='No' 1='Yes'")
    max_size = DDC_EpicsSignalRO(
        ("x", "MaxSizeX_RBV"),
        ("y", "MaxSizeY_RBV"),
        doc="max_size"
    )
    min_ = DDC_SignalWithRBV(
        ("x", "MinX"),
        ("y", "MinY"),
        doc="min"
    )
    size = DDC_SignalWithRBV(
        ("x", "SizeX"),
        ("y", "SizeY"),
        doc="size"
    )


class ROIStatNPlugin_V23(ROIStatNPlugin_V22, version=(2, 3), version_of=ROIStatNPlugin):
    ts_max_value = Cpt(EpicsSignal, "TSMaxValue")
    ts_mean_value = Cpt(EpicsSignal, "TSMeanValue")
    ts_min_value = Cpt(EpicsSignal, "TSMinValue")
    ts_net = Cpt(EpicsSignal, "TSNet")
    ts_total = Cpt(EpicsSignal, "TSTotal")


class ROIStatNPlugin_V25(ROIStatNPlugin_V23, version=(2, 5), version_of=ROIStatNPlugin):
    ts_timestamp = Cpt(EpicsSignal, "TSTimestamp")


# --- NDStats ---


class StatsPlugin_V20(PluginBase_V20, StatsPlugin, version=(2, 0), version_of=StatsPlugin):
    ...


class StatsPlugin_V22(PluginBase_V22, StatsPlugin_V20, version=(2, 2), version_of=StatsPlugin):
    hist_entropy = Cpt(SignalWithRBV, "HistEntropy")
    max_value = Cpt(SignalWithRBV, "MaxValue")
    mean_value = Cpt(SignalWithRBV, "MeanValue")
    min_value = Cpt(SignalWithRBV, "MinValue")
    net = Cpt(SignalWithRBV, "Net")
    reset = Cpt(EpicsSignal, "Reset")
    resets = DDC_EpicsSignal(("reset1", "Reset1"), doc="reset")
    sigma_value = Cpt(EpicsSignal, "SigmaValue")
    sigma_readout = Cpt(EpicsSignalRO, "Sigma_RBV")
    sigma_xy = Cpt(SignalWithRBV, "SigmaXY")
    total = Cpt(SignalWithRBV, "Total")
    max_ = DDC_SignalWithRBV(
        ("x", "MaxX"),
        ("y", "MaxY"),
        doc="max"
    )
    min_ = DDC_SignalWithRBV(
        ("x", "MinX"),
        ("y", "MinY"),
        doc="min"
    )
    sigma = DDC_SignalWithRBV(
        ("x", "SigmaX"),
        ("y", "SigmaY"),
        doc="sigma"
    )

    # Changed type to SignalWithRBV in R2-2:
    centroid = DDC_SignalWithRBV(
        ('x', 'CentroidX'),
        ('y', 'CentroidY'),
        doc='The centroid XY'
    )
    color_mode = Cpt(SignalWithRBV, 'ColorMode')
    data_type = Cpt(SignalWithRBV, 'DataType', string=True)


class StatsPlugin_V25(StatsPlugin_V22, version=(2, 5), version_of=StatsPlugin):
    ts_timestamp = Cpt(EpicsSignal, "TSTimestamp")


class StatsPlugin_V26(PluginBase_V26, StatsPlugin_V25, version=(2, 6), version_of=StatsPlugin):
    centroid_total = Cpt(SignalWithRBV, "CentroidTotal")
    eccentricity = Cpt(SignalWithRBV, "Eccentricity")
    hist_above = Cpt(SignalWithRBV, "HistAbove")
    hist_below = Cpt(SignalWithRBV, "HistBelow")
    orientation = Cpt(SignalWithRBV, "Orientation")
    resets = DDC_EpicsSignal(
        ("reset1", "Reset1"),
        ("reset2", "Reset2"),
        doc="reset"
    )
    ts_centroid_total = Cpt(EpicsSignal, "TSCentroidTotal")
    ts_eccentricity = Cpt(EpicsSignal, "TSEccentricity")
    ts_orientation = Cpt(EpicsSignal, "TSOrientation")
    kurtosis = DDC_SignalWithRBV(
        ("x", "KurtosisX"),
        ("y", "KurtosisY"),
        doc="kurtosis"
    )
    skew = DDC_SignalWithRBV(
        ("x", "SkewX"),
        ("y", "SkewY"),
        doc="skew"
    )
    ts_kurtosis = DDC_EpicsSignal(
        ("x", "TSKurtosisX"),
        ("y", "TSKurtosisY"),
        doc="ts_kurtosis"
    )
    ts_skew = DDC_EpicsSignal(
        ("x", "TSSkewX"),
        ("y", "TSSkewY"),
        doc="ts_skew"
    )


class StatsPlugin_V31(PluginBase_V31, StatsPlugin_V26, version=(3, 1), version_of=StatsPlugin):
    ...


class StatsPlugin_V32(StatsPlugin_V31, version=(3, 2), version_of=StatsPlugin):
    histogram_x = Cpt(EpicsSignalRO, "HistogramX_RBV")


class StatsPlugin_V33(PluginBase_V33, StatsPlugin_V32, version=(3, 3), version_of=StatsPlugin):
    ts_acquiring = None  # REMOVED
    ts_control = None  # REMOVED
    ts_current_point = None  # REMOVED
    ts_num_points = None  # REMOVED
    ts_read = None  # REMOVED
    ts_sigma_x = DDC_EpicsSignal(
        ("ts_sigma_x", "TSSigmaX"),
        ("ts_sigma_y", "TSSigmaY"),
        doc="ts_sigma")


class StatsPlugin_V34(PluginBase_V34, StatsPlugin_V33, version=(3, 4), version_of=StatsPlugin):
    ...


# --- NDFileTIFF ---


class TIFFPlugin_V20(FilePlugin_V20, TIFFPlugin, version=(2, 0), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V21(FilePlugin_V21, TIFFPlugin_V20, version=(2, 1), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V22(FilePlugin_V22, TIFFPlugin_V21, version=(2, 2), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V26(FilePlugin_V26, TIFFPlugin_V22, version=(2, 6), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V31(FilePlugin_V31, TIFFPlugin_V26, version=(3, 1), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V33(FilePlugin_V33, TIFFPlugin_V31, version=(3, 3), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V34(FilePlugin_V34, TIFFPlugin_V33, version=(3, 4), version_of=TIFFPlugin):
    ...


# --- NDTransform ---


class TransformPlugin_V20(PluginBase_V20, TransformPlugin, version=(2, 0), version_of=TransformPlugin):
    array_size = DDC_SignalWithRBV(
        ("array_size0", "ArraySize0"),
        ("array_size1", "ArraySize1"),
        ("array_size2", "ArraySize2"),
        doc='Array size',
    )


class TransformPlugin_V21(TransformPlugin_V20, version=(2, 1), version_of=TransformPlugin):
    name_ = None  # REMOVED
    origin_location = None  # REMOVED
    t1_max_size = None  # REMOVED DDC
    t2_max_size = None  # REMOVED DDC
    t3_max_size = None  # REMOVED DDC
    t4_max_size = None  # REMOVED DDC
    types = None  # REMOVED DDC
    width = None  # Removed array_size portions
    height = None  # Removed array_size portions
    depth = None  # Removed array_size portions
    type_ = Cpt(EpicsSignal, 'Type', string=True,
                doc="0=None 1=Rot90 2=Rot180 3=Rot270 4=Mirror 5=Rot90Mirror 6=Rot180Mirror 7=Rot270Mirror")
    array_size = DDC_EpicsSignalRO(
        ("array_size0", "ArraySize0_RBV"),
        ("array_size1", "ArraySize1_RBV"),
        ("array_size2", "ArraySize2_RBV"),
        doc='Array size',
    )


class TransformPlugin_V22(PluginBase_V22, TransformPlugin_V21, version=(2, 2), version_of=TransformPlugin):
    ...


class TransformPlugin_V26(PluginBase_V26, TransformPlugin_V22, version=(2, 6), version_of=TransformPlugin):
    ...


class TransformPlugin_V31(PluginBase_V31, TransformPlugin_V26, version=(3, 1), version_of=TransformPlugin):
    ...


class TransformPlugin_V33(PluginBase_V33, TransformPlugin_V31, version=(3, 3), version_of=TransformPlugin):
    ...


class TransformPlugin_V34(PluginBase_V34, TransformPlugin_V33, version=(3, 4), version_of=TransformPlugin):
    ...


# --- NDPva ---


class PvaPlugin(Device):
    "Serves as a base class for other versions"
    ...


class PvaPlugin_V25(PluginBase_V22, PvaPlugin, version=(2, 5), version_of=PvaPlugin):
    pv_name = Cpt(EpicsSignalRO, "PvName_RBV")


class PvaPlugin_V26(PluginBase_V26, PvaPlugin_V25, version=(2, 6), version_of=PvaPlugin):
    ...


class PvaPlugin_V31(PluginBase_V31, PvaPlugin_V26, version=(3, 1), version_of=PvaPlugin):
    ...


class PvaPlugin_V33(PluginBase_V33, PvaPlugin_V31, version=(3, 3), version_of=PvaPlugin):
    ...


class PvaPlugin_V34(PluginBase_V34, PvaPlugin_V33, version=(3, 4), version_of=PvaPlugin):
    ...


# --- NDFFT ---


class FFTPlugin(Device):
    "Serves as a base class for other versions"
    ...


class FFTPlugin_V25(PluginBase_V22, FFTPlugin, version=(2, 5), version_of=FFTPlugin):
    fft_abs_value = Cpt(EpicsSignal, "FFTAbsValue")
    fft_direction = Cpt(SignalWithRBV, "FFTDirection", string=True, doc="0='Time to freq.' 1='Freq. to time'")
    fft_freq_axis = Cpt(EpicsSignal, "FFTFreqAxis")
    fft_imaginary = Cpt(EpicsSignal, "FFTImaginary")
    fft_num_average = Cpt(SignalWithRBV, "FFTNumAverage")
    fft_num_averaged = Cpt(EpicsSignal, "FFTNumAveraged")
    fft_real = Cpt(EpicsSignal, "FFTReal")
    fft_reset_average = Cpt(EpicsSignal, "FFTResetAverage", string=True, doc="0='Done' 1='Reset'")
    fft_suppress_dc = Cpt(SignalWithRBV, "FFTSuppressDC", string=True, doc="0='Disable' 1='Enable'")
    fft_time_axis = Cpt(EpicsSignal, "FFTTimeAxis")
    fft_time_per_point = Cpt(SignalWithRBV, "FFTTimePerPoint")
    fft_time_per_point_link = Cpt(EpicsSignal, "FFTTimePerPointLink")
    fft_time_series = Cpt(EpicsSignal, "FFTTimeSeries")
    name_ = Cpt(EpicsSignal, "Name", string=True)


class FFTPlugin_V26(PluginBase_V26, FFTPlugin_V25, version=(2, 6), version_of=FFTPlugin):
    ...


class FFTPlugin_V31(PluginBase_V31, FFTPlugin_V26, version=(3, 1), version_of=FFTPlugin):
    ...


class FFTPlugin_V33(PluginBase_V33, FFTPlugin_V31, version=(3, 3), version_of=FFTPlugin):
    ...


class FFTPlugin_V34(PluginBase_V34, FFTPlugin_V33, version=(3, 4), version_of=FFTPlugin):
    ...


# --- NDScatter ---


class ScatterPlugin(Device):
    "Serves as a base class for other versions"
    ...


class ScatterPlugin_V31(PluginBase_V31, ScatterPlugin, version=(3, 1), version_of=ScatterPlugin):
    scatter_method = Cpt(SignalWithRBV, "ScatterMethod", string=True, doc="0='Round robin'")


class ScatterPlugin_V32(ScatterPlugin_V31, version=(3, 2), version_of=ScatterPlugin):
    ...


class ScatterPlugin_V33(PluginBase_V33, ScatterPlugin_V32, version=(3, 3), version_of=ScatterPlugin):
    ...


class ScatterPlugin_V34(PluginBase_V34, ScatterPlugin_V33, version=(3, 4), version_of=ScatterPlugin):
    ...


# --- NDPosPlugin ---


class PosPlugin(Device):
    "Serves as a base class for other versions"
    ...


class PosPluginPlugin_V25(PluginBase_V22, PosPlugin, version=(2, 5), version_of=PosPlugin):
    delete = Cpt(EpicsSignal, "Delete", string=True, doc="")
    duplicate = Cpt(SignalWithRBV, "Duplicate")
    expected_id = Cpt(EpicsSignalRO, "ExpectedID_RBV")
    file_valid = Cpt(EpicsSignalRO, "FileValid_RBV", string=True, doc="0='No' 1='Yes'")
    filename = Cpt(SignalWithRBV, "Filename")
    id_difference = Cpt(SignalWithRBV, "IDDifference")
    id_name = Cpt(SignalWithRBV, "IDName", string=True)
    id_start = Cpt(SignalWithRBV, "IDStart")
    index = Cpt(EpicsSignalRO, "Index_RBV")
    missing = Cpt(SignalWithRBV, "Missing")
    mode = Cpt(SignalWithRBV, "Mode", string=True, doc="0='Discard' 1='Keep'")
    position_ = Cpt(EpicsSignalRO, "Position_RBV", string=True)
    qty = Cpt(EpicsSignalRO, "Qty_RBV")
    reset = Cpt(EpicsSignal, "Reset", string=True, doc="")
    running = Cpt(SignalWithRBV, "Running")


class PosPluginPlugin_V26(PluginBase_V26, PosPluginPlugin_V25, version=(2, 6), version_of=PosPlugin):
    ...


class PosPluginPlugin_V31(PluginBase_V31, PosPluginPlugin_V26, version=(3, 1), version_of=PosPlugin):
    ...


class PosPluginPlugin_V33(PluginBase_V33, PosPluginPlugin_V31, version=(3, 3), version_of=PosPlugin):
    ...


class PosPluginPlugin_V34(PluginBase_V34, PosPluginPlugin_V33, version=(3, 4), version_of=PosPlugin):
    ...


# --- NDCircularBuff ---


class CircularBuffPlugin(Device):
    "Serves as a base class for other versions"
    ...


class CircularBuffPlugin_V22(PluginBase_V22, CircularBuffPlugin, version=(2, 2), version_of=CircularBuffPlugin):
    actual_trigger_count = Cpt(EpicsSignalRO, "ActualTriggerCount_RBV")
    capture = Cpt(SignalWithRBV, "Capture")
    current_qty = Cpt(EpicsSignalRO, "CurrentQty_RBV")
    post_count = Cpt(SignalWithRBV, "PostCount")
    post_trigger_qty = Cpt(EpicsSignalRO, "PostTriggerQty_RBV")
    pre_count = Cpt(SignalWithRBV, "PreCount")
    preset_trigger_count = Cpt(SignalWithRBV, "PresetTriggerCount")
    status_message = Cpt(EpicsSignal, "StatusMessage", string=True)
    trigger_ = Cpt(SignalWithRBV, "Trigger")
    trigger_a = Cpt(SignalWithRBV, "TriggerA", string=True)
    trigger_a_val = Cpt(EpicsSignal, "TriggerAVal")
    trigger_b = Cpt(SignalWithRBV, "TriggerB", string=True)
    trigger_b_val = Cpt(EpicsSignal, "TriggerBVal")
    trigger_calc = Cpt(SignalWithRBV, "TriggerCalc")
    trigger_calc_val = Cpt(EpicsSignal, "TriggerCalcVal")

    array_size_xyz = DDC_EpicsSignalRO(
        ("array_size_x", "ArraySizeX_RBV"),
        ("array_size_y", "ArraySizeY_RBV"),
        ("array_size_z", "ArraySizeZ_RBV"),
    )


class CircularBuffPlugin_V26(
    PluginBase_V26, CircularBuffPlugin_V22, version=(2, 6), version_of=CircularBuffPlugin
):
    ...


class CircularBuffPlugin_V31(
    PluginBase_V31, CircularBuffPlugin_V26, version=(3, 1), version_of=CircularBuffPlugin
):
    ...


class CircularBuffPlugin_V33(
    PluginBase_V33, CircularBuffPlugin_V31, version=(3, 3), version_of=CircularBuffPlugin
):
    ...


class CircularBuffPlugin_V34(
    PluginBase_V34, CircularBuffPlugin_V33, version=(3, 4), version_of=CircularBuffPlugin
):
    flush_on_soft_trigger = Cpt(
        SignalWithRBV, "FlushOnSoftTrg", string=True, doc="0='OnNewImage' 1='Immediately'"
    )


# --- NDAttributeN ---


class AttributeNPlugin(Device):
    "Serves as a base class for other versions"
    ...


class AttributeNPlugin_V22(AttributeNPlugin, version=(2, 2), version_of=AttributeNPlugin):
    attribute_name = Cpt(SignalWithRBV, "AttrName")
    ts_array_value = Cpt(EpicsSignal, "TSArrayValue")
    value_sum = Cpt(EpicsSignalRO, "ValueSum_RBV")
    value = Cpt(EpicsSignalRO, "Value_RBV")


class AttributeNPlugin_V26(AttributeNPlugin_V22, version=(2, 6), version_of=AttributeNPlugin):
    ...

# --- NDAttrPlot ---


class AttrPlotPlugin(Device):
    "Serves as a base class for other versions"
    ...


class AttrPlotPlugin_V31(PluginBase_V31, AttrPlotPlugin, version=(3, 1), version_of=AttrPlotPlugin):
    npts = Cpt(EpicsSignal, "NPts")
    reset = Cpt(EpicsSignal, "Reset")


class AttrPlotPlugin_V33(PluginBase_V33, AttrPlotPlugin_V31, version=(3, 3), version_of=AttrPlotPlugin):
    ...


class AttrPlotPlugin_V34(PluginBase_V34, AttrPlotPlugin_V33, version=(3, 4), version_of=AttrPlotPlugin):
    ...


# --- NDTimeSeriesN ---


class TimeSeriesNPlugin(Device):
    "Serves as a base class for other versions"
    ...


class TimeSeriesNPlugin_V25(TimeSeriesNPlugin, version=(2, 5), version_of=TimeSeriesNPlugin):
    name_ = Cpt(EpicsSignal, "Name", string=True)
    time_series = Cpt(EpicsSignal, "TimeSeries")


# --- NDTimeSeries ---


class TimeSeriesPlugin(Device):
    "Serves as a base class for other versions"
    ...


class TimeSeriesPlugin_V25(PluginBase_V22, TimeSeriesPlugin, version=(2, 5), version_of=TimeSeriesPlugin):
    ts_acquire = Cpt(EpicsSignal, "TSAcquire")
    ts_acquire_mode = Cpt(
        SignalWithRBV, "TSAcquireMode", string=True, doc="0='Fixed length' 1='Circ. buffer'"
    )
    ts_acquiring = Cpt(EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'")
    ts_averaging_time = Cpt(SignalWithRBV, "TSAveragingTime")
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_elapsed_time = Cpt(EpicsSignal, "TSElapsedTime")
    ts_num_average = Cpt(EpicsSignal, "TSNumAverage")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints")
    ts_read = Cpt(EpicsSignal, "TSRead", string=True, doc="0='Done' 1='Read'")
    ts_time_axis = Cpt(EpicsSignal, "TSTimeAxis")
    ts_time_per_point = Cpt(SignalWithRBV, "TSTimePerPoint")
    ts_time_per_point_link = Cpt(EpicsSignal, "TSTimePerPointLink")
    ts_timestamp = Cpt(EpicsSignal, "TSTimestamp")


class TimeSeriesPlugin_V26(PluginBase_V26, TimeSeriesPlugin_V25, version=(2, 6), version_of=TimeSeriesPlugin):
    ...


class TimeSeriesPlugin_V31(PluginBase_V31, TimeSeriesPlugin_V26, version=(3, 1), version_of=TimeSeriesPlugin):
    ...


class TimeSeriesPlugin_V33(PluginBase_V33, TimeSeriesPlugin_V31, version=(3, 3), version_of=TimeSeriesPlugin):
    ...


class TimeSeriesPlugin_V34(PluginBase_V34, TimeSeriesPlugin_V33, version=(3, 4), version_of=TimeSeriesPlugin):
    ...


# --- NDCodec ---


class CodecPlugin(Device):
    "Serves as a base class for other versions"
    ...


class CodecPlugin_V34(PluginBase_V34, CodecPlugin, version=(3, 4), version_of=CodecPlugin):
    blosc_cl_evel = Cpt(SignalWithRBV, "BloscCLevel")
    blosc_compressor = Cpt(
        SignalWithRBV, "BloscCompressor", string=True, doc="0=BloscLZ 1=LZ4 2=LZ4HC 3=SNAPPY 4=ZLIB 5=ZSTD"
    )
    blosc_num_threads = Cpt(SignalWithRBV, "BloscNumThreads")
    blosc_shuffle = Cpt(SignalWithRBV, "BloscShuffle", string=True, doc="0=None 1=Bit 2=Byte")
    codec_error = Cpt(EpicsSignal, "CodecError")
    codec_status = Cpt(EpicsSignal, "CodecStatus", string=True, doc="0=Success 1=Warning 2=Error")
    comp_factor = Cpt(EpicsSignalRO, "CompFactor_RBV")
    compressor = Cpt(SignalWithRBV, "Compressor", string=True, doc="0=None 1=JPEG 2=Blosc")
    jpeg_quality = Cpt(SignalWithRBV, "JPEGQuality")
    mode = Cpt(SignalWithRBV, "Mode", string=True, doc="0=Compress 1=Decompress")



class GatherNPlugin(Device):
    "Serves as a base class for other versions"
    def __init__(self, *args, index, **kwargs):
        self.index = index
        super().__init__(*args, **kwargs)


class GatherNPlugin_V31(GatherNPlugin, version=(3, 1), version_of=GatherNPlugin):
    gather_array_address = FCpt(SignalWithRBV, "{self.prefix}NDArrayAddress_{self.index}")
    gather_array_port = FCpt(SignalWithRBV, "{self.prefix}NDArrayPort_{self.index}", string=True)


class AttributePlugin(Device):
    "Serves as a base class for other versions"
    ...


class AttributePlugin_V20(PluginBase_V20, AttributePlugin, version=(2, 0), version_of=AttributePlugin):
    array_data = Cpt(EpicsSignalRO, 'ArrayData_RBV')
    attribute_name = Cpt(SignalWithRBV, 'AttrName')
    reset = Cpt(EpicsSignal, 'Reset', string=True, doc="0='Done Reset' 1='Reset'")
    reset_array_counter = Cpt(EpicsSignal, 'ResetArrayCounter')
    update = Cpt(EpicsSignal, 'Update', string=True, doc="0='Done Update Array' 1='Update Array'")
    update_period = Cpt(SignalWithRBV, 'UpdatePeriod')
    value_sum = Cpt(EpicsSignalRO, 'ValueSum_RBV')
    value = Cpt(EpicsSignalRO, 'Value_RBV')


class AttributePlugin_V22(PluginBase_V22, AttributePlugin_V20, version=(2, 2), version_of=AttributePlugin):
    array_data = None  # REMOVED
    attribute_name = None  # REMOVED
    reset_array_counter = None  # REMOVED
    ts_acquiring = Cpt(EpicsSignal, 'TSAcquiring', string=True, doc="0='Done' 1='Acquiring'")
    ts_control = Cpt(EpicsSignal, 'TSControl', string=True, doc="0=Erase/Start 1=Start 2=Stop 3=Read")
    ts_current_point = Cpt(EpicsSignal, 'TSCurrentPoint')
    ts_num_points = Cpt(EpicsSignal, 'TSNumPoints')
    ts_read = Cpt(EpicsSignal, 'TSRead')
    update = None  # REMOVED
    update_period = None  # REMOVED
    value_sum = None  # REMOVED
    value = None  # REMOVED
    array_size_xyz = DDC_EpicsSignalRO(
        ("x", "ArraySizeX_RBV"),
        ("y", "ArraySizeY_RBV"),
        ("z", "ArraySizeZ_RBV"),
    )


class AttributePlugin_V26(PluginBase_V26, AttributePlugin_V22, version=(2, 6), version_of=AttributePlugin):
    ts_acquiring = Cpt(EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'")
    ts_control = Cpt(EpicsSignal, 'TSControl', string=True, doc="0=Erase/Start 1=Start 2=Stop 3=Read")
    ts_current_point = Cpt(EpicsSignal, 'TSCurrentPoint')
    ts_num_points = Cpt(EpicsSignal, 'TSNumPoints')
    ts_read = Cpt(EpicsSignal, 'TSRead')


class AttributePlugin_V31(PluginBase_V31, AttributePlugin_V26, version=(3, 1), version_of=AttributePlugin):
    array_size_all = DDC_SignalWithRBV(
        ("size0", "ArraySize0"),
        ("size1", "ArraySize1"),
        ("size2", "ArraySize2"),
        ("size3", "ArraySize3"),
        ("size4", "ArraySize4"),
        ("size5", "ArraySize5"),
        ("size6", "ArraySize6"),
        ("size7", "ArraySize7"),
        ("size8", "ArraySize8"),
        ("size9", "ArraySize9"),
        doc="array_size",
    )


class AttributePlugin_V33(PluginBase_V33, AttributePlugin_V31, version=(3, 3), version_of=AttributePlugin):
    ...


class AttributePlugin_V34(PluginBase_V34, AttributePlugin_V33, version=(3, 4), version_of=AttributePlugin):
    ...


# --- NDGather / NDGatherN ---

class GatherPlugin(PluginBase_V31, version=(3, 1)):
    ...
