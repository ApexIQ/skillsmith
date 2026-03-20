import shutil
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


_ROOT = Path(__file__).resolve().parents[1]
_TMP_ROOT = _ROOT / ".tmp-unittest-global"
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_mkdtemp(suffix=None, prefix=None, dir=None):
    base = Path(dir) if dir else _TMP_ROOT
    base.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    path = base / f"{prefix or 'tmp'}{token}{suffix or ''}"
    path.mkdir(parents=True, exist_ok=False)
    return str(path)


class _SafeTemporaryDirectory:
    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False):
        self.name = _safe_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        self._closed = False
        self._ignore_cleanup_errors = ignore_cleanup_errors

    def __enter__(self):
        return self.name

    def cleanup(self):
        if self._closed:
            return
        shutil.rmtree(self.name, ignore_errors=self._ignore_cleanup_errors or True)
        self._closed = True

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        return False

    def __del__(self):
        self.cleanup()


tempfile.mkdtemp = _safe_mkdtemp
tempfile.TemporaryDirectory = _SafeTemporaryDirectory


class TempDirCompatBootstrapTests(unittest.TestCase):
    def test_tempdir_patch_bootstrapped(self):
        self.assertIs(tempfile.TemporaryDirectory, _SafeTemporaryDirectory)


if __name__ == "__main__":
    unittest.main()
