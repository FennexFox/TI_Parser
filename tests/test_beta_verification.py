import hashlib
import json
import sys
from pathlib import Path
import zipfile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_beta_distribution import extract_verified
from build_beta_distribution import REQUIRED_PATHS, RUNTIME_DATA


def archive(tmp_path, name, data, expected=None):
    target = tmp_path / 'test.zip'
    manifest = {'files': {name: {'sha256': hashlib.sha256(data if expected is None else expected).hexdigest()}}}
    with zipfile.ZipFile(target, 'w') as output:
        output.writestr('beta_manifest.json', json.dumps(manifest))
        output.writestr(name, data)
    return target


def test_rejects_tampered_bytes(tmp_path):
    target = archive(tmp_path, 'data/test.json', b'changed', b'original')
    with pytest.raises(ValueError, match='hash mismatch'):
        extract_verified(target, tmp_path / 'extract')


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside', 'dir\\outside'])
def test_rejects_unsafe_archive_paths(tmp_path, name):
    target = archive(tmp_path, name, b'bytes')
    with pytest.raises(ValueError, match='Unsafe ZIP path|Manifest membership mismatch'):
        extract_verified(target, tmp_path / 'extract')


@pytest.mark.parametrize('mutation', ['extra', 'missing'])
def test_rejects_self_consistent_wrong_distribution_membership(tmp_path, mutation):
    files = {name: b'{}' for name in REQUIRED_PATHS | {f'data/{name}' for name in RUNTIME_DATA}}
    files['data/catalog_manifest.json'] = b'{"catalogs": {}}'
    if mutation == 'extra':
        files['private-save.gz'] = b'private'
    else:
        del files['data/module_catalog.json']
    manifest = {'files': {name: {'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
    target = tmp_path / 'self-consistent.zip'
    with zipfile.ZipFile(target, 'w') as output:
        output.writestr('beta_manifest.json', json.dumps(manifest))
        for name, data in files.items():
            output.writestr(name, data)
    with pytest.raises(ValueError, match='Unexpected distribution file|Required distribution files missing'):
        extract_verified(target, tmp_path / 'extract')
