# V4.1：CORE微仓、真实执行完成与市场成熟

只读源码／已保存原账和纸面合同。0新q、账户、回测、模型或测试。V4发行once方案已被取代；本稿不继续其零fill仍耗probe的规则。

## 1. 盈新CORE的微仓不是原计划只有100股

原layer68：2022-01-10 CLOSE的cap=3200股、gross budget=8804.37元、risk_budget=2489.220370263785元，I线raw约1.98、参考价2.741370。次OPEN原价3.01，真实reserve只批准100股，随后fill100股，执行价3.011505，含费买款306.17721204935元。**计划cap、实际获批订单target和真实fill是三个量。** 该笔不是3200目标仅部分fill100，也不能仅见微仓就说原CORE有意只做最小手。

真实源：`LR study.py:16,19–31,42–60`先以原0.25%NAV参考到I线风险（含原双边费/slip）及10%gross求合法计划cap，OPEN preview只缩；实际No60 route还搜probe资本/风险、行业资本/风险、现金/单股等可行量；`native_rank.py:76–91`只换rank，不改目标。原slot的每个allowed(q)约束余量没有在此证据中逐项保存，因此本线**不猜唯一binding门、不新算q**。真实reserve100证明缩量发生在实际订单批准前，不是成交容量仅给了100。

原 [pilot.py:59–70](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:59) 每个真实partial receipt都建层，CORE任何正fill就写core_epoch；所以原core_epoch锁≠target_complete。原 [J244–245](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:243) CORE还要求flat，MOBILE不要求先有CORE或CORE完成；原盈新下一笔MOBILE69实填6300股，是不同来源/契约，不能说由100股“已验证”推导出来。

## 2. 不加价格门的执行合同

一个共享slot绑定同一事前批准的probe_id、target版本、来源事件、数量域、支撑来源及holding_chain_id。CORE和CP可以提供申请来源，不能各建一个target或同CLOSE发两单。主V5已明确slot按单次原UP事件，不是整个E0 target根或I financial epoch；三者原代码并不相等。

```text
desired_cap       = 原CLOSE意图上限（不是执行完成分母）
approved_target_Q = 原数量/准入模块事前批准并登记的统一执行目标
filled_Q          = 该probe_id真实buy receipts累计股数，按CA同域调整
remaining_Q       = approved_target_Q - filled_Q

executed_probe_target_complete
  = 有明确approved_target履历
    AND filled_Q == approved_target_Q
    AND 没有该目标的未决订单／取消ACK责任
```

target必须在对应fill前批准、版本化；不能按已成交100事后把原目标改100来毕业。反过来，若确有事前批准target100且全填100，可以说这个执行目标完成，不能再说它验证了趋势或等同3200计划完成。desired cap与approved target两字段都保留，避免迁移时择有利分母。

状态转移：

| 真实状态 | 合同结论 |
|---|---|
| reserve但0fill、尚有买单/撤单/ACK | 不完成；不并发再申 |
| 从未正fill、全部取消ACK完成 | probe机会未实耗，可按当时合法来源再申；不是自动退还CP市场状态或复活过期信号 |
| 首个partial正fill，0<filled<target | once已实耗，但target尚未完成；target冻结，不能降成filled或重新发满额target |
| partial余单已取消ACK，但仍remaining>0 | 仍未完成；可有同probe_id的completion续单通道，不是第二次probe |
| target真实填满且ACK责任清 | 只有执行complete；无固定等待、盈利、1R或保本附加门 |

partial后的completion分支必须独立于“probe信用UNUSED”判断，否则首fill耗信用后，未完成目标会永远无路补剩余。它只申请同target剩余，不借新CP刷新目标；仍须原订单/来源有效、当前保护有效、数量和资金准入允许，不自动每天追单。复权/拆股须同时改target、filled、remaining及单位；不是所有证券都100股一手。

账户CP token消费与probe实耗仍是不同账。原Budget.request在fill前已消费CP，取消并不会自动返；当前接口也不天然支持同CP重试。若要重试同一逻辑授权，需保同probe/intent归属而非第二份CP信用；若用下一合法CORE/新CP来源续单，也只补这个remaining。原CP kernel的anchor/receipt_consumed绝不因订单取消回滚。

## 3. 市场成熟与执行完成是两个必要概念，不是互证

主核心可解释为：

```text
ADD_eligible = 当时有仓及无未决责任
               AND 当前market_mature
               AND 本holding-chain中事前登记的probe target已执行complete
               AND 其资格按主卡仍有效
               AND 在完成/ACK后新发布的CP
```

连续赢家可以沿同一合法holding-chain复用早先UP已完成probe，不必每个新UP再等一次试仓；但不得借新市场generation抹掉旧结构退出责任。任何MATURE_ADD正fill再实耗其所属UP的probe机会，可避免失成熟后凭unused credit再开一份probe；零fill全ACK则不应假称已实际参与。callback只更新已知、绑定的slot/UP，不拿未来收盘事件回填上午成交。

最快时钟：首单在OPEN真实完成且ACK清，之后首个合法CLOSE若市场已成熟、新CP也发布，即可提出下一订单；不加固定等待。原同CLOSE的CORE与CP不得在次OPEN因为CORE刚fill就再变第二张ADD；完成条件不能回填到前一决策时刻。

**target_complete只说明订单执行，不说明趋势真实、交易已盈利或下一次CP有正期望。** 完整100股仍然是小目标；若原每CP层允许较大新增，规模跳跃依然可能发生。唯一可声称的约束是：complete不额外创造资本额度，新增仍独立通过原每CP数量／风险／行业／现金规则；本轮没有新资金规则，不能保证金额跳跃消失。不要为此暗加最小金额、仓位比例或等待门而再次错失强启动。

## 4. legacy adoption与仍需公开的张力

旧CORE“有仓”不自动成为新probe。adoption至少显式绑定原真实approved order（不是只看fill）、原3200 cap、原批准量、真实receipts、source/数量域、holding-chain与采用规则；不按后来盈亏临时选择100或3200分母。原core_epoch、任意held bool、利润、floor>=entry均不能代替该记录。

保留两个反例：

- **tiny complete**：target100确已事前批准并完成，market_mature也真，下一CP仍可依原规则申请较大层。它没有伪造执行完成，但仍不能叫小仓验证成功后“安全放大”；同价路径证据依旧可能共同失败。
- **probe来源归零但ADD仍健康**：分层保护异质，probe层先全部退出、后续MATURE层仍持有。主V5已选择保守不自动继承，后续ADD资格会被切断，可能又得等新UP试探；这与“不每UP重probe”的赢家目标有张力。若未来允许资格在连续holding-chain内承继，须显式adoption／承继记录，不能退化成任意held=True。本稿尊重当前选择，公开代价，不声称已两全。

主核心不必违背同slot原意：只要CORE/CP同一个probe目标、partial无重置、同CLOSE无双单，执行完成与市场成熟保持独立。但它只防0fill/partial/历史微仓被伪装为完整执行，**不能据此证明真假趋势分离或经济收益**。旧行情与CP*尚未在新账户接通，本轮不下该结论。

对主V5伪码还提交三处小闭环：顶层显式拦legacy pending_buy；0fill目标RETIRE后同slot如何rearm与“每slot一parent”一致；最后一条terminal ACK到达时也需reconcile并首次登记complete_known_at，不能只在on_fill判断完成。原CORE held/core_epoch锁在planning与Budget.request都有，parent续单未来须同时正确识别，不是仅绕过一处入口或把role改成mobile。本轮未实现这些桥，也未因此扩大测试。
