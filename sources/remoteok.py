"""RemoteOK 数据源 (JSON API)。

API: https://remoteok.io/api
返回一个 list，第一项通常是 legal notice (含 'legal' 键)，需跳过。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sources.base import JobItem, SourceBase


class RemoteOKSource(SourceBase):
    name = "remoteok"
    API_URL = "https://remoteok.io/api"

    def fetch(self) -> Iterable[JobItem]:
        resp = self.safe_get(self.API_URL, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        items: list[JobItem] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            # 第一项是 legal notice
            if "legal" in entry or "id" not in entry:
                continue
            jid = str(entry.get("id") or "")
            if not jid:
                continue
            posted_at = self._parse_posted(entry.get("date"))
            items.append(JobItem(
                source=self.name,
                source_id=jid,
                title=entry.get("position") or entry.get("title") or "",
                company=entry.get("company") or "",
                url=entry.get("url") or "",
                location=entry.get("location") or "",
                salary=entry.get("salary") or "",
                tags=entry.get("tags") or [],
                description=entry.get("description") or entry.get("summary") or "",
                posted_at=posted_at,
            ))
        return items

    @staticmethod
    def _parse_posted(raw) -> datetime | None:
        """RemoteOK 返回类似 '2024-08-15T12:34:56Z' 的时间字符串。"""
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
