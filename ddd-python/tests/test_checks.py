"""Exercise valid fixtures and injected defects without modifying the example."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
from check import run_checks, run_tests


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ddd-regression-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project with spaces"
        shutil.copytree(SKILL_ROOT / "assets/order_example", self.project,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def edit_json(self, name, change):
        path = self.project / name
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value), encoding="utf-8")

    def append(self, path, source):
        file = self.project / path
        file.write_text(file.read_text() + source, encoding="utf-8")

    def codes(self, report):
        return {finding["code"] for finding in report["findings"] if finding["status"] in ("failed", "error")}

    def inject_test(self, body):
        path = self.project / "tests/test_injected.py"
        path.write_text("import unittest\nclass Injected(unittest.TestCase):\n" + body, encoding="utf-8")

    def test_valid_project_all_checks(self):
        report = run_checks(self.project)
        self.assertEqual(report["exit_code"], 0, report["findings"])
        self.assertTrue(all(status == "passed" for status in report["checks"].values()))
        self.assertGreaterEqual(report["test_results"]["count"], 14)
        self.assertEqual(report["semantic_status"], "needs_review")

    def test_selection_does_not_claim_tests_ran(self):
        report = run_checks(self.project, {"model"})
        self.assertEqual(report["exit_code"], 0, report["findings"])
        self.assertEqual(report["checks"]["tests"], "not_run")
        self.assertIsNone(report["test_results"])

    def test_unknown_context(self):
        self.edit_json("model.json", lambda m: m["aggregates"][0].update(context="missing"))
        self.assertIn("MODEL-REFERENCE", self.codes(run_checks(self.project, {"model"})))

    def test_duplicate_ids(self):
        self.edit_json("model.json", lambda m: m["rules"].append(m["rules"][0].copy()))
        self.assertIn("MODEL-DUPLICATE", self.codes(run_checks(self.project, {"model"})))

    def test_missing_implementation(self):
        self.edit_json("model.json", lambda m: m["rules"][0].update(symbols=["domain.order.Order.missing"]))
        self.assertIn("MODEL-REFERENCE", self.codes(run_checks(self.project, {"model"})))

    def test_missing_test_symbol(self):
        self.edit_json("model.json", lambda m: m["rules"][0].update(tests=["tests.test_order.OrderTests.test_missing"]))
        self.assertIn("MODEL-TEST", self.codes(run_checks(self.project, {"model"})))

    def test_owner_must_list_invariant(self):
        self.edit_json("model.json", lambda m: m["aggregates"][0]["invariants"].remove("ORD-001"))
        self.assertIn("MODEL-OWNERSHIP", self.codes(run_checks(self.project, {"model"})))

    def test_contract_is_not_an_aggregate_invariant(self):
        self.edit_json("model.json", lambda m: m["aggregates"][0]["invariants"].append("ORD-005"))
        self.assertIn("MODEL-RULE-KIND", self.codes(run_checks(self.project, {"model"})))

    def test_responsibility_needs_basis(self):
        self.edit_json("model.json", lambda m: m["responsibilities"][0].update(rules=[], decisions=[]))
        self.assertIn("MODEL-RESPONSIBILITY", self.codes(run_checks(self.project, {"model"})))

    def test_rule_must_have_responsibility(self):
        self.edit_json("model.json", lambda m: m["responsibilities"].pop(0))
        self.assertIn("MODEL-TRACE", self.codes(run_checks(self.project, {"model"})))

    def test_assumption_remains_review_item(self):
        self.edit_json("model.json", lambda m: m["rules"][0].update(status="assumption"))
        report = run_checks(self.project, {"model"})
        self.assertEqual(report["exit_code"], 0)
        self.assertTrue(any(f["code"] == "BUSINESS-ASSUMPTION" and f["status"] == "needs_review" for f in report["findings"]))

    def test_malformed_model(self):
        self.edit_json("model.json", lambda m: m.update(rules=None))
        self.assertEqual(run_checks(self.project)["exit_code"], 2)

    def test_missing_input(self):
        (self.project / "model.json").unlink()
        self.assertEqual(run_checks(self.project)["exit_code"], 2)

    def test_invalid_json(self):
        (self.project / "model.json").write_text("{")
        self.assertIn("INPUT-ERROR", self.codes(run_checks(self.project)))

    def test_source_path_cannot_escape(self):
        self.edit_json("architecture.json", lambda p: p.update(source_roots=["../"]))
        self.assertEqual(run_checks(self.project)["exit_code"], 2)

    def test_invalid_layer_reference(self):
        self.edit_json("architecture.json", lambda p: p["layers"][0].update(allow=["missing"]))
        self.assertEqual(run_checks(self.project)["exit_code"], 2)

    def test_syntax_error_not_pass(self):
        self.append("domain/order.py", "\nthis is not valid python!!!\n")
        self.assertEqual(run_checks(self.project, {"architecture"})["exit_code"], 2)

    def test_forbidden_external_import(self):
        self.append("domain/order.py", "\nimport sqlite3\n")
        self.assertIn("ARCH-DEPENDENCY", self.codes(run_checks(self.project, {"architecture"})))

    def test_forbidden_internal_import(self):
        self.append("domain/order.py", "\nfrom infrastructure.memory import MemoryOrderRepository\n")
        self.assertIn("ARCH-DEPENDENCY", self.codes(run_checks(self.project, {"architecture"})))

    def test_import_from_package_child_is_checked(self):
        self.append("domain/order.py", "\nfrom infrastructure import memory\n")
        report = run_checks(self.project, {"architecture"})
        self.assertIn("ARCH-DEPENDENCY", self.codes(report))
        self.assertIn("ARCH-CYCLE", self.codes(report))

    def test_relative_import_cycle(self):
        self.append("domain/order.py", "\nfrom . import repository\n")
        self.assertIn("ARCH-CYCLE", self.codes(run_checks(self.project, {"architecture"})))

    def test_relative_import_escape(self):
        self.append("domain/order.py", "\nfrom ... import missing\n")
        self.assertIn("ARCH-RELATIVE", self.codes(run_checks(self.project, {"architecture"})))

    def test_justified_exception_only_waives_its_edge(self):
        self.append("application/confirm_order.py", "\nimport infrastructure.memory\n")
        self.edit_json("architecture.json", lambda p: p["exceptions"].append({
            "from": "application.confirm_order", "to": "infrastructure.memory",
            "reason": "Explicit composition root", "decision": "DEC-002"}))
        report = run_checks(self.project, {"architecture"})
        self.assertEqual(report["exit_code"], 0, report["findings"])
        self.assertTrue(any(f["code"] == "ARCH-EXCEPTION" for f in report["findings"]))
        self.append("domain/order.py", "\nimport sqlite3\n")
        self.assertIn("ARCH-DEPENDENCY", self.codes(run_checks(self.project, {"architecture"})))

    def test_exception_needs_existing_decision(self):
        self.edit_json("architecture.json", lambda p: p["exceptions"].append({
            "from": "domain.order", "to": "infrastructure.memory", "reason": "test", "decision": "missing"}))
        report = run_checks(self.project, {"architecture", "tests"})
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["checks"]["architecture"], "error")
        self.assertEqual(report["checks"]["tests"], "not_run")

    def test_dynamic_import_is_not_certified(self):
        self.append("domain/order.py", "\ndef _plugin(name):\n    return __import__(name)\n")
        report = run_checks(self.project, {"architecture"})
        self.assertTrue(any(f["code"] == "ARCH-DYNAMIC" and f["status"] == "needs_review" for f in report["findings"]))

    def test_stale_rule_comment(self):
        self.append("domain/order.py", "\n# Rules: ORD-999\n")
        self.assertIn("DOC-RULE", self.codes(run_checks(self.project, {"comments"})))

    def test_docstring_parameter_drift(self):
        self.append("domain/order.py", '\ndef helper(value):\n    """Validate.\n\n    Args:\n        removed: No longer exists.\n    """\n    return value\n')
        self.assertIn("DOC-PARAMETER", self.codes(run_checks(self.project, {"comments"})))

    def test_public_contract_requires_documentation(self):
        self.append("domain/order.py", "\ndef helper(value):\n    return value\n")
        self.assertIn("DOC-MISSING", self.codes(run_checks(self.project, {"comments"})))

    def test_removing_rule_marker(self):
        path = self.project / "domain/order.py"
        path.write_text(path.read_text().replace("Rules: ORD-001, ORD-002", "Rules: ORD-002"))
        self.assertIn("DOC-TRACE", self.codes(run_checks(self.project, {"comments"})))

    def test_business_mutation_is_caught_by_actual_tests(self):
        path = self.project / "domain/order.py"
        path.write_text(path.read_text().replace("if not self._items:", "if False:"))
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["test_results"]["outcomes"]["tests.test_order.OrderTests.test_empty_order"]["status"], "failed")
        self.assertIn("TEST-RULE-EVIDENCE", self.codes(report))

    def test_subtest_failure_is_recorded(self):
        self.inject_test("    def test_sub(self):\n        with self.subTest(case='broken'):\n            self.assertEqual(1, 2)\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["test_results"]["outcomes"]["tests.test_injected.Injected.test_sub"]["status"], "failed")
        self.assertEqual(report["exit_code"], 1)

    def test_skips_cannot_be_passed_evidence(self):
        self.inject_test("    @unittest.skip('resource unavailable')\n    def test_skip(self):\n        pass\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["test_results"]["outcomes"]["tests.test_injected.Injected.test_skip"]["status"], "skipped")
        self.assertEqual(report["exit_code"], 1)

    def test_skipped_subtest_does_not_become_success(self):
        self.inject_test("    def test_sub(self):\n        with self.subTest(case='unavailable'):\n            self.skipTest('no fixture')\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["test_results"]["outcomes"]["tests.test_injected.Injected.test_sub"]["status"], "skipped")
        self.assertEqual(report["exit_code"], 1)

    def test_expected_failure_is_not_passing_evidence(self):
        self.inject_test("    @unittest.expectedFailure\n    def test_expected(self):\n        self.fail('known defect')\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["test_results"]["outcomes"]["tests.test_injected.Injected.test_expected"]["status"], "expected_failure")
        self.assertEqual(report["exit_code"], 1)

    def test_fixture_failure_is_reported(self):
        self.inject_test("    @classmethod\n    def setUpClass(cls):\n        raise RuntimeError('fixture failed')\n    def test_case(self):\n        pass\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["exit_code"], 1)
        self.assertTrue(any(value["status"] == "error" for value in report["test_results"]["outcomes"].values()))

    def test_inherited_optimization_cannot_disable_assertions(self):
        self.inject_test("    def test_assert(self):\n        assert False, 'must execute'\n")
        with patch.dict(os.environ, {"PYTHONOPTIMIZE": "1"}):
            report = run_checks(self.project, {"tests"})
        self.assertEqual(report["test_results"]["outcomes"]["tests.test_injected.Injected.test_assert"]["status"], "failed")

    def test_runtime_exit_without_report_is_error(self):
        self.inject_test("    def test_exit(self):\n        import os\n        os._exit(0)\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("TEST-RUNNER", self.codes(report))

    def test_missing_execution_not_satisfied_by_static_symbol(self):
        self.inject_test("    def helper(self):\n        pass\n")
        self.edit_json("model.json", lambda m: m["rules"][0].update(tests=["tests.test_injected.Injected.helper"]))
        report = run_checks(self.project, {"tests"})
        self.assertIn("TEST-RULE-EVIDENCE", self.codes(report))

    def test_test_discovery_failure(self):
        self.inject_test("    raise RuntimeError('discovery broke')\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("TEST-RUNNER", self.codes(report))

    def test_zero_tests_is_not_success(self):
        for path in (self.project / "tests").glob("test_*.py"):
            path.unlink()
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["test_results"]["count"], 0)
        self.assertIn("TEST-EMPTY", self.codes(report))

    def test_runner_timeout(self):
        self.inject_test("    def test_sleep(self):\n        import time\n        time.sleep(20)\n")
        result = run_tests(self.project, "tests", timeout=0.2)
        self.assertIn("timed out", result["fatal"])

    def test_test_stdout_does_not_corrupt_results(self):
        self.inject_test("    def test_print(self):\n        print('arbitrary output')\n")
        report = run_checks(self.project, {"tests"})
        self.assertEqual(report["exit_code"], 0, report["findings"])
        self.assertIn("arbitrary output", report["test_results"]["output"])

    def test_reports_and_exit_status_from_other_directory(self):
        self.append("domain/order.py", "\nimport sqlite3\n")
        output = Path(self.temporary.name) / "output"
        process = subprocess.run([
            sys.executable, "-B", str(SKILL_ROOT / "scripts/check.py"),
            "--project", str(self.project), "--architecture",
            "--json", str(output / "report.json"), "--markdown", str(output / "report.md")
        ], cwd=self.temporary.name, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["checks"]["tests"], "not_run")
        self.assertIn("ARCH-DEPENDENCY", self.codes(report))
        self.assertTrue((output / "report.md").is_file())


if __name__ == "__main__":
    unittest.main()
