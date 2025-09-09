.. _guide_encoder_plugin_opts:

==========================
Pixel Data Encoder Options
==========================

.. currentmodule:: pydicom.pixels.encoders.base

The following applies to the functions and class methods that use the
:doc:`pixels</reference/pixels>` backend for encoding pixel data.

* The :meth:`Dataset.compress<pydicom.dataset.Dataset.compress>` method.
* The :func:`~pydicom.pixels.compress` function.
* The :meth:`Encoder.encode()<pydicom.pixels.encoders.base.Encoder.encode>` and
  :meth:`Encoder.iter_encode()<pydicom.pixels.encoders.base.Encoder.iter_encode>`
  methods.

Encoding Options
================

The following option may be used with the *JPEG 2000 Lossless* and *JPEG-LS Lossless*
transfer syntaxes:

* `include_high_bits`: :class:`bool` - if ``True`` (default) then encode all bits of
  the pixel container, otherwise encode only the *Bits Stored* number of bits. For
  example, if the pixel container size is 16-bits (*Bits Allocated* 16) and the
  actual number of bits used per pixel is 12 (*Bits Stored* 12) then:

  * If ``True`` encode the data in all 16 bits
  * If ``False`` then only encode the data in the lower 12 bits, ignoring the other 4

  Historically the DICOM Standard allowed overlay data to be stored in any unused high
  bits, however this usage was retired in 2004. Because any data in the unused high
  bits will be lost if `include_high_bits` is ``False`` and there is typically little
  difference in the resulting size of the encoded pixel data between the two options
  (unless there actually is data in the unused bits), we recommend using the default.

  This option is not available with lossy transfer syntaxes as the presence of data in
  any unused high bits will affect image quality in the *Bits Stored* bits, so data in
  the high bits is ignored.

  *RLE Lossless* and *Deflated Image Frame Compression* will both always encode the
  entire pixel container, so if you want to remove data in any high bits this should
  be done manually prior to encoding (such as with NumPy's :func:`~numpy.left_shift`
  and :func:`~numpy.right shift` functions).


Encoding Plugin Options
=======================

.. currentmodule:: pydicom.pixels.encoders

The following options are plugin and transfer syntax specific.


.. _encoder_plugin_pydicom:

pydicom
-------

+--------------------------------------------+----------+--------+-------------+
| Encoder                                    | Options                         |
+                                            +----------+--------+-------------+
|                                            | Key      | Value  | Description |
+============================================+==========+========+=============+
|:attr:`RLELosslessEncoder`                  | (none available)                |
+--------------------------------------------+----------+--------+-------------+
|:attr:`DeflatedImageFrameCompressionEncoder`| (none available)                |
+--------------------------------------------+----------+--------+-------------+

.. _encoder_plugin_gdcm:

gdcm
----

+--------------------------+-----------------------------------------------------------------------------+
| Encoder                  | Options                                                                     |
+                          +-------------------------------+--------+------------------------------------+
|                          | Key                           | Value  | Description                        |
+==========================+===============================+========+====================================+
|:attr:`RLELosslessEncoder`| ``'rle_fix_gdcm_big_endian'`` | bool   | Enable corrections for GDCM on big |
|                          |                               |        | endian systems (default ``True``)  |
+--------------------------+-------------------------------+--------+------------------------------------+


.. _encoder_plugin_pylibjpeg:

pylibjpeg
---------

+--------------------------------+----------------------------+-------------+-------------------------------+
| Encoder                        | Options                                                                  |
+                                +----------------------------+-------------+-------------------------------+
|                                | Key                        | Value       | Description                   |
+================================+============================+=============+===============================+
|:attr:`JPEG2000LosslessEncoder` | ``'use_mct'``              | bool        | Enable MCT for RGB pixel data |
|                                |                            |             | (default ``True``)            |
+--------------------------------+----------------------------+-------------+-------------------------------+
|:attr:`JPEG2000Encoder`         | ``'use_mct'``              | bool        | Enable MCT for RGB pixel data |
|                                |                            |             | (default ``True``)            |
|                                +----------------------------+-------------+-------------------------------+
|                                | ``compression_ratios``     | list[float] | The compression ratio for     |
|                                |                            |             | each quality layer            |
|                                +----------------------------+-------------+-------------------------------+
|                                | ``signal_to_noise_ratios`` | list[float] | The peak signal-to-noise      |
|                                |                            |             | ratio for each quality layer  |
+--------------------------------+----------------------------+-------------+-------------------------------+
|:attr:`RLELosslessEncoder`      | ``'byteorder'``            | ``'<'``,    | The byte order of `src` may   |
|                                |                            | ``'>'``     | be little- or big-endian      |
+--------------------------------+----------------------------+-------------+-------------------------------+

.. _encoder_plugin_pyjpegls:

pyjpegls
--------

+---------------------------------+-----------------------+--------+-------------------------------------------------+
| Encoder                         | Options                                                                          |
+                                 +-----------------------+--------+-------------------------------------------------+
|                                 | Key                   | Value  | Description                                     |
+=================================+=======================+========+=================================================+
|:attr:`JPEGLSLosslessEncoder`    | ``'interleave_mode'`` | int    | The interleave mode used by the image data, 0   |
|                                 |                       |        | for color-by-plane, 2 for color-by-pixel        |
+---------------------------------+-----------------------+--------+-------------------------------------------------+
|:attr:`JPEGLSNearLosslessEncoder`| ``'lossy_error'``     | int    | The absolute error in pixel intensity units     |
|                                 +-----------------------+--------+-------------------------------------------------+
|                                 | ``'interleave_mode'`` | int    | The interleave mode used by the image data, 0   |
|                                 |                       |        | for color-by-plane, 2 for color-by-pixel        |
+---------------------------------+-----------------------+--------+-------------------------------------------------+
