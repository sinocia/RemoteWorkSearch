"""Remote Work Search Agent 主入口。

用法:
    python main.py                       # 跑所有启用的源
    python main.py --source remoteok     # 只跑指定源
    python main.py --no-filter           # 跳过硬规则过滤 (调试用)
    python main.py --verbose             # 详细日志 (含 traceback)

退出码: 0 表示成功 (即便某些源失败也算成功)，非 0 表示致命错误。
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

import httpx
import yaml

from sources.base import SourceBase
from sources.remoteok import RemoteOKSource
from sources.weworkremotely import WeWorkRemotelySource
from sources.hn_whoishiring import HNWhoIsHiringSource
from sources.eleduck import EleduckSource
from sources.remoteco import RemoteCoSource

import storage
import filters
import writers


SOURCE_REGISTRY: dict[str, type[SourceBase]] = {
    "remoteok": RemoteOKSource,
    "weworkremotely": WeWorkRemotelySource,
    "hn_whoishiring": HNWhoIsHiringSource,
    "eleduck": EleduckSource,
    "remoteco": RemoteCoSource,
}


def load_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Remote Work Search Agent")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--source", default=None,
                        help="只跑指定源 (remoteok/weworkremotely/...)")
    parser.add_argument("--no-filter", action="store_true",
                        help="跳过硬规则过滤，仅做去重 + 写盘")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细日志 (含 traceback)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    project_root = Path(__file__).parent
    out_dir = project_root / cfg.get("output_dir", "jobs")
    db_path = project_root / cfg.get("db_path", "data/seen.db")

    conn = storage.init_db(db_path)

    enabled: dict[str, bool] = cfg.get("sources") or {}
    target_sources = (
        [args.source] if args.source else [k for k, v in enabled.items() if v]
    )

    http_cfg = cfg.get("http") or {}
    client = httpx.Client(timeout=http_cfg.get("timeout_seconds", 30))
    per_source_delay = http_cfg.get("per_source_delay_seconds", 2)

    print(f"[run] sources={target_sources} no_filter={args.no_filter}")
    by_source_new: dict[str, list] = {}
    total_raw = 0
    total_new_after_dedup = 0
    total_after_filter = 0

    for src_key in target_sources:
        cls = SOURCE_REGISTRY.get(src_key)
        if cls is None:
            print(f"[warn] unknown source: {src_key}, skip")
            continue
        src: SourceBase = cls(client, cfg)
        try:
            print(f"[{src_key}] fetching...")
            raw = list(src.fetch())
            total_raw += len(raw)
            print(f"[{src_key}] fetched raw={len(raw)}")
        except Exception as e:
            print(f"[{src_key}] fetch FAILED: {e}")
            if args.verbose:
                traceback.print_exc()
            by_source_new[src_key] = []
            time.sleep(per_source_delay)
            continue

        new = storage.filter_new(conn, raw)
        total_new_after_dedup += len(new)
        print(f"[{src_key}] new after dedup={len(new)}")

        kept = new if args.no_filter else filters.apply(new, cfg)
        total_after_filter += len(kept)
        print(f"[{src_key}] kept after filter={len(kept)}")

        # 不管是否被过滤，抓到的都标为已见
        storage.mark_seen(conn, new)

        by_source_new[src_key] = kept
        time.sleep(per_source_delay)

    # 写盘
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src_key, jobs in by_source_new.items():
        written.append(writers.write_source_md(jobs, out_dir, src_key))
    written.append(writers.write_digest_md(by_source_new, out_dir))

    print()
    print("===== summary =====")
    print(f"raw fetched      : {total_raw}")
    print(f"new after dedup  : {total_new_after_dedup}")
    print(f"kept after filter: {total_after_filter}")
    print(f"output dir       : {out_dir}")
    for p in written:
        print(f"  -> {p}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
