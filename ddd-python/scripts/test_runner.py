"""Run unittest in a subprocess and emit observed outcomes, without API calls."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class RecordedResult(unittest.TestResult):
    """Record parent test IDs, including failed subtests and skipped tests."""

    def __init__(self):
        super().__init__()
        self.outcomes = {}

    def startTest(self, test):
        super().startTest(test)
        self.outcomes[test.id()] = {"status": "running", "detail": ""}

    def record(self, test, status, detail=""):
        self.outcomes[test.id()] = {"status": status, "detail": detail}

    def addSuccess(self, test):
        super().addSuccess(test)
        if self.outcomes[test.id()]["status"] == "running":
            self.record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        parent = getattr(test, "test_case", test)
        if self.outcomes.get(parent.id(), {}).get("status") not in ("failed", "error"):
            self.record(parent, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, "expected_failure", self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "unexpected_success", "Expected failure unexpectedly passed")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record(test, "failed", self._exc_info_to_string(err, subtest))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    result = RecordedResult()
    output = io.StringIO()
    started = time.monotonic()
    fatal = None
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            loader = unittest.TestLoader()
            suite = loader.discover(str(root / args.start), top_level_dir=str(root))
            if loader.errors:
                raise RuntimeError("\n".join(loader.errors))
            suite.run(result)
        except BaseException:
            fatal = traceback.format_exc()
    payload = {
        "count": result.testsRun,
        "outcomes": result.outcomes,
        "duration_seconds": round(time.monotonic() - started, 4),
        "output": output.getvalue(),
        "fatal": fatal,
    }
    Path(args.result).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 2 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
