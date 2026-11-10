# 实际 fill 消费试探：最小合同与竞态质询

本件替代旧 V4 permission 发行消费的讨论；旧 V4 已撤销，不再据其授权输出推论。本轮只写逻辑，不运行账户或模拟价格/订单路径。

## 1. 一份目标、一本真实成交累计账

同 E0 up 的 CORE/CP 共享 `slot_id=(sid,source_segment,up_event_id)`。首次申报前一次性冻结 targetQ、单位版本及 parent_grant_id；同 CLOSE I/CP 两入口只选一份 parent，不各建 target。原 CORE 无 CP 入口保留。若两入口数量/退出来源不同，优先规则及首次 target 来源须明示，不能在失败后换来源重新领取 target。

`F = sum(本 parent 所有去重真实 buy executions 的成交股数)`；
`live_leaves = sum(未终结、cancel_pending、replace未对账子单的可能剩余股数)`；
`可再申最大余量 = max(targetQ - F - live_leaves, 0)`。

F 只因真实 fill 增加，不因卖出、亏损、撤单、CP 换号或 source generation 改变而减少。任意正 fill 即 `credit_used=True`，但不禁止同一固定 target 的剩余部分成交。不能用当前净持仓替代 F，否则卖出后可重复补满同一份 target。

## 2. 生命周期与 credit_used 是两个维度

建议语义：AVAILABLE=无正 fill 且全部子单终结后可申；ORDER_PENDING=零 fill 的活动单；PARTIAL=0<F<targetQ，可能有活动单也可能正待续单；CANCEL_PENDING=终结/撤改还未对账，F 仍保留；COMPLETE=累计真实 fill 达 target 且无未终结试探责任；SPENT=该 slot 已退役，不可新开 probe。`credit_used` 另由 F>0 锁存，不能把首个 fill 直接设为禁止余量完成的 SPENT。

PARTIAL 与 CANCEL_PENDING 可以同时存在于事实中。对外选一个主状态时，必须同时保留 F、leaves、cancel/replace 标志，不能以状态覆盖丢掉成交累计。

零 fill＋全部 terminal ACK＋累计成交对账后可重申同 target；不是新 probe。partial 后同理仅重申余量，不重建 target。若余量低于本证券合法买入单位，则保持 PARTIAL/不可下单，不能向上凑股或装成 COMPLETE；如果要退役残余，应显式标 `SPENT_INCOMPLETE`，不据此授成熟 ADD。

## 3. 迟到成交与撤改

- fill 按真实 execution_id 去重，回调晚到仍记入原 parent/slot。不能因已收到 cancel ACK 或已切新 up 而丢弃、移给新 slot。
- ACK 必须带可对账的终局 cumulative filled/leaves 状态；只有“撤单成功”字样不足以证明零 fill。terminal 回报与本地 fill ledger 不一致时保持 UNKNOWN/订单锁，不抢先重申。
- 不假设 broker 原子 replace。最小方式是 cancel → 全部旧子单终结并对账 → 仅申剩余。撤单等待中原 leaves 仍占额度；真实 fill 赢过 cancel 竞态，先记 fill 后算余量。
- 新 up 不删除旧订单/退出责任。旧 slot 可以退役，但迟到回调仍归旧 slot；同股有未终结 buy/exit/cancel/replace 时，不开启另一个 probe 或 ADD。
- 若真实成交和超过 target（异常/重复风险），不得截断 F 隐藏实仓；记录超额事实并阻止进一步新增，等对账。合同不能在缺失终局信息时保证永不超额。

## 4. 成熟 ADD 的必要合取，不加价格或 1R 阈值

`当前 market_mature=True` **且** `本 up slot 的真实 target_complete=True` **且** `无 probe/撤改/退出未终结责任` **且** `新的当时 CP 在 complete 已知之后发布并且未消费`。

旧 CORE 微仓、has_any_position 或旧 slot 完成不能被追认为本 slot 完成。若本 slot 的试探已全部卖光、只剩旧仓，也不能以旧仓冒充该 slot 的新试探支撑。PARTIAL 时市场成熟不自动另开 ADD，应先完成同 target。完成回调本身不能触发缓存的旧 CP；等后续合法决策点的新 CP，无需另加固定等待。

target 完成只说明执行完成。若 target 本来就是原 CORE 最小微仓，完成它并不证明经济规模充分；上述 market/新 CP 条件也不是独立收益保证，不能用 COMPLETE 这个名字掩盖这一点。

## 5. 可实现伪代码（外部 API 尚未接线）

```python
on_fill(exec):
    with atomic_lock(exec.sid):
        if exec.id in seen_exec: return
        slot = parent_of(exec.order_id).slot       # 不按“当前up”猜归属
        persist_fill_and_reconcile(slot, exec)     # F保真，去重，更新leaves
        slot.credit_used |= slot.F > 0
        derive_state_without_resetting_target(slot)

on_terminal_ack(report):
    with atomic_lock(report.sid):
        reconcile_cumulative_fills_and_terminal_leaves(report)
        if inconsistent_or_missing: keep_order_lock(); return
        derive_state_without_resetting_target(parent_of(report).slot)

on_decision(now, original_I, fresh_CP, market, actual_context):
    if actual_context.unknown_or_any_unreconciled_order_or_exit: return BLOCK
    slot = current_up_slot(now)
    if slot.targetQ is None:
        source = choose_one_original_CORE_or_CP(original_I, fresh_CP)
        if source is None: return NO_NEW_TARGET
        freeze_target_and_parent_once(slot, source) # 既定quantity层给Q，不新增参数
    if not slot.complete:
        remaining = slot.targetQ - slot.F - slot.live_leaves
        if slot.retired or not current_protection_and_signal_valid: return BLOCK
        return continue_same_parent_with_new_child_id(legal_floor(remaining))
    if not market.mature or not actual_context.position_linked_to_current_slot:
        return NO_MATURE_ADD
    if not fresh_CP or fresh_CP.known_at <= slot.complete_known_at: return WAIT_NEW_CP
    return one_mature_intent_consuming_this_CP()     # 不额外创建probe target
```

`continue_same_parent` 不是原 Budget.request 的无条件重放：原接口记录 duplicate_request、CP consumed 和当日 token 新鲜性，不能把续单伪装成新的 CP。未来需要明确的同 grant 余量执行入口，重验当时保护、单位和资金门；原 CP 只作初始授权 provenance，不重新发经济信用。检查点需保存 slot/target/F/seen_exec/所有子单/outbox，重启先对账，不默认 AVAILABLE。

伪代码中的 `current_protection_and_signal_valid` 指当前 up/结构授权未被撤销、价格与保护可比等持续合法性，不是要求续单再等一份新 CP/I。若 F 达 target 但仍有可能成交的 leaves/未对账报告，先取消和核对剩余责任，不能提前 COMPLETE/ADD。

未解决的经济问题不靠新参数填：target 数量来源、普通部分退出是否退役当前 slot、已完成 probe 的持仓 lineage 如何继续，需主合同明确。本件不运行或假装现代码已实现这些接口。
