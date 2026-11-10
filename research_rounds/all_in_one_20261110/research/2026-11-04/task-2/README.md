# TradingAlarm 轻量回测公共流程

本工具独立放在本任务目录，工作区 `/Users/bytedance/Documents/ChatGPT/money` 只读。仓库副本 `/Users/bytedance/repos/TradingAlarm/TradingAlarm` 停在较早阶段，不能替代当前研究。没有修改策略、平台、行情或旧结果，也没有运行新的资金路径。

投入上限最初估为 45–60 分钟。本次仅整理反复使用的四阶段入口、显式文件身份、原核账入口、字段摘要和阶段断点；不迁移旧轮、不构建任务平台。实际投入和核验见 `verification/delivery.json`。

## 可以直接使用

用项目现有 Python，工具仅依赖标准库。独立 N1 核账适配器复用项目已有 pandas/numpy/pyarrow 环境。

```sh
cd /Users/bytedance/Documents/Codex/2026-11-04/task-2
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python research_flow.py import-saved --spec examples/saved-pvr.json --output /tmp/pvr-evidence-NEW
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python research_flow.py status --run-dir /tmp/pvr-evidence-NEW
```

`--output` 必须尚不存在。`import-saved` 只核对原生完成/核账收据与已提供的产物哈希，保存版本记录并映射原 CSV 字段；明确记为 `saved_evidence_import`，不会倒签为事前冻结，也不把保存收据的核验称为重新核账。`examples/saved-n1.json` 还引用本次独立重核收据；两个示例已在 `verification/imports/` 验证，共 14 行，数值字符串原样保留，收益/回撤单位为比例，不是百分数。两轮不合并排名。

如果只需要重新核账保存的 N1 八路径：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python audit_saved_n1.py --project-root /Users/bytedance/Documents/ChatGPT/money --output /tmp/n1-audit-NEW.json
```

该适配器直接调用现有 `rs-h1-execution-20261025/code/analyze_accounts.py:audit_account`，并用原 `FeeSchedule` 再核累计最低佣金/费率组成；复用既有公司行为处理，不增加复杂权益模型。它拒绝在活跃项目下输出，原 `finish.py` 有写入副作用，不能直接导入。

## 下一轮的最小接入

`examples/new-round.template.json` 是模板，故意引用不存在的 `NEW_ROUND`；不是旧实验队列。接入时填入已经审阅、支持独立输出位置的四个原生入口：`preflight → economic → audit → report`。阶段脚本负责真实研究/核账，包装层不实现买卖或会计规则。

1. 在 `identity` 列出实际使用的代码依赖、协议和数据文件。`manifest.json` 本身的哈希仅证明清单不变，不能替代清单内实际行情文件校验；可由已有 preflight 完整验证并出具 `passed=true`。不要把认证配置或票据加入快照。
2. 每个入口必须是显式冻结的 Python 文件，参数显式接收 `{run_dir}`，并正确处理新输出。列出阶段需要保全的所有输出文件，至少包括原生完成/核账收据；大账户文件也应列全。目录本身不能代替文件清单。公共字段映射与单位在事前确定。
3. 给本轮设置有限 `max_seconds`，它限制累计子命令运行时间；哈希、检查、归档与人工开发时间单独记录，不冒称都包含在该预算里。
4. 调用以下三个入口；输出始终放在新目录。

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python research_flow.py freeze --spec /path/to/new-round.json --output /tmp/new-round-NEW
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python research_flow.py run --run-dir /tmp/new-round-NEW --through economic
PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python research_flow.py run --run-dir /tmp/new-round-NEW
```

第二次 `run` 重新核对身份、已完成阶段输出/收据，跳过前两阶段，接着核账与报告。代码/数据/协议和 wrapper SHA、源码副本、Python 及常见包版本、可得 git HEAD、阶段计时/日志/输出 SHA 均有记录；同一内核锁阻止并发运行。只有四阶段完成、明确 `passed=true` 核账通过且新摘要生成，才有 `complete.json`；完成收据绑定全部阶段收据与摘要 SHA。

## 明确边界

- 这是阶段断点，不是交易日/账户对象序列化恢复。阶段内部超时或异常会保留失败，拒绝原地重跑；只出现 `started` 的不确定状态也拒绝自动重跑。先核实原生进程和输出，再另开新尝试目录，沿用经过验证的原生恢复能力。
- 独占输出保护覆盖声明文件和包装层文件；它不是操作系统写入沙箱。旧脚本若硬编码原目录，仍可能写旧结果，因此不能直接接入。此次没有转换这些脚本。子进程超时/可捕获异常会终止其进程组；包装进程被强杀或机器中断后的存活进程须人工/原生工具核实。
- 原检查器使用 Python `assert`；入口拒绝优化模式/`PYTHONOPTIMIZE`，子命令也移除该变量。版本记录覆盖所列常见包和显式文件，不声称完整环境镜像或自动发现所有间接依赖。
- 每轮原生核账语义仍由其原检查器决定；一个 `passed` 字段不能替代代码审查。保存结果导入与新轮事前冻结分开标识，技术完成不代表策略有效。
- 摘要只映射已有指标，不重新分类尾部，不缩放本金，不拼接不同版本收益；各轮普通/未结口径须与原协议一起阅读。

## 验证与节省口径

`test_research_flow.py` 检查版本漂移、旧结果保护、阶段复用、核账失败、超时、并发锁、缺失/篡改阶段收据、旧摘要误接与历史导入等边界。独立 agent 只读审查提出的三项阻断已修复，记录在 `verification/review.json`。

能量化的收益是少重复命令与计算，而非投资收益：验收中前两阶段完成后再次启动仅调用后两阶段，完整后再运行调用数不变；历史导入两轮共 14 行无需重跑资金账户。实际每轮省时取决于被跳过阶段原计时，本次未据此虚报节省多少分钟，也未声称已经加快核心策略研究。重核保存账簿本身是验证成本，不计作节省。
