"""Multi-package and native acceptance regressions, including false-PASS cases."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import project
import workspace


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ddd project ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'; self.root.mkdir()
        self.put('packages/sales/src/sales/__init__.py', '')
        self.put('packages/sales/src/sales/api.py', 'from inventory.api import stock\n\ndef place(qty):\n    return stock() - qty\n')
        self.put('packages/inventory/src/inventory/__init__.py', '')
        self.put('packages/inventory/src/inventory/api.py', 'def stock():\n    return 10\n')
        self.put('tests/__init__.py', '')
        self.put('tests/test_order.py', 'import unittest\nfrom sales.api import place\n\nclass Orders(unittest.TestCase):\n    def test_place(self):\n        self.assertEqual(place(3), 7)\n')
        self.config = dict(version=2, packages=[
            dict(name='sales', root='packages/sales', imports=[dict(path='packages/sales/src', prefix='')], public=['sales.api'], allow=['inventory'], external=[]),
            dict(name='inventory', root='packages/inventory', imports=[dict(path='packages/inventory/src', prefix='')], public=['inventory.api'], allow=[], external=[])],
            tracked_paths=['tests'], protected_paths=['tests/**/*.py'], allowed_changes=['packages/**/*.py'],
            goals=[dict(id='extracted', kind='symbol_exists', path='packages/sales/src/sales/api.py', symbol='remaining')],
            jobs=[dict(id='regression', phase='both', format='unittest', cwd='.', timeout=10,
                       argv=['{python}', '-B', '{skill}/scripts/test_runner.py', '--root', '{project}', '--start', 'tests', '--result', '{evidence}'],
                       env={'PYTHONPATH': '{project}/packages/sales/src:{project}/packages/inventory/src'})])
        self.config_path = self.base / 'project.json'
        self.save()

    def put(self, name, text):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
        return path

    def save(self):
        self.config_path.write_text(json.dumps(self.config))

    def baseline(self):
        return project.run(self.root, self.config_path, self.base / 'before', 'baseline')

    def refactor(self):
        self.put('packages/sales/src/sales/api.py', 'from inventory.api import stock\n\ndef remaining(qty):\n    return stock() - qty\n\ndef place(qty):\n    return remaining(qty)\n')

    def verify(self):
        return project.run(self.root, self.config_path, self.base / 'after', 'verify', self.base / 'before')

    def test_multiple_src_roots_resolve_actual_imports(self):
        row = workspace.analyze(self.root, self.config, ['packages/inventory/src/inventory/api.py'])
        self.assertEqual(row['result'], 'PASS')
        self.assertEqual(row['impact']['affected'], ['inventory', 'sales'])
        self.assertEqual(row['package_edges'][0]['target'], 'inventory.api')

    def test_package_cycle_without_module_cycle(self):
        self.put('packages/inventory/src/inventory/other.py', 'from sales.api import place\n')
        self.config['packages'][1]['allow'] = ['sales']
        codes = [f['code'] for f in workspace.analyze(self.root, self.config)['findings']]
        self.assertIn('PACKAGE_CYCLE', codes)
        self.assertNotIn('MODULE_CYCLE', codes)

    def test_private_cross_package_import_fails(self):
        self.put('packages/inventory/src/inventory/internal.py', 'x = 1\n')
        self.put('packages/sales/src/sales/api.py', 'from inventory.internal import x\n')
        self.assertIn('PRIVATE_API', [f['code'] for f in workspace.analyze(self.root, self.config)['findings']])

    def test_duplicate_import_names_rejected(self):
        self.config['packages'][1]['imports'].append(dict(path='packages/inventory/src', prefix=''))
        with self.assertRaises(workspace.ProjectError):
            workspace.analyze(self.root, self.config)

    def test_relative_import_and_namespace(self):
        self.put('packages/sales/src/sales/internal.py', 'from .api import place\n')
        self.assertEqual(workspace.analyze(self.root, self.config)['result'], 'PASS')

    def test_unknown_import_never_silently_passes(self):
        self.put('packages/sales/src/sales/plugin.py', 'import missing_plugin\n')
        row = workspace.analyze(self.root, self.config)
        self.assertEqual(row['result'], 'FAIL')
        self.assertTrue(row['impact']['full_validation_required'])

    def test_dynamic_exception_widens_impact(self):
        self.put('packages/sales/src/sales/plugin.py', 'import importlib\nx = importlib.import_module("inventory.api")\n')
        self.config['dynamic_import_exceptions'] = [dict(module='sales.plugin', reason='Known plugin loader; declared edge and all jobs cover it')]
        row = workspace.analyze(self.root, self.config, ['packages/sales/src/sales/api.py'])
        self.assertEqual(row['result'], 'PASS')
        self.assertTrue(row['review_notes'])
        self.assertEqual(row['impact']['affected'], ['inventory', 'sales'])

    def test_shared_data_and_events_propagate_impact(self):
        self.config['data_resources'] = [dict(name='stock', readers=['sales'], writers=['inventory'], paths=['migrations/*'], evidence='documented stock ownership')]
        row = workspace.analyze(self.root, self.config, ['migrations/001.sql'])
        self.assertEqual(row['impact']['affected'], ['inventory', 'sales'])
        self.assertFalse(row['impact']['unclassified_changes'])

    def test_unknown_changed_file_selects_all_packages(self):
        row = workspace.analyze(self.root, self.config, ['settings.ini'])
        self.assertTrue(row['impact']['full_validation_required'])
        self.assertEqual(row['impact']['affected'], ['inventory', 'sales'])

    def test_actual_native_tests_before_after(self):
        self.assertEqual(self.baseline()['result'], 'PASS')
        self.refactor()
        self.assertEqual(self.verify()['result'], 'PASS')

    def test_noop_not_accepted(self):
        self.baseline()
        row = self.verify()
        self.assertEqual(row['result'], 'FAIL')
        self.assertEqual(next(c for c in row['checks'] if c['id'] == 'nonempty-change')['result'], 'FAIL')

    def test_tests_pass_but_goal_not_done_fails(self):
        self.baseline()
        self.put('packages/sales/src/sales/api.py', 'from inventory.api import stock\n\ndef place(qty):\n    """Only a comment change."""\n    return stock() - qty\n')
        row = self.verify()
        self.assertEqual(row['jobs'][0]['result'], 'PASS')
        self.assertEqual(row['result'], 'FAIL')

    def test_removed_or_modified_acceptance_cannot_pass(self):
        self.baseline(); self.refactor()
        self.put('tests/test_order.py', 'import unittest\nclass Fake(unittest.TestCase):\n    def test_true(self):\n        pass\n')
        row = self.verify()
        self.assertEqual(row['result'], 'FAIL')
        self.assertEqual(next(c for c in row['checks'] if c['id'] == 'protected-tests')['result'], 'FAIL')
        self.assertEqual(next(c for c in row['checks'] if c['id'] == 'regression-regression')['result'], 'FAIL')

    def test_real_behavior_regression_fails(self):
        self.baseline(); self.refactor()
        self.put('packages/inventory/src/inventory/api.py', 'def stock():\n    return 0\n')
        self.assertEqual(self.verify()['result'], 'FAIL')

    def test_config_changes_invalidate_baseline(self):
        self.baseline(); self.refactor()
        self.config['goals'] = []; self.save()
        with self.assertRaises(workspace.ProjectError):
            self.verify()

    def test_junit_skip_and_empty_cannot_pass(self):
        path = self.base / 'junit.xml'
        path.write_text('<testsuite tests="1" skipped="1"><testcase classname="C" name="x"><skipped/></testcase></testsuite>')
        self.assertEqual(project.evidence(path, 'junit'), {'C::x': 'FAIL'})
        path.write_text('<testsuite tests="0"/>')
        with self.assertRaises(workspace.ProjectError):
            project.evidence(path, 'junit')

    def test_junit_declared_tests_cannot_disappear(self):
        path = self.base / 'junit.xml'
        path.write_text('<testsuite tests="2"><testcase name="only-one"/></testsuite>')
        with self.assertRaises(workspace.ProjectError):
            project.evidence(path, 'junit')

    def test_external_evaluator_change_invalidates_baseline(self):
        evaluator = self.base / 'acceptance.py'; evaluator.write_text('pass\n')
        self.config['evaluator_files'] = [str(evaluator)]; self.save()
        self.baseline(); self.refactor(); evaluator.write_text('changed = True\n')
        with self.assertRaises(workspace.ProjectError):
            self.verify()

    def test_inherited_architecture_does_not_allow_new_violation(self):
        self.put('packages/sales/src/sales/legacy.py', 'import old_unknown\n')
        self.config['architecture_policy'] = 'no_new_violations'; self.save()
        self.baseline(); self.refactor()
        self.put('packages/sales/src/sales/new.py', 'import new_unknown\n')
        row = self.verify()
        check = next(c for c in row['checks'] if c['id'] == 'architecture')
        self.assertEqual(check['result'], 'FAIL')
        self.assertEqual(len(check['reason']), 1)
        self.assertIn('new_unknown', str(check['reason']))

    def test_duplicate_junit_ids_rejected(self):
        path = self.base / 'junit.xml'
        path.write_text('<testsuite><testcase name="x"/><testcase name="x"/></testsuite>')
        with self.assertRaises(workspace.ProjectError):
            project.evidence(path, 'junit')

    def test_zero_exit_without_evidence_fails(self):
        self.config['jobs'][0]['argv'] = ['{python}', '-c', 'pass']; self.save()
        self.assertEqual(self.baseline()['result'], 'FAIL')

    def test_timeout_fails(self):
        self.config['jobs'][0].update(argv=['{python}', '-c', 'while True: pass'], timeout=0.1); self.save()
        self.assertEqual(self.baseline()['result'], 'FAIL')

    def test_external_native_adapter_is_explicit(self):
        self.config['packages'] = [dict(name='java', root='packages', language='native')]
        row = workspace.analyze(self.root, self.config)
        self.assertEqual(row['scope']['native_packages'], ['java'])
        self.assertEqual(row['scope']['modules'], 0)

    def test_service_teardown_runs_after_job_failure(self):
        marker = self.base / 'stopped'
        self.config['services'] = [dict(id='fixture', start=['{python}', '-c', 'pass'], stop=['{python}', '-c', 'from pathlib import Path;Path('+repr(str(marker))+').touch()'])]
        self.config['jobs'][0]['argv'] = ['{python}', '-c', 'raise SystemExit(1)']; self.save()
        self.assertEqual(self.baseline()['result'], 'FAIL')
        self.assertTrue(marker.exists())

    def test_deep_dependency_graph_no_recursion_error(self):
        graph = {str(i): {str(i+1)} for i in range(2500)}; graph['2500'] = {'0'}
        self.assertTrue(workspace.cycles(graph))

    def test_traversal_rejected(self):
        self.config['packages'][0]['root'] = '../outside'
        with self.assertRaises(workspace.ProjectError):
            workspace.validate(self.config, self.root)


if __name__ == '__main__':
    unittest.main()
