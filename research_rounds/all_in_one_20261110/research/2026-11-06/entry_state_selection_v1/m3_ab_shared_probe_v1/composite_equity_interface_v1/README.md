# 窄复合权益机械接口：合成阶段
这是独立工程准备包，不是新策略、真实事件准入、独立审查 PASS 或经济运行许可。真实 commit 硬拒绝，外部税方案未裁定。

已实现：
- 官方时钟接口、同 ex 上市/入账、逐登记 CORE/ADD 层整数门；晚上市、送红股和零碎 fail-closed。
- 原轮和层归属、真实 qty 增加、原历史成本/买入身份/CP/ADD 状态不改；原保护线做已证复合坐标变换。
- 独立股份账，以真实 action_index 重放增股，不改原 BUY，不造 fill。
- 原现金函数字段兼容的 claim/event 投影，不自动注册事件或现金入账。
- 原 QuantityRule 奇零整仓/部分退出校验。
- 报告成本按权益调整后 current_qty 分摊，历史 buy_qty/buy_cash 不动；原 native mark 用实际累计现金和 current_qty，不错误按旧单位成本乘新股数。
- 原现金 register/accrue/pay 与 mark/held_open 定义的纯合成调用。

25 项测试通过。qa01/RESULT.json 明确测试范围：现存 254 actions / 113 bought rounds 仅作无增股账的数量重放完全一致，不是完整账户相位/选择队列重跑。原费用在新股 full-exit 夹具使用显式测试 callback，不能据此认证真实405股费用；原年度实际费用已另有原run独审，不混在本包。

税输入 TaxBinding 是机械输入，不是法律税事实或许可签名。EXPLICIT_ZERO 只表示调用者明确输入零，不能称免税。64位hex格式也不是独审授权。任何 HISTORICAL_CONDITIONAL 的 commit 均硬拒绝；21元只在显式合成输入每新股0.2元的夹具中验证量账本，未对真实账计税、扣现或回灌风险。

仍待新版本合同与实现：
- 外部真实事件 facts/hash/clock/registry 许可及独立审查，不可用任意 TaxBinding 字符串替代。
- 裁定股票税研究折减/准备金及对现金、risk NAV、轮净利和结算关闭的影响。
- 接原共享账户的原子交易/现金/股份流程、真实 report_layers 数量消费者与 exact费用分配。
- 新版本完整无事件相位/动作回归、已存原前缀对比、源冻结、独审和独立新锁。
本包不会接通真实经济，旧437、年度结果和锁均未动。
