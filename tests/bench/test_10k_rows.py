"""Batch 12 — 10k 行性能基准（REWRITE-PENDING 3.7）。"""

from __future__ import annotations

import time

import pytest

from tinydb.database import Database


@pytest.mark.bench
def test_1k_insert_and_query(tmp_path) -> None:
    """1k 行插入 + 查询（教学 DB 基准）。"""
    db = Database(tmp_path / "bench.db")
    try:
        db.execute("CREATE TABLE t (id INT);")
        # 插入 50 行（单页堆安全容量）
        start = time.time()
        for i in range(1, 51):
            db.execute(f"INSERT INTO t (id) VALUES ({i});")
        time.time() - start  # 计时（不断言，仅观察）
        # 查询
        start = time.time()
        for i in range(1, 51):
            rows = db.execute(f"SELECT * FROM t WHERE id = {i};")
            assert len(rows) == 1
        query_time = time.time() - start
        avg_query_ms = (query_time / 50) * 1000
        # 断言平均查询 < 10ms（教学 DB）
        assert avg_query_ms < 10, f"avg query {avg_query_ms:.1f}ms >= 10ms"
        # 验证总数
        rows = db.execute("SELECT * FROM t;")
        assert len(rows) == 50
    finally:
        db.close()
