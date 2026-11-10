# pv-segment-20261020：已完成，候选不晋升

主观复盘与下一步：[正式研究报告](../../../../docs/RESEARCH_ROUND_2026_10_20.md)。第一轮看图判断在 [trajectory-review.md](trajectory-review.md)，写于账户结果之前。

结果：量价基础账户ETF +3.11% / 最大回撤12.09%；HK7 -3.78% / 21.05%。双成本均亏损。成交量增量不稳定，频繁切段破坏大赢家；否决本具体候选，不否定研究共识。

## 证据入口

- `protocol.json` / `protocol-freeze.json`：候选收益前的机制、案例、有限参数邻域和范围。
- `trajectory-validation.json`、`*-signals.csv`、`signal-events.csv`、`*-trajectory.png`：因果、量纲与轨迹。
- `accounts.json`：24个账户，包括失败与所有预登记对照。
- `*-path.parquet`、`*-orders.json`、`*-decisions.json`：逐日账户、成交和目标，不仅汇总。
- `*-episodes.json`、`*-daily-episodes.csv`：净收益、持仓/权息/分派证券、固定尾部标签和跨窗口桥接。
- `*-fills.png`、`*-account.png`、`review-diagnostics.json`、`extra-diagnostics.json`、`*-unfilled.csv`：真实成交与主观复盘依据。
- `repair-verified/`：最终现金账修复三路重放，以此为最终修复验收。`repair-final/`是保留的中间诊断，不是最终修复成绩。
- `tests-final.log`：8项合成/因果测试；`synthetic-diagnostics.json`注明追加诊断而非预登记验证。
- `manifest.json`、`trajectory-manifest.json`、`account-manifest.json`：代码、来源、输出哈希与运行环境。首轮用到的账本代码另存 `cash-book-used-in-first-replay.py`；最终代码快照在 `code/`。

## 安全复现

需要兼容的Python3.13研究环境及项目原数据。正式仓库携带的venv链接指向旧机器，不能假定可直接使用；当前可用解释器为 `/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python`，在本轮manifest中记录实际版本。

从 `TradingAlarm/research` 运行，设置 `PYTHONDONTWRITEBYTECODE=1`、`MPLCONFIGDIR=/private/tmp/pv-mpl`、`XDG_CACHE_HOME=/private/tmp/pv-cache`。把本目录协议及freeze复制到**新结果目录**后：

```sh
python -m unittest -v test_pv_round
python run_pv_segment_round.py --output results/<新目录> --phase trajectories
# 先实际查看图、记录新的trajectory-review.md，再运行账户
python run_pv_segment_round.py --output results/<新目录> --phase accounts
python pv_review_outputs.py --output results/<新目录>
python pv_extra_diagnostics.py --output results/<新目录>
```

这是已看结果的复现，不会恢复未见样本身份。不要覆盖本目录，也不要直接运行旧实验main。修复重放需在另一个新目录准备 `original-trend_cash_book.py` 后运行 `replay_cash_repair.py --output <新目录>`；该副本是原始实现证据，不是修复后回归测试。
