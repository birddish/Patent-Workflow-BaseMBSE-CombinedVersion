"""Deprecated compatibility alias for :mod:`validate_view_patch`.

The canonical Patch validator is ``validate_view_patch.py``. This module
intentionally contains no validation rules and exists only for callers that
still import the former ``*_next`` name. New code must import the canonical
module directly.
"""

import warnings

from validate_view_patch import validate

__all__ = ["validate"]

warnings.warn(
    "validate_view_patch_next is deprecated; import validate_view_patch instead",
    DeprecationWarning,
    stacklevel=2,
)