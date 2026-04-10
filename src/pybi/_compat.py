"""Compatibility shim for Python 3.14.0rc2 + Pydantic 2.x.

Python 3.14.0rc2 changed the signature of ``typing._eval_type()``, removing
the ``prefer_fwd_module`` keyword argument that Pydantic passes.  This shim
patches the function to accept-and-ignore that kwarg until Pydantic ships a
fix targeting 3.14 final.

Remove this file once the minimum Pydantic version is bumped to a release that
no longer calls ``typing._eval_type(..., prefer_fwd_module=True)``.
"""

from __future__ import annotations

import inspect
import sys
import typing


def _apply() -> None:
    # Only patch on Python 3.14; earlier versions are unaffected.
    if sys.version_info[:2] != (3, 14):
        return

    _eval_type = getattr(typing, "_eval_type", None)
    if _eval_type is None:
        return  # Private API removed entirely - nothing to patch.

    try:
        sig = inspect.signature(_eval_type)
    except (TypeError, ValueError):
        return  # Can't introspect - leave it alone.

    if "prefer_fwd_module" in sig.parameters:
        return  # Already has the parameter - no patch needed.

    def _patched(
        t: object,
        globalns: dict | None,
        localns: dict | None,
        type_params: tuple = (),
        *,
        prefer_fwd_module: bool = False,
        **kwargs: object,
    ) -> object:
        return _eval_type(t, globalns, localns, type_params, **kwargs)

    typing._eval_type = _patched  # type: ignore[attr-defined]


_apply()
