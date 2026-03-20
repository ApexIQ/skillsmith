from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import uuid4


def _should_patch_tempfile() -> bool:
    if os.environ.get("SKILLSMITH_FORCE_SAFE_TEMP") == "1":
        return True
    return any("unittest" in str(arg).lower() for arg in sys.argv)


if _should_patch_tempfile():
    _ROOT = Path(__file__).resolve().parent
    _TMP_ROOT = _ROOT / ".tmp-unittest-global"
    _TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def _safe_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | None = None) -> str:
        base = Path(dir) if dir else _TMP_ROOT
        base.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        path = base / f"{prefix or 'tmp'}{token}{suffix or ''}"
        path.mkdir(parents=True, exist_ok=False)
        return str(path)

    class _SafeTemporaryDirectory:
        def __init__(
            self,
            suffix: str | None = None,
            prefix: str | None = None,
            dir: str | None = None,
            ignore_cleanup_errors: bool = False,
        ) -> None:
            self.name = _safe_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
            self._closed = False
            self._ignore_cleanup_errors = ignore_cleanup_errors

        def __enter__(self) -> str:
            return self.name

        def cleanup(self) -> None:
            if self._closed:
                return
            shutil.rmtree(self.name, ignore_errors=self._ignore_cleanup_errors or True)
            self._closed = True

        def __exit__(self, exc_type, exc, tb) -> bool:
            self.cleanup()
            return False

        def __del__(self) -> None:
            self.cleanup()

    tempfile.mkdtemp = _safe_mkdtemp  # type: ignore[assignment]
    tempfile.TemporaryDirectory = _SafeTemporaryDirectory  # type: ignore[assignment]
