"""W1 烟雾测试：验证 tinydb 包可导入，子包结构就位。"""


def test_import_tinydb_package() -> None:
    """tinydb 顶层包可被导入。"""
    import tinydb

    assert tinydb is not None


def test_import_tinydb_parser_subpackage() -> None:
    """tinydb.parser 子包可被导入。"""
    import tinydb.parser

    assert tinydb.parser is not None


def test_import_tinydb_executor_subpackage() -> None:
    """tinydb.executor 子包可被导入。"""
    import tinydb.executor

    assert tinydb.executor is not None


def test_tinydb_has_all() -> None:
    """tinydb 顶层包公开边界 __all__ 存在（即便当前为空或仅含占位）。"""
    import tinydb

    assert hasattr(tinydb, "__all__")
    assert isinstance(tinydb.__all__, list)
