"""研究项目管理。

把原始事实、计算结果、用户推断、未验证假设四类条目分层保存，
避免混同数据与判断。
"""
from __future__ import annotations

from macrosope.config import PROJECT_ENTRY_KINDS
from macrosope.db import Repository


class ProjectManager:
    """研究项目的高层操作，底层走 Repository。"""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def full_view(self, project_id: int) -> dict:
        """返回项目的完整视图：基本信息 + 四类条目 + 关联数据集/图表。"""
        project = self.repo.get_project(project_id)
        if project is None:
            return {}
        entries = self.repo.list_project_entries(project_id)
        grouped: dict[str, list[dict]] = {k: [] for k in PROJECT_ENTRY_KINDS}
        for e in entries:
            grouped.setdefault(e["kind"], []).append(e)
        return {
            "project": project,
            "entries": grouped,
            "dataset_ids": self.repo.list_project_datasets(project_id),
            "chart_ids": self.repo.list_project_charts(project_id),
        }

    def add_entry(self, project_id: int, kind: str, content: str) -> int:
        if kind not in PROJECT_ENTRY_KINDS:
            raise ValueError(f"未知条目类型：{kind}（应为 {PROJECT_ENTRY_KINDS}）")
        return self.repo.add_project_entry(project_id, kind, content)
