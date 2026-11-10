# B4 原生输出能否经策略层百分之百复现 E0

结论：**不能在所有合法输入上保证。** 这不是“简单规则还没找到”，而是现有 B4 原生输出丢失了 E0 所需的一项信息。允许策略保留完整 B4 历史、全部事件日志及任意内部记忆，结论仍成立。这个结论不否定 B4 可用于独立交易策略，也不评价 B4 与 E0 的经济优劣。

范围固定于当前 B4 原生 `strength_frame(joint=True)` 和固定 E0：先调用 `event_frame_numeric(joint=True, event_exit=False)`，再调用 `participation_frame(mode='volume')`。前者内部的 `target` 不是 E0；B4 研究表中额外导入的 `e0_*` 对照列也不是 B4 算法输出。本验证不使用这两种捷径。

## 信息边界和证明

B4 的输入合同是 `close/volume/segment_id/valid_strength_observation`，完整原生输出、日志及末态都由它们决定。E0 另外读取日线最低价：放量下跌待回应记忆将 `lower=L_t` 保存下来，独立收复时将其设为支持 `floor`，以后 `C_t<=floor` 触发退出。源码分别为 [B4 model.py](../../pv-strength-b4-20261025/code/model.py)、[E0 participation.py](../../pv-participation-response-20261020/code/participation.py)，定义见 [E0 固定说明](../../../docs/ALGORITHMS_E0_R_R1.md)。

设 `B(x)_{0:t}` 是行情历史 `x` 到时点 `t` 的全部 B4 可观察信息。只用 B4 的有状态策略可写成：

```text
state_t = F(state_(t-1), B(x)_t, time_t)
action_t = G(state_t, B(x)_(0:t), time_t)
```

对初始状态相同的两条行情，若全部 B4 输入流相同，归纳可得所有策略状态和动作相同，哪怕策略保留完整历史。下面原函数见证给出 `B(x)=B(y)`，但 `E0(x)_66 != E0(y)_66`；因此不存在对所有合法行情成立的这种 E0 精确映射。随机策略也不能保证对这两个不可区分输入都百分之百正确。禁止将原始最低价、E0 结果或编码了答案的序列身份注入初始化；否则已越过“仅用 B4 输出”的信息边界。

## 67 个完整 OHLCV 观察的直接见证

这是一组事前写定的合成机制探针，不是市场样本或账户回测。日期仅作有序观察标签，不宣称对应交易所日历。全部价格和成交量正且有限、OHLC 合法、同一来源段、全部观察有效。两条行情的 O/H/C/V、日期、有效性完全相同，**只有零基观察 64 的最低价不同**。前 64 行收盘价为 100、102 交替，成交量均为 100；随后如下：

| 零基观察 | 收盘/量 | A 最低价 | B 最低价 | E0 A | E0 B |
|---|---|---|---|---|---|
| 64 | 100 / 200 | 98 | 94 | 建立等待记忆，lower=98，reclaim=102 | 建立等待记忆，lower=94，reclaim=102 |
| 65 | 103 / 100 | 99 | 99 | 收复建态，floor=98，target=1 | 收复建态，floor=94，target=1 |
| 66 | 96 / 100 | 95 | 95 | exited=1，target=0 | exited=0，target=1 |

观察 65 的原始量价事件确认值为 `0.6675426463065076 < 1`，`event=0`，故两个建态都确实来自 `participation_reclaim`，没有被原通道的同日优先级覆盖。观察 66 的收盘 96 低于 98 而高于 94，直接产生退出分歧。这里的支持差异不只是一个展示字段差异，已传导到有效状态与退出信号。

真实运行原函数所得：

- B4 全部 **101 列 × 67 行**精确一致，含全部候选字段、日期字段和 phase。
- B4 全部 **17 条原生日志**及 attrs 中完整 terminal 状态精确一致。
- 上游 `event_frame_numeric` 全列精确一致；其内部 target 在本见证中始终为 0，进一步说明不能拿它代替 E0。
- E0 在观察 65 同时进入；观察 66 的 target/exited 确实不同。
- 两条输入分别截断为 65、66、67 行重新计算，六个物理前缀的 B4 全列/日志、上游事件全列、E0 全列均与完整运行的相应前缀精确一致。
- 原三份算法源码运行前后 SHA256 不变。一次固定构造，无参数扫描，无 mocked events，无账户，无下载，无模型修改。

预先固定的 [协议](../validation/compat-protocol.json)、[确定性脚本](../validation/prove_b4_e0_information_loss.py)、[核验 JSON](../validation/compat-output-v1/verification.json)、[末四行见证](../validation/compat-output-v1/witness-last-four.csv)、[输入 A](../validation/compat-output-v1/input-a-low98.csv)、[输入 B](../validation/compat-output-v1/input-b-low94.csv) 均已保存。完整 B4、原始事件和两条 E0 结果在同一输出目录，可逐字段复核。

独立子代理 `counterexample_review` 已只读审查协议、脚本、输出与原函数，并独立核对全部已登记源/产物哈希，结论通过、无阻断问题；审查没有重跑账户或修改算法。它确认以上普遍命题边界，并提醒不要把这组紧凑见证称为已经证明全局最短输入。审查摘要另存 [独立审查收据](../validation/compat-independent-review.json)。

## 可行的兼容方式与结论边界

1. **B4 + 独立策略**：可以冻结自己的入场、持有、退出规则；这会成为新的策略定义，不能预先声称等同 E0。
2. **B4 与原 E0 并行**：输入仍包含原始 OHLCV 时，可以独立执行已冻结 E0 并保留它的支持与等待记忆，作为显式兼容通道。须沿用原 E0 的预热、有效观察、来源/复权坐标、数值比较及处理顺序。它实现的是继续计算 E0，不是从 B4 指标简单映射出了 E0。
3. **扩充 B4 输出以暴露 E0 所需证据**：这是另一个接口/机制版本的设计问题；本验证没有实施，也不宣称只补一个 low 字段就足以解决全合同、初始化与数值等价。

这个反例否定的是“对所有合法行情百分之百复现”的普遍保证；不排除某个有限历史集上碰巧动作一致，也不估计实际市场分歧频率。尚未运行账户，不能把信号分歧换算成收益或成交差异；收盘信号与次可成交时点执行仍须分层。用户暂固定 B4 不会自动改变 E0 的既有名称、定义和源码。

复现时指定新的 validation 子目录，脚本拒绝覆盖原输出：

```sh
PYTHONDONTWRITEBYTECODE=1 TradingAlarm/research/.venv/bin/python \
  research_rounds/b4-baseline-contract-20261025/validation/prove_b4_e0_information_loss.py \
  --output research_rounds/b4-baseline-contract-20261025/validation/compat-output-replay-new
```
