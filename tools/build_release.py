"""Build a reproducible ZIP from an explicit list; no benchmark snapshots."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'RELEASE-MANIFEST.json'


def safe_name(value):
    path = PurePosixPath(value)
    if (not value or not path.parts or '\\' in value or ':' in value or path.is_absolute()
            or '..' in path.parts or path.as_posix() != value):
        raise ValueError('Invalid release path: ' + value)
    if path.parts[0] in ('benchmarks', 'validation', 'dist', '.git'):
        raise ValueError('Development-only path in release: ' + value)
    if any(part in ('__pycache__', '.DS_Store', '.env') or part.startswith('.env.')
           for part in path.parts) or path.suffix in ('.pyc', '.pem', '.key'):
        raise ValueError('Local or generated file in release: ' + value)
    return path


def read_names(text):
    names = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if not names or len(names) != len(set(names)):
        raise ValueError('Release list is empty or contains duplicates')
    for name in names:
        safe_name(name)
    return sorted(names)


def payload(root):
    root = Path(root).resolve()
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?', version):
        raise ValueError('Invalid VERSION')
    names = read_names((root / 'release-files.txt').read_text(encoding='utf-8'))
    required = {'VERSION', 'LICENSE', 'README.md', 'release-files.txt',
                'ddd-python/SKILL.md', 'ddd-python/LICENSE',
                'tools/install_skill.py', 'tools/build_release.py', 'tools/verify_release.py'}
    if not required.issubset(names) or MANIFEST in names:
        raise ValueError('Release list omits required files or lists generated manifest')
    files = {}
    for name in names:
        path = root.joinpath(*safe_name(name).parts)
        if any(p.is_symlink() for p in (path, *path.parents) if p != root):
            raise ValueError('Symbolic link in release path: ' + name)
        if not path.is_file():
            raise ValueError('Missing release file: ' + name)
        files[name] = path.read_bytes()
    if files['LICENSE'] != files['ddd-python/LICENSE']:
        raise ValueError('Root and installed skill licenses differ')
    return version, files


def build(root, output):
    version, files = payload(root)
    manifest = dict(version=version, files={name: hashlib.sha256(data).hexdigest()
                                         for name, data in files.items()})
    files[MANIFEST] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    prefix = 'ddd-python-skill-' + version
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / (prefix + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + '/' + name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    try:
        print('Built:', build(ROOT, args.output))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
