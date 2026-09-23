#!/usr/bin/env python3
"""Verify one completed, locked build against this checkout's recipe."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from config import load, require
from packages import compare_packages, validate_lock


def verify(directory, expected_commit=None):
    config, sources = load()
    name = config['output_image_name']
    expected_files = {f'{name}.img.xz', f'{name}.build-info.json'}
    manifest = directory / f'{name}.sha256'
    require(manifest.is_file() and not manifest.is_symlink(), 'Missing/unsafe checksum manifest')
    entries = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        require(match is not None, 'Malformed checksum entry')
        digest, filename = match.groups()
        require(filename in expected_files and filename not in entries,
                'Unexpected or duplicate checksum filename')
        entries[filename] = digest
    require(set(entries) == expected_files, 'Checksum manifest must cover image and metadata')
    for filename, digest in entries.items():
        path = directory / filename
        require(path.is_file() and not path.is_symlink(), f'Missing/unsafe artifact: {filename}')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(actual == digest, f'Checksum mismatch: {filename}')

    metadata = json.loads((directory / f'{name}.build-info.json').read_text())
    require(metadata['schema_version'] == 1, 'Unsupported metadata schema')
    require(re.fullmatch(r'[0-9a-f]{40}', metadata['piforge_commit']), 'Invalid PiForge commit')
    if expected_commit is not None:
        require(metadata['piforge_commit'] == expected_commit, 'Unexpected PiForge commit')
    require(metadata['target_architecture'] == 'arm64'
            and metadata['build_architecture'] == 'aarch64', 'Wrong architecture')
    require(metadata['validation']['build_time'] == 'passed', 'Build checks did not pass')
    for key in ('base_and_git_sources_pinned', 'package_versions_locked'):
        require(metadata['reproducibility'][key] is True, f'Unpinned build: {key}')
    require(metadata['build_configuration'] == config and metadata['source_lock'] == sources,
            'Artifact recipe differs from this checkout')
    require(metadata['retropie_setup_commit'] == config['retropie_commit'], 'RetroPie pin mismatch')
    require(metadata['base_image'] == {key: config[key] for key in
            ('base_image_version', 'base_image_url', 'base_image_sha256', 'os_release')},
            'Base image pin mismatch')
    package_lock = json.loads((Path(__file__).resolve().parents[1] / 'configs/packages.lock.json').read_text())
    validate_lock(package_lock)
    require(metadata['package_lock'] == package_lock, 'Package lock differs from this checkout')
    installed = [item for item in metadata['packages'] if item['status'] == 'installed']
    actual_packages = {item['name']: item['version'] for item in installed}
    require(len(actual_packages) == len(installed), 'Duplicate installed package records')
    compare_packages(package_lock['packages'], actual_packages)
    require(set(metadata['emulators']) == set(config['emulators']), 'Emulator inventory mismatch')
    for module, record in metadata['emulators'].items():
        require(all(record.get(key) == value for key, value in sources['sources'][module].items()),
                f'Emulator pin mismatch: {module}')
        require(re.fullmatch(r'[0-9a-f]{64}', record['binary_sha256']), f'Invalid binary digest: {module}')
    require(metadata['emulationstation'] == sources['sources']['emulationstation'],
            'EmulationStation pin mismatch')
    subprocess.run(['xz', '--test', str(directory / f'{name}.img.xz')], check=True)
    print(f"PASS artifact checksums, XZ integrity and locked provenance: {metadata['piforge_commit']}")
    print(f"Physical Pi 5 validation: {metadata['validation']['physical_pi5']}")
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--expected-commit', help='Require this exact PiForge source commit')
    args = parser.parse_args()
    verify(args.directory.resolve(), args.expected_commit)
