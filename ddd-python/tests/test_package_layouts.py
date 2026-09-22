"""Real package layouts and failures that must never look like a clean graph."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / 'scripts'))
from check import run_checks


class PackageLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ddd package layout ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repository'
        shutil.copytree(SKILL_ROOT / 'assets/order_example', self.root)

    def config(self, **values):
        path = self.root / 'architecture.json'
        data = json.loads(path.read_text())
        data.update(values)
        path.write_text(json.dumps(data))

    def add_import(self, statement):
        path = self.root / 'domain/order.py'
        path.write_text(path.read_text() + '\n' + statement + '\n')

    def codes(self, report):
        return {f['code'] for f in report['findings'] if f['status'] in ('failed', 'error')}

    def package(self, src=False):
        package = self.root / ('src/acme' if src else 'acme')
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('"""Application package."""\n')
        for name in ('domain', 'application', 'infrastructure'):
            shutil.move(str(self.root / name), package / name)
        for file in list(package.rglob('*.py')) + list((self.root / 'tests').rglob('*.py')):
            file.write_text(re.sub(r'from (domain|application|infrastructure)(\.| import)',
                                   r'from acme.\1\2', file.read_text()))
        app = package / 'application/confirm_order.py'
        app.write_text(app.read_text().replace('from acme.domain.', 'from ..domain.'))
        model = self.root / 'model.json'
        model.write_text(re.sub(r'"(domain|application|infrastructure)\.', r'"acme.\1.', model.read_text()))
        policy_path = self.root / 'architecture.json'
        policy = json.loads(policy_path.read_text())
        policy['source_roots'] = [str((package / n).relative_to(self.root))
                                  for n in ('domain', 'application', 'infrastructure')]
        for layer in policy['layers']:
            layer['prefix'] = 'acme.' + layer['prefix']
            layer['allow'] = ['acme.' + name for name in layer['allow']]
        policy['import_roots'] = [{'path': 'src' if src else '.', 'prefix': ''},
                                  {'path': 'tests', 'prefix': 'tests'}]
        policy_path.write_text(json.dumps(policy))
        return package

    def test_regular_package_relative_imports_and_traceability(self):
        self.package()
        report = run_checks(self.root)
        self.assertEqual(report['exit_code'], 0, report['findings'])
        self.assertEqual(report['test_results']['count'], 14)
        self.assertIn('acme.application.confirm_order', report['architecture_graph'])
        self.assertIn('acme.domain.repository', report['architecture_graph']['acme.application.confirm_order'])

    def test_src_mapping_preserves_qualified_symbols_without_importing_target(self):
        package = self.package(src=True)
        (package / '__init__.py').write_text('raise RuntimeError("Do not import target during indexing")')
        before = list(sys.path)
        report = run_checks(self.root, {'model', 'comments', 'architecture'})
        self.assertEqual(report['exit_code'], 0, report['findings'])
        self.assertEqual(sys.path, before)
        self.assertIn('acme.domain.order', report['scope']['source_modules'])

    def test_config_can_stay_inside_package_with_cli(self):
        package = self.package()
        docs = package / 'design'; docs.mkdir()
        for name in ('model.json', 'architecture.json'):
            shutil.move(str(self.root / name), docs / name)
        report_path = Path(self.temp.name) / 'report.json'
        result = subprocess.run([sys.executable, '-B', str(SKILL_ROOT / 'scripts/check.py'),
            '--project', str(self.root), '--model-file', 'acme/design/model.json',
            '--architecture-file', 'acme/design/architecture.json', '--all', '--json', str(report_path)],
            cwd=self.temp.name, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(report_path.read_text())['test_results']['count'], 14)

    def test_a_package_directory_can_be_the_project_with_explicit_prefix(self):
        package = self.package()
        for name in ('model.json', 'architecture.json', 'tests'):
            shutil.move(str(self.root / name), package / name)
        self.root = package
        self.config(source_roots=['domain', 'application', 'infrastructure'],
                    import_roots=[{'path': '.', 'prefix': 'acme'},
                                  {'path': 'tests', 'prefix': 'tests'}])
        report = run_checks(package, {'model', 'comments', 'architecture'})
        self.assertEqual(report['exit_code'], 0, report['findings'])
        self.assertIn('acme.domain.repository', report['architecture_graph']['acme.application.confirm_order'])

    def test_namespace_packages_keep_the_same_qualified_dependencies(self):
        package = self.package(src=True)
        for initializer in package.rglob('__init__.py'):
            initializer.unlink()
        report = run_checks(self.root, {'model', 'comments', 'architecture'})
        self.assertEqual(report['exit_code'], 0, report['findings'])
        self.assertIn('acme.domain.repository', report['architecture_graph']['acme.application.confirm_order'])

    def test_missing_mapping_does_not_fall_back_to_project_relative_names(self):
        self.package(src=True)
        self.config(import_roots=[{'path': 'tests', 'prefix': 'tests'}])
        self.assertEqual(run_checks(self.root, {'architecture'})['exit_code'], 2)

    def test_duplicate_import_names_are_rejected(self):
        self.config(import_roots=[{'path': 'domain', 'prefix': 'shared'},
                                  {'path': 'application', 'prefix': 'shared'},
                                  {'path': 'infrastructure', 'prefix': 'infrastructure'},
                                  {'path': 'tests', 'prefix': 'tests'}])
        self.assertEqual(run_checks(self.root, {'architecture'})['exit_code'], 2)

    def test_unknown_import_fails_closed(self):
        self.add_import('import omitted_dependency')
        report = run_checks(self.root, {'architecture'})
        self.assertIn('ARCH-UNKNOWN-IMPORT', self.codes(report))
        self.assertNotEqual(report['exit_code'], 0)

    def test_unscanned_local_file_is_not_an_external_library(self):
        (self.root / 'local_config.py').write_text('VALUE = 1\n')
        self.add_import('import local_config')
        self.config(external=['local_config'])
        self.assertIn('ARCH-OUTSIDE-SCOPE', self.codes(run_checks(self.root, {'architecture'})))

    def test_external_libraries_need_explicit_declaration(self):
        self.add_import('from vendor_package.api import Client')
        self.assertIn('ARCH-UNKNOWN-IMPORT', self.codes(run_checks(self.root, {'architecture'})))
        self.config(external=['vendor_package'])
        report = run_checks(self.root, {'architecture'})
        self.assertEqual(report['exit_code'], 0, report['findings'])

    def test_external_declaration_does_not_override_forbidden(self):
        self.add_import('import requests')
        self.config(external=['requests'])
        self.assertIn('ARCH-DEPENDENCY', self.codes(run_checks(self.root, {'architecture'})))

    def test_missing_local_module_does_not_resolve_to_parent_init(self):
        self.add_import('import domain.missing_child')
        report = run_checks(self.root, {'architecture'})
        self.assertIn('ARCH-UNKNOWN-IMPORT', self.codes(report))

    def test_unmatched_layer_is_an_error_even_if_other_layers_match(self):
        policy_path = self.root / 'architecture.json'
        policy = json.loads(policy_path.read_text())
        policy['layers'].append({'prefix': 'misspelled', 'allow': [], 'forbidden': []})
        policy_path.write_text(json.dumps(policy))
        self.assertIn('ARCH-EMPTY-LAYER', self.codes(run_checks(self.root, {'architecture'})))

    def test_namespace_from_parent_checks_the_child_dependency(self):
        package = self.package(src=True)
        (package / 'domain/order.py').write_text((package / 'domain/order.py').read_text()
                                               + '\nfrom .. import infrastructure\n')
        report = run_checks(self.root, {'architecture'})
        self.assertIn('ARCH-DEPENDENCY', self.codes(report))
        self.assertNotIn('ARCH-RELATIVE', self.codes(report))

    def test_star_import_does_not_pass_static_architecture(self):
        self.add_import('from domain.repository import *')
        self.assertIn('ARCH-STAR', self.codes(run_checks(self.root, {'architecture'})))

    def test_dynamic_import_is_a_failed_check(self):
        self.add_import('def _load(name):\n    return __import__(name)')
        self.assertIn('ARCH-DYNAMIC', self.codes(run_checks(self.root, {'architecture'})))

    def test_stdlib_is_allowed_but_locally_shadowed_stdlib_is_not(self):
        self.add_import('import pathlib')
        self.assertEqual(run_checks(self.root, {'architecture'})['exit_code'], 0)
        (self.root / 'pathlib.py').write_text('VALUE = 1\n')
        self.assertIn('ARCH-OUTSIDE-SCOPE', self.codes(run_checks(self.root, {'architecture'})))

    def test_source_symlink_escape_still_fails(self):
        outside = Path(self.temp.name) / 'outside'; outside.mkdir()
        (outside / 'secret.py').write_text('VALUE = 1\n')
        (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        self.config(source_roots=['linked'], import_roots=[{'path': 'linked', 'prefix': 'acme'}])
        self.assertEqual(run_checks(self.root, {'architecture'})['exit_code'], 2)


if __name__ == '__main__':
    unittest.main()
