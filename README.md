# Remote Work Search Agent

一个跑在 Ubuntu 上的定时抓取器，每 2 小时从 5 个公开远程招聘渠道拉取岗位信息，按你的技术栈关键词过滤，去重后输出到本地 Markdown 文件。

## 工作流

```
systemd timer (每 2h)
        │
        ▼
5 个源 (RemoteOK / WWR / HN / eleduck / remote.co)
        │                  (HTTP + RSS)
        ▼
   JobItem 标准化
        │
        ▼
   SQLite 去重  ── 已见过的不重复写
        │
        ▼
   硬规则过滤  ── 关键词 + 排除词 + 薪资下限
        │
        ▼
   Markdown 输出 (jobs/YYYY-MM-DD/{source}.md + _digest.md)
```

## 项目结构

```
RemoteWorkSearch/
├── README.md
├── config.yaml              # 关键词、薪资下限、源开关
├── requirements.txt
├── main.py                  # 入口
├── filters.py               # 硬规则 (关键词 + 排除词 + 薪资)
├── storage.py               # SQLite 去重
├── writers.py               # Markdown 输出
├── sources/
│   ├── __init__.py
│   ├── base.py              # JobItem + SourceBase 抽象基类
│   ├── remoteok.py          # RemoteOK JSON API
│   ├── weworkremotely.py    # WeWorkRemotely RSS
│   ├── hn_whoishiring.py    # Hacker News 月度帖 (Algolia API)
│   ├── eleduck.py           # 电鸭社区 RSS
│   └── remoteco.py          # Remote.co RSS
├── systemd/
│   ├── remote-jobs.service  # systemd 服务单元
│   ├── remote-jobs.timer    # systemd 定时器
│   └── install.sh           # 一键部署脚本
├── jobs/                    # 输出目录 (运行后生成)
│   └── 2026-10-12/
│       ├── remoteok.md
│       ├── weworkremotely.md
│       ├── hn_whoishiring.md
│       ├── eleduck.md
│       ├── remoteco.md
│       └── _digest.md       # 跨源合并 + 时间倒序的当日摘要
└── data/
    └── seen.db              # SQLite 去重库 (运行后生成)
```

## 环境要求

- Ubuntu 20.04 / 22.04 / 24.04 (任何支持 systemd 的发行版都行)
- Python 3.11 或更高
- 能访问外网 (RemoteOK / WWR / Hacker News / 电鸭 / remote.co)
- 系统包: `python3 python3-venv rsync` (Ubuntu 默认源都有)

## 安装与部署

### 方式 A: 一键部署 (推荐，生产用)

把整个项目目录拷到目标 Ubuntu 机器后：

```bash
cd /path/to/RemoteWorkSearch
sudo bash systemd/install.sh /opt/remote-jobs $USER
```

脚本会:
1. 把项目拷到 `/opt/remote-jobs` (或你指定的目录)
2. 创建 `.venv` 并 `pip install -r requirements.txt`
3. 创建 `jobs/` `data/` 和日志文件
4. 拷贝并渲染 systemd unit，启用 timer
5. 立即跑一次: `sudo systemctl start remote-jobs.service`

部署完成后定时器会每 2 小时跑一次。

### 方式 B: 手动跑 (开发/测试)

```bash
cd /path/to/RemoteWorkSearch
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 跑全部启用的源
.venv/bin/python main.py

# 只跑一个源 (调试)
.venv/bin/python main.py --source remoteok

# 跳过过滤，把抓到的全部写盘 (验证抓取质量)
.venv/bin/python main.py --no-filter

# 详细日志 (含 traceback)
.venv/bin/python main.py -v
```

## 使用方法

### 看 digest (推荐)

每天最高优先级看这个文件:

```
jobs/YYYY-MM-DD/_digest.md
```

里面按时间倒序列出当天所有跨源岗位，按源统计数量，每条带链接。

### 按源细看

如果对某个源特别感兴趣，直接看对应文件:
- `jobs/YYYY-MM-DD/remoteok.md` — 含完整描述
- `jobs/YYYY-MM-DD/hn_whoishiring.md` — HN 月度帖评论

### 配置调整

改 `config.yaml` 即可，下次运行自动生效，无需重启 systemd:
- 调整薪资下限: `salary.full_time_min_monthly` 等
- 加关键词: `include_keywords` 列表追加
- 加排除词: `exclude_keywords` 列表追加
- 关闭某源: `sources.xxx: false`

改完手动跑一次验证: `sudo systemctl start remote-jobs.service`

### systemd 运维命令

```bash
# 立即跑一次
sudo systemctl start remote-jobs.service

# 查看定时器下次执行时间
systemctl list-timers remote-jobs.timer

# 查看任务状态
systemctl status remote-jobs.service

# 实时看日志
tail -f /var/log/remote-jobs.log
tail -f /var/log/remote-jobs.err.log

# 暂停定时器
sudo systemctl stop remote-jobs.timer

# 修改定时器后重新加载
sudo systemctl daemon-reload
sudo systemctl restart remote-jobs.timer
```

## 输出格式示例

`jobs/2026-10-12/_digest.md`:

```markdown
# Daily Digest — 2026-10-12

今日新增 **5** 条 (跨 3 源)

## 按源统计

| 来源 | 数量 |
| --- | --- |
| remoteok | 3 |
| weworkremotely | 2 |
| hn_whoishiring | 0 |

## 全部岗位

- **Senior LLM Engineer** @ Acme Corp — `remoteok` — [link](...)
- **Java Backend Engineer** @ Foo — `weworkremotely` — [link](...)
```

`jobs/2026-10-12/remoteok.md` 单条:

```markdown
## Senior LLM Engineer @ Acme Corp

- **Source**: `remoteok`
- **Posted**: 2026-10-12 14:32 UTC
- **Salary**: $150k-$200k/yr
- **Tags**: `llm`, `python`, `rag`
- **URL**: https://remoteok.com/l/12345

> We're looking for an engineer to build RAG pipelines...
```

## 配置说明 (`config.yaml`)

| 字段 | 说明 | 默认/示例 |
| --- | --- | --- |
| `salary.full_time_min_monthly` | 全职月薪 USD 下限 | `3000` |
| `salary.contract_min_hourly` | 合同时薪 USD 下限 | `30` |
| `salary.full_time_min_annual` | 全职年薪 USD 下限 | `36000` |
| `include_keywords` | 命中任一即保留 | java/llm/... |
| `exclude_keywords` | 命中任一即丢弃 (优先级更高) | intern/firmware/... |
| `sources.<name>` | 源开关 | `true` |
| `http.timeout_seconds` | HTTP 超时 | `30` |
| `http.per_source_delay_seconds` | 源之间间隔 | `2` |
| `output_dir` | Markdown 输出目录 | `jobs` |
| `db_path` | SQLite 路径 | `data/seen.db` |

## 关于前端 (重要)

**当前 Phase 1 是纯命令行工具，没有 Web 前端**。"前端"就是 Markdown 文件本身。

使用方式:
- **VSCode** / **Typora** / **Obsidian** / 任何 Markdown 渲染器直接打开 `jobs/YYYY-MM-DD/_digest.md`
- 或者用 `bat` / `glow` 在终端里看高亮渲染: `glow jobs/2026-10-12/_digest.md`

如果后续想要 Web UI，可选的轻量方案 (留到 Phase 2 再做):
1. **静态 HTML 索引**: 写个脚本扫 `jobs/` 目录生成 `index.html`，浏览器直接打开
2. **本地静态服务器**: `python -m http.server` 跑在 jobs 目录，浏览器访问 `localhost:8000`
3. **接 LLM 打分**: 每条岗位让本地 Ollama 打分排序，digest 按分数倒序

这些都不是 Phase 1 的范围，需要时单独告诉我。

## 故障排查

### `fetch FAILED: ...`
单个源失败不会影响其他源，会在日志里标记 `FAILED` 并继续。常见原因:
- 网络不通 / DNS 不解析
- 该站点改了 API/RSS 结构 (代码里硬编码了字段名)
- 触发了反爬 (临时被限流，等下一轮)

加 `-v` 看完整 traceback: `python main.py -v`

### `can't compare offset-naive and offset-aware datetimes`
理论上已修复 (所有源都加了 UTC 时区)，如果还出现请告诉我哪个源报的。

### 抓到的全是 0 条
检查:
1. `config.yaml` 里对应源是不是 `true`
2. 用 `--no-filter` 跑一次看 raw 数量，如果 raw=0 是抓取层问题，raw>0 但 kept=0 是过滤过严
3. 把 `include_keywords` 临时改成 `[]` 看是否是关键词太严

### HN Who is Hiring 没数据
这是月度帖，月初才会更新新的一期。月中跑可能拿到的是上月帖，需要等月初。

### 想强制重抓
删 `data/seen.db` 即可让所有岗位重新被当成新的:

```bash
rm data/seen.db
.venv/bin/python main.py
```

## 后续阶段 (Phase 2+)

Phase 1 已经能跑通抓取-去重-过滤-输出全链路。下一阶段可选:

- **Phase 2**: 接入本地 Ollama (qwen2.5:7b) 对每条岗位打分排序，digest 按分数倒序
- **Phase 3**: 加 Web UI (静态 HTML 索引 + 搜索)
- **Phase 4**: 加更多源 (V2EX 酷工作、Wellfound RSS、Search Remotely 等)

每阶段独立交付，跑稳一阶段再开下一阶段。
