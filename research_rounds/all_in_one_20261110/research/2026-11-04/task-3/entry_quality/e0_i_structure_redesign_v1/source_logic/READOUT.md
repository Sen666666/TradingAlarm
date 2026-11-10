# E0／I／CP：实际数学与结构重设计质疑

本轮只有静态源码阅读和纸面算法。资金候选未写candidate/run_account、未启动账户/测试/后台进程；没有导入策略、运行模型、回测或继续资金实现。以下替代是待裁决假设，不是已验证改进。

## 1. 实际E0事件确认的是反转，不是上升结构

原数值源 [numeric.py:58–136](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:58)，实际B5抽出的事件部分为 [evidence.py:92–157](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:92)。同一原source段中，只用C、V均正有限的事件观察，设正在发展的摆动方向为d∈{−1,+1}、对应极值观察为p：

```text
r_t = log(C_t/C_(t−1))
σ_p = max(sqrt(Σ_(j=p−63,…,p−1) r_j² /63), 1e−8)
B_p = median(V_(p−21),…,V_(p−1))
a_(p,t) = clip(sqrt(mean(V_(p+1),…,V_t)/B_p), 0.5, 2)
confirmation_t = (−d)·log(C_t/C_p)·a_(p,t)/(sqrt(5)·σ_p)
confirmation >=1 ⇒ event_t=−d，确认pivot=C_p；direction←event，extreme←t
```

下行d=−1时继续创更低收盘就更新p；反向反弹达到确认阈值即发+event，确认先前低点。上行d=+1时对称：−event确认先前高点。σ和量背景按极值p冻结；确认量活动均值包含当前CLOSE已知量。RMS、此前63/21观察和sqrt5来自原代码，不可拿B5强度/CP的MAD尺度替代。gamma4只是浮点并列约定，不是经济有效幅度。

**+event没有比较相邻低点，也不要求C收复前一高点。** 下跌结构中的一次局部反弹可以合法产生新+event；它是真实新反转证据，不能说是无新价格变化或重复凭证，但不能自动解释成HH/HL趋势。

极值发生日p与确认日t是两只时钟。只有t收盘才能将p标作确认pivot；不能把结构信号回填到p。缺量不产生该量价事件；B5在完整价格观察上重建输出，价格有效但量缺失时仍可检查旧保护线。原source/无效价格边界不是自然日计数。

## 2. E0参与target与I target为何能继续True

[policy.py:86–114](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:86)：

1. active时先检查 `C<=旧floor`，触及即exited；同日不重新开启。
2. +event且已active，`floor=max(旧floor,确认低pivot)`；inactive且不是同日刚退出，开启target，floor取该低pivot。
3. 单个−event不关闭E0 target。event是当日脉冲，target是仍未破参与边界的持续状态。

原policy还实现过decline participation memory，但**当前native路径关闭它**：[cache.py:23–28](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:23) 及 [refresh.py:55–57](/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py:55) 明确 `decline_candidate=False`。不能把未启用的previous-close reclaim机制当当前退出后的结构恢复规则。

[policies_g1.py:16–34](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:16)：

```text
warm = G1.ready AND grade>=2
fresh = G1.fresh_up
opportunity = E0.target AND warm AND (E0.entered OR fresh)
I active时：若 !E0.target 或 C<=旧I_floor ⇒退出
否则：I_floor←max(旧I_floor, E0.floor)
I inactive且非刚退出，opportunity成立 ⇒ I active
I_buy = I active AND opportunity
```

`G1_I`的use_x=False，因此即使代码计算cold，也不会因cold退出；cold退出属于G1_X/IX。`fresh_up`可能来自新E0正event、新S21/S63确认或已确认S21上结构内新running frontier（grade.py24–29）。它不必每天发生；没有fresh不是I持有失效。

这是一种有意的entry-only强度确认与较长价格边界持有，不是“没有任何保护线”的代码缺口。但若把 `I_target=True`解释为“当前G1仍暖／当前趋势已重新验证／可再次扩张”，语义就错了。原MOBILE又用continuing Q替换当日buy_allowed，因此新CP可在grade<2、i_buy=False时继续产生申请，这已由原日志而非猜测确认。

## 3. CP并非对I完全独立的第二趋势证明

当前真实输入 [generate.py:23–27](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stock-cp1-warmup-20261031/generate.py:23)：

```python
out=f[['close','segment_id','i_target','i_floor']].copy()
out['e0_down']=ev.event.eq(-1)
out['e0_valid']=f.i_target.astype(bool)
```

名字e0_valid在股票CP链上实际是I_target。CP [model.py:26–50](/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py:26) 在I失效时清phase/anchor/frontier/scale/credit；I复活会重新SEEK。另有原−event reset与lower-anchor reset，因此旧全局高点下面也可有合法局部新receipt。

CP冻结尺度是MAD：`s=max(1.4826·median(此前63 |r|),1e−8)`、`z=max(s,log1.001)`。仅新frontier位移累积credit；位移与credit均达到sqrt5×冻结scale且当天有新frontier才receipt，候选保护为`C·exp(−sqrt21×冻结scale)`。量调制与E0的区间均量活动不同，不能混为同一数值证明。

所以I、CP共享价格且CP的生命周期受I状态控制。改I后若仍用这份输入，就必须重新生成相应CP状态/收据，不能复用旧I产生的CP缓存假称仅改一个门。若解耦，应显式选择CP输入raw E0参与target/原负event还是其他市场有效性合同，并把I仅作为下游使用许可；这是算法接口变更，不是改名或统计独立性保证。

## 4. 对“相邻确认低点抬高 OR 收复确认前高”的质疑

OR把两类不完整证据都直接升级：

- HL-only：已确认L0=80、H0=100、L1=82，当前C=90。低点抬高，但没有收复H0；后续lower-high若又把“前高”调低，收缩反弹可被一步步洗成趋势。
- reclaim-only：已确认L0=80、H0=100、L1=70，当前C=101。突破前高，但低点更低；可能是强V，也可能是大幅双向波动，不能当已证明HL结构。
- 两者均使用同一路径，不构成两张独立alpha凭证；“已确认”还必须按confirmation时间，而非pivot发生时间判断。

这些数字是假设已确认pivot输入，用于逻辑反例；未声称原E0数值检测器已在这些裸数字上生成对应事件，也没有运行合成模型。

## 5. 一个可计算替代：冻结前高的成对结构证书

建议保留原numeric事件，增加真正结构层；**HL仅表示RECOVERY，HL与同一START待收复前高共同满足才CONFIRMED**。这是结构定义更完整，不是已经证明收益更好。

定义：每个低/高pivot都存`pivot_id、price、occurred_at、confirmed_at、source_segment`。raw E0参与从off→on时进入START，冻结当时已知最后一个确认高点H_ref，之后不能被lower-high调低；若开始时无高点，保持上下文未知，首个确认高点出现时只补齐一次。反复+event但raw target未off不重置START或H_ref。

```text
HL_t = 最近相邻两个已确认低点满足 compare(L_new,L_prev)>0
        且中间有因果顺序正确的已确认高点
RECLAIM_t = compare(C_t,H_ref)>0
START→CONFIRMED：HL_t AND RECLAIM_t AND 同段完整上下文
证书支持线 F = L_new；记录当前确认低点ID、H_ref ID和确认收盘t
```

H_ref锚在START冻结，HL不能沿用被更近下破低点否定的旧“曾经HL”位。若START当天已有因果可用的HL且C已在已知H_ref上，可在该CLOSE确认，不强制再等一天，也不冒称这是START后新形成的证据。低点恰在本CLOSE才确认，也只能在该CLOSE结束后使用；下一执行时点照原时钟。

**延续明确**：CONFIRMED不是每天重新要求fresh。保留到原参与边界失效或`compare(C,F_old)<=0`；同CLOSE旧线先判，失效优先，不以当天新低确认撤旧退出或同日复活。新的有效证书只可抬支持，不能放宽旧线；若同时保留原E0边界，实际保护取`max(F_struct,原E0_floor)`，不得拿较低证书线放宽原保护。数据未知时对外输出UNKNOWN而不制造新证书。单个−event只是高pivot确认，不自动等于趋势破坏。C回到H_ref下但支持未破，记回踩诊断，不在本提案偷偷增加第二条退出线。

若采用此替代，新的结构target必须明确指CONFIRMED，START保留为启动事实，不能继续同一个bool两种解释；I以结构有效性作shadow，新的I entry仍沿原ready/warm/fresh，持有不因没有每日事件而自动退出。CP的市场receipt与I许可应显式分开，不能靠I开关清锚当“重新验证”。本轮只提出接口方向，不修改当前输出或复用旧CP冒充新模型。

最强反例与限制：深V已越前高但低点更低会迟确认；单边急涨没有回踩第二低点也无法形成HL；已确认HL+突破仍可马上失败。若L0=80/H0=100/L1=90/C=101，随后88就击穿支持——证书证明的是当时结构，不是未来走势。很小HL/HH也不自动具有经济意义；原反转尺度不是获利保证。已知历史研究中旧高等待伤过赢家，不能把本提案因名字换成“证书”就当作排除了这个代价。

## 6. 裁决范围

最关键源事实是：**反弹event≠上升结构target；I_hold≠I_buy；CP receipt的有效区间又由I_hold输入塑形。** 应先明确要保留哪一种持有哲学，再决定结构证书与CP许可怎样映射。若仅把OR换成AND却不定义持有延续、旧线优先、原pivot时钟和CP重算边界，仍不能得到可执行算法。

本线不做账户、参数、指标重算或6股timeline；源码原摘与SHA另存SOURCE_EXCERPTS/SOURCE_SHA256。没有经济有效性、最优阈值或未来收益结论。
