"""指标元数据模型。

一个指标（如 GDP、CPI、M2）必须携带完整的口径信息，数值不得脱离单位、
频率、口径单独保存。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# 枚举值
NOMINAL_OR_REAL = ("nominal", "real", "unknown")
STOCK_OR_FLOW = ("stock", "flow", "unknown")
PERIOD_OR_CUMULATIVE = ("period", "cumulative", "unknown")
SEASONAL_ADJUSTMENT = ("sa", "nsa", "unknown")


class IndicatorMeta(BaseModel):
    """指标的完整元数据。"""

    indicator_id: int | None = None

    # 标识
    name: str = Field(default="", description="指标名称")
    code: str = Field(default="", description="指标代码")

    # 口径
    definition: str = Field(default="", description="定义")
    unit: str = Field(default="", description="单位")
    frequency: str = Field(default="", description="频率 daily/weekly/monthly/quarterly/annual")
    region: str = Field(default="", description="地区或实体")
    currency: str = Field(default="", description="币种")

    # 来源
    source_org: str = Field(default="", description="来源机构")
    source_link: str = Field(default="", description="来源链接")
    updated_at: str = Field(default="", description="更新时间")

    # 口径属性
    nominal_or_real: str = Field(
        default="unknown", description="名义值/实际值 nominal/real/unknown"
    )
    stock_or_flow: str = Field(default="unknown", description="存量/流量 stock/flow/unknown")
    period_or_cumulative: str = Field(
        default="unknown", description="当期值/累计值 period/cumulative/unknown"
    )
    seasonally_adjusted: str = Field(
        default="unknown", description="是否季调 sa/nsa/unknown"
    )
    base_period: str = Field(default="", description="指数基期，如 2015=100")

    # 说明
    scope_note: str = Field(default="", description="口径说明")
    user_note: str = Field(default="", description="用户备注")
