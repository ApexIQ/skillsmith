from __future__ import annotations

try:
    from importlib.metadata import version as _package_version
except Exception:  # pragma: no cover - importlib metadata is always available in supported runtimes
    _package_version = None

from .api import compose_workflow, doctor_summary, init_project

if _package_version is not None:
    try:
        __version__ = _package_version("skillsmith")
    except Exception:
        __version__ = "1.1.2"
else:
    __version__ = "1.1.2"

__all__ = ["__version__", "compose_workflow", "doctor_summary", "init_project"]


