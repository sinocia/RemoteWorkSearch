"""Remote.co 数据源 (RSS)。

注意: remote.co 的主 feed 是整站博客，不全是招聘帖。
这里只保留标题或摘要命中招聘关键词的条目。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import re

import feedparser

from sources.base import JobItem, SourceBase


class RemoteCoSource(SourceBase):
    name = "remoteco"
    FEED_URL = "https://remote.co/feed/"

    JOB_HINTS = (
        "hiring", "job", "position", "engineer", "developer",
        "remote job", "remote role",
    )

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
            text_lc = (title + " " + summary).lower()
            if not any(h in text_lc for h in self.JOB_HINTS):
                continue
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
