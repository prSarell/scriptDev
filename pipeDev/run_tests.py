"""
Run the pipe's headless tests and print one summary.

    mayapy pipeDev/run_tests.py              # every test
    mayapy pipeDev/run_tests.py publish      # only tests whose path contains "publish"
    python pipeDev/run_tests.py              # also fine: it finds mayapy itself

Each test_*.py under pipeDev/ (outside shotSub's vendored folders) runs in
its own mayapy process, in its own folder, on throwaway files: the real
drives and Maya prefs are never touched. A test passes when it prints
"N/N passed" with no FAIL lines.

mayapy: the MAYAPY environment variable if set, else Maya 2025's default
install path.
"""

import os
import re
import sys
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = ("shotgun_api3", "__pycache__")
SUMMARY = re.compile(r"(\d+)/(\d+) passed")
TIMEOUT = 900   # seconds per test


def find_mayapy():
    if os.environ.get("MAYAPY"):
        return os.environ["MAYAPY"]
    if os.path.basename(sys.executable).lower().startswith("mayapy"):
        return sys.executable
    default = r"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
    if os.path.isfile(default):
        return default
    sys.exit("mayapy not found: set the MAYAPY environment variable to its path.")


def find_tests(pattern=""):
    tests = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.startswith("test_") and name.endswith(".py"):
                path = os.path.join(root, name)
                if pattern.lower() in os.path.relpath(path, HERE).lower():
                    tests.append(path)
    return sorted(tests)


def run(mayapy, path):
    start = time.time()
    try:
        proc = subprocess.run([mayapy, os.path.basename(path)], cwd=os.path.dirname(path),
                              capture_output=True, text=True, errors="replace",
                              timeout=TIMEOUT)
        out = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return False, "timed out after %ds" % TIMEOUT, time.time() - start
    fails = [line for line in out.splitlines() if line.startswith("FAIL")]
    counts = SUMMARY.findall(out)
    if not counts:
        return False, "no 'N/N passed' line (crashed?)\n" + out[-1500:], time.time() - start
    passed, total = (int(n) for n in counts[-1])
    ok = passed == total and not fails
    detail = "%d/%d" % (passed, total) + ("".join("\n    " + f for f in fails) if fails else "")
    return ok, detail, time.time() - start


def main(argv):
    pattern = argv[1] if len(argv) > 1 else ""
    mayapy = find_mayapy()
    tests = find_tests(pattern)
    print("Running %d test(s) with %s\n" % (len(tests), mayapy))
    failed = []
    for path in tests:
        rel = os.path.relpath(path, HERE)
        ok, detail, secs = run(mayapy, path)
        print("%s  %-55s %s  (%ds)" % ("PASS" if ok else "FAIL", rel, detail, secs))
        if not ok:
            failed.append(rel)
    print("\n%d/%d test files passed" % (len(tests) - len(failed), len(tests)))
    for rel in failed:
        print("  failed: " + rel)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
