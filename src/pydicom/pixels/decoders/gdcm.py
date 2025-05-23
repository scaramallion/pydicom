# Copyright 2024 pydicom authors. See LICENSE file for details.
"""Use GDCM <https://github.com/malaterre/GDCM> to decompress encoded
*Pixel Data*.

This module is not intended to be used directly.
"""

from typing import cast

from pydicom import uid
from pydicom.pixels.decoders.base import DecodeRunner
from pydicom.pixels.common import PhotometricInterpretation as PI

try:
    import gdcm

    GDCM_VERSION = tuple(int(x) for x in gdcm.Version.GetVersion().split("."))
    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False


DECODER_DEPENDENCIES = {
    uid.JPEGBaseline8Bit: ("gdcm>=3.0.10",),
    uid.JPEGExtended12Bit: ("gdcm>=3.0.10",),
    uid.JPEGLossless: ("gdcm>=3.0.10",),
    uid.JPEGLosslessSV1: ("gdcm>=3.0.10",),
    uid.JPEGLSLossless: ("gdcm>=3.0.10",),
    uid.JPEGLSNearLossless: ("gdcm>=3.0.10",),
    uid.JPEG2000Lossless: ("gdcm>=3.0.10",),
    uid.JPEG2000: ("gdcm>=3.0.10",),
}

# Due to SWIG issues, it appears that GDCM cannot return more than (typically)
#   2**31 - 1 bytes when using gdcm.Image.GetBuffer(). Note that this may actually
#   be as low as 2**15 - 1 bytes depending on the system architecture.
# Because of this we cannot guarantee that GDCM will succeed as a single frame of
#   data may be larger. However in most cases only multi-frame data that will
#   exceed that limit.
_GDCM_MAX_BUFFER_SIZE = 2**31 - 1


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_GDCM or GDCM_VERSION < (3, 0):
        return False

    return uid in DECODER_DEPENDENCIES


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytes:
    """Return the decoded `src` as :class:`bytes`.

    Parameters
    ----------
    src : bytes
        An encoded pixel data frame.
    runner : pydicom.pixels.decoders.base.DecodeRunner
        The runner managing the decoding.

    Returns
    -------
    bytes
        The decoded pixel data frame.
    """
    tsyntax = runner.transfer_syntax
    photometric_interpretation = runner.photometric_interpretation
    bits_stored = runner.bits_stored
    if tsyntax == uid.JPEGExtended12Bit and bits_stored != 8:
        raise NotImplementedError(
            "GDCM does not support 'JPEG Extended' for samples with 12-bit precision"
        )

    if (
        tsyntax == uid.JPEGLSNearLossless
        and runner.pixel_representation == 1
        and bits_stored < 8
    ):
        raise ValueError(
            "Unable to decode signed lossy JPEG-LS pixel data with a sample "
            "precision less than 8 bits"
        )

    if tsyntax in uid.JPEGLSTransferSyntaxes and bits_stored in (6, 7):
        raise ValueError(
            "Unable to decode unsigned JPEG-LS pixel data with a sample "
            "precision of 6 or 7 bits"
        )

    if runner.frame_length() > _GDCM_MAX_BUFFER_SIZE:
        raise ValueError(
            "GDCM cannot decode the pixel data as each frame will be larger than "
            "GDCM's maximum buffer size"
        )

    fragment = gdcm.Fragment()
    fragment.SetByteStringValue(src)

    fragments = gdcm.SequenceOfFragments.New()
    fragments.AddFragment(fragment)

    elem = gdcm.DataElement(gdcm.Tag(0x7FE0, 0x0010))
    elem.SetValue(fragments.GetPointer())

    img = gdcm.Image()
    img.SetNumberOfDimensions(2)
    img.SetDimensions((runner.columns, runner.rows, 1))
    img.SetDataElement(elem)

    pi_type = gdcm.PhotometricInterpretation.GetPIType(photometric_interpretation)
    img.SetPhotometricInterpretation(gdcm.PhotometricInterpretation(pi_type))
    if runner.samples_per_pixel > 1:
        img.SetPlanarConfiguration(runner.planar_configuration)

    ts_type = gdcm.TransferSyntax.GetTSType(str.__str__(tsyntax))
    img.SetTransferSyntax(gdcm.TransferSyntax(ts_type))

    if tsyntax in uid.JPEGLSTransferSyntaxes:
        # GDCM always returns JPEG-LS data as color-by-pixel
        runner.set_option("planar_configuration", 0)
        bits_stored = runner.get_option("jls_precision", bits_stored)
        if 0 < bits_stored <= 8:
            runner.set_option("bits_allocated", 8)
        elif 8 < bits_stored <= 16:
            runner.set_option("bits_allocated", 16)

    if tsyntax in uid.JPEG2000TransferSyntaxes:
        # GDCM pixel container size is based on precision
        bits_stored = runner.get_option("j2k_precision", bits_stored)
        if 0 < bits_stored <= 8:
            runner.set_option("bits_allocated", 8)
        elif 8 < bits_stored <= 16:
            runner.set_option("bits_allocated", 16)
        elif 16 < bits_stored <= 32:
            runner.set_option("bits_allocated", 32)

    pixel_format = gdcm.PixelFormat(
        runner.samples_per_pixel,
        runner.bits_allocated,
        bits_stored,
        bits_stored - 1,
        runner.pixel_representation,
    )
    img.SetPixelFormat(pixel_format)

    # GDCM returns char* as str, so re-encode it to bytes
    # On architectures where the C++ `int` type is 16-bit this may raise an exception
    #   if the decoded pixel data is more than 2**15 - 1 bytes:
    #       AttributeError: 'SwigPyObject' object has no attribute 'encode'
    frame = cast(bytes, img.GetBuffer().encode("utf-8", "surrogateescape"))

    # On big endian systems GDCM returns decoded data as big endian :(
    if runner._test_for("gdcm_be_system"):
        b = bytearray(frame)
        if runner.bits_allocated == 16:
            b[::2], b[1::2] = b[1::2], b[::2]
        elif runner.bits_allocated == 32:
            b[::4], b[1::4], b[2::4], b[3::4] = b[3::4], b[2::4], b[1::4], b[::4]

        frame = bytes(b)

    # GDCM returns YBR_ICT and YBR_RCT as RGB
    if tsyntax in uid.JPEG2000TransferSyntaxes and photometric_interpretation in (
        PI.YBR_ICT,
        PI.YBR_RCT,
    ):
        runner.set_option("photometric_interpretation", PI.RGB)

    return frame
