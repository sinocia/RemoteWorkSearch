"""WeWorkRemotely 数据源 (RSS)。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import re

import feedparser

from sources.base import JobItem, SourceBase


class WeWorkRemotelySource(SourceBase):
    name = "weworkremotely"
    FEED_URL = "https://weworkremotely.com/remote-jobs/feed.rss"

    def fetch(self) -> Iterable[JobItem]:
        resp = self.safe_get(self.FEED_URL)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        items: list[JobItem] = []
        for e in parsed.entries:
            link = e.get("link", "")
            sid = link.rstrip("/").rsplit("/", 1)[-1] or str(e.get("id") or link)
            posted_at = self._parse_posted(e)

            # RSS 标题通常是 "Company: Title"
            title = e.get("title", "")
            company = ""
            m = re.match(r"^(.+?):\s*(.+)$", title)
            if m:
                company = m.group(1).strip()
                title = m.group(2).strip()

            items.append(JobItem(
                source=self.name,
                source_id=sid,
                title=title,
                company=company,
                url=link,
                description=e.get("summary", "") or "",
                posted_at=posted_at,
            ))
        return items

    @staticmethod
    def _parse_posted(e) -> datetime | None:
        """feedparser 的 published_parsed 是 UTC struct_time，转 tz-aware datetime。"""
        t = e.get("published_parsed")
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        # 回退: 解析 RFC 822 字符串
        if e.get("published"):
            try:
                return datetime.strptime(
                    e["published"], "%a, %d %b %Y %H:%M:%S %z"
                )
            except Exception:
                pass
        return None
