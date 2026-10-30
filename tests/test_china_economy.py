"""中国经济交换协议：离线校验、预览、差异、审计与事务导入。"""
from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import duckdb
import pytest
from macrosope.db import Repository
from macrosope.services.china_economy import (
    INDICATOR_MAP,
    calculate_content_hash,
    default_exchange_directory,
    discover_exchange_file,
    import_exchange,
    preview_exchange,
)


def _analysis():
    return {
        "dimensions": {},
        "cycle": {"note": "指标框架，不是确定性预测"},
        "drivers": [],
        "risks": [],
        "correlation": {},
        "balances": [],
        "breadth": {},
    }


def _bundle(generated_at="2026-09-09T12:34:56+08:00", changes=None):
    changes = changes or {}
    observations = []
    metadata = []
    for index, (code, fixed) in enumerate(INDICATOR_MAP.items()):
        date = "2026-08-01"
        if code == "gdp":
            date = "2026-06-01"
        elif code == "lpr":
            date = "2026-08-20"
        value = changes.get(code, 4.7 if code == "cpi" else float(index + 1))
        observations.append({"indicator_code": code, "date": date, "value": value})
        scope = "按现有业务口径"
        if code == "exports":
            scope = "当前聚合历史序列为美元口径"
        if code == "lpr":
            scope = "按实际发布日期记录，不规范化日期"
        metadata.append(
            {
                "code": code,
                "name": fixed["name"],
                "definition": f"{fixed['name']}定义",
                "unit": fixed["unit"],
                "frequency": fixed["frequency"],
                "region": "中国",
                "source_org": "官方机构",
                "source_link": "https://example.invalid/metadata-only",
                "updated_at": generated_at,
                "dimension": fixed["dimension"],
                "nominal_or_real": None,
                "stock_or_flow": fixed.get("stock"),
                "period_or_cumulative": fixed["period"],
                "seasonally_adjusted": None,
                "scope_note": scope,
                "quality_score": 85.0,
                "technical_quality_score": 100.0,
                "provenance_quality_score": 40.0,
                "official_verified": False,
                "verification_state": "not_checked",
                "official_verification": {},
                "issues": [],
                "collection_state": "cache",
                "latest_date": date,
            }
        )
    body = {
        "schema_version": "1.0",
        "producer": "china-economy-analysis",
        "generated_at": generated_at,
        "source_status": {"mode": "cache"},
        "indicator_metadata": sorted(metadata, key=lambda item: item["code"]),
        "observations": sorted(observations, key=lambda item: (item["indicator_code"], item["date"])),
        "analysis": _analysis(),
    }
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    stamp = generated_at.replace("-", "").replace(":", "")[:15]
    return {
        "schema_version": body["schema_version"],
        "producer": body["producer"],
        "generated_at": body["generated_at"],
        "snapshot_id": f"cnmacro-{stamp}-{digest[:12]}",
        "content_hash": digest,
        "source_status": body["source_status"],
        "indicator_metadata": body["indicator_metadata"],
        "observations": body["observations"],
        "analysis": body["analysis"],
    }


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return path


def _resign(payload: dict) -> dict:
    payload = json.loads(json.dumps(payload, ensure_ascii=False))
    digest = calculate_content_hash(payload)
    payload["content_hash"] = digest
    stamp = payload["generated_at"].replace("-", "").replace(":", "")[:15]
    payload["snapshot_id"] = f"cnmacro-{stamp}-{digest[:12]}"
    return payload


def test_new_exchange_preview_and_mapping(tmp_path):
    preview = preview_exchange(_write(tmp_path / "bundle.json", _bundle()))
    assert preview.payload["schema_version"] == "1.0"
    assert len(preview.indicators) == 12
    assert len(preview.payload["observations"]) == 12
    assert preview.identity.content_hash == preview.payload["content_hash"]
    assert len(preview.identity.file_sha256) == 64


def test_default_path_is_dynamic_and_custom_directory_is_supported(tmp_path):
    project = tmp_path / "数据分析"
    assert default_exchange_directory(project) == tmp_path / "中国经济分析" / "output"
    custom = tmp_path / "自定义"
    custom.mkdir()
    versioned = _write(custom / "integration_20260909_123456.json", _bundle())
    assert discover_exchange_file(custom) == versioned


def test_discovery_prefers_versioned_then_latest_then_legacy(tmp_path):
    versioned = _write(tmp_path / "integration_20260909_123456.json", _bundle())
    _write(tmp_path / "integration_latest.json", _bundle())
    _write(
        tmp_path / "分析数据_20260909_1200.json",
        {"generated_at": "2026-09-09T12:00:00", "source_status": {}, "series": {"cpi": [{"date": "2026-08-01", "value": 1.0}]}, "analysis": _analysis()},
    )
    assert discover_exchange_file(tmp_path) == versioned
    versioned.unlink()
    assert discover_exchange_file(tmp_path).name == "integration_latest.json"
    (tmp_path / "integration_latest.json").unlink()
    assert discover_exchange_file(tmp_path).name.startswith("分析数据_")


def test_legacy_adapter_preserves_values_dates_and_file(tmp_path):
    path = _write(
        tmp_path / "分析数据_20260909_1200.json",
        {
            "generated_at": "2026-09-09T12:00:00",
            "source_status": {"indicators": []},
            "series": {
                "gdp": [{"date": "2026-06-01", "value": 5.0}],
                "lpr": [{"date": "2026-08-20", "value": 3.0}],
                "cpi": [{"date": "2026-08-01", "value": 4.7}],
                "investment": [{"date": "2026-08-01", "value": 2.1}],
            },
            "analysis": _analysis(),
        },
    )
    before = path.read_bytes()
    preview = preview_exchange(path)
    assert preview.payload["schema_version"] == "legacy-adapter-1.0"
    assert preview.payload["producer"] == "china-economy-analysis-legacy-adapter"
    assert preview.payload["snapshot_id"] == f"legacy-{preview.identity.file_sha256[:16]}"
    values = {(row["indicator_code"], row["date"]): row["value"] for row in preview.payload["observations"]}
    assert values[("cpi", "2026-08-01")] == 4.7
    assert values[("lpr", "2026-08-20")] == 3.0
    assert path.read_bytes() == before


def test_business_scale_frequency_and_scope_are_preserved(tmp_path):
    preview = preview_exchange(_write(tmp_path / "bundle.json", _bundle()))
    rows = {row["indicator_code"]: row for row in preview.payload["observations"]}
    metadata = {item["code"]: item for item in preview.payload["indicator_metadata"]}
    assert rows["cpi"]["value"] == 4.7
    assert rows["lpr"]["date"] == "2026-08-20"
    assert metadata["gdp"]["frequency"] == "quarterly"
    assert metadata["investment"]["period_or_cumulative"] == "cumulative"
    assert "美元口径" in metadata["exports"]["scope_note"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda p: p["observations"][0].update(date="2026-02-30"), "日期非法"),
        (lambda p: p["observations"][0].update(value="4.7"), "不是数值"),
        (lambda p: p["observations"].append(dict(p["observations"][0])), "重复 observation"),
        (lambda p: p["observations"][0].update(indicator_code="unknown"), "未知 indicator_code"),
        (lambda p: p["indicator_metadata"][0].update(unit="亿元"), "单位冲突"),
    ],
)
def test_blocking_validation_errors(tmp_path, mutator, message):
    payload = _bundle()
    mutator(payload)
    payload = _resign(payload)
    with pytest.raises(ValueError, match=message):
        preview_exchange(_write(tmp_path / "bad.json", payload))


def test_non_finite_json_is_rejected(tmp_path):
    text = json.dumps(_bundle(), ensure_ascii=False).replace('"value": 1.0', '"value": NaN', 1)
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="JSON 无法解析"):
        preview_exchange(path)


def test_hash_and_snapshot_validation(tmp_path):
    payload = _bundle()
    payload["content_hash"] = "0" * 64
    with pytest.raises(ValueError, match="content_hash 校验失败"):
        preview_exchange(_write(tmp_path / "hash.json", payload))
    payload = _bundle()
    payload["snapshot_id"] = "wrong"
    with pytest.raises(ValueError, match="snapshot_id"):
        preview_exchange(_write(tmp_path / "snapshot.json", payload))


def test_gdp_monthly_and_investment_period_are_blocked(tmp_path):
    payload = _bundle()
    gdp = next(row for row in payload["observations"] if row["indicator_code"] == "gdp")
    payload["observations"].append({**gdp, "date": "2026-07-01"})
    payload["observations"].sort(key=lambda item: (item["indicator_code"], item["date"]))
    next(item for item in payload["indicator_metadata"] if item["code"] == "gdp")["latest_date"] = "2026-07-01"
    with pytest.raises(ValueError, match="GDP"):
        preview_exchange(_write(tmp_path / "gdp.json", _resign(payload)))
    payload = _bundle()
    next(item for item in payload["indicator_metadata"] if item["code"] == "investment")["period_or_cumulative"] = "period"
    with pytest.raises(ValueError, match="累计口径"):
        preview_exchange(_write(tmp_path / "investment.json", _resign(payload)))


def test_real_import_duplicate_and_analysis_snapshot(repo, tmp_path):
    path = _write(tmp_path / "bundle.json", _bundle())
    preview = preview_exchange(path, repo)
    assert preview.differences["new_indicator_count"] == 12
    result = import_exchange(repo, preview, raw_dir=tmp_path / "raw")
    assert result.observation_count == 12
    assert len(result.series_ids) == 12
    assert Path(result.archived_file).is_file()
    analysis = repo.get_analysis_snapshot(result.dataset_id)
    assert analysis["analysis"]["cycle"]["note"] == "指标框架，不是确定性预测"
    repeated = import_exchange(repo, preview_exchange(path, repo), raw_dir=tmp_path / "raw")
    assert repeated.duplicate_snapshot
    assert repeated.dataset_id == result.dataset_id
    assert repeated.skipped_count == 12
    assert len(repo.list_datasets()) == 1
    assert len(list((tmp_path / "raw").iterdir())) == 1


def test_revision_creates_new_snapshot_without_overwriting_old(repo, tmp_path):
    first_path = _write(tmp_path / "first.json", _bundle())
    first = import_exchange(repo, preview_exchange(first_path, repo), raw_dir=tmp_path / "raw")
    revised_payload = _bundle("2026-09-09T12:35:56+08:00", {"cpi": 5.1})
    revised_path = _write(tmp_path / "revised.json", revised_payload)
    revised_preview = preview_exchange(revised_path, repo)
    assert revised_preview.differences["revision_count"] == 1
    revision = revised_preview.differences["revisions"][0]
    assert revision["old_value"] == 4.7
    assert revision["new_value"] == 5.1
    second = import_exchange(repo, revised_preview, raw_dir=tmp_path / "raw")
    assert second.dataset_id != first.dataset_id
    history = repo.get_indicator_history(["cpi"])
    assert set(history["value"].tolist()) == {4.7, 5.1}


def test_source_change_after_preview_is_rejected_before_archive(repo, tmp_path):
    path = _write(tmp_path / "bundle.json", _bundle())
    preview = preview_exchange(path, repo)
    _write(path, _bundle("2026-09-09T12:35:56+08:00", {"cpi": 5.1}))
    with pytest.raises(ValueError, match="预览后发生变化"):
        import_exchange(repo, preview, raw_dir=tmp_path / "raw")
    assert repo.list_datasets() == []
    assert not (tmp_path / "raw").exists()


def test_series_failure_rolls_back_facts_and_keeps_audit_archive(repo, tmp_path, monkeypatch):
    path = _write(tmp_path / "bundle.json", _bundle())
    preview = preview_exchange(path, repo)
    original = repo.import_dataset_bundle

    def fail_with_real_constraint(meta, mappings, series_payloads, **kwargs):
        observations = series_payloads[0]["observations"]
        series_payloads[0]["observations"] = __import__("pandas").concat(
            [observations, observations.tail(1)], ignore_index=True
        )
        return original(meta, mappings, series_payloads, **kwargs)

    monkeypatch.setattr(repo, "import_dataset_bundle", fail_with_real_constraint)
    with pytest.raises(duckdb.ConstraintException):
        import_exchange(repo, preview, raw_dir=tmp_path / "raw")
    assert repo.list_datasets() == []
    audit = repo.get_import_audit(preview.identity.content_hash)
    assert audit["import_status"] == "rolled_back"
    assert Path(audit["archived_file"]).is_file()


def test_preview_and_import_have_no_network_exit(repo, tmp_path, monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("禁止网络调用")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    try:
        import requests

        monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    except ImportError:
        pass
    try:
        import httpx

        monkeypatch.setattr(httpx.Client, "request", blocked)
        monkeypatch.setattr(httpx.AsyncClient, "request", blocked)
    except ImportError:
        pass
    path = _write(tmp_path / "bundle.json", _bundle())
    preview = preview_exchange(path, repo)
    result = import_exchange(repo, preview, raw_dir=tmp_path / "raw")
    assert result.observation_count == 12


def test_migration_is_idempotent_and_upgrades_v1_database(tmp_path):
    path = tmp_path / "old.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TIMESTAMP)")
        conn.execute("INSERT INTO schema_version VALUES (1, CURRENT_TIMESTAMP)")
    repo = Repository(path)
    assert repo.schema_version() == 2
    repo.migrate()
    assert repo.schema_version() == 2
    with duckdb.connect(str(path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert {"import_audits", "analysis_snapshots"} <= tables
