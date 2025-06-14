# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for the GDCM Pixel Data handler."""

from io import BytesIO
import os
import sys
import tempfile
import shutil

import pytest

try:
    import numpy

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

import pydicom
from pydicom.filereader import dcmread
from pydicom.data import get_testdata_file
from pydicom.encaps import get_frame, encapsulate
from pydicom.pixel_data_handlers import numpy_handler, gdcm_handler
from pydicom.pixels.processing import _convert_YBR_FULL_to_RGB
from pydicom.pixels.utils import get_j2k_parameters, reshape_pixel_array
from pydicom.tag import Tag

try:
    import gdcm

    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False

from .pixels.pixels_reference import (
    J2KR_16_10_1_0_1F_M1,
    JPGB_08_08_3_0_1F_RGB,
    RLE_32_1_1F,
)

# HAVE_GDCM_IN_MEMORY_SUPPORT = gdcm_handler.HAVE_GDCM_IN_MEMORY_SUPPORT
TEST_BIG_ENDIAN = sys.byteorder == "little" and HAVE_NP and HAVE_GDCM


gdcm_present_message = "GDCM is being tested"
gdcm_missing_message = "GDCM is not available in this test environment"
gdcm_im_missing_message = (
    "GDCM is not available or in-memory decoding "
    "not supported with this GDCM version"
)


empty_number_tags_name = get_testdata_file("reportsi_with_empty_number_tags.dcm")
rtplan_name = get_testdata_file("rtplan.dcm")
rtdose_name = get_testdata_file("rtdose.dcm")
ct_name = get_testdata_file("CT_small.dcm")
mr_name = get_testdata_file("MR_small.dcm")
truncated_mr_name = get_testdata_file("MR_truncated.dcm")
jpeg2000_name = get_testdata_file("JPEG2000.dcm")
jpeg2000_lossless_name = get_testdata_file("MR_small_jp2klossless.dcm")
jpeg_ls_lossless_name = get_testdata_file("MR_small_jpeg_ls_lossless.dcm")
jpeg_lossy_name = get_testdata_file("JPEG-lossy.dcm")
jpeg_lossless_name = get_testdata_file("JPEG-LL.dcm")
jpeg_lossless_odd_data_size_name = get_testdata_file("SC_rgb_small_odd_jpeg.dcm")
deflate_name = get_testdata_file("image_dfl.dcm")
rtstruct_name = get_testdata_file("rtstruct.dcm")
priv_SQ_name = get_testdata_file("priv_SQ.dcm")
nested_priv_SQ_name = get_testdata_file("nested_priv_SQ.dcm")
meta_missing_tsyntax_name = get_testdata_file("meta_missing_tsyntax.dcm")
no_meta_group_length = get_testdata_file("no_meta_group_length.dcm")
gzip_name = get_testdata_file("zipMR.gz")
color_px_name = get_testdata_file("color-px.dcm")
color_pl_name = get_testdata_file("color-pl.dcm")
explicit_vr_le_no_meta = get_testdata_file("ExplVR_LitEndNoMeta.dcm")
explicit_vr_be_no_meta = get_testdata_file("ExplVR_BigEndNoMeta.dcm")
emri_name = get_testdata_file("emri_small.dcm")
emri_big_endian_name = get_testdata_file("emri_small_big_endian.dcm")
emri_jpeg_ls_lossless = get_testdata_file("emri_small_jpeg_ls_lossless.dcm")
emri_jpeg_2k_lossless = get_testdata_file("emri_small_jpeg_2k_lossless.dcm")
color_3d_jpeg_baseline = get_testdata_file("color3d_jpeg_baseline.dcm")
sc_rgb_jpeg_dcmtk_411_YBR_FULL_422 = get_testdata_file("SC_rgb_dcmtk_+eb+cy+np.dcm")
sc_rgb_jpeg_dcmtk_411_YBR_FULL = get_testdata_file("SC_rgb_dcmtk_+eb+cy+n1.dcm")
sc_rgb_jpeg_dcmtk_422_YBR_FULL = get_testdata_file("SC_rgb_dcmtk_+eb+cy+n2.dcm")
sc_rgb_jpeg_dcmtk_444_YBR_FULL = get_testdata_file("SC_rgb_dcmtk_+eb+cy+s4.dcm")
sc_rgb_jpeg_dcmtk_422_YBR_FULL_422 = get_testdata_file("SC_rgb_dcmtk_+eb+cy+s2.dcm")
sc_rgb_jpeg_dcmtk_RGB = get_testdata_file("SC_rgb_dcmtk_+eb+cr.dcm")
sc_rgb_jpeg2k_gdcm_KY = get_testdata_file("SC_rgb_gdcm_KY.dcm")
ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm = get_testdata_file(
    "SC_rgb_gdcm2k_uncompressed.dcm"
)
J2KR_16_13_1_1_1F_M2_MISMATCH = get_testdata_file("J2K_pixelrep_mismatch.dcm")

dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class TestGDCM_JPEG_LS_no_gdcm:
    def setup_method(self):
        self.jpeg_ls_lossless = dcmread(jpeg_ls_lossless_name)
        self.jpeg_ls_lossless.pixel_array_options(use_v2_backend=True)

        self.emri_jpeg_ls_lossless = dcmread(emri_jpeg_ls_lossless)
        self.emri_jpeg_ls_lossless.pixel_array_options(use_v2_backend=True)

        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG_LS_PixelArray(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_ls_lossless.pixel_array

    def test_emri_JPEG_LS_PixelArray(self):
        with pytest.raises(NotImplementedError):
            self.emri_jpeg_ls_lossless.pixel_array


class TestGDCM_JPEG2000_no_gdcm:
    def setup_method(self):
        self.jpeg_2k = dcmread(jpeg2000_name)

        self.jpeg_2k_lossless = dcmread(jpeg2000_lossless_name)
        self.jpeg_2k_lossless.pixel_array_options(use_v2_backend=True)

        self.emri_jpeg_2k_lossless = dcmread(emri_jpeg_2k_lossless)
        self.emri_jpeg_2k_lossless.pixel_array_options(use_v2_backend=True)

        self.sc_rgb_jpeg2k_gdcm_KY = dcmread(sc_rgb_jpeg2k_gdcm_KY)
        self.sc_rgb_jpeg2k_gdcm_KY.pixel_array_options(use_v2_backend=True)

        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements"""
        # XX also tests multiple-valued AT data element
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)]
        got = self.jpeg_2k.FrameIncrementPointer
        assert expected == got

        got = self.jpeg_2k.DerivationCodeSequence[0].CodeMeaning
        expected = "Lossy Compression"
        assert expected == got

    def test_JPEG2000_pixel_array(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_2k_lossless.pixel_array

    def test_emri_JPEG2000_pixel_array(self):
        with pytest.raises(NotImplementedError):
            self.emri_jpeg_2k_lossless.pixel_array

    def test_jpeg2000_lossy(self):
        with pytest.raises(NotImplementedError):
            self.sc_rgb_jpeg2k_gdcm_KY.pixel_array


class TestGDCM_JPEGlossy_no_gdcm:
    def setup_method(self):
        self.jpeg_lossy = dcmread(jpeg_lossy_name)
        self.jpeg_lossy.pixel_array_options(use_v2_backend=True)

        self.color_3d_jpeg = dcmread(color_3d_jpeg_baseline)
        self.color_3d_jpeg.pixel_array_options(use_v2_backend=True)

        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def test_JPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = self.jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        expected = "Lossy Compression"
        assert expected == got

    def test_JPEGlossy_pixel_array(self):
        with pytest.raises(NotImplementedError):
            self.jpeg_lossy.pixel_array

    def test_JPEGBaseline_color_3D_pixel_array(self):
        with pytest.raises(NotImplementedError):
            self.color_3d_jpeg.pixel_array


class TestGDCM_JPEGlossless_no_gdcm:
    def setup_method(self):
        self.jpeg_lossless = dcmread(jpeg_lossless_name)
        self.jpeg_lossless.pixel_array_options(use_v2_backend=True)

        self.original_handlers = pydicom.config.pixel_data_handlers
        pydicom.config.pixel_data_handlers = []

    def teardown_method(self):
        pydicom.config.pixel_data_handlers = self.original_handlers

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements"""
        got = (
            self.jpeg_lossless.SourceImageSequence[0]
            .PurposeOfReferenceCodeSequence[0]
            .CodeMeaning
        )
        expected = "Uncompressed predecessor"
        assert expected == got

    def testJPEGlossless_pixel_array(self):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        with pytest.raises(NotImplementedError):
            self.jpeg_lossless.pixel_array


pi_rgb_test_ids = [
    "JPEG_RGB_411_AS_YBR_FULL",
    "JPEG_RGB_411_AS_YBR_FULL_422",
    "JPEG_RGB_422_AS_YBR_FULL",
    "JPEG_RGB_422_AS_YBR_FULL_422",
    "JPEG_RGB_444_AS_YBR_FULL",
]

pi_rgb_testdata = [
    pytest.param(
        sc_rgb_jpeg_dcmtk_411_YBR_FULL,
        "YBR_FULL",
        [
            (253, 1, 0),
            (253, 128, 132),
            (0, 255, 5),
            (127, 255, 127),
            (1, 0, 254),
            (127, 128, 255),
            (0, 0, 0),
            (64, 64, 64),
            (192, 192, 192),
            (255, 255, 255),
        ],
        True,
    ),
    pytest.param(
        sc_rgb_jpeg_dcmtk_411_YBR_FULL_422,
        "YBR_FULL_422",
        [
            (253, 1, 0),
            (253, 128, 132),
            (0, 255, 5),
            (127, 255, 127),
            (1, 0, 254),
            (127, 128, 255),
            (0, 0, 0),
            (64, 64, 64),
            (192, 192, 192),
            (255, 255, 255),
        ],
        True,
    ),
    pytest.param(
        sc_rgb_jpeg_dcmtk_422_YBR_FULL,
        "YBR_FULL",
        [
            (254, 0, 0),
            (255, 127, 127),
            (0, 255, 5),
            (129, 255, 129),
            (0, 0, 254),
            (128, 127, 255),
            (0, 0, 0),
            (64, 64, 64),
            (192, 192, 192),
            (255, 255, 255),
        ],
        True,
    ),
    pytest.param(
        sc_rgb_jpeg_dcmtk_422_YBR_FULL_422,
        "YBR_FULL_422",
        [
            (254, 0, 0),
            (255, 127, 127),
            (0, 255, 5),
            (129, 255, 129),
            (0, 0, 254),
            (128, 127, 255),
            (0, 0, 0),
            (64, 64, 64),
            (192, 192, 192),
            (255, 255, 255),
        ],
        True,
    ),
    pytest.param(
        sc_rgb_jpeg_dcmtk_444_YBR_FULL,
        "YBR_FULL",
        [
            (254, 0, 0),
            (255, 127, 127),
            (0, 255, 5),
            (129, 255, 129),
            (0, 0, 254),
            (128, 127, 255),
            (0, 0, 0),
            (64, 64, 64),
            (192, 192, 192),
            (255, 255, 255),
        ],
        True,
    ),
]


@pytest.fixture()
def set_gdcm_max_buffer_size_10k():
    original = gdcm_handler._GDCM_MAX_BUFFER_SIZE
    gdcm_handler._GDCM_MAX_BUFFER_SIZE = 10000
    yield

    gdcm_handler._GDCM_MAX_BUFFER_SIZE = original


@pytest.fixture()
def set_gdcm_max_buffer_size_25k():
    original = gdcm_handler._GDCM_MAX_BUFFER_SIZE
    gdcm_handler._GDCM_MAX_BUFFER_SIZE = 25000
    yield

    gdcm_handler._GDCM_MAX_BUFFER_SIZE = original


@pytest.mark.skipif(not HAVE_GDCM, reason="GDCM not available")
class TestsWithGDCM:
    @pytest.fixture(scope="class")
    def unicode_filename(self):
        unicode_filename = os.path.join(tempfile.gettempdir(), "ДИКОМ.dcm")
        shutil.copyfile(jpeg_ls_lossless_name, unicode_filename)
        yield unicode_filename
        os.remove(unicode_filename)

    @pytest.fixture
    def jpeg_ls_lossless(self, unicode_filename):
        return dcmread(unicode_filename)

    @pytest.fixture
    def sc_rgb_jpeg2k_gdcm_KY(self):
        return dcmread(sc_rgb_jpeg2k_gdcm_KY)

    @pytest.fixture(scope="class")
    def ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm(self):
        return dcmread(ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm)

    @pytest.fixture
    def jpeg_2k(self):
        ds = dcmread(jpeg2000_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def jpeg_2k_lossless(self):
        ds = dcmread(jpeg2000_lossless_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture(scope="class")
    def mr_small(self):
        ds = dcmread(mr_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture(scope="class")
    def emri_small(self):
        ds = dcmread(emri_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def emri_jpeg_ls_lossless(self):
        ds = dcmread(emri_jpeg_ls_lossless)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def emri_jpeg_2k_lossless(self):
        ds = dcmread(emri_jpeg_2k_lossless)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def color_3d_jpeg(self):
        ds = dcmread(color_3d_jpeg_baseline)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def jpeg_lossy(self):
        ds = dcmread(jpeg_lossy_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def jpeg_lossless(self):
        ds = dcmread(jpeg_lossless_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    @pytest.fixture
    def jpeg_lossless_odd_data_size(self):
        ds = dcmread(jpeg_lossless_odd_data_size_name)
        ds.pixel_array_options(use_v2_backend=True)
        return ds

    def test_JPEG_LS_PixelArray(self, jpeg_ls_lossless, mr_small):
        a = jpeg_ls_lossless.pixel_array
        b = mr_small.pixel_array
        assert a.mean() == b.mean()
        assert a.flags.writeable

    def test_emri_JPEG_LS_PixelArray_with_gdcm(self, emri_jpeg_ls_lossless, emri_small):
        a = emri_jpeg_ls_lossless.pixel_array
        b = emri_small.pixel_array
        assert a.mean() == b.mean()
        assert a.flags.writeable

    def test_JPEG2000(self, jpeg_2k):
        """JPEG2000: Returns correct values for sample data elements"""
        # XX also tests multiple-valued AT data element
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)]
        got = jpeg_2k.FrameIncrementPointer
        assert expected == got

        got = jpeg_2k.DerivationCodeSequence[0].CodeMeaning
        assert "Lossy Compression" == got

    def test_JPEG2000PixelArray(self, jpeg_2k_lossless, mr_small):
        a = jpeg_2k_lossless.pixel_array
        b = mr_small.pixel_array
        assert a.mean() == b.mean()
        assert a.flags.writeable

    def test_decompress_using_gdcm(self, jpeg_2k_lossless, mr_small):
        jpeg_2k_lossless.decompress(handler_name="gdcm")
        a = jpeg_2k_lossless.pixel_array
        b = mr_small.pixel_array
        assert a.mean() == b.mean()

    def test_emri_JPEG2000PixelArray(self, emri_jpeg_2k_lossless, emri_small):
        a = emri_jpeg_2k_lossless.pixel_array
        b = emri_small.pixel_array
        assert a.mean() == b.mean()
        assert a.flags.writeable

    def test_JPEG2000_lossy(
        self, sc_rgb_jpeg2k_gdcm_KY, ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm
    ):
        a = sc_rgb_jpeg2k_gdcm_KY.pixel_array
        b = ground_truth_sc_rgb_jpeg2k_gdcm_KY_gdcm.pixel_array
        if HAVE_NP:
            assert numpy.array_equal(a, b)
        else:
            assert a.mean() == b.mean()

        assert a.flags.writeable

    def test_JPEGlosslessPixelArray(self, jpeg_lossless):
        """JPEGlossless: Fails gracefully when uncompressed data asked for"""
        a = jpeg_lossless.pixel_array
        assert (1024, 256) == a.shape
        # this test points were manually identified in Osirix viewer
        assert 227 == a[420, 140]
        assert 105 == a[230, 120]
        assert a.flags.writeable

    def test_JPEGlossless_odd_data_size(self, jpeg_lossless_odd_data_size):
        pixel_data = jpeg_lossless_odd_data_size.pixel_array
        assert 27 == pixel_data.nbytes
        assert (3, 3, 3) == pixel_data.shape

    def test_JPEGlossy(self, jpeg_lossy):
        """JPEG-lossy: Returns correct values for sample data elements"""
        got = jpeg_lossy.DerivationCodeSequence[0].CodeMeaning
        assert "Lossy Compression" == got

    def test_JPEGlossyPixelArray(self, jpeg_lossy):
        a = jpeg_lossy.pixel_array
        assert (1024, 256) == a.shape
        # this test points were manually identified in Osirix viewer
        assert 244 == a[420, 140]
        assert 95 == a[230, 120]
        assert a.flags.writeable

    def test_JPEGBaselineColor3DPixelArray(self, color_3d_jpeg):
        assert "YBR_FULL_422" == color_3d_jpeg.PhotometricInterpretation
        a = color_3d_jpeg.pixel_array

        assert a.flags.writeable
        assert (120, 480, 640, 3) == a.shape
        a = _convert_YBR_FULL_to_RGB(a, bit_depth=8)
        # this test points were manually identified in Osirix viewer
        assert (41, 41, 41) == tuple(a[3, 159, 290, :])
        assert (57, 57, 57) == tuple(a[3, 169, 290, :])
        assert "YBR_FULL_422" == color_3d_jpeg.PhotometricInterpretation

    @pytest.mark.parametrize(
        "image,pi,results,convert_yuv_to_rgb", pi_rgb_testdata, ids=pi_rgb_test_ids
    )
    def test_PI_RGB(self, image, pi, results, convert_yuv_to_rgb):
        t = dcmread(image)
        assert t.PhotometricInterpretation == pi
        t.pixel_array_options(use_v2_backend=True)
        a = t.pixel_array

        assert a.flags.writeable

        assert (100, 100, 3) == a.shape
        if convert_yuv_to_rgb:
            a = _convert_YBR_FULL_to_RGB(a, bit_depth=8)
        # this test points are from the ImageComments tag
        assert results[0] == tuple(a[5, 50, :])
        assert results[1] == tuple(a[15, 50, :])
        assert results[2] == tuple(a[25, 50, :])
        assert results[3] == tuple(a[35, 50, :])
        assert results[4] == tuple(a[45, 50, :])
        assert results[5] == tuple(a[55, 50, :])
        assert results[6] == tuple(a[65, 50, :])
        assert results[7] == tuple(a[75, 50, :])
        assert results[8] == tuple(a[85, 50, :])
        assert results[9] == tuple(a[95, 50, :])
        assert pi == t.PhotometricInterpretation

    def test_bytes_io(self):
        """Test using a BytesIO as the dataset source."""
        with open(jpeg2000_name, "rb") as f:
            bs = BytesIO(f.read())

        ds = dcmread(bs)
        ds.pixel_array_options(use_v2_backend=True)
        arr = ds.pixel_array
        assert (1024, 256) == arr.shape
        assert arr.flags.writeable

    def test_pixel_rep_mismatch(self):
        """Test mismatched j2k sign and Pixel Representation."""
        ds = dcmread(J2KR_16_13_1_1_1F_M2_MISMATCH)
        ds.pixel_array_options(use_v2_backend=True)
        assert 1 == ds.PixelRepresentation
        assert 13 == ds.BitsStored

        bs = get_frame(ds.PixelData, 0)
        params = get_j2k_parameters(bs)
        assert 13 == params["precision"]
        assert not params["is_signed"]
        arr = ds.pixel_array
        assert 1 == ds.PixelRepresentation

        assert "<i2" == arr.dtype
        assert (512, 512) == arr.shape
        assert arr.flags.writeable

        assert -2000 == arr[0, 0]
        assert [621, 412, 138, -193, -520, -767, -907, -966, -988, -995] == (
            arr[47:57, 279].tolist()
        )
        assert [-377, -121, 141, 383, 633, 910, 1198, 1455, 1638, 1732] == (
            arr[328:338, 106].tolist()
        )

    def test_too_large_raises(self, set_gdcm_max_buffer_size_10k):
        """Test exception raised if the frame is too large for GDCM to decode."""
        # Single frame is 8192 bytes with 64 x 64 x 2
        ds = dcmread(jpeg2000_lossless_name)
        ds.Rows = 100
        ds.pixel_array_options(use_v2_backend=True, decoding_plugin="gdcm")
        msg = (
            "GDCM cannot decode the pixel data as each frame will be larger than "
            "GDCM's maximum buffer size"
        )
        with pytest.raises(ValueError, match=msg):
            ds.pixel_array

    def test_multi_frame_too_large_single_frame(self, set_gdcm_max_buffer_size_10k):
        """Test decoding a multi-frame image where the total pixel data is too large
        for GDCM to decode but each individual frame is just small enough to decode
        separately.
        """
        # Single frame is 8192 bytes with 64 x 64 x 2
        ds = dcmread(jpeg2000_lossless_name)
        ds.NumberOfFrames = 2
        frame = get_frame(ds.PixelData, 0, number_of_frames=1)
        ds.PixelData = encapsulate([frame, frame])
        ds.pixel_array_options(use_v2_backend=True, decoding_plugin="gdcm")
        arr = ds.pixel_array

        assert arr.shape == (2, 64, 64)
        assert numpy.array_equal(arr[0], arr[1])

    def test_multi_frame_too_large_multi_frame(self, set_gdcm_max_buffer_size_25k):
        """Test decoding a multi-frame image where the total pixel data is too large
        for GDCM to decode but multiple individual frames are small enough that many
        frames can be decoded in one go.
        """
        ds = dcmread(jpeg2000_lossless_name)
        # 11 frames will be decoded as (3, 3, 3, 2)
        ds.NumberOfFrames = 11
        frame = get_frame(ds.PixelData, 0, number_of_frames=1)
        ds.PixelData = encapsulate([frame] * 11)
        ds.pixel_array_options(use_v2_backend=True, decoding_plugin="gdcm")
        arr = ds.pixel_array

        assert arr.shape == (11, 64, 64)
        for idx in range(11):
            assert numpy.array_equal(arr[idx], arr[1])


@pytest.mark.skipif(not HAVE_GDCM, reason="GDCM not available")
class TestSupportFunctions:
    @pytest.fixture(scope="class")
    def dataset_2d(self):
        return dcmread(mr_name)

    @pytest.fixture(scope="class")
    def dataset_2d_compressed(self):
        return dcmread(jpeg2000_name)

    @pytest.fixture(scope="class")
    def dataset_3d(self):
        return dcmread(color_3d_jpeg_baseline)

    def test_create_data_element_from_compressed_2d_dataset(
        self, dataset_2d_compressed
    ):
        data_element = gdcm_handler.create_data_element(dataset_2d_compressed)

        assert 0x7FE0 == data_element.GetTag().GetGroup()
        assert 0x0010 == data_element.GetTag().GetElement()
        assert data_element.GetSequenceOfFragments() is not None
        assert data_element.GetByteValue() is None

    def test_create_data_element_from_3d_dataset(self, dataset_3d):
        data_element = gdcm_handler.create_data_element(dataset_3d)

        assert 0x7FE0 == data_element.GetTag().GetGroup()
        assert 0x0010 == data_element.GetTag().GetElement()
        assert data_element.GetSequenceOfFragments() is not None
        assert data_element.GetByteValue() is None

    def test_create_image_from_3d_dataset(self, dataset_3d):
        image = gdcm_handler.create_image(dataset_3d)
        assert 3 == image.GetNumberOfDimensions()
        assert [
            dataset_3d.Columns,
            dataset_3d.Rows,
            int(dataset_3d.NumberOfFrames),
        ] == image.GetDimensions()
        pi = gdcm.PhotometricInterpretation.GetPIType(
            dataset_3d.PhotometricInterpretation
        )
        assert pi == image.GetPhotometricInterpretation().GetType()
        uid = str.__str__(dataset_3d.file_meta.TransferSyntaxUID)
        assert uid == image.GetTransferSyntax().GetString()
        pixel_format = image.GetPixelFormat()
        assert dataset_3d.SamplesPerPixel == pixel_format.GetSamplesPerPixel()
        assert dataset_3d.BitsAllocated == pixel_format.GetBitsAllocated()
        assert dataset_3d.BitsStored == pixel_format.GetBitsStored()
        assert dataset_3d.HighBit == pixel_format.GetHighBit()
        px_repr = dataset_3d.PixelRepresentation
        assert px_repr == pixel_format.GetPixelRepresentation()
        planar = dataset_3d.PlanarConfiguration
        assert planar == image.GetPlanarConfiguration()


@pytest.fixture()
def enable_be_testing():
    def foo(*args, **kwargs):
        return True

    original_fn = gdcm_handler._is_big_endian_system
    gdcm_handler._is_big_endian_system = foo
    yield

    gdcm_handler._is_big_endian_system = original_fn


@pytest.mark.skipif(not TEST_BIG_ENDIAN, reason="Running on BE system")
class TestEndiannessConversion:
    """Test conversion for big endian systems with GDCM"""

    # Ideally we would just run the regular tests on a big endian systems, but
    #   instead we have specific tests that run on little endian and force the
    #   system endianness conversion code to run
    def test_endianness_conversion_08(self, enable_be_testing):
        """Test no endianness change for 8-bit."""
        ref = JPGB_08_08_3_0_1F_RGB
        ds = ref.ds

        assert 8 == ds.BitsAllocated
        assert 3 == ds.SamplesPerPixel

        arr = gdcm_handler.get_pixeldata(ds)
        arr = reshape_pixel_array(ds, arr)

        ref.test(arr, plugin="gdcm")

    def test_endianness_conversion_16(self, enable_be_testing):
        """Test that the endianness is changed when required."""
        # 16-bit: byte swapping required
        ref = J2KR_16_10_1_0_1F_M1
        ds = ref.ds
        assert 16 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel
        assert 0 == ds.PixelRepresentation

        arr = gdcm_handler.get_pixeldata(ds)
        arr = reshape_pixel_array(ds, arr)
        ref.test(arr.view(">u2"), plugin="gdcm")

    def test_endianness_conversion_32(self, enable_be_testing):
        """Test that the endianness is changed when required."""
        # 32-bit: byte swapping required
        ref = RLE_32_1_1F
        ds = ref.ds
        assert 32 == ds.BitsAllocated
        assert 1 == ds.SamplesPerPixel
        assert 0 == ds.PixelRepresentation

        def foo(*args, **kwargs):
            return True

        arr = gdcm_handler.get_pixeldata(ds)
        arr = reshape_pixel_array(ds, arr)
        ref.test(arr.view(">u4"), plugin="gdcm")
