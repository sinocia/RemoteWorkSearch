"""硬规则过滤器: 技术栈关键词 + 排除词 + 薪资下限。

规则顺序:
  1. 排除词命中 -> 丢弃 (优先级最高)
  2. include_keywords 任一命中 -> 保留，否则丢弃
  3. 薪资下限 -> 若能解析出数字且低于下限则丢弃，无法解析则放行
"""
from __future__ import annotations

import re
from typing import Iterable

from sources.base import JobItem


def _parse_salary(s: str) -> tuple[float | None, str]:
    """从薪资原始字符串里解析 (下限数字, 周期)。

    支持 $3000-$5000/month、$30/hr、$100k/yr、$100,000-$150,000/year 等。
    解析失败返回 (None, "")，调用方据此放行。

    Returns:
        (lower_bound, period) where period ∈ {"year", "month", "hour", ""}
    """
    if not s:
        return None, ""
    text = s.lower().replace(",", "")
    period = ""
    if "year" in text or "/yr" in text or "annual" in text:
        period = "year"
    elif "month" in text or "/mo" in text:
        period = "month"
    elif "hour" in text or "/hr" in text:
        period = "hour"

    # 抓所有数字，支持 100k / 100.5k 这种写法
    nums: list[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)(k)?", text):
        val = float(m.group(1))
        if m.group(2) == "k":
            val *= 1000
        nums.append(val)
    if not nums:
        return None, period
    return min(nums), period  # 取区间下限


def passes_salary(job: JobItem, cfg: dict) -> bool:
    """薪资下限过滤。无法解析则放行 (宁多不漏)。"""
    cfg_s = cfg.get("salary") or {}
    floor_monthly = cfg_s.get("full_time_min_monthly") or 0
    floor_hourly = cfg_s.get("contract_min_hourly") or 0
    floor_annual = cfg_s.get("full_time_min_annual") or 0

    low, period = _parse_salary(job.salary)
    if low is None:
        return True
    if period == "month":
        return low >= floor_monthly
    if period == "hour":
        return low >= floor_hourly
    if period == "year":
        return low >= floor_annual
    return True


def passes_keywords(job: JobItem, cfg: dict) -> bool:
    """先查排除词，再查命中词。"""
    hay = " ".join(
        [job.title, job.company, " ".join(job.tags), job.description]
    ).lower()
    for w in (cfg.get("exclude_keywords") or []):
        if w.lower() in hay:
            return False
    includes = [w.lower() for w in (cfg.get("include_keywords") or [])]
    if not includes:
        return True
    for w in includes:
        if w in hay:
            return True
    return False


def apply(items: Iterable[JobItem], cfg: dict) -> list[JobItem]:
    """对一批 JobItem 运行硬规则过滤，返回保留列表。"""
    out: list[JobItem] = []
    for it in items:
        if not passes_keywords(it, cfg):
            continue
        if not passes_salary(it, cfg):
            continue
        out.append(it)
    return out
