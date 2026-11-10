# V4：一次试探与 CP 保护的最小接口预审

仅源码/纸面设计，无候选运行、账户或资金参数。等待主冻结选择消费时点和 CP 输入版本，当前不对完整 V4 给 PASS。

## 三本账必须分开

1. **CP 市场收据。** 原 `model.py:27–47` 在发布 receipt 时即重置下一段 anchor/credit，`receipt_consumed` 是市场算法内部语义，不是有人买过。订单拒绝不能反向改市场 anchor。
2. **账户 CP 防重放。** 原 budget request 先记录 request ID；验证 CP 后已将其放入 consumed，随后仍可能在迁池/财务门失败。不是所有 rejected request 都留下可重用的 CP（model_without_account_check.py:218–256）。取消 ACK 不删除 consumed。
3. **每 up 一次试探信用。** 建议 key=`(sid, source_segment, original_up_event_id)`；不能以 holding generation、CP 换号、退出请求或新高刷新重发同一份信用。

## 消费时点的最小合同建议

纯信号层只能发行 probe/mature candidate，尚不知道是否真正获资；不能用原账成功成交反馈替候选消费。若主规则选择“每 up 一次真实获资试探”，建议：

`AVAILABLE -> RESERVED(唯一成功 reservation) -> USED(任意正 fill)`。

拒单不消费新 up 信用，但原 request/CP 是否已 burn 必须按原账记录，不能据此重放旧 CP。cancel_pending 不释放信用/本金；partial fill 已用掉整次信用，余单取消不退一次信用。零 fill 且真实 terminal ACK 后是否允许同 cycle 退回 AVAILABLE，需要冻结；即使退回，也只可等新的合法 CP，不能复用原 receipt/request，也不能把退款发到新的 up key。更简单的另一个明确选择是成功 reservation 即永久 burn：它是一获资尝试，不保证一次成交。这两种不能混称同一规则。

若只想做确定的纯信号演绎，可以另选择“首次合格 CP permission 发出即消费”。必须明确其是一次机会，不是一次获资/成交；被财务拒绝后也不会自动补发。不能悄悄借这个假设计算减少了多少交易。

同一 CP 同一 CLOSE 只输出一个 purpose，成熟优先；成熟订单一旦按所选消费时点成功，也应结清该 up 尚未使用的 probe entitlement。否则成熟先加、跌回 START 后仍能额外领 probe，是未定义的重复新增。每个后续成熟 CP 仍可按原新增路径申请，不因此多发 probe。purpose 不得改变 native role：CP 试探仍为 `mobile/add` 层，不能伪装成旧 CORE（旧 CORE 跳过 CP 线检查）。资金 pool 的 probe/confirmed 与试探 purpose 是不同维度，原路由/迁池不在本轮重定义。

## CP 输入与持有保护必须分离

原 CP frame 的 `e0_valid=旧 i_target`（generate.py:26、common.py:23）；`I_expand` 撤销不能直接改成 `e0_valid=False`。那会清 CP 的市场 phase/anchor/credit；若沿 project，还会把 invalid 当退出。实际 J 层内 floor 是另一份存储，kernel reset 本身并不把已持层 floor 清零（J225–238）。

最小三层接口：

- `CP_market`：吃结构存在/可比源上下文，而不是成熟新增权限；原 down 仍按原 kernel 进入 SEEK。若改吃新 I_hold/新 P，须另算同公式 CP*、保新输入身份，不能称旧收据等价。新 I_hold 是市场结构状态，不是实际实仓。
- `LayerProtection`：旧 floor/已锁 exit 属实际层；先用已生效旧线检查当前 C，再 max 新保护。入口撤权、kernel reset、新 START 都不清旧 floor/退出责任。
- `EntryPermission`：仅对新的、当时已发布 CP 分类 probe/mature；不反向影响 CP_market 或已持层退出。

若本轮继续使用原存盘 CP，只能说是旧 I/CP 上新增 permission 层；旧 CP 仍依赖旧 G1/I，不能宣称新 START 随时已有可用新 CP。反之若更换 CP 的结构上下文，则属于待重算的新联合信号，尚未在本轮实现。

## 不得跳过的冲突

- 新 generation 信号不表示旧 P 出口已成交；实际 pending_exit/buy/cancel_pending 未解除，仍阻止新增，不能由 I_hold=True 推断实仓存在、空仓或现金可用。
- 同日新 +/CP 可以产生收盘后候选，但同 receipt 不同时做 probe 与 mature，不在同 CLOSE自称已经成交完成试探。
- down 发生时，未提交候选失效；已有 pending 订单需真实撤单/ACK，竞态 fill 必须落账，不能假设撤权就瞬时抹单或返还本金。
- 路由预检与 request 必须核同一信用版本；并发或重放需要唯一 grant/order/receipt/up key。当前原 route 在 request 后 assert reserved，不能只把信用拒绝加在 request 末尾而漏掉 route.allowed 预检。

当前仅给出最小接口合同和必须冻结的选择；未声称原代码已具备上述原子信用事务。
