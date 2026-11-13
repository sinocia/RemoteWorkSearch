"""Hacker News 'Ask HN: Who is Hiring' 月度帖。

通过 Algolia HN API 获取:
  1) story 搜索，挑最新一期 "Ask HN: Who is hiring"
  2) 该 story 下按时间倒序取最新 100 条评论

每条评论就是一条岗位信息。HN 社区约定的顶部格式:
    Company | Title | Location | Salary | ...
解析时:
  - 先把 <p>/<br> 转成换行 (保留结构)
  - 再清剩余 HTML 标签
  - 取首行，按 | 分段
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import re

from sources.base import JobItem, SourceBase


class HNWhoIsHiringSource(SourceBase):
    name = "hn_whoishiring"

    STORY_SEARCH = (
        "https://hn.algolia.com/api/v1/search?"
        "tags=story&query=Ask+HN%3A+Who+is+hiring&hitsPerPage=5"
    )
    COMMENTS_BY_STORY = (
        "https://hn.algolia.com/api/v1/search_by_date?"
        "tags=comment,story_{story_id}&hitsPerPage=100"
    )

    def fetch(self) -> Iterable[JobItem]:
        story_id = self._find_latest_story_id()
        if not story_id:
            return []
        comments = self._fetch_comments(story_id)
        items: list[JobItem] = []
        for c in comments:
            text = c.get("comment_text", "") or ""
            if not text:
                continue
            company, title, location, salary, desc = self._parse_comment(text)
            ts = c.get("created_at_i")
            posted_at = (
                datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            )
            cid = str(c.get("objectID", ""))
            items.append(JobItem(
                source=self.name,
                source_id=cid,
                title=title or desc[:80],
                company=company,
                url=f"https://news.ycombinator.com/item?id={cid}",
                location=location,
                salary=salary,
                description=desc,
                posted_at=posted_at,
            ))
        return items

    def _find_latest_story_id(self) -> str | None:
        resp = self.safe_get(
            self.STORY_SEARCH, headers={"Accept": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
        hits = list(data.get("hits") or [])
        hits.sort(key=lambda h: h.get("created_at_i", 0), reverse=True)
        if not hits:
            return None
        return hits[0].get("objectID")

    def _fetch_comments(self, story_id: str) -> list[dict]:
        url = self.COMMENTS_BY_STORY.format(story_id=story_id)
        resp = self.safe_get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return list(resp.json().get("hits") or [])

    @staticmethod
    def _parse_comment(text: str) -> tuple[str, str, str, str, str]:
        """解析单条 HN 评论。

        Returns:
            (company, title, location, salary, description)
        """
        # 1) <p>/<br> 转换行，保留段落结构
        text = re.sub(r"</p>|<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        # 2) 清剩余 HTML 标签
        text = re.sub(r"<[^>]+>", " ", text)
        # 3) 合并多余空白 (但保留换行)
        text = re.sub(r"[ \t]+", " ", text)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        first_line = lines[0] if lines else ""
        # 4) 首行按 | 切
        parts = [p.strip() for p in first_line.split("|")]
        company = parts[0] if len(parts) >= 1 else ""
        title = parts[1] if len(parts) >= 2 else ""
        location = parts[2] if len(parts) >= 3 else ""
        salary = parts[3] if len(parts) >= 4 else ""
        # description 用完整清理后的文本
        desc = " ".join(lines)[:1000]
        return company, title, location, salary, desc
