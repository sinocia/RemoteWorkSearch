"""SQLite 去重存储。

单表 seen，主键 dedup_key = "{source}:{source_id}"。
即使岗位被硬规则过滤掉，只要抓到过就 mark_seen，避免下次重复抓取重复输出。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sources.base import JobItem


SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    dedup_key      TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    title          TEXT,
    company        TEXT,
    url            TEXT,
    first_seen_at  TEXT NOT NULL,
    posted_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_seen_source ON seen(source);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """打开/创建 SQLite 数据库并建表。"""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def filter_new(conn: sqlite3.Connection, items: Iterable[JobItem]) -> list[JobItem]:
    """过滤掉已见过的，返回新增列表（同批次内也会去重）。"""
    cur = conn.execute("SELECT dedup_key FROM seen")
    seen_keys: set[str] = {row[0] for row in cur}
    new: list[JobItem] = []
    for it in items:
        if it.dedup_key in seen_keys:
            continue
        seen_keys.add(it.dedup_key)
        new.append(it)
    return new


def mark_seen(conn: sqlite3.Connection, items: Iterable[JobItem]) -> None:
    """把岗位批量写入 seen 表（已存在则忽略）。"""
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            it.dedup_key,
            it.source,
            it.source_id,
            it.title,
            it.company,
            it.url,
            now_iso,
            it.posted_at.isoformat() if it.posted_at else None,
        )
        for it in items
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO seen
           (dedup_key, source, source_id, title, company, url,
            first_seen_at, posted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
