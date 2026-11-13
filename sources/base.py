"""数据模型与数据源基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable

import httpx


@dataclass
class JobItem:
    """标准化后的岗位条目。

    所有数据源产出的对象都归一化到这个结构，下游过滤/去重/写盘都基于它。

    Attributes:
        source:       数据源标识 (如 "remoteok" / "weworkremotely")。
        source_id:    该源内的唯一 ID。
        title:        岗位标题。
        company:      公司名，未知填空字符串。
        url:          原始岗位链接。
        location:     地点或远程友好字段。
        salary:       薪资原始字符串，保留原文以备 LLM 解析。
        tags:         技术标签列表。
        description:  岗位描述摘要（可能截断）。
        posted_at:    发布时间，建议带时区 (UTC)。
    """
    source: str
    source_id: str
    title: str
    company: str = ""
    url: str = ""
    location: str = ""
    salary: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    posted_at: datetime | None = None

    @property
    def dedup_key(self) -> str:
        """跨源去重主键: source + source_id。"""
        return f"{self.source}:{self.source_id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        return d


class SourceBase(ABC):
    """所有数据源的抽象基类。

    子类需要:
      - 定义类属性 name (用于配置开关、输出文件名)
      - 实现 fetch() 返回 Iterable[JobItem]
    fetch 内部失败请抛异常或返回空列表，由 main 统一捕获。
    """

    name: str = "base"

    def __init__(self, client: httpx.Client, config: dict):
        self.client = client
        self.config = config

    @abstractmethod
    def fetch(self) -> Iterable[JobItem]:
        ...

    def safe_get(self, url: str, **kwargs) -> httpx.Response:
        """带超时与 UA 的 GET 封装。"""
        http_cfg = self.config.get("http") or {}
        kwargs.setdefault("timeout", http_cfg.get("timeout_seconds", 30))
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("User-Agent", http_cfg.get("user_agent", "Mozilla/5.0"))
        return self.client.get(url, headers=headers, **kwargs)
