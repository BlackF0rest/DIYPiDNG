import warnings
import os
import numpy as np
import types
from .dng import Tag, dngIFD, dngTag, DNG, DNGTags
from .defs import Compression, DNGVersion
from .packing import *
from .camdefs import BaseCameraModel

class DNGBASE:
    def __init__(self) -> None:
        self.compress = None
        self.path = None
        self.tags = None
        self.filter = None

    def __data_condition__(self, data : np.ndarray)  -> None:
        if data.dtype != np.uint16:
            raise Exception("RAW Data is not in correct format. Must be uint16_t Numpy Array. ")

    def __tags_condition__(self, tags : DNGTags)  -> None:
        if not tags.get(Tag.ImageWidth):
            raise Exception("No width is defined in tags.")
        if not tags.get(Tag.ImageLength):
            raise Exception("No height is defined in tags.")
        if not tags.get(Tag.BitsPerSample):
            raise Exception("Bit per pixel is not defined.")     

    def __unpack_pixels__(self, data : np.ndarray) -> np.ndarray:
        return data   

    def __filter__(self, rawFrame: np.ndarray, filter : types.FunctionType) -> np.ndarray:

        if not filter:
            return rawFrame

        processed = filter(rawFrame)
        if not isinstance(processed, np.ndarray):
            raise TypeError("return value is not a valid numpy array!")
        elif processed.shape != rawFrame.shape:
            raise ValueError("return array does not have the same shape!")
        if processed.dtype != np.uint16:
            raise ValueError("array data type is invalid!")

        return processed


    def __process__(self, rawFrame : np.ndarray, tags: DNGTags, compress : bool) -> bytearray:

        width = tags.get(Tag.ImageWidth).rawValue[0]
        length = tags.get(Tag.ImageLength).rawValue[0]
        bpp = tags.get(Tag.BitsPerSample).rawValue[0]

        compression_scheme = Compression.LJ92 if compress else Compression.Uncompressed

        if compress:
            from ljpegCompress import pack16tolj
            tile = pack16tolj(rawFrame, int(width*2),
                              int(length/2), bpp, 0, 0, 0, "", 6)
        else:
            if bpp == 8:
                tile = rawFrame.astype('uint8').tobytes()
            elif bpp == 10:
                tile = pack10(rawFrame).tobytes()
            elif bpp == 12:
                tile = pack12(rawFrame).tobytes()
            elif bpp == 14:
                tile = pack14(rawFrame).tobytes()
            elif bpp == 16:
                tile = rawFrame.tobytes()
        
        dngTemplate = DNG()

        dngTemplate.ImageDataStrips.append(tile)
        # set up the FULL IFD
        mainIFD = dngIFD()
        mainTagStripOffset = dngTag(
            Tag.TileOffsets, [0 for tile in dngTemplate.ImageDataStrips])
        mainIFD.tags.append(mainTagStripOffset)
        mainIFD.tags.append(dngTag(Tag.NewSubfileType, [0]))
        mainIFD.tags.append(dngTag(Tag.TileByteCounts, [len(
            tile) for tile in dngTemplate.ImageDataStrips]))
        mainIFD.tags.append(dngTag(Tag.Compression, [compression_scheme]))
        mainIFD.tags.append(dngTag(Tag.Software, "PiDNG"))
        mainIFD.tags.append(dngTag(Tag.DNGVersion, DNGVersion.V1_4))
        mainIFD.tags.append(dngTag(Tag.DNGBackwardVersion, DNGVersion.V1_0))

        for tag in tags.list():
            try:
                mainIFD.tags.append(tag)
            except Exception as e:
                print("TAG Encoding Error!", e, tag)

        dngTemplate.IFDs.append(mainIFD)

        totalLength = dngTemplate.dataLen()

        mainTagStripOffset.setValue(
            [k for offset, k in dngTemplate.StripOffsets.items()])

        buf = bytearray(totalLength)
        dngTemplate.setBuffer(buf)
        dngTemplate.write()

        return buf

    def options(self, tags : DNGTags, path : str, compress=False) -> None:
        self.__tags_condition__(tags)
        self.tags = tags
        self.compress = compress
        self.path = path

    def convert(self, image : np.ndarray, filename=""):

        if self.tags is None:
            raise Exception("Options have not been set!")
        
        # valdify incoming data
        self.__data_condition__(image)
        unpacked = self.__unpack_pixels__(image)
        filtered = self.__filter__(unpacked, self.filter)
        buf = self.__process__(filtered, self.tags, self.compress)

        file_output = False
        if len(filename) > 0:
            file_output = True

        if file_output:
            if not filename.endswith(".dng"):
                filename = filename + '.dng'
            outputDNG = os.path.join(self.path, filename)
            with open(outputDNG, "wb") as outfile:
                outfile.write(buf)
            return outputDNG
        else:
            return buf


class RAW2DNG(DNGBASE):
    def __init__(self) -> None:
        super().__init__()


class CAM2DNG(DNGBASE):
    def __init__(self, model : BaseCameraModel) -> None:
        super().__init__()
        self.model = model

    def options(self, path : str, compress=False) -> None:
        self.__tags_condition__(self.model.tags)
        self.tags = self.model.tags
        self.compress = compress
        self.path = path


class RPICAM2DNG(CAM2DNG):
    def __data_condition__(self, data : np.ndarray)  -> None:
        if data.dtype != np.uint8:
            warnings.warn("RAW Data is not in correct format. Already unpacked? ")

    def __unpack_pixels__(self, data : np.ndarray) -> np.ndarray:

        if data.dtype != np.uint8:
            return data

        height = self.model.tags.get(Tag.ImageLength).rawValue[0] 

        ver = 6
        if  height == 1080:
            ver = 4
        elif height == 1520:
            ver = 5
        elif height == 3040:
            ver = 6
        elif height == 760:
            ver = 3
        elif height == 2464:
            ver = 2
        elif height == 1944:
            ver = 1

        reshape, crop = {
            1: ((1952, 3264), (1944, 3240)),    # 2592x1944
            2: ((2480, 4128), (2464, 4100)),    # 3280x2464
            3: ((768, 1280),  (760, 1265)),     # 1012x760
            4: ((1080, 3072), (1080, 3042)),    # 2028x1080
            5: ((1520, 3072), (1520, 3042)),    # 2028x1520
            6: ((3040, 6112), (3040, 6084)),    # 4056x3040
            
        }[ver]
        data = data.reshape(reshape)[:crop[0], :crop[1]]

        if ver < 4:
            data = data.astype(np.uint16) << 2
            for byte in range(4):
                data[:, byte::5] |= ((data[:, 4::5] >> ((byte+1) * 2)) & 0b11)
            data = np.delete(data, np.s_[4::5], 1)
        else:
            data = data.astype(np.uint16)
            shape = data.shape
            unpacked_data = np.zeros((shape[0], int(shape[1] / 3 * 2)), dtype=np.uint16)
            unpacked_data[:, ::2] = (data[:, ::3] << 4) + (data[:, 2::3] & 0x0F)
            unpacked_data[:, 1::2] = (data[:, 1::3] << 4) + ((data[:, 2::3] >> 4) & 0x0F)
            data = unpacked_data
        return data

class PICAM2DNG(RPICAM2DNG):
    """For use within picamera2 library"""
    def options(self, compress=False) -> None:
        self.__tags_condition__(self.model.tags)
        self.tags = self.model.tags
        self.compress = compress
        self.path = ""
    

