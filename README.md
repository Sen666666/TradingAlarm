# TradingAlarm

本地行情与交易辅助工作台，以及围绕量价趋势、行业选择和有限资金配置的研究记录。

本仓库于 **2026-11-10** 整理为精简发布版本，包含应用和算法源码、研究合同、结论、失败记录及小型核验结果。较大的研究身份与结果元数据以[可核验压缩档案](research_archive/README.md)保留。完整本地研究归档约349 GiB；行情、特征、大型账簿、检查点和认证资料不在这个 Git 仓库中。它是源码与研究记录仓库，不是完整数据备份。具体范围见[发布说明](docs/GITHUB_PUBLICATION.md)。

## 当前状态

- **产品**：科技交易台与独立自动模拟仓已经本机验收。产品沿用 ACT20_BREAK，研究候选没有自动替换产品默认策略。
- **研究**：最新主线为51分类下的行业资本分配和 M1—M12 对照。固定1709股中，1692股进入50个具名行业，17股未分类排除；不是历史时点全A股。
- **最新阻断**：M12 v2恢复在2024-10-08发生前缀不一致，最后认证日为2024-09-30；结果仍不可用。不能把原始导出日期当成已认证回测终点。
- **成熟度**：尚未得到已验证、可迁移且长期稳定盈利的通用策略。软件验收、局部收益和会计通过不能代替策略有效性。

## 从哪里阅读

1. [研究哲学与长期共识](docs/RESEARCH_CONSENSUS.md)、[每轮全流程复盘](docs/RESEARCH_REVIEW_CHECKLIST.md)。
2. [最新研究交接](docs/handoff_2026-11-10/README.md)、[已验证结果与反证](docs/handoff_2026-11-10/VERIFIED_RESULTS.md)、[51分类与公式](docs/handoff_2026-11-10/FORMULAS_AND_SCOPE.md)。
3. [最新恢复失败的独立诊断](docs/handoff_2026-11-10/contributions/m12_runtime/final_export_status/independent_diagnosis/V12_RECOVERY_20241008_HANDOFF_DIAGNOSIS.md)。
4. [研究源码与文档导航](docs/RESEARCH_DIRECTORY_INDEX.md)：包含10月原研究和11月外置研究的归档视图。
5. [交易台交付](docs/TRADING_DESK_BUILD.md)、[自动模拟仓](docs/AUTOMATIC_PAPER_ACCOUNT.md)。
6. [股票数据缺口核查](reports/stock-data-gap-audit-20261110/FINDINGS.txt)。

历史文档保留当时的范围、数字与停止条件。旧文档中的“下一步”不代表当前自动执行授权；其中“完整归档”“已复制”等说明描述的是原本地资料范围，不代表数据已上传到GitHub。

## 交易台运行

建议Python 3.13。安装应用依赖：

```sh
python3 -m venv TradingAlarm/research/.venv
TradingAlarm/research/.venv/bin/python -m pip install -r TradingAlarm/requirements.txt
```

首次克隆后需先按[本地数据与运行环境](docs/LOCAL_DATA_SETUP.md)恢复自己有权限使用的数据。仓库不含行情快照和研究派生输入，因此尚未恢复资料的克隆不能直接生成交易指引。

资料恢复后，从根目录运行：

```sh
TRADINGALARM_ENABLE_LIVE=0 TradingAlarm/research/.venv/bin/python TradingAlarm/server.py
```

本机入口：`http://127.0.0.1:8765`；自动模拟仓：`http://127.0.0.1:8765/simulation`。

在线行情需要本人客户端会话及独立本机配置，仓库不携带会话材料。真实账本和模拟账本分别位于本机 `TradingAlarm/runtime/`，不进入Git。应用没有券商下单接口，实际委托由用户执行。

## 研究原则

以量价证据发现和持续参与趋势，通过稀疏大赢家覆盖试错代价；接受低胜率和正常右侧回吐。普通交易成本后基本相抵是理想方向，少量普通净亏可接受。80%是大行情愿景，20%是回撤研究目标，30%仅为事后尾部分类界线。

数据要求服务于具体研究问题：价格坐标、量额单位、时间顺序和因果前缀必须正确；精确现金及可卖日期在影响实际路径时局部核实，不把全历史元数据完备作为所有算法研究的前置条件。

## 验证

无需真实行情的既有测试：

```sh
python3 -m unittest discover -s TradingAlarm -p 'test_sessions.py' -v
PYTHONPATH=TradingAlarm:TradingAlarm/tests python3 -m unittest \
  test_desk.JournalTests test_desk.AmendmentAndEntitlementTests -v
```

完整产品、行情解码和历史研究检查需要本地数据及对应冻结依赖。历史失败尝试原样保留，不把全档案AST扫描等同于所有实验都能运行。本次不申请workflow权限，因此不上传Actions工作流；下面是本地既有检查。

## 目录

| 路径 | 内容 |
|---|---|
| `TradingAlarm/` | 本地应用、交易台、模拟执行与测试 |
| `research_rounds/` | 10月实验的源码、规则与小型结果 |
| `research_rounds/all_in_one_20261110/research/` | 10/29至11/09外置研究的源码和文档视图 |
| `docs/` | 共识、公式、交接与发布边界 |
| `reports/` | 只读数据盘点等报告 |
| `publication/` | 本次导出的文件清单与验证记录 |

本仓库没有为第三方行情或客户端材料授予再分发许可。源码许可尚未另行指定。
