# TradingAlarm：行情应用与趋势交易研究私有交接仓库

**最新结果：价格区域候选已完成15例轨迹、10组账户及主观复盘，否决晋升。** ETF量价−2.78%、HK−3.60%；减少交易未抵消普通损耗，区域边界在整理与走弱之间缺少可靠区分。下一步仅做固定案例的路径顺序与边界失效归因，不立即扩展模型或账户；R2关闭、R5未启动。 用户已明确恢复研究，见[阶段报告](docs/RESEARCH_PRICE_REGION_2026_10_20.md)。

**2026-10-20 最新进展：** [行为面板补齐与A股复查](docs/RESEARCH_BEHAVIOR_COVERAGE_2026_10_20.md)完成，保留15例固定面板；下一步进入一个候选的量价机制设计与实现。当前任务始终以docs/HANDOFF.md顶部为准。

**2026-10-20 当前状态：用户已恢复按纠偏路线研究。** 见[固定行为面板与阶段发现](docs/RESEARCH_BEHAVIOR_PANEL_2026_10_20.md)及[状态语义草案](docs/TREND_STATE_CONTRACT.md)。先补齐案例覆盖，再冻结一个候选；历史暂停记录已被本次恢复指令覆盖。

**历史记录：2026-10-20 曾暂停后续实验，先完成路线审查（现已恢复）。** 见[趋势动物图片对照与研究纠偏](docs/reviews/2026-10-20-trend-animal/ROUTE_REVIEW.md)。恢复研究须遵循用户后续指令；不要自动执行旧实验队列。

截至 2026-10-18 的完整工作快照。包含可运行行情应用、同花顺只读适配器、已保存市场数据、回测引擎、研究脚本及成功/失败实验的原始结果。**目前没有验证出达到“大行情账户收益超过 80%、回撤目标 20%”的可交易策略。**

## 新 agent 从这里开始

2026-10-20 已明确长期共识与当前执行计划。研究核心是量价趋势算法和简单策略，通过每轮主观复查争取稀疏大赢家与普通盈亏基本相抵；基础修复服务于研究。

1. [交接状态](docs/HANDOFF.md)：当前状态、证据边界和接手位置。
2. [必须遵守的研究共识](docs/RESEARCH_CONSENSUS.md)：输入、输出、跳变、收益结构和迭代原则。
3. [下一步 agent 执行计划](docs/NEXT_RESEARCH_TASKS.md)：任务依赖、有限修复、算法回测与主观纠偏、交付标准。
4. [研究路线和证据索引](docs/RESEARCH.md)：已有算法和成功/失败材料。
5. [数据源与同花顺协议](docs/DATA_SOURCES.md)：数据范围和既有授权。
6. [安装、验证和复现](docs/REPRODUCIBILITY.md)：运行脚本前必读。
7. [历史目录索引](docs/catalog.json)、[迁移时校验清单](docs/payload-manifest.json)：它们记录原快照，不自动包含后续新增文件；[私有迁移范围说明](docs/SECURITY.md)。
8. [2026-10-19审查](docs/reviews/2026-10-19-tradingalarm/REVIEW_AND_PLAN.md)：审查证据；其方法建议服从最新共识。
9. [2026-10-20首轮研究结果](docs/RESEARCH_ROUND_2026_10_20.md)：量价分段、24组账户、主观纠偏和有限修复；候选不晋升。

## 立即运行（不需要同花顺登录）

```sh
cd TradingAlarm
TRADINGALARM_ENABLE_LIVE=0 python3 server.py --port 8765
```

打开 http://127.0.0.1:8765/ 。离线搜索及图表使用保存快照，不代表实时行情；在线搜索、行情需要本人的合法会话。详细界面说明在 [TradingAlarm/README.md](TradingAlarm/README.md)，其中在线验证日期是历史记录。

研究 venv 需 Python ≥3.11（推荐 3.13；系统自带 3.9 装不了 numpy 2.4.3/pandas 3.0.1）。本机解释器为 uv 安装的 CPython 3.13.7：`~/.local/share/uv/python/cpython-3.13.7-macos-aarch64-none/bin/python3.13`。用 `requirements-research.lock.txt` 可复现本机已验证的完整版本。

```sh
~/.local/share/uv/python/cpython-3.13.7-macos-aarch64-none/bin/python3.13 -m venv TradingAlarm/research/.venv  # 或任一 Python ≥3.11
TradingAlarm/research/.venv/bin/python -m pip install -r requirements-research.lock.txt  # 或 requirements-research.txt
python3 scripts/verify_payload.py
```

## 内容与携带方式

- `TradingAlarm/`：Python 标准库后端、原生 JS 前端、测试和离线市场快照。
- `TradingAlarm/research/`：研究程序、协议、版本记录、progress.json；`data/` 和 `results/` 完整保留，不依赖 Git LFS。
- `artifacts/ths-analysis-20261016/deep/`：运行所需的解码实现及脱离认证的行情/搜索测试夹具。
- `docs/`、`scripts/`：面向下一个 coding agent 的说明、索引、校验工具。

这是本地 Git 仓库，尚未配置远端。交接优先使用下述仅打包 main 的 bundle，避免复制本机工具内部引用。包含约 2 GB 数据，最大单文件约 631 MB；直接上传到有单文件上限的托管平台会失败，需先规划数据分片或 LFS 迁移。不要把数据排除后仍称完整交接。可用 `git bundle create /仓库外/TradingAlarm-private.bundle main` 离线转交，再 `git clone -b main TradingAlarm-private.bundle TradingAlarm-handoff`。

根据本人明确授权，本版已包含私有票据、认证抓包与应用配置，见 [内网迁移说明](docs/PRIVATE_MIGRATION.md)。AirDrop 请使用 `TradingAlarm-private.bundle`；客户端可执行文件和工具安装环境不包含。已有票据可通过专用入口使用，跨机器远端接受情况尚未验证。第三方市场数据与协议研究材料不附带商业再分发授权；本仓库未授予第三方数据开源许可证。

本轮接续：[量价冲击与ETF／股票分仓第二阶段](docs/RESEARCH_ROUND_2026_10_20_IMPACT_SECTOR.md)。完整证据位于 `TradingAlarm/research/results/pv-impact-sector-20261020/`。
