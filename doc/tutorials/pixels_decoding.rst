===================================
Decoding and visualizing Pixel Data
===================================

This tutorial is about decoding and visualizing *Pixel Data* and covers:

* An introduction to *Pixel Data*
* Decoding compressed and uncompressed *Pixel Data*
* Visualization

**Prerequisites**

.. code-block:: bash

    python -m pip install -U pydicom>=2.1 numpy matplotlib

.. code-block:: bash

    conda install numpy matplotlib
    conda install -c conda-forge pydicom>=2.1


*Pixel Data*
============

Many DICOM Information Object Definitions (IODs) contain bulk pixel data,
which is usually used to represent one or more image frames (although
:dcm:`other types of data<part03/sect_A.18.3.html>` are possible). In these
IODs the pixel data is (almost) always contained in the (7FE0,0010) *Pixel
Data* element. The only exception to this is :dcm:`Parametric Map
<part03/sect_A.75.3.html>` which may instead contain data in the (7FE0,0008)
*Float Pixel Data* or (7FE0,0009) *Double Float Pixel Data* elements.

*pydicom* reads in pixel data as the raw encoded binary data found in
the file:

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pydicom.data import get_testdata_file
    >>> path = get_testdata_file("CT_small.dcm")
    >>> ds = dcmread(path)
    >>> ds.PixelData # doctest: +ELLIPSIS
    b'\xaf\x00\xb4\x00\xa6\x00\x8f\x00\x8b\x00...

To understand the encoded data we must look at two things:

* The dataset's *Transfer Syntax UID*, which tells us if the encoded data is
  compressed, and if so which compression method was used
* The group ``0x0028`` elements, which tell us how to *interpret* the
  data once its uncompressed

The *Transfer Syntax UID*
-------------------------

.. code-block:: python

    >>> tsyntax = ds.file_meta.TransferSyntaxUID
    >>> tsyntax, tsyntax.name, tsyntax.is_compressed
    ('1.2.840.10008.1.2.1', 'Explicit VR Little Endian', False)

*Explicit VR Little Endian*, *Implicit VR Little Endian* and *Deflated Explicit
VR Little Endian* have uncompressed pixel data, while all other transfer
syntaxes use a compressed format such as :dcm:`RLE<part05/sect_8.2.2.html>` or
JPEG.

Group ``0x0028`` elements
-------------------------

Conveniently, all the elements that affect the interpretation of the
pixel data have the same group number, ``0x0028``:

.. code-block:: python

    >>> print(ds.group_dataset(0x0028))
    (0028, 0002) Samples per Pixel                   US: 1
    (0028, 0004) Photometric Interpretation          CS: 'MONOCHROME2'
    (0028, 0010) Rows                                US: 128
    (0028, 0011) Columns                             US: 128
    (0028, 0030) Pixel Spacing                       DS: [0.661468, 0.661468]
    (0028, 0100) Bits Allocated                      US: 16
    (0028, 0101) Bits Stored                         US: 16
    (0028, 0102) High Bit                            US: 15
    (0028, 0103) Pixel Representation                US: 1
    (0028, 0120) Pixel Padding Value                 SS: -2000
    (0028, 1052) Rescale Intercept                   DS: "-1024.0"
    (0028, 1053) Rescale Slope                       DS: "1.0"

Briefly:

* The **data type** of each pixel value (signed/unsigned, 1/8/16/32-bit),
  is given by *Bits Allocated*, *Bits Stored* and *Pixel Representation*. A
  *Bits Stored* value of ``1`` also indicates the data has been bit-packed.
* The **shape** of the data is given by *Rows*, *Columns*,
  *Samples per Pixel*, *Number of Frames* (not included in this dataset)
* The **order** of the pixel values is given by *Planar Configuration*
  (when *Samples per Pixel* > 1).
* The **colorspace** (monochrome/RGB/YBR) is given by *Photometric
  Interpretation*

A full explanation for how each element affects the pixel data is available in
:dcm:`Part 3 of the DICOM Standard <part03/sect_C.7.6.3.html>`.


Decoding
========

Uncompressed Transfer Syntaxes
------------------------------

Since *Bits Allocated* is ``16``, each pixel (technically, each :dcm:`sample
value<part05/chapter_D.html>`) is contained in 2 bytes, with the value itself
taking up *Bits Stored* number of bits within the container. As *Pixel
Representation* is ``1`` (`2's complement
<https://en.wikipedia.org/wiki/Two%27s_complement>`_) and *Bits Stored* ``16``
every pixel value is a 16-bit signed integer.

.. code-block:: python

    >>> sv = ds.PixelData[:2]  # The (0, 0) pixel
    >>> sv
    b'\xaf\x00'
    >>> int.from_bytes(sv, byteorder='little', signed=True)
    175

Decoding the pixel data rapidly becomes much more complicated than this once
you have to account for the various data types, shapes and pixel orderings,
so if `NumPy <https://numpy.org/>`_ is installed *pydicom* will
do the work for you and return the pixel data as an :class:`~numpy.ndarray`:

.. code-block:: python

    >>> arr = ds.pixel_array
    >>> arr.shape
    (128, 128)
    >>> arr
    array([[175, 180, 166, ..., 203, 207, 216],
           [186, 183, 157, ..., 181, 190, 239],
           [184, 180, 171, ..., 152, 164, 235],
           ...,
           [906, 910, 923, ..., 922, 929, 927],
           [914, 954, 938, ..., 942, 925, 905],
           [959, 955, 916, ..., 911, 904, 909]], dtype=int16)


Compressed Transfer Syntaxes
----------------------------

Converting JPEG, JPEG-LS or JPEG 2000 compressed pixel data to an
:class:`~numpy.ndarray` requires one or more third party Python packages to
decompress the data before it can be decoded.

.. code-block:: python

    >>> path = get_testdata_file("MR2_J2KR.dcm")
    >>> ds = dcmread(path)
    >>> tsyntax = ds.file_meta.TransferSyntaxUID
    >>> tsyntax, tsyntax.name, tsyntax.is_compressed
    ('1.2.840.10008.1.2.4.90', 'JPEG 2000 Image Compression (Lossless Only)', True)

.. code-block:: python

    >>> ds.pixel_array
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File ".../pydicom/dataset.py", line 1634, in pixel_array
        self.convert_pixel_data()
      File ".../pydicom/dataset.py", line 1343, in convert_pixel_data
        self._convert_pixel_data_without_handler()
      File ".../pydicom/dataset.py", line 1428, in _convert_pixel_data_without_handler
        raise RuntimeError(msg + ', '.join(pkg_msg))
    RuntimeError: The following handlers are available to decode the pixel data however they are missing required dependencies: GDCM (req. GDCM), Pillow (req. Pillow), pylibjpeg (req. pylibjpeg)

For this tutorial we'll be using
`pylibjpeg <https://github.com/pydicom/pylibjpeg>`_ to handle JPEG
decompression but you could use :doc:`any of the appropriate third party
libraries<../old/image_data_handlers>` supported by *pydicom*.

Visualization
=============
