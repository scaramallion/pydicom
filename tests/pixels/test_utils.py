# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Tests for the pixels.utils module."""

import importlib
from io import BytesIO
import logging
import os
import random
from struct import pack
from sys import byteorder

import pytest

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom import dcmread, config
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import get_frame
from pydicom.pixels import pixel_array, iter_pixels, convert_color_space
from pydicom.pixels.utils import (
    as_pixel_options,
    _passes_version_check,
    _get_jpg_parameters,
    reshape_pixel_array,
    pixel_dtype,
    get_expected_length,
    get_j2k_parameters,
    get_nr_frames,
    pack_bits,
    unpack_bits,
    expand_ybr422,
)
from pydicom.uid import (
    EnhancedMRImageStorage,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    UncompressedTransferSyntaxes,
)

from .pixels_reference import (
    PIXEL_REFERENCE,
    RLE_16_1_10F,
    EXPL_16_1_10F,
    EXPL_8_3_1F_YBR422,
    IMPL_16_1_1F,
    JPGB_08_08_3_0_1F_RGB_NO_APP14,
    JPGB_08_08_3_0_1F_RGB_APP14,
    JPGB_08_08_3_0_1F_RGB,
    JLSL_08_08_3_0_1F_ILV0,
    JLSL_08_08_3_0_1F_ILV1,
    JLSL_08_08_3_0_1F_ILV2,
    JLSN_08_01_1_0_1F,
    EXPL_1_1_3F,
)
from ..test_helpers import assert_no_warning


HAVE_PYLJ = bool(importlib.util.find_spec("pylibjpeg"))
HAVE_RLE = bool(importlib.util.find_spec("rle"))

SKIP_RLE = not (HAVE_NP and HAVE_PYLJ and HAVE_RLE)


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestPixelArray:
    """Tests for pixel_array()"""

    def test_src(self):
        """Test the supported `src` types."""
        # Explicit VR
        # str
        p = EXPL_16_1_10F.path
        arr = pixel_array(os.fspath(p))
        EXPL_16_1_10F.test(arr)

        # Path
        arr = pixel_array(p)
        EXPL_16_1_10F.test(arr)

        # BinaryIO (io.BufferedReader)
        with open(p, "rb") as f:
            arr = pixel_array(f)
            EXPL_16_1_10F.test(arr)
            assert not f.closed

        # Implicit VR
        arr = pixel_array(IMPL_16_1_1F.path)
        IMPL_16_1_1F.test(arr)

    def test_ds_out(self):
        """Test the `ds_out` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        arr = pixel_array(os.fspath(p), ds_out=ds)
        EXPL_16_1_10F.test(arr)
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.file_meta.SourceApplicationEntityTitle == "gdcmanon"

    def test_specific_tags(self):
        """Test the `specific_tags` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        tags = [0x00100010, 0x00080016]
        arr = pixel_array(os.fspath(p), ds_out=ds)
        EXPL_16_1_10F.test(arr)
        assert "PatientName" not in ds
        assert "SOPClassUID" not in ds

        arr = pixel_array(os.fspath(p), ds_out=ds, specific_tags=tags)
        EXPL_16_1_10F.test(arr)
        assert "PatientName" in ds
        assert ds.SOPClassUID == EnhancedMRImageStorage

    def test_index(self):
        """Test the `index` kwarg."""
        for index in (0, 4, 9):
            arr = pixel_array(EXPL_16_1_10F.path, index=index)
            assert arr.shape == (64, 64)
            EXPL_16_1_10F.test(arr, index=index)

    def test_raw(self):
        """Test the `raw` kwarg."""
        rgb = pixel_array(EXPL_8_3_1F_YBR422.path, raw=False)
        ybr = pixel_array(EXPL_8_3_1F_YBR422.path, raw=True)

        assert np.array_equal(
            convert_color_space(ybr, "YBR_FULL", "RGB"),
            rgb,
        )

    @pytest.mark.skipif(SKIP_RLE, reason="pylibjpeg-rle not available")
    def test_decoding_plugin(self):
        """Test the `decoding_plugin` kwarg."""
        arr1 = pixel_array(RLE_16_1_10F.path, decoding_plugin="pydicom")
        arr2 = pixel_array(RLE_16_1_10F.path, decoding_plugin="pylibjpeg")
        assert np.array_equal(arr1, arr2)

    def test_missing_file_meta(self):
        """Test a dataset with no file meta."""
        ds = dcmread(EXPL_16_1_10F.path)
        b = BytesIO()
        del ds.file_meta
        ds.save_as(b)
        b.seek(0)

        msg = (
            "'transfer_syntax_uid' is required if the dataset in 'src' is not "
            "in the DICOM File Format"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

        arr = pixel_array(b, transfer_syntax_uid=ExplicitVRLittleEndian)
        EXPL_16_1_10F.test(arr)

    def test_missing_required_element(self):
        """Test a dataset missing required elements."""
        ds = dcmread(EXPL_8_3_1F_YBR422.path)
        b = BytesIO()
        del ds.Columns
        del ds.Rows
        del ds.BitsAllocated
        del ds.BitsStored
        del ds.PhotometricInterpretation
        del ds.SamplesPerPixel
        del ds.PlanarConfiguration
        del ds.PixelRepresentation
        ds.save_as(b)
        b.seek(0)

        msg = r"Missing required element: \(0028,0100\) 'Bits Allocated'"
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

        msg = r"Missing required element: \(0028,0101\) 'Bits Stored'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0011\) 'Columns'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0004\) 'Photometric Interpretation'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0103\) 'Pixel Representation'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0010\) 'Rows'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "pixel_representation": EXPL_8_3_1F_YBR422.ds.PixelRepresentation,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0002\) 'Samples per Pixel'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "pixel_representation": EXPL_8_3_1F_YBR422.ds.PixelRepresentation,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

        msg = r"Missing required element: \(0028,0006\) 'Planar Configuration'"
        opts = {
            "bits_allocated": EXPL_8_3_1F_YBR422.ds.BitsAllocated,
            "bits_stored": EXPL_8_3_1F_YBR422.ds.BitsStored,
            "columns": EXPL_8_3_1F_YBR422.ds.Columns,
            "rows": EXPL_8_3_1F_YBR422.ds.Rows,
            "photometric_interpretation": EXPL_8_3_1F_YBR422.ds.PhotometricInterpretation,
            "samples_per_pixel": EXPL_8_3_1F_YBR422.ds.SamplesPerPixel,
            "pixel_representation": EXPL_8_3_1F_YBR422.ds.PixelRepresentation,
        }
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b, **opts)

    def test_missing_pixel_data(self):
        """Test dataset missing Pixel Data"""
        ds = dcmread(EXPL_8_3_1F_YBR422.path)
        b = BytesIO()
        del ds.PixelData
        ds.save_as(b)
        b.seek(0)

        msg = (
            "The dataset in 'src' has no 'Pixel Data', 'Float Pixel Data' or "
            "'Double Float Pixel Data' element, no pixel data to decode"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_array(b)

    def test_extended_offsets(self):
        """Test that the extended offset table values are retrieved OK"""
        ds = EXPL_8_3_1F_YBR422.ds
        offsets = (
            b"\x00\x00\x00\x00\x00\x00\x00\x01",
            b"\x00\x00\x00\x00\x00\x00\x00\x02",
        )
        ds.ExtendedOffsetTable = offsets[0]
        ds.ExtendedOffsetTableLengths = offsets[1]
        opts = as_pixel_options(ds)
        assert opts["extended_offsets"] == offsets

        offsets = (
            b"\x00\x00\x00\x00\x00\x00\x00\x03",
            b"\x00\x00\x00\x00\x00\x00\x00\x04",
        )
        opts = as_pixel_options(ds, **{"extended_offsets": offsets})
        assert opts["extended_offsets"] == offsets


@pytest.mark.skipif(not HAVE_NP, reason="NumPy is not available")
class TestIterPixels:
    """Tests for iter_pixels()"""

    def test_src(self):
        """Test the supported `src` types."""
        # Explicit VR
        # str
        p = EXPL_16_1_10F.path
        for index, frame in enumerate(iter_pixels(os.fspath(p))):
            EXPL_16_1_10F.test(frame, index=index)

        # Path
        for index, frame in enumerate(iter_pixels(p)):
            EXPL_16_1_10F.test(frame, index=index)

        # BinaryIO (io.BufferedReader)
        with open(p, "rb") as f:
            for index, frame in enumerate(iter_pixels(f)):
                EXPL_16_1_10F.test(frame, index=index)

            assert not f.closed

        # Implicit VR
        for index, frame in enumerate(iter_pixels(IMPL_16_1_1F.path)):
            IMPL_16_1_1F.test(frame, index=index)

    def test_ds_out(self):
        """Test the `ds_out` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        frame_gen = iter_pixels(p, ds_out=ds)
        frame = next(frame_gen)
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.file_meta.SourceApplicationEntityTitle == "gdcmanon"
        EXPL_16_1_10F.test(frame, index=0)

        for index, frame in enumerate(frame_gen):
            EXPL_16_1_10F.test(frame, index=index + 1)

    def test_specific_tags(self):
        """Test the `specific_tags` kwarg works as intended"""
        p = EXPL_16_1_10F.path
        ds = Dataset()
        tags = [0x00100010, 0x00080016]

        frame_gen = iter_pixels(p, ds_out=ds)
        frame = next(frame_gen)
        assert "PatientName" not in ds
        assert "SOPClassUID" not in ds
        assert ds.SamplesPerPixel == 1
        assert ds.PixelRepresentation == 0
        assert ds.file_meta.SourceApplicationEntityTitle == "gdcmanon"
        EXPL_16_1_10F.test(frame, index=0)
        for index, frame in enumerate(frame_gen):
            EXPL_16_1_10F.test(frame, index=index + 1)

        frame_gen = iter_pixels(p, ds_out=ds, specific_tags=tags)
        frame = next(frame_gen)
        assert "PatientName" in ds
        assert ds.SOPClassUID == EnhancedMRImageStorage
        EXPL_16_1_10F.test(frame, index=0)
        for index, frame in enumerate(frame_gen):
            EXPL_16_1_10F.test(frame, index=index + 1)

    def test_indices(self):
        """Test the `indices` kwarg."""
        p = EXPL_16_1_10F.path
        indices = [0, 4, 9]
        frame_gen = iter_pixels(p, indices=indices)
        count = 0
        for frame in frame_gen:
            EXPL_16_1_10F.test(frame, index=indices[count])
            count += 1

        assert count == 3

    def test_raw(self):
        """Test the `raw` kwarg."""
        processed = iter_pixels(EXPL_8_3_1F_YBR422.path, raw=False)
        raw = iter_pixels(EXPL_8_3_1F_YBR422.path, raw=True)
        for rgb, ybr in zip(processed, raw):
            assert np.array_equal(
                convert_color_space(ybr, "YBR_FULL", "RGB"),
                rgb,
            )

    @pytest.mark.skipif(SKIP_RLE, reason="pylibjpeg-rle not available")
    def test_decoding_plugin(self):
        """Test the `decoding_plugin` kwarg."""
        pydicom_gen = iter_pixels(RLE_16_1_10F.path, decoding_plugin="pydicom")
        pylibjpeg_gen = iter_pixels(RLE_16_1_10F.path, decoding_plugin="pylibjpeg")
        for frame1, frame2 in zip(pydicom_gen, pylibjpeg_gen):
            assert np.array_equal(frame1, frame2)


def test_version_check(caplog):
    """Test _passes_version_check() when the package is absent"""
    with caplog.at_level(logging.ERROR, logger="pydicom"):
        assert _passes_version_check("foo", (3, 0)) is False
        assert "No module named 'foo'" in caplog.text


class TestGetJpgParameters:
    """Tests for _get_jpg_parameters()"""

    def test_jpg_no_app(self):
        """Test parsing a JPEG codestream with no APP markers."""
        data = get_frame(JPGB_08_08_3_0_1F_RGB_NO_APP14.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [0, 1, 2]
        assert "app" not in info
        assert "lossy_error" not in info
        assert "interleave_mode" not in info

    def test_jpg_app(self):
        """Test parsing a JPEG codestream with APP markers."""
        data = get_frame(JPGB_08_08_3_0_1F_RGB_APP14.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [0, 1, 2]
        assert info["app"][b"\xFF\xEE"] == (
            b"\x41\x64\x6F\x62\x65\x00\x65\x00\x00\x00\x00\x00"
        )
        assert "lossy_error" not in info
        assert "interleave_mode" not in info

    def test_jpg_component_ids(self):
        """Test parsing a JPEG codestream with ASCII component IDs."""
        data = get_frame(JPGB_08_08_3_0_1F_RGB.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 100
        assert info["width"] == 100
        assert info["components"] == 3
        assert info["component_ids"] == [82, 71, 66]  # R, G, B
        assert isinstance(info["app"][b"\xFF\xEE"], bytes)
        assert "lossy_error" not in info
        assert "interleave_mode" not in info

    def test_jls_ilv0(self):
        """Test parsing a lossless JPEG-LS codestream with ILV 0."""
        data = get_frame(JLSL_08_08_3_0_1F_ILV0.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [1, 2, 3]
        assert "app" not in info
        assert info["lossy_error"] == 0
        assert info["interleave_mode"] == 0

    def test_jls_ilv1(self):
        """Test parsing a lossless JPEG-LS codestream with ILV 1."""
        data = get_frame(JLSL_08_08_3_0_1F_ILV1.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [1, 2, 3]
        assert "app" not in info
        assert info["lossy_error"] == 0
        assert info["interleave_mode"] == 1

    def test_jls_ilv2(self):
        """Test parsing a lossless JPEG-LS codestream with ILV 2."""
        data = get_frame(JLSL_08_08_3_0_1F_ILV2.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 256
        assert info["width"] == 256
        assert info["components"] == 3
        assert info["component_ids"] == [1, 2, 3]
        assert "app" not in info
        assert info["lossy_error"] == 0
        assert info["interleave_mode"] == 2

    def test_jls_lossy(self):
        """Test parsing a lossy JPEG-LS codestream."""
        data = get_frame(JLSN_08_01_1_0_1F.ds.PixelData, 0)
        info = _get_jpg_parameters(data)
        assert info["precision"] == 8
        assert info["height"] == 45
        assert info["width"] == 10
        assert info["components"] == 1
        assert info["component_ids"] == [1]
        assert "app" not in info
        assert info["lossy_error"] == 2
        assert info["interleave_mode"] == 0

    def test_invalid(self):
        """Test invalid codestreams."""
        assert _get_jpg_parameters(b"\x00\x00") == {}
        data = get_frame(JLSN_08_01_1_0_1F.ds.PixelData, 0)
        assert _get_jpg_parameters(data[:20]) == {}


REFERENCE_DTYPE = [
    # BitsAllocated, PixelRepresentation, as_float, numpy dtype string
    (1, 0, False, "uint8"),
    (1, 1, False, "uint8"),
    (8, 0, False, "uint8"),
    (8, 1, False, "int8"),
    (16, 0, False, "uint16"),
    (16, 1, False, "int16"),
    (32, 0, False, "uint32"),
    (32, 1, False, "int32"),
    (32, 0, True, "float32"),
    (64, 0, True, "float64"),
]


@pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
def test_pixel_dtype_raises():
    """Test that pixel_dtype raises exception without numpy."""
    with pytest.raises(ImportError, match="Numpy is required to determine the dtype"):
        pixel_dtype(None)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestPixelDtype:
    """Tests for pixel_dtype()."""

    def setup_method(self):
        """Setup the test dataset."""
        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    def test_unknown_pixel_representation_raises(self):
        """Test an unknown PixelRepresentation value raises exception."""
        self.ds.BitsAllocated = 16
        with pytest.warns(UserWarning):
            self.ds.PixelRepresentation = -1
        # The bracket needs to be escaped
        with pytest.raises(ValueError, match=r"value of '-1' for '\(0028,0103"):
            pixel_dtype(self.ds)

        self.ds.PixelRepresentation = 2
        with pytest.raises(ValueError, match=r"value of '2' for '\(0028,0103"):
            pixel_dtype(self.ds)

    def test_unknown_bits_allocated_raises(self):
        """Test an unknown BitsAllocated value raises exception."""
        self.ds.BitsAllocated = 0
        self.ds.PixelRepresentation = 0
        # The bracket needs to be escaped
        with pytest.raises(ValueError, match=r"value of '0' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 2
        with pytest.raises(ValueError, match=r"value of '2' for '\(0028,0100"):
            pixel_dtype(self.ds)

        self.ds.BitsAllocated = 15
        with pytest.raises(ValueError, match=r"value of '15' for '\(0028,0100"):
            pixel_dtype(self.ds)

    def test_unsupported_dtypes(self):
        """Test unsupported dtypes raise exception."""
        self.ds.BitsAllocated = 24
        self.ds.PixelRepresentation = 0

        with pytest.raises(
            NotImplementedError, match="data type 'uint24' needed to contain"
        ):
            pixel_dtype(self.ds)

    @pytest.mark.parametrize("bits, pixel_repr, as_float, dtype", REFERENCE_DTYPE)
    def test_supported_dtypes(self, bits, pixel_repr, as_float, dtype):
        """Test supported dtypes."""
        self.ds.BitsAllocated = bits
        self.ds.PixelRepresentation = pixel_repr
        # Correct for endianness of system
        ref_dtype = np.dtype(dtype)
        endianness = self.ds.file_meta.TransferSyntaxUID.is_little_endian
        if endianness != (byteorder == "little"):
            ref_dtype = ref_dtype.newbyteorder("S")

        assert ref_dtype == pixel_dtype(self.ds, as_float=as_float)

    def test_byte_swapping(self):
        """Test that the endianness of the system is taken into account."""
        # The main problem is that our testing environments are probably
        #   all little endian, but we'll try our best
        self.ds.BitsAllocated = 16
        self.ds.PixelRepresentation = 0

        # explicit little
        meta = self.ds.file_meta

        # < is little, = is native, > is big
        if byteorder == "little":
            self.ds._read_little = True
            assert pixel_dtype(self.ds).byteorder in ["<", "="]
            meta.TransferSyntaxUID = ExplicitVRBigEndian
            self.ds._read_little = False
            assert pixel_dtype(self.ds).byteorder == ">"
        elif byteorder == "big":
            self.ds._read_little = True
            assert pixel_dtype(self.ds).byteorder == "<"
            meta.TransferSyntaxUID = ExplicitVRBigEndian
            self.ds._read_little = False
            assert pixel_dtype(self.ds).byteorder in [">", "="]

    def test_no_endianness_raises(self):
        ds = Dataset()
        ds.BitsAllocated = 8
        ds.PixelRepresentation = 1
        msg = (
            "Unable to determine the endianness of the dataset, please set "
            "an appropriate Transfer Syntax UID in 'Dataset.file_meta'"
        )
        with pytest.raises(AttributeError, match=msg):
            pixel_dtype(ds)


if HAVE_NP:
    _arr1_1 = [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7, 4, 5, 6, 7, 8]

    _arr2_1 = _arr1_1[:]
    _arr2_1.extend(
        [25, 26, 27, 28, 29, 26, 27, 28, 29, 30, 27, 28, 29, 30, 31, 28, 29, 30, 31, 32]
    )

    _arr1_3_0 = [1, 9, 17, 2, 10, 18, 3, 11, 19, 4, 12, 20, 5, 13, 21, 2, 10, 18, 3, 11]
    _arr1_3_0.extend(
        [19, 4, 12, 20, 5, 13, 21, 6, 14, 22, 3, 11, 19, 4, 12, 20, 5, 13, 21, 6]
    )
    _arr1_3_0.extend(
        [14, 22, 7, 15, 23, 4, 12, 20, 5, 13, 21, 6, 14, 22, 7, 15, 23, 8, 16, 24]
    )

    _arr1_3_1 = _arr1_1[:]
    _arr1_3_1.extend(
        [9, 10, 11, 12, 13, 10, 11, 12, 13, 14, 11, 12, 13, 14, 15, 12, 13, 14, 15, 16]
    )
    _arr1_3_1.extend(
        [17, 18, 19, 20, 21, 18, 19, 20, 21, 22, 19, 20, 21, 22, 23, 20, 21, 22, 23, 24]
    )

    _arr2_3_0 = _arr1_3_0[:]
    _arr2_3_0.extend(
        [25, 33, 41, 26, 34, 42, 27, 35, 43, 28, 36, 44, 29, 37, 45, 26, 34, 42, 27, 35]
    )
    _arr2_3_0.extend(
        [43, 28, 36, 44, 29, 37, 45, 30, 38, 46, 27, 35, 43, 28, 36, 44, 29, 37, 45, 30]
    )
    _arr2_3_0.extend(
        [38, 46, 31, 39, 47, 28, 36, 44, 29, 37, 45, 30, 38, 46, 31, 39, 47, 32, 40, 48]
    )

    _arr2_3_1 = _arr1_3_1[:]
    _arr2_3_1.extend(
        [25, 26, 27, 28, 29, 26, 27, 28, 29, 30, 27, 28, 29, 30, 31, 28, 29, 30, 31, 32]
    )
    _arr2_3_1.extend(
        [33, 34, 35, 36, 37, 34, 35, 36, 37, 38, 35, 36, 37, 38, 39, 36, 37, 38, 39, 40]
    )
    _arr2_3_1.extend(
        [41, 42, 43, 44, 45, 42, 43, 44, 45, 46, 43, 44, 45, 46, 47, 44, 45, 46, 47, 48]
    )

    RESHAPE_ARRAYS = {
        "reference": np.asarray(
            [
                [  # Frame 1
                    [[1, 9, 17], [2, 10, 18], [3, 11, 19], [4, 12, 20], [5, 13, 21]],
                    [[2, 10, 18], [3, 11, 19], [4, 12, 20], [5, 13, 21], [6, 14, 22]],
                    [[3, 11, 19], [4, 12, 20], [5, 13, 21], [6, 14, 22], [7, 15, 23]],
                    [[4, 12, 20], [5, 13, 21], [6, 14, 22], [7, 15, 23], [8, 16, 24]],
                ],
                [  # Frame 2
                    [
                        [25, 33, 41],
                        [26, 34, 42],
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                    ],
                    [
                        [26, 34, 42],
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                    ],
                    [
                        [27, 35, 43],
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                        [31, 39, 47],
                    ],
                    [
                        [28, 36, 44],
                        [29, 37, 45],
                        [30, 38, 46],
                        [31, 39, 47],
                        [32, 40, 48],
                    ],
                ],
            ]
        ),
        "1frame_1sample": np.asarray(_arr1_1),
        "2frame_1sample": np.asarray(_arr2_1),
        "1frame_3sample_0config": np.asarray(_arr1_3_0),
        "1frame_3sample_1config": np.asarray(_arr1_3_1),
        "2frame_3sample_0config": np.asarray(_arr2_3_0),
        "2frame_3sample_1config": np.asarray(_arr2_3_1),
    }


@pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
def test_reshape_pixel_array_raises():
    """Test that reshape_pixel_array raises exception without numpy."""
    with pytest.raises(ImportError, match="Numpy is required to reshape"):
        reshape_pixel_array(None, None)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestReshapePixelArray:
    """Tests for reshape_pixel_array()."""

    def setup_method(self):
        """Setup the test dataset."""
        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        self.ds.Rows = 4
        self.ds.Columns = 5

        # Expected output ref_#frames_#samples
        self.ref_1_1 = RESHAPE_ARRAYS["reference"][0, :, :, 0]
        self.ref_1_3 = RESHAPE_ARRAYS["reference"][0]
        self.ref_2_1 = RESHAPE_ARRAYS["reference"][:, :, :, 0]
        self.ref_2_3 = RESHAPE_ARRAYS["reference"]

    def test_reference_1frame_1sample(self):
        """Test the 1 frame 1 sample/pixel reference array is as expected."""
        # (rows, columns)
        assert (4, 5) == self.ref_1_1.shape
        assert np.array_equal(
            self.ref_1_1,
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )

    def test_reference_1frame_3sample(self):
        """Test the 1 frame 3 sample/pixel reference array is as expected."""
        # (rows, columns, planes)
        assert (4, 5, 3) == self.ref_1_3.shape

        # Red channel
        assert np.array_equal(
            self.ref_1_3[:, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Green channel
        assert np.array_equal(
            self.ref_1_3[:, :, 1],
            np.asarray(
                [
                    [9, 10, 11, 12, 13],
                    [10, 11, 12, 13, 14],
                    [11, 12, 13, 14, 15],
                    [12, 13, 14, 15, 16],
                ]
            ),
        )
        # Blue channel
        assert np.array_equal(
            self.ref_1_3[:, :, 2],
            np.asarray(
                [
                    [17, 18, 19, 20, 21],
                    [18, 19, 20, 21, 22],
                    [19, 20, 21, 22, 23],
                    [20, 21, 22, 23, 24],
                ]
            ),
        )

    def test_reference_2frame_1sample(self):
        """Test the 2 frame 1 sample/pixel reference array is as expected."""
        # (nr frames, rows, columns)
        assert (2, 4, 5) == self.ref_2_1.shape

        # Frame 1
        assert np.array_equal(
            self.ref_2_1[0, :, :],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Frame 2
        assert np.array_equal(
            self.ref_2_1[1, :, :],
            np.asarray(
                [
                    [25, 26, 27, 28, 29],
                    [26, 27, 28, 29, 30],
                    [27, 28, 29, 30, 31],
                    [28, 29, 30, 31, 32],
                ]
            ),
        )

    def test_reference_2frame_3sample(self):
        """Test the 2 frame 3 sample/pixel reference array is as expected."""
        # (nr frames, row, columns, planes)
        assert (2, 4, 5, 3) == self.ref_2_3.shape

        # Red channel, frame 1
        assert np.array_equal(
            self.ref_2_3[0, :, :, 0],
            np.asarray(
                [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6], [3, 4, 5, 6, 7], [4, 5, 6, 7, 8]]
            ),
        )
        # Green channel, frame 2
        assert np.array_equal(
            self.ref_2_3[1, :, :, 1],
            np.asarray(
                [
                    [33, 34, 35, 36, 37],
                    [34, 35, 36, 37, 38],
                    [35, 36, 37, 38, 39],
                    [36, 37, 38, 39, 40],
                ]
            ),
        )

    def test_1frame_1sample(self):
        """Test reshaping 1 frame, 1 sample/pixel."""
        self.ds.SamplesPerPixel = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_1sample"])
        assert (4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_1_1)

    def test_1frame_3sample_0conf(self):
        """Test reshaping 1 frame, 3 sample/pixel for 0 planar config."""
        self.ds.NumberOfFrames = 1
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_1frame_3sample_1conf(self):
        """Test reshaping 1 frame, 3 sample/pixel for 1 planar config."""
        self.ds.NumberOfFrames = 1
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_1config"])
        assert (4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_1_3)

    def test_2frame_1sample(self):
        """Test reshaping 2 frame, 1 sample/pixel."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["2frame_1sample"])
        assert (2, 4, 5) == arr.shape
        assert np.array_equal(arr, self.ref_2_1)

    def test_2frame_3sample_0conf(self):
        """Test reshaping 2 frame, 3 sample/pixel for 0 planar config."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 0
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["2frame_3sample_0config"])
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

    def test_2frame_3sample_1conf(self):
        """Test reshaping 2 frame, 3 sample/pixel for 1 planar config."""
        self.ds.NumberOfFrames = 2
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 1
        arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["2frame_3sample_1config"])
        assert (2, 4, 5, 3) == arr.shape
        assert np.array_equal(arr, self.ref_2_3)

    def test_compressed_syntaxes_0conf(self):
        """Test the compressed syntaxes that are always 0 planar conf."""
        for uid in [
            "1.2.840.10008.1.2.4.50",
            "1.2.840.10008.1.2.4.57",
            "1.2.840.10008.1.2.4.70",
            "1.2.840.10008.1.2.4.90",
            "1.2.840.10008.1.2.4.91",
        ]:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 1
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_compressed_syntaxes_1conf(self):
        """Test the compressed syntaxes that are always 1 planar conf."""
        for uid in ["1.2.840.10008.1.2.5"]:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 0
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_1config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_uncompressed_syntaxes(self):
        """Test that uncompressed syntaxes use the dataset planar conf."""
        for uid in UncompressedTransferSyntaxes:
            self.ds.file_meta.TransferSyntaxUID = uid
            self.ds.PlanarConfiguration = 0
            self.ds.NumberOfFrames = 1
            self.ds.SamplesPerPixel = 3

            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

            self.ds.PlanarConfiguration = 1
            arr = reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_1config"])
            assert (4, 5, 3) == arr.shape
            assert np.array_equal(arr, self.ref_1_3)

    def test_invalid_nr_frames_warns(self):
        """Test an invalid Number of Frames value shows an warning."""
        self.ds.SamplesPerPixel = 1
        self.ds.NumberOfFrames = 0
        # Need to escape brackets
        with pytest.warns(UserWarning, match=r"value of 0 for \(0028,0008\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_1sample"])

    def test_invalid_samples_raises(self):
        """Test an invalid Samples per Pixel value raises exception."""
        self.ds.SamplesPerPixel = 0
        # Need to escape brackets
        with pytest.raises(ValueError, match=r"value of 0 for \(0028,0002\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_1sample"])

    def test_invalid_planar_conf_raises(self):
        self.ds.SamplesPerPixel = 3
        self.ds.PlanarConfiguration = 2
        # Need to escape brackets
        with pytest.raises(ValueError, match=r"value of 2 for \(0028,0006\)"):
            reshape_pixel_array(self.ds, RESHAPE_ARRAYS["1frame_3sample_0config"])


REFERENCE_LENGTH = [
    # (frames, rows, cols, samples), bit depth,
    #   result in (bytes, pixels, ybr_bytes)
    # YBR can only be 3 samples/px and > 1 bit depth
    # No 'NumberOfFrames' in dataset
    ((0, 0, 0, 0), 1, (0, 0, None)),
    ((0, 1, 1, 1), 1, (1, 1, None)),  # 1 bit -> 1 byte
    ((0, 1, 1, 3), 1, (1, 3, None)),  # 3 bits -> 1 byte
    ((0, 1, 3, 3), 1, (2, 9, None)),  # 9 bits -> 2 bytes
    ((0, 2, 2, 1), 1, (1, 4, None)),  # 4 bits -> 1 byte
    ((0, 2, 4, 1), 1, (1, 8, None)),  # 8 bits -> 1 byte
    ((0, 3, 3, 1), 1, (2, 9, None)),  # 9 bits -> 2 bytes
    ((0, 512, 512, 1), 1, (32768, 262144, None)),  # Typical length
    ((0, 512, 512, 3), 1, (98304, 786432, None)),
    ((0, 0, 0, 0), 8, (0, 0, None)),
    ((0, 1, 1, 1), 8, (1, 1, None)),  # Odd length
    ((0, 9, 1, 1), 8, (9, 9, None)),  # Odd length
    ((0, 1, 2, 1), 8, (2, 2, None)),  # Even length
    ((0, 512, 512, 1), 8, (262144, 262144, None)),
    ((0, 512, 512, 3), 8, (786432, 786432, 524288)),
    ((0, 0, 0, 0), 16, (0, 0, None)),
    ((0, 1, 1, 1), 16, (2, 1, None)),  # 16 bit data can't be odd length
    ((0, 1, 2, 1), 16, (4, 2, None)),
    ((0, 512, 512, 1), 16, (524288, 262144, None)),
    ((0, 512, 512, 3), 16, (1572864, 786432, 1048576)),
    ((0, 0, 0, 0), 32, (0, 0, None)),
    ((0, 1, 1, 1), 32, (4, 1, None)),  # 32 bit data can't be odd length
    ((0, 1, 2, 1), 32, (8, 2, None)),
    ((0, 512, 512, 1), 32, (1048576, 262144, None)),
    ((0, 512, 512, 3), 32, (3145728, 786432, 2097152)),
    # NumberOfFrames odd
    ((3, 0, 0, 0), 1, (0, 0, None)),
    ((3, 1, 1, 1), 1, (1, 3, None)),
    ((3, 1, 1, 3), 1, (2, 9, None)),
    ((3, 1, 3, 3), 1, (4, 27, None)),
    ((3, 2, 4, 1), 1, (3, 24, None)),
    ((3, 2, 2, 1), 1, (2, 12, None)),
    ((3, 3, 3, 1), 1, (4, 27, None)),
    ((3, 512, 512, 1), 1, (98304, 786432, None)),
    ((3, 512, 512, 3), 1, (294912, 2359296, 196608)),
    ((3, 0, 0, 0), 8, (0, 0, None)),
    ((3, 1, 1, 1), 8, (3, 3, None)),
    ((3, 9, 1, 1), 8, (27, 27, None)),
    ((3, 1, 2, 1), 8, (6, 6, None)),
    ((3, 512, 512, 1), 8, (786432, 786432, None)),
    ((3, 512, 512, 3), 8, (2359296, 2359296, 1572864)),
    ((3, 0, 0, 0), 16, (0, 0, None)),
    ((3, 512, 512, 1), 16, (1572864, 786432, None)),
    ((3, 512, 512, 3), 16, (4718592, 2359296, 3145728)),
    ((3, 0, 0, 0), 32, (0, 0, None)),
    ((3, 512, 512, 1), 32, (3145728, 786432, None)),
    ((3, 512, 512, 3), 32, (9437184, 2359296, 6291456)),
    # NumberOfFrames even
    ((4, 0, 0, 0), 1, (0, 0, None)),
    ((4, 1, 1, 1), 1, (1, 4, None)),
    ((4, 1, 1, 3), 1, (2, 12, None)),
    ((4, 1, 3, 3), 1, (5, 36, None)),
    ((4, 2, 4, 1), 1, (4, 32, None)),
    ((4, 2, 2, 1), 1, (2, 16, None)),
    ((4, 3, 3, 1), 1, (5, 36, None)),
    ((4, 512, 512, 1), 1, (131072, 1048576, None)),
    ((4, 512, 512, 3), 1, (393216, 3145728, 262144)),
    ((4, 0, 0, 0), 8, (0, 0, None)),
    ((4, 512, 512, 1), 8, (1048576, 1048576, None)),
    ((4, 512, 512, 3), 8, (3145728, 3145728, 2097152)),
    ((4, 0, 0, 0), 16, (0, 0, None)),
    ((4, 512, 512, 1), 16, (2097152, 1048576, None)),
    ((4, 512, 512, 3), 16, (6291456, 3145728, 4194304)),
    ((4, 0, 0, 0), 32, (0, 0, None)),
    ((4, 512, 512, 1), 32, (4194304, 1048576, None)),
    ((4, 512, 512, 3), 32, (12582912, 3145728, 8388608)),
]


class TestGetExpectedLength:
    """Tests for get_expected_length()."""

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_LENGTH)
    def test_length_in_bytes(self, shape, bits, length):
        """Test get_expected_length(ds, unit='bytes')."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[0] == get_expected_length(ds, unit="bytes")

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_LENGTH)
    def test_length_in_pixels(self, shape, bits, length):
        """Test get_expected_length(ds, unit='pixels')."""
        ds = Dataset()
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[1] == get_expected_length(ds, unit="pixels")

    @pytest.mark.parametrize("shape, bits, length", REFERENCE_LENGTH)
    def test_length_ybr_422(self, shape, bits, length):
        """Test get_expected_length for YBR_FULL_422."""
        if shape[3] != 3 or bits == 1:
            return

        ds = Dataset()
        ds.PhotometricInterpretation = "YBR_FULL_422"
        ds.Rows = shape[1]
        ds.Columns = shape[2]
        ds.BitsAllocated = bits
        if shape[0] != 0:
            ds.NumberOfFrames = shape[0]
        ds.SamplesPerPixel = shape[3]

        assert length[2] == get_expected_length(ds, unit="bytes")


class TestGetJ2KParameters:
    """Tests for get_j2k_parameters()."""

    def test_precision(self):
        """Test getting the precision for a JPEG2K bytestream."""
        base = b"\xff\x4f\xff\x51" + b"\x00" * 38
        # Signed
        for ii in range(135, 144):
            params = get_j2k_parameters(base + bytes([ii]))
            assert ii - 127 == params["precision"]
            assert params["is_signed"]

        # Unsigned
        for ii in range(7, 16):
            params = get_j2k_parameters(base + bytes([ii]))
            assert ii + 1 == params["precision"]
            assert not params["is_signed"]

    def test_not_j2k(self):
        """Test result when no JPEG2K SOF marker present"""
        base = b"\xff\x4e\xff\x51" + b"\x00" * 38
        assert {} == get_j2k_parameters(base + b"\x8F")

    def test_no_siz(self):
        """Test result when no SIZ box present"""
        base = b"\xff\x4f\xff\x52" + b"\x00" * 38
        assert {} == get_j2k_parameters(base + b"\x8F")

    def test_short_bytestream(self):
        """Test result when no SIZ box present"""
        assert {} == get_j2k_parameters(b"")
        assert {} == get_j2k_parameters(b"\xff\x4f\xff\x51" + b"\x00" * 20)


class TestGetNrFrames:
    """Tests for get_nr_frames()."""

    def test_none(self):
        """Test warning when (0028,0008) 'Number of Frames' has a value of
        None"""
        ds = Dataset()
        ds.NumberOfFrames = None
        msg = (
            r"A value of None for \(0028,0008\) 'Number of Frames' is "
            r"non-conformant. It's recommended that this value be "
            r"changed to 1"
        )
        with pytest.warns(UserWarning, match=msg):
            assert 1 == get_nr_frames(ds)

    def test_zero(self):
        """Test warning when (0028,0008) 'Number of Frames' has a value of 0"""
        ds = Dataset()
        ds.NumberOfFrames = 0
        msg = (
            r"A value of 0 for \(0028,0008\) 'Number of Frames' is "
            r"non-conformant. It's recommended that this value be "
            r"changed to 1"
        )
        with pytest.warns(UserWarning, match=msg):
            assert 1 == get_nr_frames(ds)

    def test_missing(self):
        """Test return value when (0028,0008) 'Number of Frames' does not
        exist"""
        ds = Dataset()
        with assert_no_warning():
            assert 1 == get_nr_frames(ds)

    def test_existing(self):
        """Test return value when (0028,0008) 'Number of Frames' exists."""
        ds = Dataset()
        ds.NumberOfFrames = random.randint(1, 10)
        with assert_no_warning():
            assert ds.NumberOfFrames == get_nr_frames(ds)


REFERENCE_PACK_UNPACK = [
    (b"", []),
    (b"\x00", [0, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x01", [1, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x02", [0, 1, 0, 0, 0, 0, 0, 0]),
    (b"\x04", [0, 0, 1, 0, 0, 0, 0, 0]),
    (b"\x08", [0, 0, 0, 1, 0, 0, 0, 0]),
    (b"\x10", [0, 0, 0, 0, 1, 0, 0, 0]),
    (b"\x20", [0, 0, 0, 0, 0, 1, 0, 0]),
    (b"\x40", [0, 0, 0, 0, 0, 0, 1, 0]),
    (b"\x80", [0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\xAA", [0, 1, 0, 1, 0, 1, 0, 1]),
    (b"\xF0", [0, 0, 0, 0, 1, 1, 1, 1]),
    (b"\x0F", [1, 1, 1, 1, 0, 0, 0, 0]),
    (b"\xFF", [1, 1, 1, 1, 1, 1, 1, 1]),
    #              | 1st byte              | 2nd byte
    (b"\x00\x00", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x00\x01", [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    (b"\x00\x80", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\xFF", [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]),
    (b"\x01\x80", [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x80\x80", [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\xFF\x80", [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1]),
]


class TestUnpackBits:
    """Tests for unpack_bits()."""

    @pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
    @pytest.mark.parametrize("src, output", REFERENCE_PACK_UNPACK)
    def test_unpack_np(self, src, output):
        """Test unpacking data using numpy."""
        assert np.array_equal(unpack_bits(src, as_array=True), np.asarray(output))

        as_bytes = pack(f"{len(output)}B", *output)
        assert unpack_bits(src, as_array=False) == as_bytes

    @pytest.mark.skipif(HAVE_NP, reason="Numpy is available")
    @pytest.mark.parametrize("src, output", REFERENCE_PACK_UNPACK)
    def test_unpack_bytes(self, src, output):
        """Test unpacking data without numpy."""
        as_bytes = pack(f"{len(output)}B", *output)
        assert unpack_bits(src, as_array=False) == as_bytes

        msg = r"unpack_bits\(\) requires NumPy if 'as_array = True'"
        with pytest.raises(ValueError, match=msg):
            unpack_bits(src, as_array=True)


REFERENCE_PACK_PARTIAL = [
    #              | 1st byte              | 2nd byte
    (b"\x00\x40", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),  # 15-bits
    (b"\x00\x20", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x10", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x08", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x04", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x02", [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
    (b"\x00\x01", [0, 0, 0, 0, 0, 0, 0, 0, 1]),  # 9-bits
    (b"\x80", [0, 0, 0, 0, 0, 0, 0, 1]),  # 8-bits
    (b"\x40", [0, 0, 0, 0, 0, 0, 1]),
    (b"\x20", [0, 0, 0, 0, 0, 1]),
    (b"\x10", [0, 0, 0, 0, 1]),
    (b"\x08", [0, 0, 0, 1]),
    (b"\x04", [0, 0, 1]),
    (b"\x02", [0, 1]),
    (b"\x01", [1]),
    (b"", []),
]


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestPackBits:
    """Tests for pack_bits()."""

    @pytest.mark.parametrize("output, input", REFERENCE_PACK_UNPACK)
    def test_pack(self, input, output):
        """Test packing data."""
        assert output == pack_bits(np.asarray(input), pad=False)

    def test_non_binary_input(self):
        """Test non-binary input raises exception."""
        with pytest.raises(
            ValueError, match=r"Only binary arrays \(containing ones or"
        ):
            pack_bits(np.asarray([0, 0, 2, 0, 0, 0, 0, 0]))

    def test_ndarray_input(self):
        """Test non 1D input gets ravelled."""
        arr = np.asarray(
            [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 1, 0, 1, 0, 1, 0],
                [1, 1, 1, 1, 1, 1, 1, 1],
            ]
        )
        assert (3, 8) == arr.shape
        b = pack_bits(arr, pad=False)
        assert b"\x00\x55\xff" == b

    def test_padding(self):
        """Test odd length packed data is padded."""
        arr = np.asarray(
            [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 1, 0, 1, 0, 1, 0],
                [1, 1, 1, 1, 1, 1, 1, 1],
            ]
        )
        assert 3 == len(pack_bits(arr, pad=False))
        b = pack_bits(arr, pad=True)
        assert 4 == len(b)
        assert 0 == b[-1]

    @pytest.mark.parametrize("output, input", REFERENCE_PACK_PARTIAL)
    def test_pack_partial(self, input, output):
        """Test packing data that isn't a full byte long."""
        assert output == pack_bits(np.asarray(input), pad=False)

    def test_functional(self):
        """Test against a real dataset."""
        ds = EXPL_1_1_3F.ds
        arr = ds.pixel_array
        arr = arr.ravel()
        assert ds.PixelData == pack_bits(arr)


@pytest.mark.skipif(not HAVE_NP, reason="Numpy is not available")
class TestExpandYBR422:
    """Tests for expand_ybr422()."""

    def test_8bit(self):
        """Test 8-bit expansion."""
        ds = EXPL_8_3_1F_YBR422.ds
        assert ds.PhotometricInterpretation == "YBR_FULL_422"
        ref = ds.pixel_array

        expanded = expand_ybr422(ds.PixelData, ds.BitsAllocated)
        arr = np.frombuffer(expanded, dtype="u1")
        assert np.array_equal(arr, ref.ravel())

    def test_16bit(self):
        """Test 16-bit expansion."""
        # Have to make our own 16-bit data
        ds = EXPL_8_3_1F_YBR422.ds
        ref = ds.pixel_array.astype("float32")
        ref *= 65535 / 255
        ref = ref.astype("u2")
        # Subsample
        # YY BB RR YY BB RR YY BB RR YY BB RR -> YY YY BB RR YY YY BB RR
        src = bytearray(ref.tobytes())
        del src[2::12]
        del src[2::11]
        del src[2::10]
        del src[2::9]

        # Should be 2/3rds of the original number of bytes
        nr_bytes = ds.Rows * ds.Columns * ds.SamplesPerPixel * 2
        assert len(src) == nr_bytes * 2 // 3
        arr = np.frombuffer(expand_ybr422(src, 16), "u2")
        assert np.array_equal(arr, ref.ravel())
        # Spot check values
        arr = arr.reshape(100, 100, 3)
        assert (19532, 21845, 65535) == tuple(arr[5, 50, :])
        assert (42662, 27242, 49601) == tuple(arr[15, 50, :])