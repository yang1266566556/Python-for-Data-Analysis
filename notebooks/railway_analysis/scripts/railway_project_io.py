"""Read historical records at the current project location without rewriting them."""
from pathlib import Path, PureWindowsPath
import hashlib
import json

PROJECT_DIR = Path(__file__).resolve().parents[1]
# This is a provenance prefix, never a fallback location for opening files.
ORIGINAL_PROJECT = PureWindowsPath(r"D:\yangz\大三上\机器学习\第二次作业\railway_analysis")
MIGRATION_MANIFEST = PROJECT_DIR / "provenance/migration_manifest.json"


def normalize_record(value):
    """Relocate recorded project paths in memory; leave dates and hashes intact."""
    if isinstance(value, dict):
        return {key: normalize_record(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_record(item) for item in value]
    if not isinstance(value, str):
        return value
    recorded = PureWindowsPath(value)
    if recorded.is_absolute() and recorded.is_relative_to(ORIGINAL_PROJECT):
        return str(PROJECT_DIR.joinpath(*recorded.relative_to(ORIGINAL_PROJECT).parts))
    if "\\" in value and recorded.parts and recorded.parts[0] in {
        "data", "config", "evidence", "environment", "scripts", "docs"
    }:
        return str(Path(*recorded.parts))
    return value


def read_project_json(path):
    """Read saved JSON without changing any source-file bytes or their hashes."""
    path = Path(normalize_record(str(path)))
    return normalize_record(json.loads(path.read_text(encoding="utf-8-sig")))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def script_hash_matches(path, expected):
    """Accept an exact script or its explicitly recorded, verified portable adaptation.

    Historical protocols reference the original script bytes. Adapted scripts and
    their original snapshots must both match the migration record. Data hashes
    continue to use the existing sha() functions and are never translated.
    """
    path = Path(path).resolve()
    actual = _sha(path)
    if actual == expected:
        return True
    if path.parent != (PROJECT_DIR / "scripts").resolve():
        return False
    manifest = json.loads(MIGRATION_MANIFEST.read_text(encoding="utf-8"))
    entry = manifest["adapted_scripts"].get(path.name)
    if entry is None:
        return False
    original = PROJECT_DIR / "provenance/original_scripts" / path.name
    return (
        actual == entry["runtime_sha256"]
        and expected == entry["original_sha256"]
        and _sha(original) == entry["original_sha256"]
    )


def script_hashes_match(actual, expected):
    """Compare a protocol's named script hashes against current verified scripts."""
    if actual.keys() != expected.keys():
        return False
    return all(
        digest == expected[name]
        or (digest == _sha(PROJECT_DIR / "scripts" / name)
            and script_hash_matches(PROJECT_DIR / "scripts" / name, expected[name]))
        for name, digest in actual.items()
    )


def check_runtime_sources():
    """Fail visibly if a copied script or portability helper changes unexpectedly."""
    manifest = json.loads(MIGRATION_MANIFEST.read_text(encoding="utf-8"))
    for relative, expected in manifest["runtime_files"].items():
        if _sha(PROJECT_DIR / relative) != expected:
            raise ValueError(f"作业运行代码与迁入记录不一致：{relative}。请复核改动及实验版本。")
    for name, record in manifest["adapted_scripts"].items():
        original = PROJECT_DIR / "provenance/original_scripts" / name
        if _sha(original) != record["original_sha256"]:
            raise ValueError(f"原脚本来源快照发生变化：{name}")
    return len(manifest["runtime_files"])
