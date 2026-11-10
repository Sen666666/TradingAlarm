# 对当前纸面稿与输入边界的追加意见

只读到 `independent_design/DESIGN.md` 和 `path_inputs`；无候选状态机运行。

1. **OR 与 AND 是两条经济规则。** 当前 independent_design 保留 HL OR reclaim；source_logic 的口头替代曾是 HL AND reclaim。后者不是修复前视的必然结果：能排除部分 lower-high 反弹，也会延后深 V/单边推进。必须先冻结主定义，不能看七股后换。
2. **严格 cross 的确认延迟陷阱。** 若原 +event 在价格已经站上旧 H 后才确认 START，而此时没有可比较前低，则 `Cprev>H && C>H` 不满足 START 内新 cross。之后单调推进也无法 CONFIRM，除非先跌回再涨或再等一个 HL。“本 START 首次消费当前已收复的证据”与“本 START 内发生新 cross”均可因果，但不是同一规则。必须明确这份延迟代价，而不能称为仍未收复 H。
3. **左边界不是冷启动。** 七个 inputs 文件是指定日期 slice，共 2103 行，输入说明本身没有承诺从真实 source 起点重建候选。若要继承此前已确认的 H/L/证书，需处理原完整历史前缀；否则 slice 初段只能标 LEFT_CENSORED/UNKNOWN。原 native I/E0 可作对照，不能直接作为新证书的初始化状态。
4. **旧破坏与新启动同日可分事件，不能抹责任。** independent_design 明确允许旧支持破坏后同日新 +event 新 START，这比原 policy 的同日 entered 禁止更宽，是候选语义变化。若仅生成信号，可分别记录旧 INVALIDATE 与新 START；若未来接到账户，旧退出未完成不能被新 START 撤销、当卖清或当现金。
5. **没有后验保证。** HL_ONLY 仍可能处于 lower-high 反弹；收复失败在事后才知道。跌回 H 立即降级与只等支持 L 破坏也是两种不同尺度，当前纸面稿仍列为待裁决分叉，不能给“唯一候选已通过”的结论。

当前可确认的是原源码时钟和这些设计反例。尚无唯一冻结候选，也无已生成的六/七股新信号表，所以本轮不对候选给 PASS，不给收益判断。
