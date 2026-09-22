"""Test distribution boundaries and preservation of an existing installation."""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_release import build, payload, read_names
from install_skill import install
from verify_release import unpack


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ddd distribution ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_reproducible_archive_excludes_unlisted_files(self):
        root = self.base / 'source'
        _, files = payload(ROOT)
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (root / 'private.txt').write_text('must not ship')
        first = build(root, self.base / 'first')
        second = build(root, self.base / 'second')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        extracted = unpack(first, self.base / 'extracted')
        self.assertFalse((extracted / 'private.txt').exists())
        self.assertFalse((extracted / 'benchmarks').exists())

    def test_release_list_rejects_escape_and_local_material(self):
        for name in ('.', '../secret', '/secret', 'a/../secret', 'a\\secret',
                     'benchmarks/file.py', '.env', 'ddd-python/.env.local', 'a.pyc'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                read_names(name)

    def test_installer_preserves_existing_directory(self):
        skills = self.base / 'skills'
        target = install(skills)
        sentinel = target / 'user-change.txt'
        sentinel.write_text('keep me')
        with self.assertRaises(FileExistsError):
            install(skills)
        self.assertEqual(sentinel.read_text(), 'keep me')

    def test_installer_rejects_source_symlink(self):
        source = self.base / 'skill'
        shutil.copytree(ROOT / 'ddd-python', source)
        (source / 'external').symlink_to(ROOT / 'LICENSE')
        with self.assertRaises(ValueError):
            install(self.base / 'skills', source)
        self.assertFalse((self.base / 'skills/ddd-python').exists())

    def test_builder_rejects_symlink_in_listed_file(self):
        root = self.base / 'source'
        _, files = payload(ROOT)
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (root / 'README.md').unlink()
        (root / 'README.md').symlink_to(ROOT / 'README.md')
        with self.assertRaises(ValueError):
            build(root, self.base / 'dist')

    def test_modified_member_is_rejected_even_with_updated_zip_checksum(self):
        archive = build(ROOT, self.base / 'dist')
        with zipfile.ZipFile(archive) as original:
            members = [(info, original.read(info)) for info in original.infolist()]
        with zipfile.ZipFile(archive, 'w') as modified:
            for info, data in members:
                modified.writestr(info, b'corrupted' if info.filename.endswith('/README.md') else data)
        archive.with_suffix('.zip.sha256').write_text(
            hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        with self.assertRaises(ValueError):
            unpack(archive, self.base / 'unpacked')
        self.assertFalse((self.base / 'unpacked').exists())


if __name__ == '__main__':
    unittest.main()
