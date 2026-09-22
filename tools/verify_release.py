"""Verify and execute a trusted release in a clean temporary installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

from build_release import MANIFEST, read_names, safe_name


def unpack(archive, destination):
    """Validate all members before writing any; hashes check integrity, not identity."""
    archive = Path(archive)
    checksum = archive.with_suffix('.zip.sha256')
    expected = checksum.read_text(encoding='utf-8').strip().split()
    if expected != [hashlib.sha256(archive.read_bytes()).hexdigest(), archive.name]:
        raise ValueError('Archive checksum mismatch')
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if not names or len(names) != len(set(names)):
            raise ValueError('Empty archive or duplicate members')
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ValueError('Archive requires one root directory')
        prefix = roots.pop()
        if not re.fullmatch(r'ddd-python-skill-\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?', prefix):
            raise ValueError('Unexpected archive root')
        contents = {}
        for info in bundle.infolist():
            relative = info.filename[len(prefix) + 1:]
            safe_name(relative)
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Release contains a directory entry or symbolic link')
            contents[relative] = bundle.read(info)
        manifest = json.loads(contents.pop(MANIFEST))
        if prefix != 'ddd-python-skill-' + manifest['version']:
            raise ValueError('Version does not match archive root')
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
        if hashes != manifest['files']:
            raise ValueError('Member hashes or inventory mismatch')
        if read_names(contents['release-files.txt'].decode()) != sorted(contents):
            raise ValueError('Release list does not match archive contents')
        if contents['VERSION'].decode().strip() != manifest['version']:
            raise ValueError('VERSION does not match manifest')
        if contents['LICENSE'] != contents['ddd-python/LICENSE']:
            raise ValueError('Installed license mismatch')
        target = Path(destination) / prefix
        target.mkdir(parents=True, exist_ok=False)
        for name, data in contents.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return target


def run(argv, cwd, env):
    result = subprocess.run([str(arg) for arg in argv], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=180)
    if result.returncode:
        raise ValueError('Command failed:\n' + result.stdout)
    return result.stdout


def verify(archive):
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONOPTIMIZE', 'PYTHONHOME'):
        env.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    with tempfile.TemporaryDirectory(prefix='ddd clean release ') as tmp:
        base = Path(tmp)
        root = unpack(archive, base / 'unpacked')
        skills = base / 'installed skills'
        unrelated = base / 'unrelated working directory'
        unrelated.mkdir()
        install = [sys.executable, '-B', root / 'tools/install_skill.py', '--skills-dir', skills]
        run(install, unrelated, env)
        installed = skills / 'ddd-python'
        # Compare the full installed tree before executing anything from it.
        source_files = {p.relative_to(root / 'ddd-python'): p.read_bytes()
                        for p in (root / 'ddd-python').rglob('*') if p.is_file()}
        actual = {p.relative_to(installed): p.read_bytes() for p in installed.rglob('*') if p.is_file()}
        if actual != source_files:
            raise ValueError('Installed contents differ from bundled skill')
        repeated = subprocess.run([str(a) for a in install], cwd=unrelated, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        if repeated.returncode == 0:
            raise ValueError('Installer overwrote an existing skill')
        if actual != {p.relative_to(installed): p.read_bytes() for p in installed.rglob('*') if p.is_file()}:
            raise ValueError('Repeated installation modified files')
        output = run([sys.executable, '-B', installed / 'scripts/check.py', '--self-test'], unrelated, env)
        tests = json.loads(output)
        if (tests.get('fatal') or not tests.get('count')
                or len(tests['outcomes']) != tests['count']
                or any(row['status'] != 'passed' for row in tests['outcomes'].values())):
            raise ValueError('Self-test evidence is incomplete')
        report = base / 'example.json'
        run([sys.executable, '-B', installed / 'scripts/check.py', '--all', '--json', report], unrelated, env)
        example = json.loads(report.read_text(encoding='utf-8'))
        if example['exit_code'] or any(value != 'passed' for value in example['checks'].values()):
            raise ValueError('Example validation failed')
        run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', root / 'tests', '-v'], unrelated, env)
        return dict(result='PASS', tool_tests=tests['count'],
                    example_tests=example['test_results']['count'],
                    installed_files=len(actual), overwrite_protection='PASS',
                    packaging_tests='PASS', python=sys.version.split()[0], platform=sys.platform)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.archive.resolve()), indent=2))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        parser.exit(1, 'FAIL: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
