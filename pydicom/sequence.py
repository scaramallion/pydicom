"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
import collections

from pydicom.dataset import Dataset, OverlayDataset
from pydicom.multival import MultiValue


def validate_dataset(elem):
    """Check that `elem` is a Dataset instance."""
    if not isinstance(elem, Dataset):
        raise TypeError('Sequence contents must be Dataset instances.')

    return elem


class Sequence(MultiValue):
    """Class to hold multiple Datasets in a list.

    This class is derived from MultiValue and as such enforces that all items
    added to the list are Dataset instances. In order to due this, a validator
    is substituted for type_constructor when constructing the MultiValue super
    class
    """
    def __init__(self, iterable=None):
        """Initialize a list of Datasets.

        Parameters
        ----------
        iterable : list-like of pydicom.dataset.Dataset, optional
            An iterable object (e.g. list, tuple) containing Datasets. If not
            used then an empty Sequence is generated.
        """
        # We add this extra check to throw a relevant error. Without it, the
        # error will be simply that a Sequence must contain Datasets (since a
        # Dataset IS iterable). This error, however, doesn't inform the user
        # that the actual issue is that their Dataset needs to be INSIDE an
        # iterable object
        if isinstance(iterable, Dataset):
            raise TypeError('The Sequence constructor requires an iterable')

        # If no inputs are provided, we create an empty Sequence
        if not iterable:
            iterable = list()

        # validate_dataset is used as a pseudo type_constructor
        super(Sequence, self).__init__(validate_dataset, iterable)

    def __str__(self):
        """String description of the Sequence."""
        lines = [str(x) for x in self]
        return "[" + "".join(lines) + "]"

    def __repr__(self):
        """String representation of the Sequence."""
        formatstr = "<%(classname)s, length %(count)d, at %(id)X>"
        return formatstr % {'classname': self.__class__.__name__,
                            'id': id(self), 'count': len(self)}

class OverlaySequence(list):
    """A list wrapper class for OverlaySequence.
    
    Changes made to the OverlaySequence are reflected in the parent Dataset.
    """
    def __init__(self):
        self._type = OverlayDataset
        super(OverlaySequence, self).__init__(list())
    
    def _check(self, val):
        if not isinstance(val, self._type):
            raise TypeError('OverlaySequence contents must be OverlayDataset '
                            'instances.')
        return val

    def append(self, val):
        super(OverlaySequence, self).append(self._check(val))

    def extend(self, values):
        super(OverlaySequence, self).extend((self._check(x) for x in values))

    def insert(self, position, val):
        super(OverlaySequence, self).insert(position, self._check(val))

    def __setitem__(self, i, val):
        """Set an item of the list, making sure it is of the right VR type"""
        if isinstance(i, slice):
            val = [self._check(x) for x in val]
        else:
            val = self._check(val)
        super(OverlaySequence, self).__setitem__(i, val)
    
    def __delitem__(self, key):
        """When an item is deleted, delete the elements from the dataset too."""
        if isinstance(key, slice):
            for ii in self[key]:
                ii.delete_all()
        else:
            self[key].delete_all()

        super(OverlaySequence, self).__delitem__(key)
        
    def pop(self, key):
        """When an item is popped, delete the elements from the dataset too."""
        self[key].delete_all()
        super(OverlaySequence, self).pop(key)
        
    def remove(self, item):
        """When an item is removed, delete the elements from the dataset too."""
        self[self.index(item)].delete_all()
        super(OverlaySequence, self).remove(item)
