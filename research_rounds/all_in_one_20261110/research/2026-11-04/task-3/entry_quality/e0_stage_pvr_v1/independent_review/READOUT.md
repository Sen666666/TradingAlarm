# E0确认峰谷：源码与保存字段独立取证

结论：当前stock_signal真实调用的numeric事件是因果确认事件；已确认局部峰/谷的“发生日”和“确认日”不同。原事件表保存发生日/峰谷价/观察滞后，确认日是事件输出行的index；没有保存真实确认时刻、行情发布时刻或接收时刻。现有单日19字段已丢弃这些峰谷细节，不能直接恢复。

本审仅读源码/AST、最新signal表schema与原盈新两条既存event；零模型、零账户、零事件重构。原11算法SHA与2026冻结一致；旧封存目录未修改。完整逐行最小片段见[SOURCE_EXCERPTS.md](SOURCE_EXCERPTS.md)，来源SHA见[SOURCE_SHA256.json](SOURCE_SHA256.json)。

## 实际调用与双日期

[stock_signal.py:29](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:29) 固定 `event_frame_numeric(f.close,f.volume,joint=True,event_exit=False)`；34行把当前确认event和pivot价交给E0，40行重建E0，46行投影G1_I。原native [cache.py:23](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:23) 对既存event执行相同E0/I消费；并非从未来极值重建确认时点。

[numeric.py:95](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:95) 的核心顺序为：先检查旧floor；仅严格新close极值才把ext改成当前；`t>ext` 才计算反转确认；达到阈值则当前行写 `event=-direction`、`confirmed_pivot_price=prices[ext]`、`pivot_age=t-ext`、`confirmed_pivot_date=d.index[ext].date()`；最后 `direction,ext=event,t`。每行最多一次，不当日递归第二个反转。

因此 `+1` 是确认此前close谷、进入上行leg，`−1` 是确认此前close峰、进入下行leg。不是日内HIGH/LOW枢轴。`confirmed_pivot_date` 的名字不表示确认日期；确认日是 `row t` 的index。`confirmation` 是数值确认强度，并非时间戳。[numeric.py:130](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:130) 只按当前行建表再reindex，不把事件写回ext发生日，pivot信息也不向发生日前回填。

原盈新同源既存event两例（不是新canonical价格）：

|确认行日|event|确认pivot发生日|pivot价|pivot_age|
|---|---:|---|---:|---:|
|2022-01-06|+1|2021-12-31|2.255055048923375|3有效数值观察|
|2022-01-17|−1|2022-01-14|4.305105093399171|1有效数值观察|

这些index为日标签；不提供当年几点可见的证明。将1/17确认的峰倒填到1/14来给1/14–16排序，会产生未来信息。

## 冻结尺度、有效观察与同日优先

[numeric.py:74](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:74)：sigma是当前之前63个局部logreturn的RMS（1e−8数值地板），量基准是previous21成交量中位数。反转使用极值当时的 `sigma[ext]` 和 `baseline[ext]`；activity只累计ext之后至当前t的已完成成交量，平方根后clip .5..2。阈值为 `(-direction)*log(Ct/Cext)*activity/(sqrt(5)*sigma[ext]) >=1`，不是CP/G1的MAD尺度。达到阈值需要当前完成日线；不能声称发生日当时已确认。

[numeric.py:23](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:23) 的gamma4数值tie保早极值/原日期；只有strict新极值换ext。数值事件只在finite正close与volume观察上推进；reindex后event0可来自未观察/无效行，不能仅以0断言那天已知“无事件”。未预热leg也未知，初始默认下行不代表已有一个确认峰。

[E0 policy:99](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:99) 先用旧floor比较当前C并标exited，106行后处理up事件；退出行的 `elif not exited` 禁同日重新入。down事件本身并不硬退E0：当前配置event_exit=False，policy也仅以+事件作入场/ratchet；stock_signal的decline_candidate=False关闭额外参与回收支路。

[G1_I project:20](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:20) 先检查E0 shadow与旧I floor，再ratchet，30行同样禁止退出当日再入。G1_I的暖门是entry-only；不启用G1_X cold退出。因此 `numeric_event=-1`、`numeric_leg_direction=-1`、`e0_exited=1`、`i_exited=1` 是不同事实，不能互作别名。

## 19字段能否原样恢复

[stock_signal.py:47](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:47) 最后只返回E0五列、I六列、G1五列、numeric event/leg与close共19列。pivot价、pivot发生日、pivot_age、developing extreme价/日、confirmation、sigma/baseline/activity和确认时刻均不在返回字段；最新ALL_SIGNALS的schema也未保这些pivot字段。

单日event方向、leg、当前close与E0/I ratchet floor不能逆推出历史峰价：floor主要承载生效谷线且会max，既不保存高点，也不保留被较高旧线吞掉的低点。数个固定日期snapshot还缺中间事件。若另有同源完整有效close/event序列及mask、segment、初始化/tie，理论上可额外重构极值；这不是现有19字段直接读回，本审没有做该重构。

部分原1709的prepared events确实保存pivot价、发生日、age与确认行index，可在source/factor/segment完全一致时按确认行as-of读取；不能替代当前canonical5517重算的不同源事件。当前全本地样本若需此状态，应额外保存模型当时生成的event细节及source/prefix/code身份，或另获授权从<=t前缀重构。真实available_at仍须独立数据证据，不能把名义日线CLOSE时钟伪作历史发布时刻。

本次取证PASS；未来E0阶段/PVR分析的峰谷输入尚不在19字段中，不能据此声明其已可生成或已验证。
