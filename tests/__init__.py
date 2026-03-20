from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4


_ROOT = Path(__file__).resolve().parents[1]
_TMP_ROOT = _ROOT / ".tmp-unittest"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


class _WorkspaceTemporaryDirectory:
    """Workspace-local TemporaryDirectory replacement for restricted Windows sandboxes."""

    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        ignore_cleanup_errors: bool = False,
    ) -> None:
        base = Path(dir) if dir else _TMP_ROOT
        base.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        name = f"{prefix or 'tmp'}{token}{suffix or ''}"
        self.name = str(base / name)
        Path(self.name).mkdir(parents=True, exist_ok=False)
        self._ignore_cleanup_errors = ignore_cleanup_errors
        self._closed = False

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


tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory  # type: ignore[assignment]
