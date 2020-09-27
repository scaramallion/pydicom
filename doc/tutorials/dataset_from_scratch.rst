=============================
Create a dataset from scratch
=============================

In this tutorial we're going to create a new and conformant *Secondary Capture
(SC) Image* instance. It covers:

* How to use the DICOM Standard to understand an IOD
* Creating the *SC Image* dataset

This tutorial assumes that you're familiar with the :doc:`basics reading,
modifying and writing datasets</tutorials/dataset_basics>`. It also requires
`NumPy <https://numpy.org/>`_, so if you haven't installed it yet check out
the :ref:`installation guide<tut_install_libs>` for more details.


Using the DICOM Standard
========================

What exactly is it that makes a DICOM dataset an SC Image? What collection of
elements and what values for those elements are needed before we can call a
dataset a conformant *SC Image* SOP Instance? (FIXME: rewrite this)

To find out we need to look at DICOM Standard, specifically :dcm:`Part 3
<part03/ps3.3.html>` which contains every DICOM Information Object Definition
(IOD).

.. note::

    An IOD is the abstract data model DICOM uses to describe a real-world
    object, such as a slice of CT data (with the CT Image IOD). More
    information on DICOM's information model can be found
    :dcm:`here<part03/chapter_6.html>` and :dcm:`here
    <part03/chapter_A.html#sect_A.1>`.

If you open :dcm:`Part 3<part03/PS3.3.html>` in a new tab and scroll down to
:dcm:`Annex A<part03/chapter_A.html>`, you'll see that it
contains top-level summaries of every composite IOD. Scroll a bit further to
:dcm:`Annex A.8<part03/sect_A.8.html>` and you'll find the summary for
*Secondary Capture Image IOD*, and in particular :dcm:`Annex A.8.1.3
<part03/sect_A.8.html#sect_A.8.1.3>` for a table containing the modules that
make up an *SC Image*:

+-----------+---------------------------+-----------------------------------------------------+-------+
| IE        | Module                    | Reference                                           | Usage |
+===========+===========================+=====================================================+=======+
| Patient   | Patient                   | :dcm:`C.7.1.1<part03/sect_C.7.html#sect_C.7.1.1>`   | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Clinical Trial Subject    | :dcm:`C.7.1.3<part03/sect_C.7.html#sect_C.7.1.3>`   | U     |
+-----------+---------------------------+-----------------------------------------------------+-------+
| Study     | General Study             | :dcm:`C.7.2.1<part03/sect_C.7.2.html#sect_C.7.2.1>` | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Patient Study             | :dcm:`C.7.2.2<part03/sect_C.7.2.2.html>`            | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Clinical Trial Study      | :dcm:`C.7.2.3<part03/sect_C.7.2.3.html>`            | U     |
+-----------+---------------------------+-----------------------------------------------------+-------+
| Series    | General Series            | :dcm:`C.7.3.1<part03/sect_C.7.3.html#sect_C.7.3.1>` | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Clinical Trial Series     | :dcm:`C.7.3.2<part03/sect_C.7.3.2.html>`            | U     |
+-----------+---------------------------+-----------------------------------------------------+-------+
| Equipment | General Equipment         | :dcm:`C.7.5.1<part03/sect_C.7.5.html#sect_C.7.5.1>` | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | SC Equipment              | :dcm:`C.8.6.1<part03/sect_C.8.6.html#sect_C.8.6.1>` | M     |
+-----------+---------------------------+-----------------------------------------------------+-------+
| Image     | General Image             | :dcm:`C.7.6.1<part03/sect_C.7.6.html#sect_C.7.6.1>` | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | General Reference         | :dcm:`C.12.4<part03/sect_C.12.4.html>`              | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Image Pixel               | :dcm:`C.7.6.3<part03/sect_C.7.6.3.html>`            | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Device                    | :dcm:`C.7.6.12<part03/sect_C.7.6.12.html>`          | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Specimen                  | :dcm:`C.7.6.22<part03/sect_C.7.6.22.html>`          | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | SC Image                  | :dcm:`C.8.6.2<part03/sect_C.8.6.2.html>`            | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Overlay Plane             | :dcm:`C.9.2<part03/sect_C.9.2.html>`                | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Modality LUT              | :dcm:`C.11.1<part03/sect_C.11.html#sect_C.11.1>`    | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | VOI LUT                   | :dcm:`C.11.2<part03/sect_C.11.2.html>`              | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | ICC Profile               | :dcm:`C.11.15<part03/sect_C.11.15.html>`            | U     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | SOP Common                | :dcm:`C.12.1<part03/sect_C.12.html#sect_C.12.1>`    | M     |
+           +---------------------------+-----------------------------------------------------+-------+
|           | Common Instance Reference | :dcm:`C.12.2<part03/sect_C.12.2.html>`              | U     |
+-----------+---------------------------+-----------------------------------------------------+-------+

Each *module* is a group of related elements, and a module is either mandatory
(with a *usage* M), conditional (C), or optional (U). For our *SC Image* we'll
only include the mandatory modules, but depending on what you intend to include
in your dataset you may need to use conditional and optional modules as
well.

To start with, let's take a quick look at the :dcm:`General Study
<part03/sect_C.7.2.html#sect_C.7.2.1>` module. It contains a table listing the
elements that are part of the module, each with a name, tag, type and
description. The first few elements of that table are below:

+-------------------------+-------------+------+----------------------------------+
| Name                    | Tag         | Type | Description                      |
+=========================+=============+======+==================================+
| Study Instance UID      | (0020,000D) | 1    | Unique identifier for the Study. |
+-------------------------+-------------+------+----------------------------------+
| Study Date              | (0020,000D) | 2    | Date the Study started.          |
+-------------------------+-------------+------+----------------------------------+
| Study Time              | (0020,000D) | 2    | Time the Study started.          |
+-------------------------+-------------+------+----------------------------------+
| Referring Physician's   | (0020,000D) | 2    | Name of the Patient's            |
| Name                    |             |      | referring physician.             |
+-------------------------+-------------+------+----------------------------------+
| Referring Physician     | (0008,0096) | 3    | Identification of the Patient's  |
| Identification Sequence |             |      | referring physician.             |
|                         |             |      | Only a single item is permitted  |
|                         |             |      | in this Sequence.                |
+-------------------------+-------------+------+----------------------------------+
| > Include :dcm:`Table 10-1 "Person Identification Macro Attributes Description  |
| <part03/chapter_10.html#table_10-1>`                                            |
+-------------------------+-------------+------+----------------------------------+

There are four important thingsssss to note:

Element type
------------

The element's :dcm:`type<part05/sect_7.4.html>` determines whether or not it's
required by the module:

* **Type 1** elements are required and may not be empty
* **Type 1C** elements are required under certain conditions and may not be
  empty
* **Type 2** elements are required but may be empty
* **Type 2C** elements are required under certain conditions but may be empty
* **Type 3** elements are optional


Sequence elements
-----------------

Elements with the word "sequence" in their name have a VR of **SQ**, which
makes them sequences. You should be familiar with the concept of a sequence
element from the dataset basics tutorial, but in summary they can be thought
of as a dataset in miniature, which can be nested up to an arbitrary depth. In
the table above we have one as Type 3 *Referring Physician Identification
Sequence*. If you look at the row after it, you'll see that it starts with a
'>' character, which indicates that the depth of the current element(s) within
the sequence. If there's a single '>' then the element lies in the first
sequence, two '>>' indicates that the element lies in a sequence which itself
lies in another sequence.

Macros
------

Sometimes you'll see that a row in the module table includes a link to a
macro. Macros are similar to modules, in that they're a collection of elements,
but in this case they're used for frequently appearing groups that define a
particular thing.


.. warning::

    Just because you have a dataset that meets the minimum requirements of
    an IOD doesn't mean all third-party applications will accept it. You must
    check their DICOM Conformance Statement to see if there are any Type 2 or
    Type 3 elements that must be present and/or have values.

The same element sometimes appears in multiple modules, often with different
values for the type. When this happens you should look to either the IOD's
Module subsection for any constraints or module specializations. When all else
fails, usually the value in the more specialized module (such as *SC Image*
compared to *General Image*) will be correct.

Creating the dataset
--------------------
