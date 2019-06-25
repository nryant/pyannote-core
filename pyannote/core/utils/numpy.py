#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2018 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Hervé BREDIN - http://herve.niderb.fr

import numpy as np
from ..segment import Segment
from ..segment import SlidingWindow
from ..annotation import Annotation
from ..feature import SlidingWindowFeature
from .generators import string_generator


def one_hot_encoding(annotation, support, window, labels=None, mode='center'):
    """Convert annotation to one-hot-encoded numpy array

    Parameters
    ----------
    annotation : `pyannote.core.Annotation`
    support : `pyannote.core.Timeline`
    window : `SlidingWindow`
        Use this `window`.
    labels : list, optional
        Predefined list of labels. Defaults to using labels in `annotation`.

    Returns
    -------
    y : `pyannote.core.SlidingWindowFeature`
        (N, K) array where y[t, k] > 0 when labels[k] is active at timestep t.
        y[t, k] = NAN means we have no idea.
    labels : list
        List of labels.

    See also
    --------
    See `one_hot_decoding` to convert `y` back to a `pyannote.core.Annotation`
    instance
    """

    if not isinstance(window, SlidingWindow):
        if hasattr(window, 'sliding_window'):
            window = window.sliding_window
        else:
            msg = (f"`window` must be an instance of `SlidingWindow` "
                   f"or have an attribute called 'sliding_window'.")
            raise TypeError(msg)

    extent = support.extent()
    window = SlidingWindow(start=extent.start,
                           step=window.step,
                           duration=window.duration)

    n_samples = window.samples(extent.duration, mode=mode)

    # defaults to `labels` contained by `annotation`
    labels = annotation.labels() if labels is None else labels
    indices = {label: i for i, label in enumerate(labels)}

    # one-hot encoding
    # -1 = unknown / +1 = active / 0 = inactive
    y = -np.ones((n_samples, len(labels)), dtype=np.int8)
    for i, j in window.crop(support, mode=mode, return_ranges=True):
        i = max(0, i)
        j = min(n_samples, j)
        y[i:j, :] = 0

    for label in annotation.labels():
        try:
            k = indices[label]
        except KeyError as e:
            msg = f'List of `labels` does not contain label "{label}".'
            print(indices.keys())
            raise ValueError(msg)

        for i, j in window.crop(annotation.label_timeline(label),
                                mode=mode, return_ranges=True):
            i = max(0, i)
            j = min(n_samples, j)
            y[i:j, k] += 1

    y = np.minimum(y, 1, out=y)

    return SlidingWindowFeature(y, window), labels


def one_hot_decoding(y, window, labels=None):
    """Convert one-hot-encoded numpy array to annotation

    Parameters
    ----------
    y : (N, K) or (N, ) numpy.ndarray
        When y has shape (N, K), y[t, k] > 0 means kth label is active at
        timestep t. When y has shape (N, ), y[t] = 0 means no label is active
        at timestep t, y[t] = k means (k-1)th label is active.
    window : `SlidingWindow`
        Use this `window`.
    labels : list, optional
        Predefined list of labels.  Defaults to labels generated by
        `pyannote.core.utils.generators.string_generator`.

    Returns
    -------
    annotation : pyannote.core.Annotation

    See also
    --------
    `one_hot_encoding`
    """

    if not isinstance(window, SlidingWindow):
        if hasattr(window, 'sliding_window'):
            window = window.sliding_window
        else:
            msg = (f"`window` must be an instance of `SlidingWindow` "
                   f"or have an attribute called 'sliding_window'.")
            raise TypeError(msg)

    if len(y.shape) < 2:
        N, = y.shape
        if labels is not None:
            K = len(labels)
        else:
            K = np.max(y)

        y_ = np.zeros((N, K), dtype=np.int64)
        for t, k in enumerate(y):
            if k == 0:
                continue
            y_[t, k - 1] = 1
        y = y_

    N, K = y.shape

    if labels is None:
        labels = string_generator()
        labels = [next(labels) for _ in range(K)]

    annotation = Annotation()

    y_off = np.zeros((1, K), dtype=np.int64)
    y = np.vstack((y_off, y, y_off))
    diff = np.diff(y, axis=0)
    for k, label in enumerate(labels):
        for t in np.where(diff[:, k] != 0)[0]:
            if diff[t, k] > 0:
                onset_t = window[t].middle
            else:
                segment = Segment(onset_t, window[t].middle)
                annotation[segment, k] = label

    return annotation
