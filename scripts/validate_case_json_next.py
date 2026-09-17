"""Deprecated compatibility alias for :mod:`validate_case_json`.

The canonical validator is ``validate_case_json.py``. This module intentionally
contains no validation rules and exists only for callers that still import the
former ``*_next`` name. New code must import the canonical module directly.
"""

import warnings

from validate_case_json import validate

__all__ = ["validate"]

warnings.warn(
    "validate_case_json_next is deprecated; import validate_case_json instead",
    DeprecationWarning,
    stacklevel=2,
)