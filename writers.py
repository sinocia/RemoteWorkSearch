"""Markdown 输出: 每个源一个文件 + 跨源每日 digest。

输出目录结构:
    jobs/
      2026-10-12/
        remoteok.md
        weworkremotely.md
        hn_whoishiring.md
        eleduck.md
        remoteco.md
        _digest.md      # 跨源合并 + 按时间倒序的 Top 摘要
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sources.base import JobItem


def _md_escape(s: str) -> str:
    """简单转义: 把换行替换成空格，去掉首尾空白。"""
    return (s or "").replace("\r", " ").replace("\n", " ").strip()


def _format_posted(posted_at) -> str:
    """统一格式化 posted_at 字段为字符串。"""
    if not posted_at:
        return "unknown"
    if isinstance(posted_at, str):
        return posted_at
    try:
        return posted_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(posted_at)


def _sort_key(j: JobItem) -> datetime:
    """排序键: posted_at 为空或 naive 时都兜底成 tz-aware 最小值。

    避免上游漏加时区时 sort 抛 TypeError。
    """
    if not j.posted_at:
        return datetime.min.replace(tzinfo=timezone.utc)
    if j.posted_at.tzinfo is None:
        return j.posted_at.replace(tzinfo=timezone.utc)
    return j.posted_at


def write_source_md(jobs: list[JobItem], out_dir: Path, source_name: str) -> Path:
    """写单个源的 Markdown 文件，返回路径。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_dir = out_dir / today
    day_dir.mkdir(parents=True, exist_ok=True)
    fpath = day_dir / f"{source_name}.md"

    lines = [f"# {source_name} — {today}", ""]
    if not jobs:
        lines.append("_无新岗位_")
        lines.append("")
    else:
        lines.append(f"共 **{len(jobs)}** 条")
        lines.append("")
        for j in jobs:
            company_part = (
                _md_escape(j.company) if j.company else "(未知公司)"
            )
            lines.append(f"## {_md_escape(j.title)} @ {company_part}")
            lines.append("")
            lines.append(f"- **Source**: `{j.source}`")
            lines.append(f"- **Posted**: {_format_posted(j.posted_at)}")
            if j.location:
                lines.append(f"- **Location**: {_md_escape(j.location)}")
            if j.salary:
                lines.append(f"- **Salary**: {_md_escape(j.salary)}")
            if j.tags:
                lines.append(
                    f"- **Tags**: {', '.join(f'`{t}`' for t in j.tags)}"
                )
            lines.append(f"- **URL**: {j.url}")
            lines.append("")
            if j.description:
                desc = _md_escape(j.description)
                if len(desc) > 800:
                    desc = desc[:800] + "..."
                lines.append(f"> {desc}")
                lines.append("")
            lines.append("---")
            lines.append("")
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return fpath


def write_digest_md(by_source: dict[str, list[JobItem]], out_dir: Path) -> Path:
    """写每日摘要: 跨源合并 + 按 posted_at 倒序。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_dir = out_dir / today
    day_dir.mkdir(parents=True, exist_ok=True)
    fpath = day_dir / "_digest.md"

    all_jobs: list[JobItem] = []
    for v in by_source.values():
        all_jobs.extend(v)
    all_jobs.sort(key=_sort_key, reverse=True)

    lines = [f"# Daily Digest — {today}", ""]
    lines.append(f"今日新增 **{len(all_jobs)}** 条 (跨 {len(by_source)} 源)")
    lines.append("")
    lines.append("## 按源统计")
    lines.append("")
    lines.append("| 来源 | 数量 |")
    lines.append("| --- | --- |")
    for src, jobs in by_source.items():
        lines.append(f"| {src} | {len(jobs)} |")
    lines.append("")
    lines.append("## 全部岗位")
    lines.append("")
    if not all_jobs:
        lines.append("_今日无新增_")
    else:
        for j in all_jobs:
            title = _md_escape(j.title)
            company = _md_escape(j.company) if j.company else "未知"
            lines.append(
                f"- **{title}** @ {company} — `{j.source}` "
                f"— [{j.url}]({j.url})"
            )
    fpath.write_text("\n".join(lines), encoding="utf-8")
    return fpath
