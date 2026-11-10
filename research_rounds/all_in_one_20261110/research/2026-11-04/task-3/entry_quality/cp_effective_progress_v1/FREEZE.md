# 一个固定CP候选：扣除回落损耗的前沿余额

本轮独立于用户的UP/成交信用设计，只研究原CP丢掉的负向价格路径。没有账户、新数量、新资金/收益，无参数搜索。本候选不是外生数据或统计独立alpha；新信息是原CP当前压缩状态不能保留的负收益总变差、先后顺序和跨reset近期记忆。

## 原控制与范围

使用当前No60原native I_target驱动的原CP缓存与同源CP-input。不是V4的CP*，不混用两种输入版本。原CP形成、receipt、candidate/保护线保持原样；CORE和每UP一次小试探的原信号不受本余额过滤。新余额只产生供连续MATURE_ADD使用的effective_advance_receipt，不证明当时已满足V5执行/mature/资金门。

计算母体：盈新000620.SZ原完整前缀后展示2022-01；海002583.SZ展示2024-01及2024-09—11；银之杰300085.SZ展示2024-09—11；半导体固定2026H1原25层/18股的全部原CP事件，不按盈亏筛。半导体carry扩展若有，仅另附期初实际持仓母体，不替换固定25，也不称全126股行业覆盖。窗口在候选运行前固定；本轮不以这些片段宣称全年或样本外有效。

## 数学与顺序

CP输入的原有效观察钟。对每个source可比段：

```
lambda = 20/21                       # 唯一固定记忆假设，不扫10/20/40
loss_t = max(-original_CP.r_t, 0)
innovation_t = original_CP.delta_frontier_t * original_CP.m_t
pre_balance_t = lambda * balance_(t-1) + innovation_t - loss_t
h_t = sqrt(5) * original_CP.scale_t   # 用当次原used scale，非next_scale/当日s
```

source首次/换段及原CP尚未ready时balance=0，不跨不可比段继承；ready后任何必需原字段缺失必须UNKNOWN并停止该段候选，不填未来值。ready、r、m、delta_frontier来自原已存CP，原重置日delta=0。

原reset_reason为`start/E0_down_reset/lower_anchor/E0_invalid`时先完成上述当日loss更新，再`pre_balance=min(pre_balance,0)`：未确认的正余额失效，但负债不被换锚洗掉。I无效期间没有frontier创新credit，仍记录已知负r、负债按lambda衰减。只有source不可比/未准备才归零。原CP即使本候选不通过，仍照原逻辑receipt_consumed重锚，不回滚原市场CP状态。

```
effective_advance_t = original_CP.receipt_t
                      AND ge_original(pre_balance_t, h_t)
balance_t = 0 if effective_advance_t else pre_balance_t
```

一根bar至多一个有效推进。余额清零是市场数学收据消费，**不是**试探成交信用或资金授权消费；不取决于原账是否买入/盈利。执行重申仍按V5真实fill/ACK规则，不用该余额模拟成交。

21观察记忆沿用原CP已使用的21观察单位作为待证伪先验，非经济定律或最优估计。lambda均值记忆21、半衰期约14.2观察；时间流逝本身会减轻债务，不是‘只有创新高才偿债’，也不是固定冷却。负r权重固定1，新增frontier沿原m量额乘数；低量下跌也全部记损耗，这一不对称是明确假设。

## 为什么不等于原CP或净收益阈值

原CP只累计fresh frontier*m，跌幅不直接扣credit；下行/invalid/降锚又清市场credit。两个同收盘、同anchor/frontier/冻结scale、同总frontier credit的路径，可以有不同下行总变差，本余额因而不同。它仍是同一价量数据的不同历史记忆，不证明独立预测力。

它也不等于净价格变动：跌后回到旧frontier没有innovation，却已扣loss，等于有意不给普通恢复涨幅偿债。可能过罚健康宽幅整理和深V，这是主要肥尾冲突，不能只挑失败反弹展示。下行重置保负债可以降低连续失败后反弹的信用，但真正新主线也可能背着旧债启动；CORE/小试探保留仅保证数学门没有删除该入口，不保证实际得到资金或后续有效放大。

## 固定输出与可否决条件

每个展示日保原C/r/m/fresh/used_scale/rawreceipt/reset、balance_before/pre/after/loss/innovation/threshold/有效收据与原因；从完整原前缀递推后截窗，不在展示起点清债。原CP全部事件须保留，包括被拒与尾部大行情。被拒原层只标旧路径静态触及，不称少亏/新账户收益。

四组逐项给：首个启动receipt是否延迟、原CP通过/拒绝数、债务被哪些当时可知负bar形成、原大赢家加层信号触及、失败反例。做一次真实截断前缀一致性，不扫参数。若强趋势后续加层被大幅抑制、或失败与赢家无法分开，否决此候选；不微调lambda/权重救样本。
