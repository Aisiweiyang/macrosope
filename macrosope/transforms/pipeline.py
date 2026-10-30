"""变换管道：可查看、可撤销、可重新运行。

每个变换步骤记录 op_type / 参数 / 公式 / 输入输出序列，输出序列标记为派生。
撤销 = 删除输出序列与步骤记录；重跑 = 按记录的输入与参数重新计算并覆盖输出。
"""
from __future__ import annotations

from macrosope.db import Repository
from macrosope.models import IndicatorMeta, TransformStep
from macrosope.transforms.base import apply_transform, get_definition
from macrosope.transforms.frequency import validate_freq_conversion


class Pipeline:
    """在 Repository 之上执行序列变换并记账。"""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------ 执行
    def apply(
        self,
        op_type: str,
        input_series_ids: list[int],
        params: dict | None = None,
        output_name: str | None = None,
        output_unit: str | None = None,
    ) -> list[int]:
        """执行一个变换，返回新输出序列 id 列表。"""
        params = params or {}
        defn = get_definition(op_type)
        input_metas: list[dict] = []
        for sid in input_series_ids:
            m = self.repo.get_series(sid)
            if m is None:
                raise ValueError(f"输入序列 {sid} 不存在")
            input_metas.append(m)
        input_dfs = [self.repo.get_observations(sid) for sid in input_series_ids]
        if any(df.empty for df in input_dfs):
            raise ValueError("输入序列无数据")

        # 频率转换方向校验（禁止升频伪造）
        if op_type == "resample":
            validate_freq_conversion(
                input_metas[0].get("frequency", ""), params.get("to_freq", "")
            )

        result = apply_transform(op_type, input_dfs, params)
        result = result.dropna(subset=["date"]).sort_values("date")

        out_unit = (
            output_unit
            if output_unit is not None
            else _resolve_unit(defn.output_unit, input_metas[0].get("unit", ""))
        )
        out_freq = _resolve_freq(defn.output_frequency, params, input_metas[0].get("frequency", ""))

        indicator = self._build_indicator(
            op_type, defn, params, input_metas, out_unit, out_freq, output_name
        )
        iid = self.repo.create_indicator(indicator)
        sid = self.repo.create_series(
            indicator_id=iid,
            entity=input_metas[0].get("entity", ""),
            unit=out_unit,
            frequency=out_freq,
            currency=input_metas[0].get("currency", ""),
            is_derived=True,
            source_dataset_id=input_metas[0].get("source_dataset_id"),
        )
        self.repo.insert_observations(sid, result)

        seq = len(self.repo.list_steps()) + 1
        step = TransformStep(
            op_type=op_type,
            params=params,
            formula=defn.formula,
            description=self._describe(op_type, input_metas, params),
            input_series=input_series_ids,
            output_series=[sid],
            seq=seq,
        )
        self.repo.create_step(step)
        return [sid]

    def undo(self, step_id: int) -> None:
        """撤销：删除该步骤的输出序列与步骤记录。"""
        step = self.repo.get_step(step_id)
        if step is None:
            raise ValueError(f"步骤 {step_id} 不存在")
        for sid in step.output_series:
            self.repo.delete_series(sid)
        self.repo.delete_step(step_id)

    def rerun(self, step_id: int) -> None:
        """重新运行：按记录的输入与参数重算，覆盖输出序列。"""
        step = self.repo.get_step(step_id)
        if step is None:
            raise ValueError(f"步骤 {step_id} 不存在")
        input_dfs = [self.repo.get_observations(sid) for sid in step.input_series]
        result = apply_transform(step.op_type, input_dfs, step.params)
        result = result.dropna(subset=["date"]).sort_values("date")
        for sid in step.output_series:
            self.repo.insert_observations(sid, result)

    # ------------------------------------------------------------------ 辅助
    @staticmethod
    def _describe(op_type: str, input_metas: list[dict], params: dict) -> str:
        names = "、".join(
            str(m.get("indicator_name") or m.get("indicator_id")) for m in input_metas
        )
        p = ", ".join(f"{k}={v}" for k, v in params.items()) if params else "无参数"
        return f"[{op_type}] 输入：{names}；参数：{p}"

    @staticmethod
    def _build_indicator(
        op_type: str,
        defn,
        params: dict,
        input_metas: list[dict],
        out_unit: str,
        out_freq: str,
        output_name: str | None,
    ) -> IndicatorMeta:
        first = input_metas[0]
        in_names = [str(m.get("indicator_name") or "") for m in input_metas]
        if output_name:
            name = output_name
        elif len(input_metas) == 1:
            name = f"{in_names[0]}·{defn.label}"
        else:
            name = f"{defn.label}({', '.join(in_names)})"
        return IndicatorMeta(
            name=name,
            code="",
            definition=f"{'、'.join(in_names)} 经「{defn.label}」变换派生",
            unit=out_unit,
            frequency=out_freq,
            region=first.get("region", "") or first.get("entity", ""),
            currency=first.get("currency", ""),
            source_org="宏观数据工作台派生",
            source_link="",
            updated_at="",
            nominal_or_real=first.get("nominal_or_real", "unknown"),
            stock_or_flow=first.get("stock_or_flow", "unknown"),
            period_or_cumulative="period"
            if op_type in ("yoy", "mom", "annualized_mom", "period_change", "log_diff",
                           "cumulative_to_period", "structure_change", "growth_contribution")
            else first.get("period_or_cumulative", "unknown"),
            seasonally_adjusted=first.get("seasonally_adjusted", "unknown"),
            base_period="",
            scope_note=f"公式：{defn.formula}；参数：{params or {}}",
            user_note="",
        )


def _resolve_unit(output_unit: str, input_unit: str) -> str:
    return input_unit if output_unit == "same" else output_unit


def _resolve_freq(output_frequency: str, params: dict, input_freq: str) -> str:
    if output_frequency == "same":
        return input_freq
    if output_frequency.startswith("from_param:"):
        key = output_frequency.split(":", 1)[1]
        return str(params.get(key, input_freq))
    return output_frequency
