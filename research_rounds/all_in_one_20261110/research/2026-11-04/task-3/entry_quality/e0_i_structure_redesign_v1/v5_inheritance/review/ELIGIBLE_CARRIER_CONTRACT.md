# 按结构身份与健康层继承：独立最小合同

本件替代此前“必须 probe 本人仍有存量/连续 holding-chain”的更窄建议。只做逻辑与既有源码时序审查，不运行账户、订单或价格路径。

## 1. 身份只有一套权威生成器

`structure_id = (V3_policy_version, sid, comparable_source_segment, I_hold_generation)`。

原 down 只更新 recovery_cycle/R、降 mature，不自动换结构身份。V3 旧 P 失效、该结构 I_hold 真正失效或 source 不可比时，封存旧 id；后来的新 generation 不继承它。这里 I invalid 必须属于生成该 id 的结构 I，不能把旧 G1-I 的层退出混成全局失效、却又保留仍 active 的 V3 generation，否则可能永久杀死同一个 id 而无新 id 可恢复。

结构身份不等于 up、行业 episode、资金 pool 或当前持仓数量。实际暂时 flat 本身不自动换 V3 root，但没有当前健康 carrier 时不能 ADD。旧 id 的 latefill 仍归旧 id，不能因收到回报时市场已新开结构而重贴新标签；旧仓及 pending 仍占真实风险，不因失去继承资格而消失。

## 2. Carrier 是当前健康的实际层

设当前决策为 t，s 为当前有效结构身份。对层 l：

```
healthy(l,t) = actual_remaining_qty(l,t) > 0
             AND l.structure_id == s
             AND current_C、l.previous_effective_floor 可比且已知
             AND C_t > l.previous_effective_floor
             AND l 未因自己的保护/硬退出触发而 retired
             AND l 不属于已提出/未完成的 exit targets

Carrier_s(t) = {l : healthy(l,t) AND Certified(l)}
```

触线层即使尚未卖出，也从资格集合排除；反弹或撤单不能默默复活已失效层的资格。其它同 id 健康层不因此整链作废。源/旧 floor 未知则资格未知，不把未知当健康，也不凭未知虚构价格退出。

## 3. Certified 需要时间有向的真实 provenance

- **probe seed**：事前登记 approved_target，真实累计 fill 达目标、子单终局/累计成交对账完成。cap、当前 held=100、kind=CORE 均不能替代。legacy 需要明确 adoption 或新目标记录。
- **ADD carrier**：有实际正 ADD fill，且其原 grant 保存了当时已合格的 carrier/certificate 见证、同一 structure_id、当时 current_mature/新鲜CP及无未结责任的检查来源。仅旧 kind='add'/role=mobile 不够——原规则也把 flat 首次 MOBILE 叫 add。
- 认证关系是向过去的 DAG：每份新 grant 只能引用其被知晓之前已成立的证书，不能拿自己未来 fill 或另一个尚未成立的 ADD 互相认证。
- 历史授予合法后，原见证 carrier 后来退出，不回溯抹掉已合法形成的 ADD provenance。当前 ADD 层若自己健康，可以接棒；无需原 probe 本人仍活。
- 若允许原真实 ADD 作迁入 seed，应签发显式 legacy-adoption 证书：原加层前已有实仓、原真实 CP/批准/fill 来源、结构映射及迁入时当前健康性，不能仅看 kind。该证书 known_at 是实际采纳时钟，不回填为过去早已运行新规则；不按盈亏择取迁入。此分支是否采用由主合同明示。
- partial/未结 parent、buy/replace/cancel/exit 仍按执行合同锁住新增；不能借某个健康 carrier 绕开另一份未结目标。真实 partial ADD 不得伪装 complete；剩余是否已明确退役按主合同记录。

## 4. ADD 的完整入口公式

```
ADD_eligible(t) = current_structure_alive(s,t)
              AND I_hold(t) is True
              AND I_mature(t) is True
              AND Carrier_s(t) 非空
              AND fresh_CP(t) 未被消费
              AND CP.known_at > max(所用carrier证书known_at,
                                   required_exit_unlock_known_at)
              AND 全sid无pending_buy/exit/cancel/replace/partial未结责任
              AND source/保护/执行context全部已知
```

不能只用 I_hold 推断实际有仓；不能仅用 has_position 推断 carrier。任一未知不能授权；本式没有新增价格、1R、股数或资金阈值。现有资金/数量/行业门以后仍需另行检查，不因存在 carrier 而自动可加仓。

`required_exit_unlock_known_at` 是该 sid 目标退出完成并终局/累计成交对账后，使相关退出锁首次清除的事件钟，不是每次状态查询的当前时间。没有先前退出锁时不凭空制造这项门。CP 若在锁中已发布，不能在解锁后补用；需要解锁后新的、当前可用 CP。carrier 证书的 known_at 也必须覆盖其真实 fill 与必要终局对账已可知的时钟。

## 5. 不同 floor 的固定顺序

1. 先检查当前结构 t−1 的旧 P/global I invalid；若全局失效，整个旧 id 禁止继承，旧责任保留。
2. 各实际层分别用自己 t−1 已生效的保护线检查 C。CORE/MOBILE 适用的保护源按原类型/已选版本，不能偷把 CORE 全改 CP。
3. 命中的层立即 retire 资格并提出其 exit。不得用本日 CP 候选/新线回写遮掉触发。该层失败不自动撤其它健康层证书。
4. 未触发的层才按自身规则 max 抬线，不回撤；不能用全股 min floor 假装所有层安全，也不能用全股 max floor 一层触发杀全链。
5. 任一退出尚未完成时，全 sid 不 ADD；这只是订单责任锁，不等于其它层永久失去资格。真实目标退出完结/ACK与对账清锁后，用下一份新鲜 CP、当前 mature 和重新检查后的健康层再判断，不重放被锁时的旧 CP。

## 6. 最小反例与应有结论

- `probe旧线 > C > healthy_ADD旧线 > 结构P`：probe retire、ADD可保认证。此刻 pending exit 挡全部 ADD；退出完成后若同结构仍 alive/mature、ADD仍健康、新CP合法，ADD可承接。禁止整链 invalidate。
- down 但未破结构 P：structure_id 不变，证书不清；成熟许可先退。后来恢复不必强制另开 probe；仍需健康 carrier、新CP、无锁。
- 结构 P 真破，即使某层更宽旧线暂未破：旧 structure_id 全部不可继承。不得用这层残仓或旧 id latefill 认证新结构。
- 只剩未登记 target 的 legacy 微 CORE：无 Certified carrier；不能仅因还有100股成熟。
- 两个旧 MOBILE/add 互相声称对方成熟：没有可追溯 seed/当时 grant 见证，均不能自证。历史案例只能证明不同 floor/健康层原事实，不能凭名称自动 adoption。
- 其它层健康但有 partial/cancel/exit未结：资格证书可保留，入口仍锁；不能以“健康层继承”绕开真实订单责任。

当前方案在逻辑上可闭合；实际历史层的 adoption、未来 grant 见证字段和执行接线尚需明示。本件不把旧原账全部 add 层自动认证为新规则成熟层，也不宣称收益有效。

主线程/原事实 owners 的最新证据仅支持“不同 floor 下早层退出、晚层可继续存续”的原事实；目前没有证明继承后又出现新 CP 并能扩仓的赢家案例。本逻辑审查没有重算这些原账样本或认证其经济效果，不能把理论 carrier 可继承等同实证收益支持。
