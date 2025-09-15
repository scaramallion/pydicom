# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Interface for *Pixel Data* encoding, not intended to be used directly."""

from typing import cast

from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.pixels.common import PhotometricInterpretation as PI
from pydicom.pixels.utils import _passes_version_check, unpack_bits
from pydicom import uid

try:
    from pylibjpeg.utils import get_pixel_data_encoders, Encoder

    _ENCODERS = get_pixel_data_encoders()
except ImportError:
    _ENCODERS = {}


ENCODER_DEPENDENCIES = {
    uid.JPEG2000Lossless: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.5"),
    uid.JPEG2000: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.5"),
    uid.RLELossless: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-rle>=2.2"),
}
_OPENJPEG_SYNTAXES = [uid.JPEG2000Lossless, uid.JPEG2000]
_RLE_SYNTAXES = [uid.RLELossless]


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not _passes_version_check("pylibjpeg", (2, 0)):
        return False

    if uid in _OPENJPEG_SYNTAXES:
        return _passes_version_check("openjpeg", (2, 5))

    if uid in _RLE_SYNTAXES:
        return _passes_version_check("rle", (2, 2))

    return False


def _encode_frame(src: bytes, runner: EncodeRunner) -> bytes | bytearray:
    """Return `src` as an encoded codestream."""
    runner.set_frame_option(runner.index, "encoding_plugin", "pylibjpeg")

    # RLE Lossless: always include unused high bits
    # JPEG 2000 Lossless: may or may not include unused high bits
    # JPEG 2000: never include unused high bits
    opts = dict(runner.options)
    # opts["bits_stored"] = runner.get_frame_option(runner.index, "precision")

    tsyntax = runner.transfer_syntax
    encoder = cast(Encoder, _ENCODERS[tsyntax])

    if runner.get_frame_option(runner.index, "bits_allocated", 8) == 1:
        pixels_per_frame = runner.rows * runner.columns * runner.samples_per_pixel
        src = cast(bytes, unpack_bits(src, as_array=False)[:pixels_per_frame])
        runner.set_frame_option(runner.index, "bits_allocated", 8)

    bits_allocated = runner.get_frame_option(runner.index, "bits_allocated")

    if tsyntax == uid.RLELossless:
        # RLE Lossless: always include all bits of the pixel cell
        opts["bits_stored"] = bits_allocated
        return cast(bytes, encoder(src, **opts))

    if runner.photometric_interpretation == PI.RGB:
        opts["use_mct"] = False

    cr = opts.pop("compression_ratios", opts.get("j2k_cr", None))
    psnr = opts.pop("signal_noise_ratios", opts.get("j2k_psnr", None))

    # JPEG 2000 Lossless: may or may not include all bits of the pixel cell
    if tsyntax == uid.JPEG2000Lossless:
        if cr or psnr:
            raise ValueError(
                "A lossy configuration option is being used with a transfer "
                "syntax of 'JPEG 2000 Lossless' - did you mean to use 'JPEG "
                "2000' instead?"
            )

        # pylibjpeg-openjpeg is unable to encode more than 24 bits
        if runner.get_option("include_high_bits", True):
            if bits_allocated > 24 and runner.bits_stored <= 24:
                raise ValueError(
                    "Unable to encode data that uses more than 24-bits per pixel, pass "
                    "'include_high_bits=False' to encode only the (0028,0101) 'Bits Stored' "
                    f"number of bits ({runner.bits_stored})"
                )

            opts["bits_stored"] = bits_allocated

        return cast(bytes, encoder(src, **opts))

    # JPEG 2000: never include unused high bits in the pixel cell
    if not cr and not psnr:
        raise ValueError(
            "The 'JPEG 2000' transfer syntax requires a lossy configuration "
            "option such as 'j2k_cr' or 'j2k_psnr'"
        )

    if cr and psnr:
        raise ValueError(
            "Multiple lossy configuration options are being used with the "
            "'JPEG 2000' transfer syntax, please specify only one"
        )

    cs = encoder(src, **opts, compression_ratios=cr, signal_noise_ratios=psnr)

    return cast(bytes, cs)
