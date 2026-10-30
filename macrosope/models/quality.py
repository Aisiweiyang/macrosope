"""数据质量检查结果模型。

问题分三级：错误（必须处理）、警告（可继续但需说明）、提示（建议人工检查）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from macrosope.config import LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING


class Issue(BaseModel):
    """一条质量检查发现的问题。"""

    level: str = LEVEL_INFO  # error/warning/info
    code: str = ""           # 唯一问题代码，如 duplicate_dates
    message: str = ""
    column: str = ""         # 相关列（可为空）
    rows: list[int] = Field(default_factory=list)  # 相关行号（0-based）
    detail: str = ""         # 附加说明


class QualityReport(BaseModel):
    """一次质量检查的汇总。"""

    issues: list[Issue] = Field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == LEVEL_ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == LEVEL_WARNING]

    @property
    def infos(self) -> list[Issue]:
        return [i for i in self.issues if i.level == LEVEL_INFO]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def by_level(self, level: str) -> list[Issue]:
        return [i for i in self.issues if i.level == level]

    def add(
        self,
        level: str,
        code: str,
        message: str,
        column: str = "",
        rows: list[int] | None = None,
        detail: str = "",
    ) -> None:
        self.issues.append(
            Issue(
                level=level,
                code=code,
                message=message,
                column=column,
                rows=rows or [],
                detail=detail,
            )
        )
