# 量条件事件记忆原型：2026-10-20

本轮已完成，**冻结、不晋升**。原型之后机制修订0次，账户调用0次。完整结论见[研究报告](../../docs/RESEARCH_VOLUME_RESPONSE_2026_10_20.md)，下一动作见[执行计划](../../docs/NEXT_RESEARCH_TASKS.md)。本目录中的全部历史已见，不是样本外。

## 读什么

1. [计算前协议](protocol.md)、[理论及排重审查](reviews/theory-design-review.md)：唯一机制、时序、对照和停止条件。
2. [数据准备审查](reviews/data-readiness.md)、[输入清单](inputs/manifest.json)：14条保存OHLCV、18固定窗口、掩码和原证据哈希，不采新数据。
3. [root原图判断](reviews/raw-root.md)、[独立原图判断](reviews/raw-independent.md)：先看无模型OHLCV。`raw/`保留图与生成记录。
4. [root模型图判断](reviews/model-root-v0.md)、[独立模型图判断](reviews/model-independent-v0.md)：全部18窗实际查看；`results/v0-verified/figures/`为对应完整图。
5. [全事件补充复盘](reviews/event-chain-review.md)：23事件逐一核对，按结局和等待时长机械选择的4张补图；是看到结果后的探索，不能充作新增独立验证。
6. [独立合成验证](validation/independent.json)、[真实验证](validation/real-attempt-1.json)、[真实失败定位](validation/real-attempt-1-diagnostics.json)、[机制审查](reviews/mechanism-review.md)：成功和失败分别保留。
7. [下一问题的设计边界](reviews/next-design-boundary.md)、[冻结记录](freeze.json)、[本轮文件哈希](manifest.json)。

## 保存结果的含义

- `results/v0/`：首次运行的基础复原失败快照。保护点相等时log往返舍入导致9行不同，运行在候选输出前中止；后用原内部pivot坐标恢复修复。
- `results/v0-verified/`：通过基础复原后的完整候选、对照、事件账本、18图、实际运行代码快照及协议。**目录名不代表所有后来验证通过，也不代表策略有效。**
- `validation/independent-attempt*.json`等失败材料：保留前缀类型漂移等过程，不删。
- 当前`code/volume_response.py`比成功运行快照多字段类型及坐标保护；14条保存主要状态与入口重算一致，不声称代码字节一致。
- 真实综合验证250项中239通过、11失败；126个固定前缀通过。单位缩放时实际事件及状态相同，3日期事实标签和上游诊断的数值边界仍未全面通过。冻结不晋升，不将它接到生产或账户。
- 23事件和545建态是信号统计，不是交易、胜率或PnL；上裁决16次不能叫69.6%胜率。

`all_conflicts`只消融新增事件选择的量门槛，上游仍含量；完整价格对照另列`price_original`。`no_conflicts`核对关闭新机制能否恢复原结构。既有结构不因新量事件退出，不意味着改变建态后全部持有轨迹必然相同。

## 有限复现

默认先读结果。不要重跑输入复制脚本、旧账户或全量研究脚本。若需要复现，工作目录为仓库根，使用本机可用环境并指定一个尚不存在的输出目录：

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/pv-mpl XDG_CACHE_HOME=/private/tmp/pv-cache \
  /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python \
  research_rounds/pv-volume-response-20261020/code/run_study.py \
  --output research_rounds/pv-volume-response-20261020/results/reproduction-new
```

`run_study.py`拒绝覆盖已有输出，只执行信号与作图，不导入账户。代码快照用于核对当次实现；在快照目录直接运行时相对输入路径不同，不能把上述入口替换成快照路径后仍宣称相同复现。正式仓库旧venv链接不可用，当前可用Python为上方workspace环境。版本见验证记录。

复现不会使已见数据成为未见样本。新实验必须另立冻结协议和目录；本轮0/1次机制修订的决定及失败不得覆盖。
