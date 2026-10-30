"""变换注册表与调度。

每个变换操作都登记了公式、输入、参数、输出单位、输出频率、
缺失值处理、适用条件与局限性，供界面展示。
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from macrosope.models import TransformDefinition
from macrosope.transforms import calculations as calc
from macrosope.transforms import cleaning
from macrosope.transforms import frequency as freq

# 输出单位/频率的特殊标记
_SAME = "same"  # 与输入一致


def _def(
    op_type: str,
    label: str,
    formula: str,
    input_fields: str,
    params_desc: str,
    output_unit: str = _SAME,
    output_frequency: str = _SAME,
    missing_handling: str = "缺失值保留为 NaN，不填充",
    applicability: str = "",
    limitations: str = "",
) -> TransformDefinition:
    return TransformDefinition(
        op_type=op_type,
        label=label,
        formula=formula,
        input_fields=input_fields,
        params_desc=params_desc,
        output_unit=output_unit,
        output_frequency=output_frequency,
        missing_handling=missing_handling,
        applicability=applicability,
        limitations=limitations,
    )


# op_type -> (函数, 定义, 输入序列数)
TRANSFORM_REGISTRY: dict[str, tuple[Callable, TransformDefinition, int]] = {
    # ------------------------------------------------------------ 清洗
    "sort_by_date": (
        cleaning.sort_by_date,
        _def("sort_by_date", "按日期排序", "按日期升序排列", "单序列", "无",
             applicability="任何序列", limitations="不改变数值"),
        1,
    ),
    "drop_duplicates": (
        cleaning.drop_duplicates,
        _def("drop_duplicates", "删除重复值", "按日期去重，保留首个", "单序列", "无",
             missing_handling="去重不涉及缺失值",
             limitations="重复日期若代表不同实体会被合并，需先确认"),
        1,
    ),
    "unit_convert": (
        cleaning.unit_convert,
        _def("unit_convert", "单位转换", "新值 = 原值 × 系数", "单序列", "系数 factor",
             applicability="如 亿元 → 万亿元（factor=0.0001）",
             limitations="仅做线性缩放，不改变口径"),
        1,
    ),
    "fill_missing": (
        cleaning.fill_missing,
        _def("fill_missing", "缺失值处理", "keep/drop/ffill/interp", "单序列", "方法 method",
             missing_handling="keep 保持；drop 删除；ffill 前向填充；interp 线性插值",
             limitations="前向填充与插值会制造不存在的值，可能造成数据失真，必须用户主动选择"),
        1,
    ),
    "manual_edit": (
        cleaning.manual_edit,
        _def("manual_edit", "手动修正单个值", "指定日期值改为给定值", "单序列", "编辑列表 [{date, value}]",
             applicability="人工核对后的修正", limitations="覆盖原始值，需记录原因"),
        1,
    ),
    # ------------------------------------------------------------ 增长率
    "yoy": (
        calc.yoy,
        _def("yoy", "同比增长率", "(本期值 / 上年同期值 - 1) × 100%", "单序列", "频率 freq",
             output_unit="%",
             applicability="有完整年同期数据的序列",
             limitations="首年数据无同比；跨年数据口径变化会失真"),
        1,
    ),
    "mom": (
        calc.mom,
        _def("mom", "环比增长率", "(本期值 / 上期值 - 1) × 100%", "单序列", "无",
             output_unit="%",
             limitations="受季节性影响明显，季调前慎用"),
        1,
    ),
    "annualized_mom": (
        calc.annualized_mom,
        _def("annualized_mom", "年化环比", "((1 + 环比)^期数/年 - 1) × 100%", "单序列", "每年期数 periods_per_year",
             output_unit="%",
             limitations="假设环比持续不变，仅适合平滑序列"),
        1,
    ),
    "period_change": (
        calc.period_change,
        _def("period_change", "指定期变化率", "(本期值 / 前 k 期值 - 1) × 100%", "单序列", "期数 periods",
             output_unit="%"),
        1,
    ),
    "log_diff": (
        calc.log_diff,
        _def("log_diff", "对数差分", "scale × (ln(x_t) - ln(x_{t-1}))", "单序列", "缩放系数 scale（默认 100）",
             output_unit="%（当 scale=100）",
             applicability="近似增长率，适合剧烈波动序列",
             limitations="要求取值严格为正"),
        1,
    ),
    # ------------------------------------------------------------ 累计/当期
    "cumulative_to_period": (
        calc.cumulative_to_period,
        _def("cumulative_to_period", "累计值转当期值", "当期值 = 累计值_t - 累计值_{t-1}", "单序列", "无",
             limitations="仅对流量类累计指标有意义；存量指标不适用"),
        1,
    ),
    "period_to_cumulative": (
        calc.period_to_cumulative,
        _def("period_to_cumulative", "当期值转累计值", "累计值 = Σ 当期值（滚动累加）", "单序列", "无",
             limitations="跨年度累加需先按年重置，否则口径错误"),
        1,
    ),
    # ------------------------------------------------------------ 指数化
    "index_to_date": (
        calc.index_to_date,
        _def("index_to_date", "指定日期=100", "指数 = 值 / 基期值 × 100", "单序列", "基期日期 base_date",
             output_unit="指数（基期=100）",
             applicability="多指标横向比较时消除量纲"),
        1,
    ),
    "index_first": (
        calc.index_first,
        _def("index_first", "首期=100", "指数 = 值 / 首期值 × 100", "单序列", "无",
             output_unit="指数（首期=100）"),
        1,
    ),
    "index_year_avg": (
        calc.index_year_avg,
        _def("index_year_avg", "年度平均=100", "指数 = 值 / 基期年度均值 × 100", "单序列", "基期年度 base_year",
             output_unit="指数（基期年=100）"),
        1,
    ),
    # ------------------------------------------------------------ 移动统计
    "moving_average": (
        calc.moving_average,
        _def("moving_average", "移动平均", "过去 window 期的算术平均", "单序列", "窗口 window",
             limitations="平滑会滞后，窗口越大越滞后"),
        1,
    ),
    "moving_median": (
        calc.moving_median,
        _def("moving_median", "移动中位数", "过去 window 期的中位数", "单序列", "窗口 window",
             limitations="对异常值更稳健，但同样滞后"),
        1,
    ),
    "rolling_volatility": (
        calc.rolling_volatility,
        _def("rolling_volatility", "滚动波动率", "过去 window 期的标准差", "单序列", "窗口 window",
             applicability="适合收益率序列"),
        1,
    ),
    # ------------------------------------------------------------ 标准化
    "zscore": (
        calc.zscore,
        _def("zscore", "Z-score", "(x - 均值) / 标准差", "单序列", "无",
             output_unit="无量纲", limitations="受异常值影响"),
        1,
    ),
    "minmax": (
        calc.minmax,
        _def("minmax", "Min-Max 标准化", "(x - min) / (max - min)", "单序列", "无",
             output_unit="无量纲", limitations="范围受极值影响"),
        1,
    ),
    "percentile_rank": (
        calc.percentile_rank,
        _def("percentile_rank", "历史百分位", "当前值在历史中的百分位排名", "单序列", "无",
             output_unit="%（0-100）"),
        1,
    ),
    # ------------------------------------------------------------ 结构
    "share": (
        calc.share,
        _def("share", "占比", "每个值 / 全部值之和 × 100", "单序列", "缩放 scale（默认 100）",
             output_unit="%",
             applicability="横截面结构分析（如各行业占 GDP）"),
        1,
    ),
    "structure_change": (
        calc.structure_change,
        _def("structure_change", "结构变化", "当期占比 - 上期占比", "单序列（已为占比）", "无",
             output_unit="百分点",
             limitations="需先算出占比序列"),
        1,
    ),
    # ------------------------------------------------------------ 双序列
    "growth_contribution": (
        calc.growth_contribution,
        _def("growth_contribution", "增长贡献", "(Δ分量_t) / (总量_{t-1}) × 100", "分量序列 + 总量序列",
             "无", output_unit="%",
             limitations="分量与总量口径需一致"),
        2,
    ),
    "per_capita": (
        calc.per_capita,
        _def("per_capita", "人均指标", "指标值 / 人口数", "指标序列 + 人口序列", "无",
             applicability="如 人均GDP = GDP / 人口"),
        2,
    ),
    "nominal_to_real": (
        calc.nominal_to_real,
        _def("nominal_to_real", "名义转实际", "名义值 / 平减指数 × 100", "名义序列 + 平减指数序列", "无",
             applicability="平减指数需与名义值同基期",
             limitations="口径不同会得到错误结果"),
        2,
    ),
    # ------------------------------------------------------------ 频率
    "resample": (
        freq.resample,
        _def("resample", "频率转换", "按聚合方法降频（sum/mean/first/last/max/min）",
             "单序列", "目标频率 to_freq、聚合方法 method",
             output_frequency="from_param:to_freq",
             missing_handling="聚合时忽略缺失，结果可能缺失",
             applicability="只允许降频；流量用求和、存量用期末、利率价格用平均或期末",
             limitations="禁止把低频插值成高频（伪造数据）"),
        1,
    ),
}


def get_definition(op_type: str) -> TransformDefinition:
    if op_type not in TRANSFORM_REGISTRY:
        raise ValueError(f"未知变换操作：{op_type}")
    return TRANSFORM_REGISTRY[op_type][1]


def apply_transform(
    op_type: str, inputs: list[pd.DataFrame], params: dict | None = None
) -> pd.DataFrame:
    """执行一个变换，返回新的序列 DataFrame。"""
    if op_type not in TRANSFORM_REGISTRY:
        raise ValueError(f"未知变换操作：{op_type}")
    params = params or {}
    fn, _, n_inputs = TRANSFORM_REGISTRY[op_type]
    if len(inputs) != n_inputs:
        raise ValueError(f"变换 {op_type} 需要 {n_inputs} 个输入序列，实际 {len(inputs)} 个")
    if n_inputs == 1:
        return fn(inputs[0], **params)
    return fn(inputs[0], inputs[1], **params)


TRANSFORM_DEFS: dict[str, TransformDefinition] = {
    op: entry[1] for op, entry in TRANSFORM_REGISTRY.items()
}
