"""Exercise verification using tiny compressed fixtures, never a full image."""
import contextlib
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from config import load

spec = importlib.util.spec_from_file_location('verify_artifacts', ROOT / 'scripts/verify-artifacts.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        config, sources = load()
        lock = json.loads((ROOT / 'configs/packages.lock.json').read_text())
        name = config['output_image_name']
        self.image = self.directory / f'{name}.img.xz'
        self.info = self.directory / f'{name}.build-info.json'
        self.manifest = self.directory / f'{name}.sha256'
        self.image.write_bytes(lzma.compress(b'disposable artifact integrity fixture'))
        self.metadata = {
            'schema_version': 1, 'piforge_commit': 'a' * 40,
            'target_architecture': 'arm64', 'build_architecture': 'aarch64',
            'validation': {'build_time': 'passed', 'physical_pi5': 'not_run'},
            'reproducibility': {'base_and_git_sources_pinned': True, 'package_versions_locked': True},
            'build_configuration': config, 'source_lock': sources, 'package_lock': lock,
            'retropie_setup_commit': config['retropie_commit'],
            'base_image': {key: config[key] for key in
                           ('base_image_version', 'base_image_url', 'base_image_sha256', 'os_release')},
            'packages': [{'name': key, 'version': value, 'status': 'installed'}
                         for key, value in lock['packages'].items()],
            'emulators': {key: {**sources['sources'][key], 'binary_sha256': 'b' * 64}
                          for key in config['emulators']},
            'emulationstation': sources['sources']['emulationstation'],
        }
        self.write_manifest()

    def write_manifest(self):
        self.info.write_text(json.dumps(self.metadata))
        self.manifest.write_text(''.join(
            f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
            for path in (self.image, self.info)))

    def verify(self, commit=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return verifier.verify(self.directory, commit)

    def test_valid_artifact_and_expected_commit(self):
        self.assertEqual(self.verify('a' * 40), self.metadata)
        with self.assertRaisesRegex(ValueError, 'Unexpected PiForge commit'):
            self.verify('c' * 40)

    def test_checksum_detects_corruption(self):
        self.image.write_bytes(self.image.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            self.verify()

    def test_truncated_stream_fails_even_with_matching_checksum(self):
        self.image.write_bytes(self.image.read_bytes()[:-8])
        self.write_manifest()
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()

    def test_rejects_missing_duplicate_and_path_traversal_entries(self):
        original = self.manifest.read_text()
        invalid = [original.splitlines()[0] + '\n', original + original.splitlines()[0] + '\n',
                   original.replace(self.image.name, '../outside.img.xz')]
        for value in invalid:
            with self.subTest(value=value):
                self.manifest.write_text(value)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_rejects_symlink_artifact(self):
        moved = self.directory / 'other.xz'
        self.image.rename(moved)
        self.image.symlink_to(moved.name)
        with self.assertRaisesRegex(ValueError, 'Missing/unsafe artifact'):
            self.verify()

    def test_rejects_bootstrap_package_drift_and_missing_emulator(self):
        original = json.dumps(self.metadata)
        for change in ('bootstrap', 'packages', 'emulators', 'source'):
            self.metadata = json.loads(original)
            if change == 'bootstrap':
                self.metadata['reproducibility']['package_versions_locked'] = False
            elif change == 'packages':
                self.metadata['packages'].pop()
            elif change == 'emulators':
                self.metadata['emulators'].pop('lr-mgba')
            else:
                self.metadata['emulators']['lr-mgba']['commit'] = 'c' * 40
            self.write_manifest()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify()


if __name__ == '__main__':
    unittest.main()
