# 数据位置与安全接手命令

这些命令以本机 H2FKQQK24K 为准。默认只读检查；交接没有授权启动新的研究队列、重复运行活跃账户或实盘下单。文件中保存的旧 next action 是历史记录，不自动变成现在的执行指令。

## 1 阅读与检索

```sh
P=/Users/bytedance/Documents/ChatGPT/money
H="$P/docs/handoff_2026-11-10"
B=/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1
E=/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1
cat "$H/README.md"
cat "$H/SNAPSHOT_VERIFICATION.json"
grep 'mainline_candidate_v12' "$H/RESEARCH_DIRECTORY_INDEX.csv"
rg -n 'INDEPENDENT_READOUT|2025-01-20' "$H/snapshots/20261109_sector51" -g '*.md'
```

`FILE_INDEX.csv`约118MiB，建议grep或Python流式处理，不用表格软件全量加载。`project_snapshot`是相对本交接目录路径；`absolute_source`为原文真实位置。`copied_snapshot`表示已复制且有SHA；`original_in_project`表示文件已在主工程；`indexed_original_only`表示只索引，迁移必须另带原文件。10/29补充清单的快照路径相对 `supplement_20261029/`。

## 2 活跃账户先查不启动

```sh
V="$B/mainline_candidate_v12_winner_funding_cash_688200_v2"
cat "$V/runtime_checkpoint/LATEST.json"
tail -20 "$V/recovery_001/RECOVERY_STDOUT.log"
tail -3 "$V/CHECKPOINT_RECEIPTS.jsonl"
cat "$V/recovery_001/LAUNCH_RECEIPT.json"
/bin/ps -p 46341 -o pid,ppid,etime,%cpu,%mem,command
find "$V" -maxdepth 2 -name RUN_STATUS.json -o -name FINAL\*.json
```

PID只代表保存时状态，必须按命令行/启动时间核身份；进程不存在不等于结果完成。若ps受本机权限限制，记录限制，不据此称已停止。不得盲删RUN_STARTED、RECOVERY_STARTED或锁，也不得一断联就重新运行。检查点只读LATEST指向的COMMIT，勿加载来源不可信pickle。

目前原run的一次性启动与恢复均已发生。**不要执行** `run_approved_once.py --mode run` 或 `recovery_001/recover.py --mode run`；只有按原运行状态、精确同manifest及独立审批准备的恢复才能继续。当前本应自动算到93日的1/20，不越过1/21。

原代码核对过的轻量接口检查写法是 `run_approved_once.py --mode check`，不是注释里旧的 `--check`。这是源码/许可检查，不是重跑历史；若现有进程仍活，优先只读日志，不做竞争恢复。真实运行解释器与完整命令见RUNTIME_SNAPSHOT.json，不假设系统python与原环境同版。

## 3 当前输入的精确入口

- V/FROZEN_INPUTS.json：全部冻结输入路径及SHA、执行日历、start/end、checkpoint_binding；迁移时以此清单为准，不自行拼接最新数据。
- E/momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet 与 RIGHT3.parquet。
- E/pvr_persistence_breadth_v1/STOCK_DAILY.parquet。
- B/joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv。
- /Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json。
- P/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json、economic-protocol.json。
- B/mainline_m7_cash_batch_design_v6/EXACT_CASH_BATCH_MANIFEST.json：冻结63个事件；q0_factor_only_enabled=false，cash_model=UNCHANGED_NET80。
- B/october_remaining_cash_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_688200_V1.json：唯一新增现金adapter，SHA256 af9b6319597e47ea858c0125bf0e43d31c270da056e06db8d470d76bdc025686。

Data()默认封存到2026-06-30，但真实循环受2024-09-02—2025-01-20的93日约束，不能把数据可读日期称账户完成日期。

## 4 测试与核账

本次没有重跑策略、指标或历史账户。源码、合同和已有检查报告均有快照。合成PASS仅支持接口和边界，不证明实绩。

后续在独立位置获准验证时，可使用当前同一环境的 `synthetic_tests.py`、`checkpoint_tests.py`、`bridge_branch_tests.py`、`runner_tests.py`。它们会生成QA文件，**不能为了交接直接原地重跑并覆盖既有审计**。先核源码/输入manifest、输出目录与准入。原M12的gzip分支簿必须解压字节等价核验，不能只glob *.json后漏审。

轻量公共流程的说明已保存于 `snapshots/20261104_task2/README.md`。它能导入已保存证据或调用明确冻结的四阶段入口，不会自动使未完成账户成为完成。示例原输出必须换全新目录，不能从此文自动执行研究模板。

## 5 应用和原平台

主工程 TradingAlarm/README.md 保存科技交易台的旧验收与运行方式，正式账户、自动模拟账户在 TradingAlarm/runtime/，本交接未复制或改动数据库。应用并未接入M12，不得把研究候选当交易台默认版本。

历史启动命令为：

```sh
cd /Users/bytedance/Documents/ChatGPT/money
TradingAlarm/research/.venv/bin/python TradingAlarm/server.py
```

地址 http://127.0.0.1:8765。启动前检查是否已有服务，并阅读其当前数据更新/会话约束。本交接没有启动服务器，没有替用户录入资金或成交。测试须使用专用TRADINGALARM_RUNTIME和TRADINGALARM_TEST_MODE=1，不能把虚构资金写进正式账。

## 6 搬迁注意

不要只git clone：大量实验与大数据没有提交。先按两份FILE_INDEX及CURRENT_INPUT_DEPENDENCIES复制；保留源目录结构或逐个核对代码绝对路径，不批量改路径后冒称原manifest仍一致。仅本次副本有重新核出的SHA；大数据expected_sha来自旧冻结manifest，应在接收端再次逐字节核验。不要带入认证票据、私密抓包或账户数据库，除非该具体接收环境及内容已获授权。
