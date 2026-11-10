# 连续持有链延续成熟资格：补充审查

主线程进一步明确：不强迫每个新 up 都重新试探。ADD 可以引用本连续 holding-chain 内、事前登记 approved_target、真实完成、仍有可关联存量的 probe target，来自当前或此前 up 均可；当前 market_mature、新鲜且确认晚于目标 complete 已知时点的 CP、无未终结责任仍必需。本补件取代前稿“只可引用当前 up 完成”的更窄建议。

**该延续规则没有必然的致命竞态，但以下身份和原子记账条件不可省。**

1. 合格履历必须来自登记的目标及真实 fills，不能把旧 CORE 100 股、planner cap 或当前持仓量倒推成 approved_target/complete。需 explicit adoption 或新 probe；这是来源确认，不加价格/1R阈值。
2. “仍有存量”应可关联到该 probe target/明确的合格 lineage，不能只靠同股另一份 legacy 微仓撑着 holding-chain。实际完全 flat 后旧链封存；未终结旧单/latefill责任保留，但不自动把已封存证明复活成新链成熟资格。
3. 当前若已开始 PARTIAL probe，其剩余 target 仍可重申时，不并行另开 ADD。按 partial 优先，先完成或显式退役剩余授权；退役不清 F、不冒充 complete。没有当前 probe 的健康历史合格链，则无需为每个 up 另造 probe。
4. MATURE_ADD 保留自身 purpose。成熟撤销后不把其未成交余量改名成 probe，以绕过成熟门。零 fill 并全部终局对账，只说明该 parent 未贡献信用消费；后续能否续/新申仍重验当前角色授权。
5. `up_credit_used[u] = OR(该 u 绑定的任一 probe/MATURE_ADD grant 是否有真实正 fill)`，是单调记忆。后来某单零 fill cancel ACK，不能恢复此前另一单已经用掉的信用。成交后卖出也不退款。
6. 用 grant 内冻结的 up_key 归属成交，不用回调到达时“当前 up”猜。旧成熟单跨 down/new-up 后迟到成交仍归旧 key；同股未终结责任清前新 key 不能抢单。若主合同另要把 latefill 也占新周期信用，必须显式写转移规则，不能默改身份。
7. complete_known_at 来自所有相关子单终局和累计真实 fills 对账；已全额 filled 的终局状态不必虚构 cancel ACK。只有晚于该已知时钟的新 CP 才能申请 ADD；同 CLOSE I+CP 的旧 CP 不在下一次 fill 回调中自动升级。

执行完成与趋势成熟继续分开：就算 approved_target 明确且只有100股，它也只证明这份执行目标完成；当前市场成熟和新CP是另外条件，不据“complete”标签宣称经济规模充分或收益已验证。

本轮仅纸面/原源码逻辑审查，未运行订单、账户、价格路径或参数测试。
