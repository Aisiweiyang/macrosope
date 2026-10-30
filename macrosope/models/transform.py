"""变换步骤模型。

所有清洗与计算操作都记录为一个 TransformStep，可查看、可撤销、可重新运行。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TransformStep(BaseModel):
    """一次变换的完整记录。"""

    step_id: int | None = None
    op_type: str = ""            # rename/date_parse/yoy/moving_average/resample/...
    params: dict = Field(default_factory=dict)  # 参数
    formula: str = ""            # 人类可读公式
    description: str = ""        # 说明
    input_series: list[int] = Field(default_factory=list)   # 输入序列 id
    output_series: list[int] = Field(default_factory=list)  # 输出序列 id
    seq: int = 0                 # 在管道中的顺序
    created_at: str = ""


class TransformDefinition(BaseModel):
    """变换操作的元数据（公式、适用条件、局限性等），用于界面展示。"""

    op_type: str
    label: str = ""
    formula: str = ""
    input_fields: str = ""       # 输入指标说明
    params_desc: str = ""        # 参数说明
    output_unit: str = ""        # 输出单位
    output_frequency: str = ""   # 输出频率
    missing_handling: str = ""   # 缺失值处理
    applicability: str = ""      # 适用条件
    limitations: str = ""        # 局限性
