# V5：保留CORE，试探按真实成交消耗

用户已否决V4删除CORE及发行即耗。V4授权结果仅保历史，CP*市场事实可复用。本文件是修正后的伪代码和条件演绎；未跑账户、未生成新数量/现金/收益，未声称原账ACK足以运行新执行路径。

## 1 分清市场、执行、规模

- 市场I_hold/I_mature沿V3；CP*原公式以I_hold/P形成，mature只管新增。负E0撤mature不强卖；保护/结构退出仍先检查旧线。
- 保留原CORE eligibility、flat及core_epoch入口，不要求当日CP，也不要求mature；续同一已批准target不再当作新CORE，不被自己第一次fill后的held/core_epoch锁错误阻断。
- CORE与CP共享同一次原UP事件的trial slot：key=(sid,source_segment,up_event_id)。这不同于整个E0 target root或行业financial epoch；新UP才有新slot，名称/role切换不重发。
- CORE或CP同收盘最多一个目标；flat时原CORE优先。CP若同日出现，绑定该意图而不另发MOBILE。CP市场重锚、CP防重放、up真实成交记忆是三本账。
- cap是策略/风险提出的上限；approved_target_Q是下单前明确批准的固定目标；filled_F是真实去重累计成交。三者不同，不能看到held=100就事后定义Q=100。

## 2 目标与订单状态

每个probe slot最多一个probe parent target。事前固定target_id、approved_target_Q、保护类型、source_refs、up_key及风险约束。任何改价/重申/role补充不增加Q；新子单只追同目标余量。真实企业行为可按同一比例调整Q/F/leaves，不是新额度。

```
F = sum(unique execution_id 对应的历史买入成交量)
live_leaves = sum(所有未终结、含cancel_pending子单的剩余量)
uncommitted = max(0, Q - F - live_leaves)
target_complete = F == Q AND 所有子单终结且成交/terminal ACK已对账
```

F不因卖出/止损/撤单而减少。首个正fill令所属up.used=True，但不禁止同parent的remaining继续完成。used是本up所有probe/ADD正fill的单调OR，不是最后一张订单的状态。MATURE_ADD真实正fill也耗本up未用试探，防随后跌回又领一次probe。

资金预检拒绝、从未提交订单时不消费。已提交后未完成就占槽；未知、partial、cancel_pending都不能并行新授权。零fill且全部terminal ACK及cumQty与真实fill ledger核同后，可按同parent重申；partial后也只能同parent补Q-F。收到‘撤单成功’字样不等于可立即复用：若terminal cumQty与本地fill不符，先补齐对账。旧单latefill归旧up/target，不能借当前up洗信用。

## 3 可运行控制流程伪代码

以下接口由执行器提供真实事件；不是用原账成交替新路径模拟。

```python
def on_fill(fill):
    target = targets[fill.parent_id]
    if fill.execution_id in target.executions:
        return                         # 幂等，重复回报不重复加F
    target.executions.add(fill.execution_id)
    target.F += fill.qty
    persist_real_fill_before_checks(target, fill)
    up_slots[target.up_key].used |= fill.qty > 0
    reconcile_children(target)         # terminal cumQty/本地fill不符则保持锁
    if target.F + unresolved_leaves(target) > target.Q:
        return mark_OVERFILL_UNKNOWN_and_lock_new_risk(target)  # 不裁F、不丢真成交
    latch_completion_if_reconciled(target)

def on_terminal_ack(status):
    target = targets[status.parent_id]
    persist_status_then_reconcile(target, status)
    latch_completion_if_reconciled(target)  # 最后ACK后到也可完成，不等另一笔fill

def latch_completion_if_reconciled(target):
    if complete_and_reconciled(target) and target.complete_known_at is None:
        target.complete_known_at = now_received()  # 首次锁存；重复回报不改钟

def continue_same_target(target, facts, context):
    if unresolved_orders_or_ack(target) or context.pending_exit:
        return WAIT
    if not original_parent_still_valid(target, facts):
        return CANCEL_OR_RETIRE_REMAINDER  # F、旧fill责任不清零
    qty = target.Q - target.F
    if qty <= 0:
        return COMPLETE
    # 当前真实报价、保护、原资金/行业/风险规则须重验，只能缩不能扩Q
    return submit_new_child(target.id, qty_limit=qty)

def on_close(facts, context):
    exits = original_exits_using_previous_known_lines(facts, context)
    update_V3_I_and_CP_market_once(facts)
    update_old_layer_lines_by_original_max_rule_if_not_exiting(facts)
    if exits:
        retire_only_targeted_layer_carriers(exits)
        if exits.include_current_structure_failure:
            retire_current_structure_id_permanently()
        return REQUEST_EXITS_AND_CANCEL_BUYS
    if (context.unknown or context.pending_buy or context.pending_exit
        or context.cancel_ack_pending or context.replace_unreconciled):
        return WAIT
    if has_unfinished_parent(facts.sid):
        return continue_same_target(active_parent(facts.sid), facts, context)

    slot = up_slots[facts.up_key]
    if original_CORE_eligible(facts, context) and not slot.used:
        # 保留无CP CORE；同close CP只绑定此target，不另开一单
        return propose_one_probe_target(kind="CORE", refs=coincident_refs(facts))
    if not fresh_CP_receipt(facts):
        return NONE
    if facts.I_mature and qualified_execution_chain(context, facts):
        return propose_one_ADD_target(cp_id=facts.cp_id)
    if not slot.used:
        return propose_one_probe_target(kind="CP_PROBE", refs=[facts.cp_id])
    return NO_SECOND_PROBE

def approve_target(proposal, real_approval):
    # 预检无副作用；真实批准后原子登记一个parent，所有子单同id系谱
    # 若预检拒绝，不写成used；不从后来的filled量倒推approved_target_Q
    return register_immutable_parent(proposal, Q=real_approval.target_Q)
```

当前有partial parent，即使mature和新CP均真，也先续该目标，不能开ADD绕过。新CP可以记为市场事实/保护更新，不能缓存成目标完成后自动升级的一张旧ADD凭证。ADD parent保持ADD用途；mature退化后取消其未成交余量，不能改名probe续买。零fill后可重申合法parent或正常申请，但永远查整个up的历史正fill记忆，不能退款另一单的消耗。

original_parent_still_valid只验当前structure/source/UP、保护、用途权限及真实报价/原风险，不重套旧CP必须当日fresh或CORE首次fill后not-held/core_epoch门。子单DAY到期不是parent市场授权到期：全ACK后同parent可续。source/结构/UP真正撤销才退役旧parent；仅ADD价格许可暂退时取消/暂停余量，不能改名probe或重设Q。新UP可有新slot，但旧未结责任不解除。

同一次up/CP只一个close意图束、一个outbox intent_id。重试同订单不发新资金目标。原Budget.request的duplicate/consume和原core_epoch接口并非天然支持此parent续单协议，不能把旧request原样多调几次当实现完成。

## 4 旧CORE微仓与成熟资格

本节按[V5结构继承补充](V5_INHERITANCE_CONTRACT.md)更新：同结构当前健康且有认证谱系的ADD可承接；局部退出只移除该层，全股未结退出期间仍锁新增，结构P失效才永久封旧id。

market_mature来自当前价格结构，不来自持有股数或订单complete。执行complete也不产生额外风险额度。

qualified_execution_chain要求：当前有效structure_id中存在健康且有认证谱系的实际层。谱系起点须有事前probe批准目标及真实complete/对账证明；合法授予并真实成交的ADD可携带此历史证明，原probe本人无需仍有存量。无未终结probe/退出责任；当前CP必须晚于所用证明和必要退出解锁首次被知晓的时刻。连续赢家不强制每个新up再试；当前up任意ADD正fill仍耗其试探机会。

旧CORE100股不能仅凭has_position=True追认为合格链。若有明确事前parent批准Q=100且真实填100，可以证明执行complete；若目标为3200且仅100，则仍partial。无论哪种都必须另满足当前I_mature及完成后新CP，不能凭‘完成了最小一手’推定经济成熟。

某层保护失败只撤该层carrier资格，不能无条件撤掉同结构其它健康认证ADD。全结构P失效则旧id永不继承；新I_hold不能复活旧id。mature单独退权不清仓，保留历史证明但当前不ADD。卖出不返F/信用；原probe全卖后有健康认证ADD可承接，只有无谱系旧CORE则不能冒充。所有carrier空时不能凭历史空证书ADD；后续按新UP/probe规则重试，旧pending责任仍先处理。

## 5 原始事实与条件演绎

### 盈新

原CORE68：1/10信号，cap=3200；1/11原实际reserve/fill100@3.011505。同1/10也有市场CP，但CORE intent的CP ID为空。V5保CORE入口并合并同close证据，不另加一单。不能事后把100 held当作新合同的Q完整证明。

1/20新up且CP出现、I_mature=False。原1/20→1/21资金拒绝，无fill。V5不耗试探；若根本未提交子单可在合法信号/原CORE入口重申；若已提交则必须全cancel ACK对账后只续原目标。1/21仍未mature，重申用途只能probe/同parent续单，不能按原大MOBILE量视作成熟加层。

1/24收盘3.98>恢复峰3.78且新CP出现。如果此前新合同目标已实际完成并及时对账、仍有其存量且无保护退出，则可提一次ADD；若partial则只补余量，零成交未形成持仓则仍是probe。原122后于1/25真实买4700@4.002是旧路径事实，不能当V5的新数量/成交。真突破仍可能失败，V5不证明已分辨真假趋势。

### 海能达

9/20有CP*而原账无该股intent/fill；不能因为‘市场发行过’耗V5试探，也不能凭此宣称新试探已建仓。

10/14原CORE信号没有CP，V5保留：原10/15 reserve/fill100@8.90445。若新合同在成交前明确批准目标并按真实回报完成，则10/18及10/21的新CP、当前mature与无锁条件可支持ADD；若旧100没有可审的目标履历，不能仅因held而ADD，须明确迁入证据或新probe。原2017/2039后实际分别1100@12.006和1000@14.007只作旧路径注释。

11/4成熟撤权不强卖旧CORE；若原CP保护已提出退出则执行链资格也撤销，不能拿剩下的100股CORE继续认证成熟。11/20新up有CP但未收复28.20，最多probe。原11/20→11/21资金拒绝、无fill，不耗V5信用；后续合法重申仍受订单真实ACK与固定目标约束，不必因此永久等下一个up。

## 6 当前证据边界

原账有reserve/fill/release_buy，但没有真实券商exchange cancel ACK/latency；release_buy不等于真实撤单确认。不能从旧期末orders空倒推历史ACK，也不能借原成交替新路径消费。这里交付的是可执行接口合同与真实原事件的条件推演，未运行账户或声称V5的新成交/收益已成立。

风险额度仍须原有规则对旧仓＋新单重新核算。即使Q=100事前获批且已执行、market_mature与新CP均真，原资金层仍可能给出较大下一层；本合同没有新增资金规则，不能保证这种规模跳跃已消失。它修复重复授权、退款与微仓伪认证，不保证正期望。
