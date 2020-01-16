=============================
Create a dataset from scratch
=============================

In this tutorial we're going to be creating a conformant *Computed Tomography
(CT) Image* instance from scratch, using *pydicom*.

* Understand what makes a *CT Image*
* Creating the dataset

This tutorial assumes that you're familiar with the :doc:`basics reading,
modifying and writing datasets</tutorials/dataset_basics>`. It also requires
`NumPy <https://numpy.org/>`_, so if you haven't installed it yet check out
the :ref:`installation guide<tut_install_libs>` for more details.


What is a CT Image?
===================

What exactly is it that makes a DICOM dataset a CT Image? What collection of
elements and what values for those elements are needed before we can call a
dataset a conformant *CT Image* SOP Instance?

To find out we need to look at DICOM Standard, specifically Part 3 which
contains every DICOM Information Object Definition (IOD). An IOD is (something)

If you open :dcm:`Part 3<part03/PS3.3.html>` in a new tab and scroll down to
:dcm:`Annex A<part03/chapter_A.html>`, you'll see that it
contains top-level summaries of every composite IOD. Scroll a bit further to
:dcm:`Annex A.3<part03/sect_A.3.html>` and you'll find the summary for
*Computed Tomography Image IOD*, and in particular :dcm:`Annex A.3.3
<part03/sect_A.3.3.html>` for the summary of modules that make up a *CT Image*.
