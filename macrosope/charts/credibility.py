"""图表可信度检查。

在生成图表前检查口径一致性等问题。允许用户在看到警告后继续，
但绝不静默隐藏问题。
"""
from __future__ import annotations

from macrosope.config import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING
from macrosope.models import ChartSpec, QualityReport
from macrosope.quality.checks import run_metadata_checks

_STACKABLE = ("stacked_bar",)
_DUAL_AXIS = ("dual_axis",)


def check_chart(spec: ChartSpec, series_metas: list[dict]) -> QualityReport:
    """对即将生成的图表做可信度检查。series_metas 为序列元数据列表。"""
    report = run_metadata_checks(series_metas)

    # 堆叠图表要求单位一致、口径可加
    if spec.chart_type in _STACKABLE and len(series_metas) > 1:
        units = {str(m.get("unit", "") or "") for m in series_metas}
        if len(units) > 1:
            report.add(
                LEVEL_ERROR,
                "stack_incompatible_units",
                f"堆叠图表要求各序列单位一致，实际单位：{sorted(units)}",
            )
        kinds = {str(m.get("stock_or_flow", "") or "") for m in series_metas}
        if len(kinds) > 1:
            report.add(
                LEVEL_WARNING,
                "stack_mixed_stock_flow",
                "堆叠序列混用存量与流量，相加可能无意义",
            )

    # 双轴可能制造虚假相关性
    if spec.chart_type in _DUAL_AXIS:
        report.add(
            LEVEL_WARNING,
            "dual_axis_misleading",
            "双轴图可能制造虚假相关性：两个不同量纲的序列共用时间轴，"
            "视觉上的同步未必代表因果关系。建议改用指数化比较或上下分图。",
        )

    # 标题是否说明指标口径
    if not spec.title:
        report.add(
            LEVEL_WARNING,
            "missing_title",
            "图表缺少标题，建议标题说明指标名称与口径（单位/频率/是否季调）",
        )
    else:
        units_present = {str(m.get("unit", "") or "") for m in series_metas}
        if any(u and u not in spec.title for u in units_present):
            report.add(
                LEVEL_INFO,
                "title_missing_scope",
                "标题未包含单位信息，建议补充口径说明",
            )

    # 是否缺少数据来源
    if not spec.source:
        report.add(
            LEVEL_WARNING,
            "missing_source",
            "图表缺少数据来源，建议补充来源机构",
        )

    # 纵轴是否不合理截断（柱状图应从零开始）
    opts = spec.options or {}
    if spec.chart_type in ("bar", "stacked_bar") and opts.get("y_min") not in (None, 0):
        report.add(
            LEVEL_WARNING,
            "axis_truncated",
            "柱状图纵轴未从零开始，可能夸大差异",
        )

    return report
