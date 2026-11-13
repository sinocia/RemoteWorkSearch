"""电鸭社区 (eleduck) 数据源 (RSS)。

eleduck 的远程招聘分类是 5: https://eleduck.com/categories/5
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import re

import feedparser

from sources.base import JobItem, SourceBase


class EleduckSource(SourceBase):
    name = "eleduck"
    FEED_URL = "https://eleduck.com/categories/5/feed"

    def fetch(self) -> Iterable[JobItem]:
        resp = self.safe_get(self.FEED_URL)
        if resp.status_code != 200:
            return []
        parsed = feedparser.parse(resp.content)
        items: list[JobItem] = []
        for e in parsed.entries:
            link = e.get("link", "")
            sid = link.rstrip("/").rsplit("/", 1)[-1] or str(e.get("id") or link)
            posted_at = self._parse_posted(e)
            title = e.get("title", "")
            summary = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")
            summary = re.sub(r"\s+", " ", summary).strip()
            items.append(JobItem(
                source=self.name,
                source_id=sid,
                title=title,
                url=link,
                description=summary,
                posted_at=posted_at,
            ))
        return items

    @staticmethod
    def _parse_posted(e) -> datetime | None:
        """feedparser 的 published_parsed 是 UTC struct_time。"""
        t = e.get("published_parsed")
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        if e.get("published"):
            try:
                return datetime.strptime(
                    e["published"], "%a, %d %b %Y %H:%M:%S %z"
                )
            except Exception:
                pass
        return None
