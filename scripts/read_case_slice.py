"""Deprecated compatibility command for the canonical case projection reader.

The implementation and command-line contract live in
``inspect_case_json.py``. This module deliberately contains no projection
rules; it only forwards the legacy command name for existing callers. New
code should invoke ``inspect_case_json.py`` directly.
"""

from inspect_case_json import main as _canonical_main

main = _canonical_main


if __name__ == "__main__":
    raise SystemExit(main())