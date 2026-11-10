# 原CP负路径与数据准备：尚未运行候选余额

本线仅提取现存原CP、原generator input、facts及已存V4 CP*显示行；没有重新生成CP、计算候选B、拟合、账户、数量或收益。`CP_B`是原成交额21日中位数，绝不是候选余额B_t。

## 已见事实

| 固定窗口 | 原CP观察日 | r<0日 | 累计负log幅Σmax(−r,0) | 原receipt |
|---|---:|---:|---:|---:|
| 盈新000620，2022Jan | 19 | 6 | 0.5483485368 | 9 |
| 海能达002583，2024Jan | 22 | 11 | 0.3565938808 | 0 |
| 海能达002583，2024Sep—Nov全月 | 58 | 24 | 1.0486391804 | 20 |

累计负log幅仅描述原路径，不能当候选B或未来亏损。原receipt日、每个原reset_reason、r/m/fresh/used scale/candidate及输入I状态均见`ORIGINAL_WINDOW_DAILY.csv/json`。

盈新最直接的原链：1/14 raw C=3.78；1/17、18、19的raw C依次3.59、3.28、2.99，原r分别−0.0515718071、−0.0903087801、−0.0925700350；原reset依次down/lower_anchor/lower_anchor，credit归零。1/20 raw C=3.29，fresh=0.0956141774、m=1.4284789781、used_scale=0.0317145783，原credit=0.1365828424即发receipt；1/21、24、25又各发。不是拿当前s/next_scale替换历史冻结scale。

## 原公式确实遗漏什么

真实母体：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py`。

- 22—24行：r=log(C)差；s为前63个|r|中位数×1.4826；量调制m=1+0.5|tanh(r/s)|tanh(log(amount/Bamount))。
- 30—38行：source、unready/invalid、down、lower_anchor控制原锚与credit。unready/invalid归零；down/lower_anchor换当前价锚并归零。
- 40—45行：只有超过已见frontier的增量fresh才加`fresh*m`；负r不直接扣credit。收据要求fresh>0、位移与credit均达到sqrt(5)×冻结scale。
- 48—49行：每次原receipt之后原CP内部再次重锚、credit=0、下一scale改当时z。该原内部消费与账户消费是不同的账。

所以保留reset以前的负路径是新增的信息，不是原CP credit的重命名。但CP原高点/重置仍使用同一价格序列；不存在新增独立外生证据。

## 候选数学审查，尚未算任何历史B

对拟议`B_t=(20/21)B_prev+fresh*m−max(−r,0)`：

1. 在连续同源CP观察内，fresh>0意味着当日r>0（上一收盘不高于旧frontier）。两个完整原prefix实际同日fresh>0且r<0均为0。因此不是同一bar把同一次跌幅一边奖励一边扣除。
2. 这不是净log收益。忽略衰减、量调制与重置，余额为`Σ新frontier幅度−Σ下跌幅度`；净log收益则是`Σ全部上涨幅度−Σ下跌幅度`。两者差了未创新frontier的恢复上涨。1→0.9→1一圈，新frontier贡献为0而跌幅已扣；收复旧高不偿这笔债。这可以是故意较严的“恢复不补账”定义，但若称净有效价格进展，就隐含重复惩罚恢复的经济选择。
3. 20/21同时衰减正信用和负债。无新进展的静置会使债务趋零；不能同时宣称只有新进展才能还债。持续缓慢单向上涨也可能因正信用衰减而达不到门，不能仅讨论削弱反复反弹。
4. 原receipt即使未通过候选门，仍会按母体重置CP锚/scale。候选B若保留，则会跨多个原receipt累积；effective pass后清零与原receipt归零必须分别写，不能误把任何原receipt都清B。
5. 原down/invalid/lower_anchor“只清正余额”与当日r扣减的先后必须冻结，且只扣一次。source/缺失/ready边界、首个可比r的初始化也须明确；本线不自行补ε或把缺值当0。

## 数据范围、已有CP*及缺口

原native CP完整prefix：盈新2013-01-04至2022-01-28共2178行；海2013-01-04至2024-11-29共2852行。各自前64行原CP未ready；本次三类native CP/input/facts在prefix内索引一致，没有窗口字段缺失。两股原input都只有segment0；源码中的`source_reset`原因可能被同日unprepared/start覆盖，因此不能只看最终reset_reason判断是否发生source边界。

上游E0 price source相对CP曾有2015-06-02这一额外观察，是既有V4记录的排除项；本线未把它补进native CP或重算r。此事实不等于native facts本身也包含该日。

已存V4 CP*输入是V3 I_hold/P，旧native CP输入是旧I_target，不能互换：海2024Jan旧CP无receipt，已存CP*却在1/25有一张。盈新Jan两者都9张；海Sep—11/27都20张。11/28、29只有原CP完整字段，没有既存V4显示CP*，在输出中明确为`NOT_SAVED_IN_REUSED_V4_DISPLAY`，没有补算。

候选要以旧native CP还是CP*为底层必须由主freeze指定；完整prefixCSV是旧native字段，选窗JSON另附已存CP*，绝不混列为同一母体。等待freeze期间候选执行数为0。

`SOURCE_MANIFEST.json`绑定原文件与提取脚本；`SUMMARY.json`记录原计数及缺口。`ORIGINAL_FULL_PREFIX.csv`均由现存字段直接复制，未运行任何模型。
