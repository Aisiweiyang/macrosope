"""Public source archives must exclude runtime data and reject unsafe inputs."""
from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare_release", Path(__file__).resolve().parents[1] / "scripts" / "prepare_release.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_public_archive_excludes_user_data_and_unreviewed_samples(tmp_path):
    root = tmp_path / "source"
    for name in release.PUBLIC_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "macrosope"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    for name in ("data/private.csv", "venv/secret.py", "sample_data/personal.csv", ".env"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("must never be published", encoding="utf-8")
    manifest = release.inspect_files(root, release.public_files(root))
    archive = release.build_release(root, tmp_path / "dist", manifest)
    with zipfile.ZipFile(archive) as bundle:
        assert len(bundle.namelist()) == len(release.PUBLIC_FILES)
        assert all(".." not in Path(name).parts for name in bundle.namelist())
        assert not any("private" in name or "personal" in name or "/venv/" in name
                       for name in bundle.namelist())
    recorded = json.loads(archive.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert recorded["files"] == manifest


def test_public_check_rejects_private_key_without_printing_it(tmp_path):
    path = tmp_path / "leak.md"
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    path.write_text(marker + "\nsensitive payload", encoding="utf-8")
    with pytest.raises(ValueError, match="private key") as exc:
        release.inspect_files(tmp_path, [path])
    assert "sensitive payload" not in str(exc.value)


def test_public_check_rejects_missing_required_files(tmp_path):
    with pytest.raises(ValueError, match="Missing or unsafe public file"):
        release.public_files(tmp_path)
