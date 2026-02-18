"""Quick smoke test for all skillsmith CLI commands via Python entry point."""
import sys
import subprocess
from pathlib import Path

CWD = str(Path(__file__).parent)  # always the project root, works on any machine
PY = sys.executable

def run(argv, label):
    script = (
        f"import sys; sys.argv={argv!r}; "
        f"from skillsmith.cli import main; main(standalone_mode=False)"
    )
    result = subprocess.run(
        [PY, "-c", script],
        capture_output=True, text=True, cwd=CWD
    )
    ok = result.returncode == 0
    status = "OK  " if ok else "FAIL"
    print(f"[{status}] {label}")
    if not ok:
        out = (result.stdout + result.stderr).strip()[:300]
        print(f"       {out}")
    return ok

tests = [
    (["skillsmith", "--help"],                          "--help"),
    (["skillsmith", "list"],                            "list"),
    (["skillsmith", "list", "--category", "security"], "list --category security"),
    (["skillsmith", "lint", "--local"],                 "lint --local"),
    (["skillsmith", "lint", "--spec", "agentskills"],  "lint --spec agentskills"),
    (["skillsmith", "doctor"],                          "doctor"),
    (["skillsmith", "budget"],                          "budget"),
    (["skillsmith", "compose", "build a saas mvp"],    "compose 'build a saas mvp'"),
    (["skillsmith", "serve", "--help"],                 "serve --help"),
]

passed = sum(run(a, l) for a, l in tests)
total = len(tests)
print(f"\n{'='*40}")
print(f"Result: {passed}/{total} passed")
if passed == total:
    print("ALL TESTS PASSED - ready to build and publish!")
else:
    print(f"FAILURES: {total - passed} command(s) failed")
    sys.exit(1)
