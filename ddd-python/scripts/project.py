"""PASS/FAIL project acceptance: inspect, freeze baseline, then verify saved changes.

Commands execute trusted project code. This runner is not a security sandbox.
"""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from workspace import ProjectError, analyze, goals, inside, inventory, match, read, sha, validate

ENGINE = Path(__file__).resolve().parent


def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def engine_hash(config=None):
    values = {name: sha(ENGINE / name) for name in ('project.py', 'workspace.py', 'test_runner.py')}
    for name in (config or {}).get('evaluator_files', []):
        values[str(Path(name).resolve())] = sha(name)
    return values


def finding_key(value):
    """Moving line numbers alone does not turn an inherited issue into new debt."""
    if isinstance(value, dict):
        return {key: finding_key(item) for key, item in value.items() if key != 'line'}
    if isinstance(value, list):
        return [finding_key(item) for item in value]
    return value


def evidence(path, kind):
    """An exit code alone never counts as test execution evidence."""
    records = {}
    def add(key, status):
        if not key or key in records:
            raise ProjectError('Missing or duplicate test/check ID: ' + key)
        records[key] = status
    if kind == 'junit':
        try:
            tree = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ProjectError('Invalid JUnit evidence: ' + str(exc))
        cases = list(tree.iter('testcase'))
        for case in cases:
            if not case.get('name'):
                raise ProjectError('JUnit testcase is missing its name')
            key = case.get('classname', '') + '::' + case.get('name', '')
            status = 'FAIL' if any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped')) else 'PASS'
            add(key, status)
        for suite in tree.iter('testsuite'):
            if suite.get('tests') is not None and int(suite.get('tests')) != len(list(suite.iter('testcase'))):
                raise ProjectError('JUnit testcase count does not match declared total')
            # Frameworks sometimes record setup/discovery failures outside testcase.
            if suite.find('error') is not None or suite.find('failure') is not None:
                raise ProjectError('JUnit suite-level failure')
            for key in ('failures', 'errors', 'skipped'):
                if int(suite.get(key, '0')) and all(v == 'PASS' for v in records.values()):
                    raise ProjectError('JUnit totals report ' + key)
    elif kind == 'unittest':
        data = read(path)
        if data.get('fatal') or not data.get('count'):
            raise ProjectError('Unittest did not complete: ' + str(data.get('fatal')))
        for key, row in data['outcomes'].items():
            add(key, 'PASS' if row['status'] == 'passed' else 'FAIL')
        if len(records) != data['count']:
            raise ProjectError('Unittest evidence count mismatch')
    elif kind == 'checks':
        for row in read(path)['checks']:
            if row['result'] not in ('PASS', 'FAIL'):
                raise ProjectError('Check result must be PASS or FAIL')
            add(row['id'], row['result'])
    else:
        raise ProjectError('Unknown evidence format')
    if not records:
        raise ProjectError('No tests or assertions executed')
    return records


def command(argv, cwd, timeout, log, variables, environment=None):
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ProjectError('Timeout must be positive and finite')
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ProjectError('Commands require argv lists, never shell strings')
    # Replace only supported placeholders; preserve braces in code arguments.
    def expand(value):
        for key, replacement in variables.items():
            value = value.replace('{' + key + '}', str(replacement))
        return value
    argv = [expand(a) for a in argv]
    env = os.environ.copy(); env.pop('PYTHONOPTIMIZE', None)
    env.update({key: expand(value) for key, value in (environment or {}).items()})
    start = time.monotonic()
    with Path(log).open('w', encoding='utf-8') as stream:
        try:
            process = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=os.name == 'posix')
        except OSError as exc:
            stream.write(str(exc))
            return dict(result='FAIL', reason_code='ENVIRONMENT', reason=str(exc), exit_code=None)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()
            return dict(result='FAIL', reason_code='TIMEOUT', exit_code=None)
    return dict(result='PASS' if code == 0 else 'FAIL', exit_code=code,
                reason_code=None if code == 0 else 'COMMAND_FAILED', seconds=round(time.monotonic() - start, 3))


def run_jobs(root, config, output, phase):
    jobs = [j for j in config['jobs'] if phase == 'after' or j['phase'] == 'both']
    results, services, lifecycle = [], [], []
    variables = dict(project=root, artifacts=output, python=sys.executable, skill=ENGINE.parent)
    try:
        for index, service in enumerate(config.get('services', [])):
            row = command(service['start'], root, service.get('timeout', 120), output / ('service-%d-start.log' % index), variables)
            lifecycle.append(dict(id=service['id'], phase='start', **row))
            if row['result'] != 'PASS':
                raise ProjectError('Service failed to start: ' + service['id'])
            services.append((index, service))
            if service.get('ready'):
                row = command(service['ready'], root, service.get('timeout', 120), output / ('service-%d-ready.log' % index), variables)
                lifecycle.append(dict(id=service['id'], phase='ready', **row))
                if row['result'] != 'PASS':
                    raise ProjectError('Service readiness failed: ' + service['id'])
        for job in jobs:
            directory = output / job['id']; directory.mkdir()
            path = directory / ('evidence.xml' if job['format'] == 'junit' else 'evidence.json')
            print('Running:', job['id'], flush=True)
            row = command(job['argv'], inside(root, job.get('cwd', '.')), job.get('timeout', 300), directory / 'output.log',
                          dict(variables, evidence=path), job.get('env'))
            row.update(id=job['id'], phase=job['phase'], evidence=str(path), records={})
            try:
                row['records'] = evidence(path, job['format'])
                if any(value != 'PASS' for value in row['records'].values()):
                    row.update(result='FAIL', reason_code='TEST_FAILURE_OR_SKIP')
            except (ProjectError, KeyError, TypeError, ValueError) as exc:
                row.update(result='FAIL', reason_code='INCOMPLETE_EVIDENCE', reason=str(exc))
            results.append(row)
    except ProjectError as exc:
        lifecycle.append(dict(result='FAIL', reason_code='ENVIRONMENT', reason=str(exc)))
    finally:
        for index, service in reversed(services):
            row = command(service['stop'], root, service.get('timeout', 120), output / ('service-%d-stop.log' % index), variables)
            lifecycle.append(dict(id=service['id'], phase='stop', **row))
    for job in jobs:
        if not any(r['id'] == job['id'] for r in results):
            results.append(dict(id=job['id'], phase=job['phase'], result='FAIL', reason_code='NOT_EXECUTED', records={}))
    return results, lifecycle


def protected_files(root, config):
    values = {}
    for pattern in config.get('protected_paths', []):
        if Path(pattern).is_absolute() or '..' in Path(pattern).parts:
            raise ProjectError('Invalid protected path pattern')
        for path in root.glob(pattern):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                inside(root, str(path.relative_to(root)))
                values[str(path.relative_to(root))] = sha(path)
    return values


def render(report):
    lines = ['# 项目重构验收', '', '**' + report['result'] + '**', '', '阶段：`' + report['phase'] + '`。不计算分数或通过率。', '',
             '| 检查 | 结果 | 原因 |', '|---|---|---|']
    for row in report.get('checks', []):
        lines.append('| %s | %s | %s |' % (row['id'], row['result'], str(row.get('reason', row.get('reason_code') or '')).replace('|', '/').replace('\n', ' ')))
    for job in report.get('jobs', []):
        lines.append('| %s | %s | %s |' % (job['id'], job['result'], job.get('reason_code') or '实际执行，证据见 JSON'))
    lines += ['', '结论只适用于声明的源码、目标与测试环境；未自动证明领域边界或所有运行时依赖。']
    return '\n'.join(lines) + '\n'


def run(root, config_path, output, phase, baseline=None, changed=None):
    root, config_path, output = Path(root).resolve(), Path(config_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ProjectError('Refusing to overwrite evidence: ' + str(output))
    config = validate(read(config_path), root)
    if phase != 'inspect':
        if not config.get('jobs') or not any(j['phase'] == 'both' for j in config['jobs']):
            raise ProjectError('Native baseline/regression jobs are required')
        if not config.get('goals') and not any(j['phase'] == 'after' for j in config['jobs']):
            raise ProjectError('Explicit refactoring goals or after-phase acceptance required')
    output.mkdir(parents=True)
    config_hash, engine = sha(config_path), engine_hash(config)
    files, protected = inventory(root, config), protected_files(root, config)
    checks, previous = [], None
    if phase == 'verify':
        if baseline is None:
            raise ProjectError('verify requires --baseline')
        previous = read(Path(baseline) / 'report.json')
        if previous['phase'] != 'baseline' or previous['config_hash'] != config_hash or previous['engine'] != engine:
            raise ProjectError('Baseline/config/evaluator mismatch; prepare a fresh baseline')
        if previous['result'] != 'PASS':
            checks.append(dict(id='baseline', result='FAIL', reason='Baseline validation was incomplete or failed'))
        changed = sorted(name for name in files.keys() | previous['files'].keys() if files.get(name) != previous['files'].get(name))
        checks.append(dict(id='nonempty-change', result='PASS' if changed else 'FAIL', reason='' if changed else 'No tracked refactoring changes'))
        illegal = [name for name in changed if not match(name, config.get('allowed_changes', []))]
        checks.append(dict(id='change-scope', result='FAIL' if illegal else 'PASS', reason=', '.join(illegal)))
        checks.append(dict(id='protected-tests', result='PASS' if previous['protected_files'] == protected else 'FAIL', reason='Protected tests must match the baseline'))
    graph = analyze(root, config, changed)
    # Baseline records legacy architecture; the candidate must satisfy declared policy.
    if phase != 'baseline':
        findings = graph['findings']
        if phase == 'verify' and config.get('architecture_policy') == 'no_new_violations':
            inherited = [finding_key(f) for f in previous['architecture']['findings']]
            findings = [f for f in findings if finding_key(f) not in inherited]
            graph['inherited_findings'] = [f for f in graph['findings'] if finding_key(f) in inherited]
        checks.append(dict(id='architecture', result='FAIL' if findings else 'PASS', reason=findings))
    if phase == 'verify':
        checks.extend(goals(root, config.get('goals', [])))
    jobs, lifecycle = ([], []) if phase == 'inspect' else run_jobs(root, config, output, 'after' if phase == 'verify' else 'before')
    checks.extend(dict(id='service-' + str(i), **row) if 'id' not in row else dict(row, id='service-' + row['id'] + '-' + row['phase']) for i, row in enumerate(lifecycle))
    if previous:
        for old in previous['jobs']:
            new = next((j for j in jobs if j['id'] == old['id']), {'records': {}})
            missing = sorted(key for key, status in old['records'].items() if status == 'PASS' and new['records'].get(key) != 'PASS')
            checks.append(dict(id='regression-' + old['id'], result='FAIL' if missing else 'PASS', reason=missing))
    if inventory(root, config) != files or protected_files(root, config) != protected or sha(config_path) != config_hash or engine_hash(config) != engine:
        checks.append(dict(id='evidence-integrity', result='FAIL', reason='Source/config/evaluator changed during validation'))
    result = 'PASS' if all(r['result'] == 'PASS' for r in checks + jobs) else 'FAIL'
    report = dict(version=2, result=result, phase=phase, project=str(root), generated_at=datetime.now(timezone.utc).isoformat(),
                  config_hash=config_hash, engine=engine, files=files, protected_files=protected, architecture=graph,
                  checks=checks, jobs=jobs, semantic_scope='Only explicit executable acceptance; no LLM judge or design score.')
    write(output / 'report.json', report)
    (output / 'report.md').write_text(render(report), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('inspect', 'baseline', 'verify'))
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--changed', nargs='*')
    args = parser.parse_args()
    existed = args.output.exists()
    try:
        report = run(args.project, args.config, args.output, args.phase, args.baseline, args.changed)
        print(report['result'])
        return 0 if report['result'] == 'PASS' else 1
    except (ProjectError, OSError, KeyError, TypeError, ValueError) as exc:
        print('FAIL: validation incomplete:', exc, file=sys.stderr)
        if not existed:
            write(args.output / 'report.json', dict(result='FAIL', reason_code='CONFIGURATION', reason=str(exc)))
        return 2


if __name__ == '__main__':
    sys.exit(main())
