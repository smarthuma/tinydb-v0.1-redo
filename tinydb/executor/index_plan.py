"""索引路径：IndexPlanner 决策 index_seek vs heap_scan（REQ-QE-010, REWRITE-PENDING 3.4）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class IndexPlan:
    """查询计划。"""

    strategy: Literal["index_seek", "heap_scan"]
    index_page_id: int | None = None
    seek_key: object | None = None


class IndexPlanner:
    """索引决策器（简化：无索引元数据时全表扫描）。"""

    def plan(self, where: object, table: str) -> IndexPlan:
        """生成查询计划。"""
        # 简化实现：始终走 heap_scan（索引元数据由 Batch 9+ 补充）
        return IndexPlan(strategy="heap_scan")


__all__: list[str] = ["IndexPlan", "IndexPlanner"]
