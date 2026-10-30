"""图表配置模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChartSpec(BaseModel):
    """一张图表的完整配置，可序列化保存/恢复。"""

    chart_id: int | None = None
    name: str = ""
    chart_type: str = ""  # line/bar/stacked_bar/area/scatter/bubble/hist/box/heatmap/...

    # 数据选择
    series_ids: list[int] = Field(default_factory=list)
    date_range: list[str] = Field(default_factory=list)  # [start, end]

    # 文字标注
    title: str = ""
    subtitle: str = ""
    x_label: str = ""
    y_label: str = ""
    unit: str = ""
    source: str = ""
    footnote: str = ""       # 图下注释
    updated_at: str = ""     # 数据更新时间

    # 图形选项
    options: dict = Field(default_factory=dict)
    # options 可包含: colors, log_y, decimals, width, height, show_legend,
    #              zero_line, baseline_value, show_zero_line 等
