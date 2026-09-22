"""Install the bundled skill locally, without networking or overwriting."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def install(skills_dir, source=None):
    source = Path(source) if source is not None else ROOT / 'ddd-python'
    if not (source / 'SKILL.md').is_file() or not (source / 'LICENSE').is_file():
        raise ValueError('Skill entrypoint or license is missing')
    if source.is_symlink() or any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('Skill source must not contain symbolic links')
    parent = Path(skills_dir).expanduser().resolve()
    destination = parent / 'ddd-python'
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Existing skill left unchanged: ' + str(destination))
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ddd-install-', dir=str(parent)) as tmp:
        staged = Path(tmp) / 'ddd-python'
        shutil.copytree(source, staged,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Existing skill left unchanged: ' + str(destination))
        staged.rename(destination)
    return destination


def main():
    default = Path(os.environ.get('CODEX_HOME') or str(Path.home() / '.codex')) / 'skills'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, default=default)
    args = parser.parse_args()
    try:
        print('Installed:', install(args.skills_dir))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
