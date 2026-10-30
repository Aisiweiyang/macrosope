"""Build a public source ZIP from an explicit allowlist, without user data.

Uses the Python standard library only. Run from any working directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILES = (
    ".gitattributes", ".gitignore", ".streamlit/config.toml", "AGENTS.md",
    "README.md", "LICENSE", "CONTRIBUTING.md", "CHANGELOG.md",
    "pyproject.toml", "requirements.txt", "requirements-dev.txt", "constraints.txt",
    "app.py", "运行.cmd", "sample_data/generate_sample_data.py",
    "sample_data/cpi_ppi_m2_wide.csv", "sample_data/gdp_investment_long.csv",
    "sample_data/social_finance_gbk.csv", "sample_data/macro_monthly.xlsx",
    "sample_data/population.json", "sample_data/trade.parquet",
)
PUBLIC_GLOBS = (
    "macrosope/**/*.py", "pages/*.py", "tests/*.py", "demo/*.py", "scripts/*.py",
    "docs/*.md", ".github/**/*.yml", ".github/**/*.md",
)
TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".yml", ".cmd", ".json", ".csv"}
SENSITIVE_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"),
    "API key": re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "personal home path": re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/]|/(?:Users|home)/)[^\s\"'<>]+"),
}


def public_files(root: Path) -> list[Path]:
    """Collect reviewed file types; reject symlinks and missing required files."""
    selected = {root / name for name in PUBLIC_FILES}
    for pattern in PUBLIC_GLOBS:
        selected.update(root.glob(pattern))
    result = []
    for path in sorted(selected):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts:
            continue
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
            raise ValueError(f"Symlink in public path: {relative.as_posix()}")
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Missing or unsafe public file: {relative.as_posix()}")
        result.append(path)
    return result


def inspect_files(root: Path, files: list[Path]) -> list[dict]:
    """Scan common secret formats without printing matching secret values."""
    manifest = []
    for path in files:
        data = path.read_bytes()
        if path.suffix.lower() in TEXT_SUFFIXES:
            encoding = "gbk" if path.name == "social_finance_gbk.csv" else "utf-8-sig"
            content = data.decode(encoding)
            for label, pattern in SENSITIVE_PATTERNS.items():
                if pattern.search(content):
                    raise ValueError(f"Review required ({label}): {path.relative_to(root).as_posix()}")
        manifest.append({
            "path": path.relative_to(root).as_posix(),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return manifest


def build_release(root: Path, output_dir: Path, manifest: list[dict]) -> Path:
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    prefix = f"{metadata['name']}-{metadata['version']}"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{prefix}-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for entry in manifest:
            data = (root / entry["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError(f"File changed during packaging: {entry['path']}")
            info = zipfile.ZipInfo(f"{prefix}/{entry['path']}")
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {archive.name}\n", encoding="utf-8"
    )
    archive.with_suffix(".manifest.json").write_text(
        json.dumps({"name": metadata["name"], "version": metadata["version"],
                    "archive_sha256": checksum, "files": manifest},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="inspect only; do not write a ZIP")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    manifest = inspect_files(ROOT, public_files(ROOT))
    print(f"Public source check passed: {len(manifest)} files; no user data directories included.")
    if not args.check:
        archive = build_release(ROOT, args.output_dir, manifest)
        print(f"Created: {archive.name} ({archive.stat().st_size:,} bytes)")
        print("Wrote per-file manifest and archive SHA256 alongside the ZIP.")


if __name__ == "__main__":
    main()
