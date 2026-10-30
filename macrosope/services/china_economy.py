"""中国经济分析交换文件的纯离线预览、差异识别与事务导入。"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from macrosope.config import PROJECT_ROOT
from macrosope.db import Repository
from macrosope.export import sanitize_filename
from macrosope.models import DatasetMeta, FieldMapping, IndicatorMeta

SHANGHAI = ZoneInfo("Asia/Shanghai")
SUPPORTED_SCHEMAS = {"1.0", "legacy-adapter-1.0"}
VERSIONED_PATTERN = re.compile(r"^integration_(\d{8})_(\d{6})\.json$")
LEGACY_PATTERN = re.compile(r"^分析数据_(\d{8})_(\d{4}|\d{6})\.json$")
SNAPSHOT_PATTERN = re.compile(r"^cnmacro-(\d{8}T\d{6})-([0-9a-f]{12})$")

INDICATOR_MAP: dict[str, dict[str, Any]] = {
    "gdp": {"name": "GDP 累计同比", "unit": "%", "frequency": "quarterly", "period": "cumulative", "dimension": "增长"},
    "industrial": {"name": "规模以上工业增加值同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "增长"},
    "pmi": {"name": "制造业 PMI", "unit": "指数", "frequency": "monthly", "period": "period", "dimension": "信心"},
    "non_man_pmi": {"name": "非制造业 PMI", "unit": "指数", "frequency": "monthly", "period": "period", "dimension": "信心"},
    "cpi": {"name": "CPI 同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "价格"},
    "ppi": {"name": "PPI 同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "价格"},
    "m2": {"name": "M2 同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "流动性", "stock": "stock"},
    "m1": {"name": "M1 同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "流动性", "stock": "stock"},
    "lpr": {"name": "1年期 LPR", "unit": "%", "frequency": "irregular", "period": "period", "dimension": "流动性"},
    "retail": {"name": "社会消费品零售总额同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "需求"},
    "investment": {"name": "固定资产投资累计同比", "unit": "%", "frequency": "monthly", "period": "cumulative", "dimension": "需求"},
    "exports": {"name": "出口同比", "unit": "%", "frequency": "monthly", "period": "period", "dimension": "需求"},
}

METADATA_FIELDS = {
    "code", "name", "definition", "unit", "frequency", "region", "source_org",
    "source_link", "updated_at", "dimension", "nominal_or_real", "stock_or_flow",
    "period_or_cumulative", "seasonally_adjusted", "scope_note", "quality_score",
    "technical_quality_score", "provenance_quality_score", "official_verified",
    "verification_state", "official_verification", "issues", "collection_state",
    "latest_date",
}
ANALYSIS_FIELDS = {"dimensions", "cycle", "drivers", "risks", "correlation", "balances", "breadth"}


@dataclass(frozen=True)
class PreviewIdentity:
    content_hash: str
    file_sha256: str
    size: int
    mtime_ns: int


@dataclass
class ExchangePreview:
    path: Path
    payload: dict
    identity: PreviewIdentity
    indicators: list[dict]
    warnings: list[str] = field(default_factory=list)
    differences: dict = field(default_factory=dict)


@dataclass
class ImportResult:
    dataset_id: int
    series_ids: list[int]
    observation_count: int
    skipped_count: int
    new_indicator_count: int
    new_date_count: int
    duplicate_count: int
    revision_count: int
    archived_file: str
    duplicate_snapshot: bool = False


def default_exchange_directory(project_root: Path | None = None) -> Path:
    """按两个独立项目的同级关系推导默认目录，不保存机器绝对路径。"""
    root = (project_root or PROJECT_ROOT).resolve()
    return root.parent / "中国经济分析" / "output"


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def calculate_content_hash(payload: dict) -> str:
    body = {key: value for key, value in payload.items() if key not in {"snapshot_id", "content_hash"}}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_constant(value: str):
    raise ValueError(f"JSON 包含非法非有限数值：{value}")


def _read_source(path: Path) -> tuple[dict, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"无法读取交换文件：{exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8-sig"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"JSON 无法解析：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("交换文件顶层必须是 JSON 对象")
    return payload, raw


def _aware_generated_at(value: Any, fallback: datetime | None = None) -> str:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        if fallback is None:
            raise ValueError("generated_at 不是有效 ISO 8601 时间") from None
        parsed = fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI).replace(microsecond=0).isoformat(timespec="seconds")


def _legacy_metadata(code: str, frame: list[dict], source_status: dict) -> dict:
    fixed = INDICATOR_MAP[code]
    by_code = {str(item.get("key")): item for item in source_status.get("indicators", [])}
    status = by_code.get(code, {})
    verification = status.get("official_verification") or {}
    dates = [str(row.get("date")) for row in frame]
    issues = list(status.get("issues") or [])
    issues.append("由旧版分析数据在内存中适配；部分元数据在原文件中不存在")
    scope = "旧版文件未提供完整口径元数据。"
    if code == "gdp":
        scope += " GDP 保持季度观察期，不升频。"
    elif code == "lpr":
        scope += " LPR 保留旧文件中的实际发布日期。"
    elif code == "investment":
        scope += " 固定资产投资保持累计同比口径。"
    elif code == "exports":
        scope += " 当前聚合历史序列为美元口径。"
    return {
        "code": code,
        "name": fixed["name"],
        "definition": None,
        "unit": fixed["unit"],
        "frequency": fixed["frequency"],
        "region": "中国",
        "source_org": status.get("publisher"),
        "source_link": verification.get("url") or status.get("official_url"),
        "updated_at": status.get("data_updated_at"),
        "dimension": fixed["dimension"],
        "nominal_or_real": None,
        "stock_or_flow": fixed.get("stock"),
        "period_or_cumulative": fixed["period"],
        "seasonally_adjusted": None,
        "scope_note": scope,
        "quality_score": status.get("quality_score"),
        "technical_quality_score": status.get("technical_quality_score"),
        "provenance_quality_score": status.get("provenance_score"),
        "official_verified": status.get("official_verified"),
        "verification_state": verification.get("state", "not_checked"),
        "official_verification": verification,
        "issues": issues,
        "collection_state": status.get("collection_state", "unknown"),
        "latest_date": max(dates) if dates else None,
    }


def adapt_legacy(payload: dict, file_sha256: str, source_path: Path) -> tuple[dict, list[str]]:
    series = payload.get("series")
    if not isinstance(series, dict) or not series:
        raise ValueError("旧版文件缺少可适配的 series")
    unknown = sorted(set(series) - set(INDICATOR_MAP))
    if unknown:
        raise ValueError(f"未知 indicator_code：{', '.join(unknown)}")
    source_status = payload.get("source_status") if isinstance(payload.get("source_status"), dict) else {}
    fallback = datetime.fromtimestamp(source_path.stat().st_mtime, tz=UTC).astimezone(SHANGHAI)
    generated_at = _aware_generated_at(payload.get("generated_at"), fallback)
    metadata = []
    observations = []
    for code in sorted(series):
        rows = series[code]
        if not isinstance(rows, list):
            raise ValueError(f"旧版 series.{code} 必须是数组")
        metadata.append(_legacy_metadata(code, rows, source_status))
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"旧版 series.{code} 包含非法记录")
            observations.append(
                {"indicator_code": code, "date": row.get("date"), "value": row.get("value")}
            )
    body = {
        "schema_version": "legacy-adapter-1.0",
        "producer": "china-economy-analysis-legacy-adapter",
        "generated_at": generated_at,
        "source_status": source_status,
        "indicator_metadata": metadata,
        "observations": sorted(observations, key=lambda item: (item["indicator_code"], str(item["date"]))),
        "analysis": payload.get("analysis") or {},
    }
    digest = hashlib.sha256(canonical_bytes(body)).hexdigest()
    adapted = {
        "schema_version": body["schema_version"],
        "producer": body["producer"],
        "generated_at": body["generated_at"],
        "snapshot_id": f"legacy-{file_sha256[:16]}",
        "content_hash": digest,
        "source_status": body["source_status"],
        "indicator_metadata": body["indicator_metadata"],
        "observations": body["observations"],
        "analysis": body["analysis"],
    }
    return adapted, ["正在预览旧版分析数据；适配仅发生在内存中，原文件未修改"]


def _parse_date(value: Any, label: str) -> str:
    text = str(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"{label} 日期必须使用 YYYY-MM-DD：{text}")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} 日期非法：{text}") from exc
    if parsed.strftime("%Y-%m-%d") != text:
        raise ValueError(f"{label} 日期非法：{text}")
    return text


def validate_exchange(payload: dict, path: Path | None = None) -> None:
    required = {
        "schema_version", "producer", "generated_at", "snapshot_id", "content_hash",
        "source_status", "indicator_metadata", "observations", "analysis",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"交换文件缺少必填字段：{', '.join(missing)}")
    schema = str(payload["schema_version"])
    if schema not in SUPPORTED_SCHEMAS:
        raise ValueError(f"不支持的 schema_version：{schema}")
    if schema == "1.0" and payload["producer"] != "china-economy-analysis":
        raise ValueError(f"未知 producer：{payload['producer']}")
    generated = datetime.fromisoformat(str(payload["generated_at"]))
    if generated.tzinfo is None or generated.utcoffset() != timedelta(hours=8):
        raise ValueError("generated_at 必须包含 Asia/Shanghai 对应的 +08:00 时区")

    expected_hash = calculate_content_hash(payload)
    if not re.fullmatch(r"[0-9a-f]{64}", str(payload["content_hash"])):
        raise ValueError("content_hash 必须是 SHA256 小写十六进制字符串")
    if expected_hash != payload["content_hash"]:
        raise ValueError("content_hash 校验失败")
    if schema == "1.0":
        match = SNAPSHOT_PATTERN.fullmatch(str(payload["snapshot_id"]))
        expected_stamp = generated.astimezone(SHANGHAI).strftime("%Y%m%dT%H%M%S")
        if not match or match.group(1) != expected_stamp or match.group(2) != expected_hash[:12]:
            raise ValueError("snapshot_id 不符合 cnmacro-时间-哈希前缀规则")
    elif not re.fullmatch(r"legacy-[0-9a-f]{16}", str(payload["snapshot_id"])):
        raise ValueError("旧版适配 snapshot_id 不符合规则")

    if path is not None:
        version_match = VERSIONED_PATTERN.fullmatch(path.name)
        if version_match:
            filename_stamp = "".join(version_match.groups())
            if filename_stamp != generated.astimezone(SHANGHAI).strftime("%Y%m%d%H%M%S"):
                raise ValueError("版本文件名时间与 generated_at 不一致")

    metadata = payload["indicator_metadata"]
    observations = payload["observations"]
    if not isinstance(metadata, list) or not isinstance(observations, list):
        raise ValueError("indicator_metadata 和 observations 必须是数组")
    meta_by_code: dict[str, dict] = {}
    for index, item in enumerate(metadata, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 个 indicator_metadata 不是对象")
        absent = sorted(METADATA_FIELDS - set(item))
        if absent:
            raise ValueError(f"指标元数据缺少字段：{', '.join(absent)}")
        code = str(item["code"])
        if code in meta_by_code:
            raise ValueError(f"indicator_metadata.code 重复：{code}")
        if code not in INDICATOR_MAP:
            raise ValueError(f"未知 indicator_code：{code}")
        expected = INDICATOR_MAP[code]
        if item["unit"] != expected["unit"]:
            raise ValueError(f"指标 {code} 单位冲突：应为 {expected['unit']}，实际为 {item['unit']}")
        if item["frequency"] != expected["frequency"]:
            raise ValueError(f"指标 {code} 频率冲突：应为 {expected['frequency']}，实际为 {item['frequency']}")
        if code == "investment" and item["period_or_cumulative"] != "cumulative":
            raise ValueError("固定资产投资必须保持累计口径")
        if not isinstance(item["issues"], list):
            raise ValueError(f"指标 {code} 的 issues 必须是数组")
        meta_by_code[code] = item

    seen: set[tuple[str, str]] = set()
    dates_by_code: dict[str, list[str]] = {}
    for index, item in enumerate(observations, start=1):
        if not isinstance(item, dict) or set(item) != {"indicator_code", "date", "value"}:
            raise ValueError(f"第 {index} 条 observation 必须且只能包含 indicator_code/date/value")
        code = str(item["indicator_code"])
        if code not in INDICATOR_MAP:
            raise ValueError(f"未知 indicator_code：{code}")
        date_text = _parse_date(item["date"], f"指标 {code}")
        value = item["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"指标 {code} 在 {date_text} 的 value 不是数值")
        if not math.isfinite(float(value)):
            raise ValueError(f"指标 {code} 在 {date_text} 的 value 不是有限数值")
        key = (code, date_text)
        if key in seen:
            raise ValueError(f"同一文件内重复 observation：{code} {date_text}")
        seen.add(key)
        dates_by_code.setdefault(code, []).append(date_text)

    if set(meta_by_code) != set(dates_by_code):
        raise ValueError("indicator_metadata 与 observations 的指标代码无法一一对应")
    for code, values in dates_by_code.items():
        ordered = sorted(values)
        if code == "gdp":
            gaps = [
                (datetime.strptime(right, "%Y-%m-%d") - datetime.strptime(left, "%Y-%m-%d")).days
                for left, right in zip(ordered, ordered[1:], strict=False)
            ]
            if any(gap < 80 for gap in gaps):
                raise ValueError("GDP 相邻观察期明显不符合季度频率")
        if meta_by_code[code]["latest_date"] != ordered[-1]:
            raise ValueError(f"指标 {code} 的 latest_date 与 observations 不一致")

    analysis = payload["analysis"]
    if not isinstance(analysis, dict):
        raise ValueError("analysis 必须是对象")
    missing_analysis = sorted(ANALYSIS_FIELDS - set(analysis))
    if missing_analysis:
        raise ValueError(f"analysis 缺少字段：{', '.join(missing_analysis)}")
    canonical_bytes(payload)


def discover_exchange_file(directory: str | Path) -> Path:
    directory = Path(directory).expanduser()
    if not directory.is_dir():
        raise ValueError(f"交换目录不存在：{directory}")
    versioned = sorted(
        (path for path in directory.iterdir() if path.is_file() and VERSIONED_PATTERN.fullmatch(path.name)),
        key=lambda path: path.name,
        reverse=True,
    )
    if versioned:
        payload, _ = _read_source(versioned[0])
        validate_exchange(payload, versioned[0])
        return versioned[0]
    latest = directory / "integration_latest.json"
    if latest.is_file():
        payload, _ = _read_source(latest)
        validate_exchange(payload, latest)
        return latest
    legacy = sorted(
        (path for path in directory.iterdir() if path.is_file() and LEGACY_PATTERN.fullmatch(path.name)),
        key=lambda path: path.name,
        reverse=True,
    )
    if legacy:
        return legacy[0]
    raise ValueError("目录中没有 integration 交换文件或可兼容的分析数据 JSON")


def _differences(repo: Repository | None, payload: dict) -> dict:
    empty = {
        "new_indicators": [], "new_indicator_count": 0, "new_dates": [],
        "new_date_count": 0, "duplicate_count": 0, "revisions": [], "revision_count": 0,
    }
    if repo is None:
        return empty
    codes = sorted({item["indicator_code"] for item in payload["observations"]})
    history = repo.get_indicator_history(codes)
    existing_codes = set(history["indicator_code"].astype(str)) if not history.empty else set()
    latest: dict[tuple[str, str], dict] = {}
    if not history.empty:
        for row in history.to_dict("records"):
            key = (str(row["indicator_code"]), pd.Timestamp(row["date"]).strftime("%Y-%m-%d"))
            latest.setdefault(key, row)
    result = {**empty, "new_indicators": sorted(set(codes) - existing_codes)}
    result["new_indicator_count"] = len(result["new_indicators"])
    for item in payload["observations"]:
        code, date_text, new_value = item["indicator_code"], item["date"], float(item["value"])
        if code not in existing_codes:
            continue
        old = latest.get((code, date_text))
        if old is None:
            result["new_dates"].append({"indicator_code": code, "date": date_text, "value": new_value})
        elif float(old["value"]) == new_value:
            result["duplicate_count"] += 1
        else:
            result["revisions"].append({
                "indicator_code": code,
                "date": date_text,
                "old_value": float(old["value"]),
                "new_value": new_value,
                "difference": new_value - float(old["value"]),
                "old_dataset_id": int(old["dataset_id"]) if not pd.isna(old["dataset_id"]) else None,
                "old_snapshot_id": None if pd.isna(old["snapshot_id"]) else old["snapshot_id"],
            })
    result["new_date_count"] = len(result["new_dates"])
    result["revision_count"] = len(result["revisions"])
    return result


def preview_exchange(path: str | Path, repo: Repository | None = None) -> ExchangePreview:
    path = Path(path).resolve()
    payload, raw = _read_source(path)
    file_sha = hashlib.sha256(raw).hexdigest()
    warnings: list[str] = []
    if "series" in payload and "indicator_metadata" not in payload:
        payload, warnings = adapt_legacy(payload, file_sha, path)
    validate_exchange(payload, path if payload["schema_version"] == "1.0" else None)
    by_code: dict[str, list[dict]] = {}
    for row in payload["observations"]:
        by_code.setdefault(row["indicator_code"], []).append(row)
    meta = {item["code"]: item for item in payload["indicator_metadata"]}
    summaries = []
    for code in sorted(by_code):
        rows = by_code[code]
        item = meta[code]
        summaries.append({
            "indicator_code": code,
            "name": item["name"],
            "start_date": min(row["date"] for row in rows),
            "end_date": max(row["date"] for row in rows),
            "observations": len(rows),
            "unit": item["unit"],
            "frequency": item["frequency"],
            "technical_quality_score": item["technical_quality_score"],
            "provenance_quality_score": item["provenance_quality_score"],
            "quality_score": item["quality_score"],
            "official_verified": item["official_verified"],
            "verification_state": item["verification_state"],
            "collection_state": item["collection_state"],
            "issues": "；".join(str(issue) for issue in item["issues"]),
        })
        warnings.extend(str(issue) for issue in item["issues"] if issue)
        for field_name in ("definition", "updated_at", "nominal_or_real", "stock_or_flow", "seasonally_adjusted"):
            if item.get(field_name) is None:
                warnings.append(f"{code} 缺少 {field_name}")
    stat = path.stat()
    return ExchangePreview(
        path=path,
        payload=payload,
        identity=PreviewIdentity(payload["content_hash"], file_sha, stat.st_size, stat.st_mtime_ns),
        indicators=summaries,
        warnings=sorted(set(warnings)),
        differences=_differences(repo, payload),
    )


def _archive_source(path: Path, raw_dir: Path, content_hash: str) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / f"{content_hash[:16]}__{sanitize_filename(path.name)}"
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() == source_hash:
            return destination
        raise ValueError(f"原始归档目标已存在但内容不同：{destination}")
    descriptor, temp_name = tempfile.mkstemp(prefix=".china_economy_", suffix=".tmp", dir=raw_dir)
    try:
        with path.open("rb") as source, os.fdopen(descriptor, "wb") as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        os.link(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)
    return destination


def _series_payloads(payload: dict) -> list[dict]:
    metadata = {item["code"]: item for item in payload["indicator_metadata"]}
    grouped: dict[str, list[dict]] = {}
    for row in payload["observations"]:
        grouped.setdefault(row["indicator_code"], []).append(row)
    result = []
    for code in sorted(grouped):
        item = metadata[code]
        indicator = IndicatorMeta(
            name=str(item["name"] or ""),
            code=code,
            definition=str(item["definition"] or ""),
            unit=str(item["unit"] or ""),
            frequency=str(item["frequency"] or ""),
            region=str(item["region"] or ""),
            source_org=str(item["source_org"] or ""),
            source_link=str(item["source_link"] or ""),
            updated_at=str(item["updated_at"] or ""),
            nominal_or_real=str(item["nominal_or_real"] or "unknown"),
            stock_or_flow=str(item["stock_or_flow"] or "unknown"),
            period_or_cumulative=str(item["period_or_cumulative"] or "unknown"),
            seasonally_adjusted=str(item["seasonally_adjusted"] or "unknown"),
            scope_note=str(item["scope_note"] or ""),
            user_note=(
                f"综合质量 {item['quality_score']}；技术质量 {item['technical_quality_score']}；"
                f"来源可信度 {item['provenance_quality_score']}；核验状态 {item['verification_state']}"
            ),
        )
        observations = pd.DataFrame(grouped[code])[["date", "value"]]
        observations["date"] = pd.to_datetime(observations["date"], format="%Y-%m-%d")
        result.append({
            "indicator": indicator,
            "series": {"entity": item["region"], "unit": item["unit"], "frequency": item["frequency"], "currency": ""},
            "observations": observations,
        })
    return result


def import_exchange(
    repo: Repository,
    preview: ExchangePreview,
    *,
    raw_dir: str | Path | None = None,
) -> ImportResult:
    """确认后重新校验指纹，并按不可变快照策略事务导入。"""
    refreshed = preview_exchange(preview.path, repo)
    if refreshed.identity != preview.identity:
        raise ValueError("源文件在预览后发生变化，请重新预览")

    existing = repo.get_import_audit(preview.identity.content_hash)
    if existing and existing.get("import_status") == "success":
        dataset_id = int(existing["dataset_id"])
        return ImportResult(
            dataset_id=dataset_id,
            series_ids=repo.list_dataset_series_ids(dataset_id),
            observation_count=0,
            skipped_count=len(preview.payload["observations"]),
            new_indicator_count=0,
            new_date_count=0,
            duplicate_count=len(preview.payload["observations"]),
            revision_count=0,
            archived_file=str(existing.get("archived_file") or ""),
            duplicate_snapshot=True,
        )

    archive_root = Path(raw_dir) if raw_dir is not None else Path(repo.db_path).parent / "raw"
    archived = _archive_source(preview.path, archive_root, preview.identity.content_hash)
    warning_summary = "；".join(preview.warnings)[:4000]
    audit_id = repo.begin_import_audit({
        "provider": preview.payload["producer"],
        "schema_version": preview.payload["schema_version"],
        "snapshot_id": preview.payload["snapshot_id"],
        "content_hash": preview.payload["content_hash"],
        "file_sha256": preview.identity.file_sha256,
        "source_file": str(preview.path),
        "archived_file": str(archived),
        "generated_at": preview.payload["generated_at"],
        "warning_summary": warning_summary,
    })
    generated_date = datetime.fromisoformat(preview.payload["generated_at"]).strftime("%Y-%m-%d")
    dataset = DatasetMeta(
        name=f"中国经济跟踪 {generated_date}",
        source_filename=preview.path.name,
        source_format="json",
        import_params={
            "schema_version": preview.payload["schema_version"],
            "snapshot_id": preview.payload["snapshot_id"],
            "content_hash": preview.payload["content_hash"],
            "file_sha256": preview.identity.file_sha256,
            "offline_import": True,
        },
        row_count=len(preview.payload["observations"]),
        column_count=3,
        raw_path=str(archived),
    )
    mappings = [
        FieldMapping(column="indicator_code", role="indicator"),
        FieldMapping(column="date", role="date"),
        FieldMapping(column="value", role="value"),
    ]
    try:
        dataset_id, series_ids = repo.import_dataset_bundle(
            dataset,
            mappings,
            _series_payloads(preview.payload),
            analysis_snapshot={
                "snapshot_id": preview.payload["snapshot_id"],
                "generated_at": preview.payload["generated_at"],
                "analysis": preview.payload["analysis"],
            },
        )
    except Exception as exc:
        repo.finish_import_audit(
            audit_id, "rolled_back", warning_summary=f"{warning_summary}；导入失败：{exc}"[:4000]
        )
        raise
    repo.finish_import_audit(
        audit_id, "success", dataset_id=dataset_id, warning_summary=warning_summary
    )
    differences = preview.differences
    return ImportResult(
        dataset_id=dataset_id,
        series_ids=series_ids,
        observation_count=len(preview.payload["observations"]),
        skipped_count=0,
        new_indicator_count=differences["new_indicator_count"],
        new_date_count=differences["new_date_count"],
        duplicate_count=differences["duplicate_count"],
        revision_count=differences["revision_count"],
        archived_file=str(archived),
    )
