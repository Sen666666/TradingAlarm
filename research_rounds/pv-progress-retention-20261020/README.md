# 上涨成果保留、侵蚀、收复：2026-10-20

只做量价轨迹研究。29条保存序列、15个固定案例及3个截图代理窗口；18张新模型图均已实际查看。没有账户、订单或交易收益计算。没有真实数据v1，不扫参数。

入口：

- [模型输出前观察](raw-review.md)、[设计决策](design-decision.md)、[冻结协议](protocol-v0.json)。
- [逐图主观复盘与否决理由](subjective-review-v0.md)。
- [趋势动物对照：日期、形态和量背景](comparison-review.md)、[原图身份核对](image-review.md)。
- [最终独立设计审查](design-review-final.md)、[8组独立合成验证](mechanical-validation-synthetic.json)、[90项真实序列检查](v0/validation.json)。
- [代码/输入冻结](v0/freeze.json)、[输出清单](v0/manifest.json)。整个目录的最终清单为 `manifest-final.json`。

`design-review.md`审查的是输出前被否决的自适应预算，不是最终实现。`design-decision.md`是早期设计快照；其量分段随后在冻结前按审查修正，**最终以protocol-v0.json的(E,t]侵蚀背景和(E,T]峰谷背景分别定义为准**。修正缘由见最终设计审查，旧快照不覆盖。

主审复看6张上一轮原始图，加上本轮18张模型图；上一轮已有60图不重复计入本轮。原图含上海房产和BTC，本轮没有把它们当A/H案例，也没有半导体/证券的第三方同标走势图。

## 重要解释

所有比例使用对数价格位移。例如52%是某段上涨成果还保留52%，不是账户赚52%。向下段的retention保留的是下跌成果。parent不是交易状态，可能陈旧。`primary_direction`只代表sqrt21参照尺度，未被认可为成熟主导趋势；`expanding/repairing/eroding`均须结合方向读取。量背景均值不能替代当日q。

本轮没有新增理论公式归因。将Wyckoff对推进与回撤的量价比较作为观察框架；将O'Neil状态/量价与横向排名分开作为职责边界。公式与主尺度是本项目假设，不是大师原公式，也不是“趋势动物”逆向还原。

## 有限复现

不要直接重跑原目录的runner，它会拒绝覆盖。用可运行的Python环境，指定当前仓库根及不存在的新目录：

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/tradingalarm-progress-mpl \
  /path/to/python research_rounds/pv-progress-retention-20261020/code/replay_progress.py \
  --repo /path/to/TradingAlarm \
  --output /tmp/progress-retention-new-run
```

`--prepare-only`只做代码与29输入哈希校验及路径重定位，不计算模型。协议会记录原协议哈希，参数、案例及模型代码不变。独立合成验证脚本为 `code/test_progress_properties.py`，其CLI先读脚本；不要覆盖已保存验证JSON。原始研究输入27条来自旧结果中仅date/close/volume列，新增2条通信代理由本轮inputs保存；没有导入旧账户runner。

本轮以原生 `research_rounds/pv-progress-retention-20261020/` 相对位置同步到正式仓库，便于冻结笔记的相对原图链接在两处一致。复现检查不会需要票据或联网。
