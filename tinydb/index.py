"""B+ Tree 索引（REQ-BT-001..009, REWRITE-PENDING 3.2/3.6）。

节点页 layout：
- leaf: ``[is_leaf=1 u8][key_count u16][(key_bytes + rowid u64) * n][next_leaf u64]``
- internal: ``[is_leaf=0 u8][key_count u16][first_child u32]
  [(separator_key + child_page_id u32) * n]``

key_bytes = ``[type_tag u8][len u16][payload]``，type_tag 1=INT 2=FLOAT 3=TEXT 4=BOOL。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Protocol, cast, runtime_checkable

from tinydb.storage import FileStore, Page, PageType, alloc_page, free_page
from tinydb.types import ColumnType


@runtime_checkable
class _Comparable(Protocol):
    def __lt__(self, other: object) -> bool: ...
    def __le__(self, other: object) -> bool: ...
    def __gt__(self, other: object) -> bool: ...

_IS_LEAF_STRUCT = struct.Struct("<B")
_COUNT_STRUCT = struct.Struct("<H")
_U32_STRUCT = struct.Struct("<I")
_ROWID_STRUCT = struct.Struct("<Q")
_TYPE_TAG_STRUCT = struct.Struct("<B")
_KEY_LEN_STRUCT = struct.Struct("<H")

_TYPE_TO_TAG: dict[ColumnType, int] = {
    ColumnType.INT: 1,
    ColumnType.FLOAT: 2,
    ColumnType.TEXT: 3,
    ColumnType.BOOL: 4,
}
_TAG_TO_TYPE: dict[int, ColumnType] = {v: k for k, v in _TYPE_TO_TAG.items()}


@dataclass
class _Node:
    """B+ Tree 节点（内存态）。"""

    page_id: int
    is_leaf: bool
    keys: list[_Comparable] = field(default_factory=list)
    values: list[int] = field(default_factory=list)  # leaf: rowid; internal: child_page_id
    children: list[int] = field(default_factory=list)  # internal (len = len(keys) + 1)
    next_leaf: int = 0  # leaf 链表指针


class BPlusTree:
    """B+ Tree 索引。"""

    def __init__(
        self,
        store: FileStore,
        root_page_id: int,
        key_type: ColumnType,
        order: int,
    ) -> None:
        self._store = store
        self._root_page_id = root_page_id
        self._key_type = key_type
        self._order = order
        self._min_keys = max(1, order // 2)
        self.page_ids: set[int] = {root_page_id}

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, store: FileStore, key_type: ColumnType, order: int = 64) -> BPlusTree:
        """创建空索引，根为单叶。"""
        root_page_id = alloc_page(store, PageType.INDEX)
        node = _Node(page_id=root_page_id, is_leaf=True)
        _write_node(store, node)
        return cls(store, root_page_id, key_type, order)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def seek(self, key: _Comparable) -> list[int]:
        """精确查找，返回 rowid 列表。"""
        leaf = self._find_leaf(key)
        for i, k in enumerate(leaf.keys):
            if k == key:
                return [leaf.values[i]]
        return []

    def range(self, lo: _Comparable, hi: _Comparable, inclusive: bool = True) -> list[int]:
        """范围查询，返回升序 rowid。"""
        result: list[int] = []
        leaf = self._find_leaf(lo)
        while leaf is not None:
            for i, key in enumerate(leaf.keys):
                if key is None:
                    continue
                if _key_in_range(key, lo, hi, inclusive):
                    result.append(leaf.values[i])
                elif _key_greater(key, hi):
                    return result
            if leaf.next_leaf == 0:
                break
            leaf = _read_node(self._store, leaf.next_leaf)
        return result

    def full_scan(self) -> list[int]:
        """全量升序扫描。"""
        node = _read_node(self._store, self._root_page_id)
        while not node.is_leaf:
            if not node.children:
                break
            node = _read_node(self._store, node.children[0])
        result: list[int] = []
        while node is not None:
            result.extend(node.values)
            if node.next_leaf == 0:
                break
            node = _read_node(self._store, node.next_leaf)
        return result

    # ------------------------------------------------------------------
    # 修改
    # ------------------------------------------------------------------
    def insert(self, key: _Comparable, rowid: int) -> None:
        """插入 key→rowid 映射。"""
        path: list[tuple[_Node, int]] = []
        node = self._find_leaf_with_path(key, path)
        for i, k in enumerate(node.keys):
            if k == key:
                node.values[i] = rowid
                _write_node(self._store, node)
                return
        idx = _bisect_right(node.keys, key)
        node.keys.insert(idx, key)
        node.values.insert(idx, rowid)
        _write_node(self._store, node)
        if len(node.keys) > self._order:
            self._split_and_propagate(path)

    def delete(self, key: _Comparable) -> None:
        """删除 key 映射。"""
        path: list[tuple[_Node, int]] = []
        node = self._find_leaf_with_path(key, path)
        for i, k in enumerate(node.keys):
            if k == key:
                node.keys.pop(i)
                node.values.pop(i)
                _write_node(self._store, node)
                if len(node.keys) < self._min_keys and node.page_id != self._root_page_id:
                    self._rebalance(path)
                return

    # ------------------------------------------------------------------
    # 内部遍历
    # ------------------------------------------------------------------
    def _find_leaf(self, key: _Comparable) -> _Node:
        node = _read_node(self._store, self._root_page_id)
        while not node.is_leaf:
            child_idx = _child_index(node.keys, key)
            node = _read_node(self._store, node.children[child_idx])
        return node

    def _find_leaf_with_path(
        self, key: _Comparable, path: list[tuple[_Node, int]]
    ) -> _Node:
        node = _read_node(self._store, self._root_page_id)
        while not node.is_leaf:
            child_idx = _child_index(node.keys, key)
            path.append((node, child_idx))
            node = _read_node(self._store, node.children[child_idx])
        return node

    # ------------------------------------------------------------------
    # split
    # ------------------------------------------------------------------
    def _split_and_propagate(self, path: list[tuple[_Node, int]]) -> None:
        if not path:
            # 根叶溢出：创建新的 internal 根
            child = _read_node(self._store, self._root_page_id)
            if not child.is_leaf or len(child.keys) <= self._order:
                return
            mid = len(child.keys) // 2
            sep_key = child.keys[mid]
            new_page_id = alloc_page(self._store, PageType.INDEX)
            self.page_ids.add(new_page_id)
            new_node = _Node(
                page_id=new_page_id,
                is_leaf=True,
                keys=child.keys[mid:],
                values=child.values[mid:],
                next_leaf=child.next_leaf,
            )
            child.keys = child.keys[:mid]
            child.values = child.values[:mid]
            child.next_leaf = new_page_id
            _write_node(self._store, child)
            _write_node(self._store, new_node)
            # 创建 internal 根
            new_root_id = alloc_page(self._store, PageType.INDEX)
            self.page_ids.add(new_root_id)
            new_root = _Node(
                page_id=new_root_id,
                is_leaf=False,
                keys=[sep_key],
                children=[child.page_id, new_page_id],
            )
            _write_node(self._store, new_root)
            self._root_page_id = new_root_id
            return

        parent, child_idx = path[-1]
        child = _read_node(self._store, parent.children[child_idx])
        if len(child.keys) <= self._order:
            return
        mid = len(child.keys) // 2
        sep_key = child.keys[mid]
        new_page_id = alloc_page(self._store, PageType.INDEX)
        self.page_ids.add(new_page_id)

        if child.is_leaf:
            new_node = _Node(
                page_id=new_page_id,
                is_leaf=True,
                keys=child.keys[mid:],
                values=child.values[mid:],
                next_leaf=child.next_leaf,
            )
            child.keys = child.keys[:mid]
            child.values = child.values[:mid]
            child.next_leaf = new_page_id
        else:
            new_node = _Node(
                page_id=new_page_id,
                is_leaf=False,
                keys=child.keys[mid + 1 :],
                children=child.children[mid + 1 :],
            )
            child.keys = child.keys[:mid]
            child.children = child.children[: mid + 1]

        _write_node(self._store, child)
        _write_node(self._store, new_node)
        parent.keys.insert(child_idx, sep_key)
        parent.children.insert(child_idx + 1, new_page_id)
        _write_node(self._store, parent)
        if len(parent.keys) > self._order:
            self._split_and_propagate(path[:-1])

    # ------------------------------------------------------------------
    # rebalance
    # ------------------------------------------------------------------
    def _rebalance(self, path: list[tuple[_Node, int]]) -> None:
        if not path:
            return
        parent, child_idx = path[-1]
        node = _read_node(self._store, parent.children[child_idx])
        if len(node.keys) >= self._min_keys:
            return
        if child_idx > 0:
            left = _read_node(self._store, parent.children[child_idx - 1])
            if len(left.keys) > self._min_keys:
                self._redistribute_left(parent, child_idx, left, node)
                return
            self._merge_into_left(parent, child_idx, left, node)
            return
        if child_idx < len(parent.children) - 1:
            right = _read_node(self._store, parent.children[child_idx + 1])
            if len(right.keys) > self._min_keys:
                self._redistribute_right(parent, child_idx, node, right)
                return
            self._merge_into_right(parent, child_idx, node, right)

    def _redistribute_left(
        self, parent: _Node, child_idx: int, left: _Node, node: _Node
    ) -> None:
        if node.is_leaf:
            node.keys.insert(0, left.keys.pop())
            node.values.insert(0, left.values.pop())
            parent.keys[child_idx - 1] = node.keys[0]
        else:
            node.keys.insert(0, parent.keys[child_idx - 1])
            node.children.insert(0, left.children.pop())
            parent.keys[child_idx - 1] = left.keys.pop()
        _write_node(self._store, left)
        _write_node(self._store, node)
        _write_node(self._store, parent)

    def _redistribute_right(
        self, parent: _Node, child_idx: int, node: _Node, right: _Node
    ) -> None:
        if node.is_leaf:
            node.keys.append(right.keys.pop(0))
            node.values.append(right.values.pop(0))
            parent.keys[child_idx] = right.keys[0]
        else:
            node.keys.append(parent.keys[child_idx])
            node.children.append(right.children.pop(0))
            parent.keys[child_idx] = right.keys.pop(0)
        _write_node(self._store, node)
        _write_node(self._store, right)
        _write_node(self._store, parent)

    def _merge_into_left(
        self, parent: _Node, child_idx: int, left: _Node, node: _Node
    ) -> None:
        if node.is_leaf:
            left.keys.extend(node.keys)
            left.values.extend(node.values)
            left.next_leaf = node.next_leaf
        else:
            left.keys.append(parent.keys[child_idx - 1])
            left.keys.extend(node.keys)
            left.children.extend(node.children)
        _write_node(self._store, left)
        free_page(self._store, node.page_id)
        self.page_ids.discard(node.page_id)
        parent.keys.pop(child_idx - 1)
        parent.children.pop(child_idx)
        _write_node(self._store, parent)
        self._maybe_shrink_root(parent)
        if (
            parent.page_id != self._root_page_id
            and len(parent.keys) < self._min_keys
        ):
            self._rebalance([])

    def _merge_into_right(
        self, parent: _Node, child_idx: int, node: _Node, right: _Node
    ) -> None:
        if node.is_leaf:
            right.keys = node.keys + right.keys
            right.values = node.values + right.values
        else:
            right.keys = [parent.keys[child_idx]] + node.keys + right.keys
            right.children = node.children + right.children
        _write_node(self._store, right)
        free_page(self._store, node.page_id)
        self.page_ids.discard(node.page_id)
        parent.keys.pop(child_idx)
        parent.children.pop(child_idx)
        _write_node(self._store, parent)
        self._maybe_shrink_root(parent)
        if (
            parent.page_id != self._root_page_id
            and len(parent.keys) < self._min_keys
        ):
            self._rebalance([])

    def _maybe_shrink_root(self, parent: _Node) -> None:
        if parent.page_id == self._root_page_id and not parent.keys and parent.children:
            new_root = parent.children[0]
            free_page(self._store, parent.page_id)
            self.page_ids.discard(parent.page_id)
            self._root_page_id = new_root

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def height(self) -> int:
        """树高。"""
        h = 1
        node = _read_node(self._store, self._root_page_id)
        while not node.is_leaf:
            if not node.children:
                break
            node = _read_node(self._store, node.children[0])
            h += 1
        return h

    def close(self) -> None:
        pass


# ----------------------------------------------------------------------
# 节点序列化
# ----------------------------------------------------------------------
def _write_node(store: FileStore, node: _Node) -> None:
    """把节点写回页。"""
    parts = [
        _IS_LEAF_STRUCT.pack(1 if node.is_leaf else 0),
        _COUNT_STRUCT.pack(len(node.keys)),
    ]
    if node.is_leaf:
        for key, rowid in zip(node.keys, node.values, strict=False):
            parts.append(_encode_key(key))
            parts.append(_ROWID_STRUCT.pack(rowid))
        parts.append(_ROWID_STRUCT.pack(node.next_leaf))
    else:
        parts.append(_U32_STRUCT.pack(node.children[0]))
        for sep, child in zip(node.keys, node.children[1:], strict=False):
            parts.append(_encode_key(sep))
            parts.append(_U32_STRUCT.pack(child))
    body = b"".join(parts)
    store.write_page(Page(page_id=node.page_id, page_type=PageType.INDEX, lsn=0, body=body))


def _read_node(store: FileStore, page_id: int) -> _Node:
    """从页读取节点。"""
    page = store.read_page(page_id)
    offset = 0
    is_leaf = _IS_LEAF_STRUCT.unpack(page.body[offset : offset + 1])[0] == 1
    offset += 1
    key_count = _COUNT_STRUCT.unpack(page.body[offset : offset + 2])[0]
    offset += 2
    node = _Node(page_id=page_id, is_leaf=is_leaf)
    if is_leaf:
        for _ in range(key_count):
            key, offset = _decode_key(page.body, offset)
            rowid = _ROWID_STRUCT.unpack(page.body[offset : offset + 8])[0]
            offset += 8
            node.keys.append(key)
            node.values.append(rowid)
        if offset + 8 <= len(page.body):
            node.next_leaf = _ROWID_STRUCT.unpack(page.body[offset : offset + 8])[0]
    else:
        first_child = _U32_STRUCT.unpack(page.body[offset : offset + 4])[0]
        offset += 4
        node.children.append(first_child)
        for _ in range(key_count):
            sep, offset = _decode_key(page.body, offset)
            child = _U32_STRUCT.unpack(page.body[offset : offset + 4])[0]
            offset += 4
            node.keys.append(sep)
            node.children.append(child)
    return node


def _encode_key(key: object) -> bytes:
    """编码 key 为 ``[type_tag u8][len u16][payload]``。

    直接使用 struct 编码，避免 ``types.encode`` 的 NULL sentinel 碰撞
    （INT 0 的全零字节会被 ``types.decode`` 误判为 NULL）。
    """
    if isinstance(key, bool):
        tag = _TYPE_TO_TAG[ColumnType.BOOL]
        payload = b"\x01" if key else b"\x00"
    elif isinstance(key, int):
        tag = _TYPE_TO_TAG[ColumnType.INT]
        payload = key.to_bytes(8, "little", signed=True)
    elif isinstance(key, float):
        tag = _TYPE_TO_TAG[ColumnType.FLOAT]
        payload = struct.pack("<d", key)
    elif isinstance(key, str):
        tag = _TYPE_TO_TAG[ColumnType.TEXT]
        payload = key.encode("utf-8")
    else:
        raise TypeError(f"unsupported key type: {type(key)}")
    return _TYPE_TAG_STRUCT.pack(tag) + _KEY_LEN_STRUCT.pack(len(payload)) + payload


def _decode_key(body: bytes, offset: int) -> tuple[_Comparable, int]:
    """解码 key，返回 (key, new_offset)。"""
    tag = _TYPE_TAG_STRUCT.unpack(body[offset : offset + 1])[0]
    offset += 1
    length = _KEY_LEN_STRUCT.unpack(body[offset : offset + 2])[0]
    offset += 2
    payload = body[offset : offset + length]
    offset += length
    col_type = _TAG_TO_TYPE.get(tag, ColumnType.INT)
    if col_type is ColumnType.INT:
        return cast("_Comparable", int.from_bytes(payload, "little", signed=True)), offset
    if col_type is ColumnType.FLOAT:
        return cast("_Comparable", struct.unpack("<d", payload)[0]), offset
    if col_type is ColumnType.BOOL:
        return cast("_Comparable", payload[0] != 0), offset
    return cast("_Comparable", payload.decode("utf-8")), offset


def _infer_type(key: object) -> ColumnType:
    """推断 key 的列类型。"""
    if isinstance(key, bool):
        return ColumnType.BOOL
    if isinstance(key, int):
        return ColumnType.INT
    if isinstance(key, float):
        return ColumnType.FLOAT
    if isinstance(key, str):
        return ColumnType.TEXT
    raise TypeError(f"unsupported key type: {type(key)}")


# ----------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------
def _child_index(keys: list[_Comparable], key: _Comparable) -> int:
    """找到 key 应落入的子节点索引。"""
    for i, sep in enumerate(keys):
        if key < sep:
            return i
    return len(keys)


def _bisect_right(keys: list[_Comparable], key: _Comparable) -> int:
    """二分插入位置（右侧）。"""
    lo, hi = 0, len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid] <= key:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _key_greater(key: _Comparable, other: _Comparable) -> bool:
    """key > other。"""
    return other < key


def _key_in_range(
    key: _Comparable, lo: _Comparable, hi: _Comparable, inclusive: bool,
) -> bool:
    """判断 key 是否在范围内。"""
    if inclusive:
        return lo <= key <= hi
    return lo < key < hi


__all__: list[str] = [
    "BPlusTree",
]
