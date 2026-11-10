# V4接口：CP事实、旧保护与新增许可

状态：其中V4“一发行即消耗”控制器已被用户V4.1取代，不可用于V4.1实现；保留此稿作历史。源代码事实仍有效，V4.1执行目标分析另见V4_1_EXECUTION_TARGET_REVIEW.md。

仅静态源码与三条已存源记录读取，0账户、0新CP计算、0测试、0资金参数。已亲读主SIGNAL_FREEZE_V4.md；其选择CP*重算、一次permission发行、唯一purpose，取代本线先前未冻结的通用意图束建议。以下伪代码是信号接口合同，不冒充原账户已经支持它。

## 核心源结论

| 源／行号 | 真实动作 | V4边界 |
|---|---|---|
| `continuous-protection-lines-20261028/code/model.py:30–38` | source变更／未ready／I输入失效清内部phase/锚/credit；负原E0事件重设SEEK、锚=本日logC、scale=当日z；SEEK下再创新低也重锚 | 仅CP内部市场状态，不持有账户层对象 |
| 同文件40–50 | 仅新frontier位移计credit；displacement、credit都≥sqrt5×冻结scale且当日真新frontier才receipt；candidate=C·exp(−sqrt21×旧冻结scale)；随后重锚并冻结next_scale | `q.scale`是产本收据的旧scale，`q.next_scale`不是；market `receipt_consumed`不是账户消费 |
| `case-stock-cp1-warmup-20261031/generate.py:23–27` | `e0_valid=f.i_target.astype(bool)`，`e0_down=原event.eq(-1)` | 名字e0_valid实为旧I_hold输入。mature下降不得喂到这里当I失效；否则人为清锚、改变后续收据 |
| `joint_v3.py:225–240` | ACT/off I先整股申请退；MOBILE先C<=旧层floor才退，否则再max(old,I线,当日receipt candidate)；CORE继承I线 | **负E0 reset不清、不降低已持MOBILE保护**。若同日破了原I/层旧线仍会退出，不能把退出因果归给CP清锚。新增mature门也不能阻断旧层原保护更新 |
| 同文件243–257 | CORE eventQ+flat+core_epoch未用；MOBILE freshCP+continuingQ；新MOBILE初始线max(I,该CPcandidate) | 新probe不等于原CORE；若有持仓还想probe，旧CORE的not-held门并不允许，仅改role名不成立 |
| 同文件302–322 | 下一OPEN先退出/结算/sync，再按PVR与CORE先序处理原意图；每sid成功reserve后进done；之后才查买入window | 原done防同OPEN重复成功reserve，但不是跨阶段共享证据账 |
| 实际No60 `EFFECTIVE_NO60_ROUTE.txt:4–28`、`EFFECTIVE_NO60_MODEL.txt:215–259` | 正常route先纯搜量，q0不request；mobile request才查并消费CP ID；request内部先写request ID/consume，再migrate与终检 | 不能把request当无副作用preview调用两次。CORE并不会自动消费同日CP；当前CORE锁是实际fill后写，不能拿它充当UP周期锁 |

绝对路径与原文逐行摘录在V4_CP_SOURCE_EXCERPTS.txt。No60有效route/request来自已验证的静态还原，confirmed60/global3%已移除；未引用旧模板的这两个门。

## 三种“消费”不能混同

1. **CP市场receipt_consumed**：模型在发收据当日把下一锚移到当前价；不管有没有下单都发生。
2. **账户CP consumed**：Budget的单次token记录；现mobile request会写，core不会。reserve后零fill/撤单也不自动返还该证据。
3. **V4一次up周期probe**：应以原UP确认观察的`up_cycle_id=(sid,source,up_confirmation_observation_id)`记，不能用每天可fresh的G1 i_buy，也不能用长E0根或原CORE epoch替代。一个逻辑请求的partial fills不算多次probe。

主V4已明确选择**信号层一次成功发行**，不是一次实际试仓成交。资金拒绝、跳空取消和零fill均不返；这是明确的miss代价。CP*使用V3 I_hold/P重新计算，不能把本表原CP数值或旧canonical ID充当CP*。

## 真实共享价格观察，不是假收据

| 原日／股票 | 原I／G1 | 原CP已存事实 |
|---|---|---|
| 海能达2024-10-18，C_adj67.158178251/raw11.95 | I_buy=True，G1=4，fresh理由为S21 running price frontier | receipt=True；delta_frontier0.095644964，displacement0.119877277，credit0.160955117；used_scale0.0277129564，next_scale0.0325065397 |
| 太保2024-09-06，C_adj45.080416968/raw30.99 | I_buy=True，G1=4，同running frontier理由 | receipt=True；delta_frontier0.024168387，displacement0.044539771，credit0.056663276；used_scale0.0117667284 |
| 太保2024-09-18，C_adj44.294891794/raw30.45 | I_buy=False，G1=−3，fresh=False | **仍receipt=True**；delta_frontier0.026623869，credit0.036225236；used_scale0.0120176165 |

G1 fresh的当前C价格推进与CP `p-frontier`都可消费同一CLOSE涨价观察，但formation区间、尺度和量修正并不相同；太保9/18也证明二者不是等价公式。不能称CP未有真实新推进、重复旧receipt；应防的是把共享观察当两张独立趋势证明／两份新增请求。CP candidate低于旧层floor时旧层只取max，新的收据不等于旧仓真的提线。

## 最小信号伪代码：主V4唯一purpose

```python
def decide_CP_permission(row, ctx, ledger):
    # V3/CP* kernel各处理本日市场观察一次，不在重复调用时重发up信用。
    # 每个固定HELD/FLAT条件分支各有一份ledger，不是两账户实单。
    cp = row.current_CP_star_receipt
    if cp is None:
        return 'NO_CP'
    key = (row.cp_version, row.sid, row.segment, row.confirmed_CLOSE_day)
    if key in ledger.decisions:
        return ledger.decisions[key]  # 同key只返回原decision/intent_id
    if not ctx.known or not row.source_and_CP_known:
        return ledger.remember(key, 'UNKNOWN')
    if ctx.pending_exit or ctx.pending_buy or ctx.cancel_ack_pending or ctx.exit_required_today:
        return ledger.remember(key, 'BLOCK_ORDER_RESPONSIBILITY')
    if row.I_hold is not True or row.up_after_R is not True:
        return ledger.remember(key, 'BLOCK_NO_HOLD_OR_NEW_UP')
    if ctx.has_position and row.I_expand is True:
        purpose = 'MATURE_CP_ADD'
    elif ledger.up_credit_state == 'UNUSED':
        purpose = 'START_CP_PROBE'  # HELD或FLAT，后者永不伪ADD
    else:
        return ledger.remember(key, 'BLOCK_UP_CREDIT_USED')
    # 一个原子permission发行：claim CPkey，结清本up未用信用，写唯一outbox。
    return ledger.issue_once(key=key, up_key=ledger.up_credit_key, purpose=purpose)
```

每个原正event只创建一份新UNUSED信用，旧信用不累积；每个负event关闭旧信用。issue_once给PROBE或ADD都结清unused probe，因此同日up+mature+CP、有仓时只ADD一次，无仓时只PROBE一次；以后HELD仍mature且出现**另一个真实新CP***，可再ADD，不是同up只许一次成熟扩张。

purpose不是旧预算pool/role/kind，不能直接改名塞进旧request；V4明确新PROBE也按MOBILE/add保护，**原无CP的I-only CORE入口消失**，不再是原CORE优先／失败后MOBILE fallback的同一算法。可能晚入、漏入或保护更紧，不能称保留所有旧买入。现Budget.request非纯预检／原子发行接口，未来若接线需单独桥接；本轮不接。

新mature只能作下游新增许可：不要赋给原`row.i_target`，否则J225会全股退；不要赋给CP输入e0_valid，否则清锚；也不要用它跳过已有层保护。主V4选择新I_hold/P作为CP*输入，所以候选值／收据时点本来可能改变，即使max持有规则不变也不能声称原退出路径已完全保留。本线只读原CP，不声称旧三例在CP*仍有同样收据。

## 仍不能解决什么，以及两处必须消歧的边界

- 每个真实新up仍能新发probe；量价反弹事件可能反复发生在下降结构，once只限制一个up周期，不限制周期数，也不证明下次是真的。成熟恢复与CP*同依赖上涨，去双发行不等于获得两份独立证据；盈新式真突破后失败仍可能获许可。
- FLAT首permission若没成交，同up信用仍耗尽，后续即使持续强涨也不能当ADD；这是发行once的miss代价。条件表不自动把PROBE变有仓，不能把HELD分支的后续ADD假装成FLAT真实路径。
- 主卡要求“跌回R未用probe不能补领”，但若仅在**发行ADD时**烧credit，市场曾mature却无CP或被订单锁挡发行、随后失mature时，unused credit仍可能落入PROBE分支。若本意禁止此类fallback，需退权时结清unused credit或记录mature_seen；若仅指已发ADD后的fallback，现burn已覆盖。不能依靠预期CP序列代替明确状态规则。
- 本日新support_exit与新代up并存时，HELD分支必须先落实对应层／代际的exit_required_today；只读昨日pending_clear再看新I_hold=True会抹旧退出。FLAT没有旧仓责任，两者不能用同一个虚构仓位替代。已有外部锁的反例不能代替这个同CLOSE新退出案例。
- CP kernel要求完整有限close/amount与显式bool valid。已准备后未知不能简单dropna、bool(NaN)或未来补值；本线未验证缺失后的CP*恢复状态，须沿主卡显式UNKNOWN规则报告，不能把原CP缓存补进来。

本线不要求新增阈值、资金方案或测试扩张；上述是接口真实性和能力边界，不是收益结论。
