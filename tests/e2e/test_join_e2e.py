"""JOIN 端到端测试（REQ-JQ-001..012 执行层）。"""

from __future__ import annotations

import pytest

from tinydb import Database


@pytest.fixture
def db(tmp_path: str) -> Database:
    path = tmp_path / "test.db"
    db = Database(str(path))
    db.execute("CREATE TABLE users (id INT, name TEXT)")
    db.execute("CREATE TABLE scores (id INT, user_id INT, score INT)")
    db.execute("INSERT INTO users VALUES (1, 'alice')")
    db.execute("INSERT INTO users VALUES (2, 'bob')")
    db.execute("INSERT INTO users VALUES (3, 'carol')")
    db.execute("INSERT INTO scores VALUES (1, 1, 90)")
    db.execute("INSERT INTO scores VALUES (2, 1, 85)")
    db.execute("INSERT INTO scores VALUES (3, 2, 70)")
    return db


class TestInnerJoin:
    """INNER JOIN 执行（REQ-JQ-001）。"""

    def test_basic_inner_join(self, db: Database) -> None:
        rows = db.execute(
            "SELECT users.name, scores.score "
            "FROM users INNER JOIN scores ON users.id = scores.user_id",
        )
        assert len(rows) == 3
        names = {r["name"] for r in rows}
        assert names == {"alice", "bob"}

    def test_inner_join_no_match(self, db: Database) -> None:
        rows = db.execute(
            "SELECT users.name FROM users "
            "INNER JOIN scores ON users.id = scores.user_id "
            "WHERE scores.score > 100",
        )
        assert rows == []


class TestLeftJoin:
    """LEFT JOIN 执行（REQ-JQ-002）。"""

    def test_left_join_fills_null(self, db: Database) -> None:
        rows = db.execute(
            "SELECT users.name, scores.score "
            "FROM users LEFT JOIN scores ON users.id = scores.user_id",
        )
        # carol has no scores -> row with NULL score
        carol_rows = [r for r in rows if r["name"] == "carol"]
        assert len(carol_rows) == 1
        assert carol_rows[0]["score"] is None


class TestJoinWithWhereOrderLimit:
    """JOIN + WHERE + ORDER + LIMIT（REQ-JQ-006）。"""

    def test_join_with_where_and_order(self, db: Database) -> None:
        rows = db.execute(
            "SELECT users.name, scores.score "
            "FROM users JOIN scores ON users.id = scores.user_id "
            "WHERE scores.score > 80 "
            "ORDER BY scores.score DESC",
        )
        assert rows[0]["score"] == 90
        assert rows[1]["score"] == 85


class TestEmptyTableJoin:
    """空表 JOIN（REQ-JQ-012）。"""

    def test_inner_join_empty_right(self, db: Database) -> None:
        db.execute("CREATE TABLE empty_t (id INT)")
        rows = db.execute(
            "SELECT users.name FROM users JOIN empty_t ON users.id = empty_t.id",
        )
        assert rows == []


class TestAmbiguousColumn:
    """歧义列检测（REQ-JQ-004）。"""

    def test_unqualified_ambiguous_raises(self, db: Database) -> None:
        from tinydb.errors import AmbiguousColumn

        with pytest.raises(AmbiguousColumn):
            db.execute(
                "SELECT id FROM users JOIN scores ON users.id = scores.user_id",
            )


class TestExplain:
    """EXPLAIN 执行（REQ-EP-005）。"""

    def test_explain_returns_plan(self, db: Database) -> None:
        rows = db.execute("EXPLAIN SELECT * FROM users WHERE id = 1")
        assert len(rows) == 1
        assert "node" in rows[0]
