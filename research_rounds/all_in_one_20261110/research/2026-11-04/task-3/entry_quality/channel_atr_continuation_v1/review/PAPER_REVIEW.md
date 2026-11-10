纸面判定：通道位置与 ATR 推进可以提供不同于原 CP 压缩态的描述，但尚未证明能区分失败与肥尾。20/55 应作为事前并列口径；不按利润挑窗口，不顺带替换原 CP 保护。以下是独立接口建议和必须冻结的边界，尚不是父线程已选定的可执行规范。

“新信息”应精确到来源：若通道取 prior close 的最高值，它仍是原价格历史的不同记忆；若取真实 adjusted H，ATR 又使用真实 H/L，则增加了原 CP close/amount 公式没有直接使用的日内区间信息。缺 H/L 或用 C 伪造 H/L 时不能维持后一说法。不同状态变量不等于独立 alpha。

必须在看标签前决定的输入合同：

1. `U_N(t)` 究竟是此前 N 个完成观察的最高 C，还是最高 H；当日一律排除。20/55 分开保存，不能临时 OR/AND 或逐股择优。
2. ATR14 的 TR、平滑和初值。一个可审查定义是同可比价格域 `TR=max(H−L,abs(H−Cprev),abs(L−Cprev))`；Wilder(α=1/14)和 SMA14 不是同一特征。须指定 current ATR 还是 prior ATR、最少观察数、缺失/停牌与 source 变段规则。本文不擅自替父线程选定。
3. `H,L,C,Cprev` 使用同一因果复权坐标。raw ATR 与 adjusted C 相除、或将 split 前旧 raw high 与 split 后 raw C 比较均不可用。只有 raw 显示缺 factor 时应将执行换算标 UNKNOWN，不能无条件废掉已独立有效的 adjusted 特征；实际完整输入缺失则不发该分支新凭证。
4. 使用原合法 source/market clock，注明 N 是市场 session 还是有效成交观察。已证实停牌可按冻结规则跳过并报告 span；未知缺报价不能偷偷压缩为短窗口、ffill 或凭未来成交量补成已知停牌。

一份最小、无重复信用的 continuation 状态可以这样表述：

```
generation_id; launched; channel_latched[N];
break_known_at[N]; break_reference_high[N];
proof_frontier[N]; proof_ATR_reference[N];
last_issued_receipt[N]; source_id
```

E0 只提供合法 launch：同一仍有效结构内的后续 +event 不重开通道账或清推进历史。E0 负事件是否终止此账必须单独明说，不能把旧 V3 的撤 mature 规则默默继承。原 I/P 失效、source 不可比和新 root 的关系也须冻结；source 重置不等于撤销旧实际层的退出责任。试探可仍由原合法 E0/CORE 入口提供，通道未准备或未突破不应被说成原试探已删除，也不能由“入口保留”保证实际上有仓位。

在 launch 后，当前完成 CLOSE 满足 `C_t>U_N(t)` 才能叫该 N 口径的通道突破；记录当时已知的 U 和时间，锁存 breakthrough。`(C_t−U_N(t))/ATR_ref` 可报告净突破距离，但是否另要求其超过某个正阈值属于额外政策，不能暗中加入。START 当天已在旧通道上方是否可确认必须明说；无需伪造一个此前没有的 hard cross。

突破后不应要求每一根 bar 自己涨超过一 ATR。一个可审的累计版本是：每次发行推进收据时冻结当前 close frontier F 和当时 ATR 单位 a；之后只在新的最高完成 C 达到 `F + k*a` 时发行下一张，并把 F 更新为该实际新高、a 更新为该次冻结的 ATR。k 是待事前指定的政策，本文不选数值。价格从前次 F 起累计，不能用“最近一根涨幅”代替；也不能把所有正涨幅相加。若父卡选择从首次突破固定 ATR/anchor 计整级 milestone，同样必须保持最大已到级数，不能回撤后重复发旧级。

共同行为约束：只有新 price frontier 可以推进；ATR 自己收缩不发新收据；同 CLOSE 多级跳跃最多一个当日市场收据且记录跨级，不积压成以后平价补发的收据；新 CP、新 E0+、拒单或未成交不回滚市场 frontier。信号收据发行与真实订单/成交信用分开，旧凭证不能在退出锁解除后冒作新凭证。具体是否允许丢弃跨级 overshoot 是冻结选择，不是经济最优结论。

关键反例及预期处理：

| 情况 | 正确边界 |
|---|---|
| 每天小幅推进，任一单日都不足一 ATR | 累计 frontier 到已冻结里程碑后可有推进；若逐日比较则错误锁死平滑趋势。 |
| 在旧高之下来回反弹 | 不能累计正涨幅领多次信用；未破通道仍不是 breakout。 |
| 旧最高值滚出 20/55 窗口，C 本身未创新高 | 可能是合法 rolling-channel break，但不是收复同一历史压力位；保留 rolloff 描述，不把窗口降低冒作新价格推进。 |
| ATR 收缩、价格不动 | 用 current ATR 重算整数级可凭空晋级；冻结推进单位或要求新 frontier 防止此项。 |
| 一根跳空越多个 milestone | 当日一个收据、跨级另记，不能承诺多笔成交或把余级排队到以后。 |
| 未过 55 通道但快速加速 | 只证明较短尺度推进，不能改称已破 55；可以保原试探。另开 acceleration 路径会增加新尺度/阈值和弱证据授权，当前不应为救覆盖临时补进去。 |
| E0 新 +、新 CP、同 root 重入或订单被拒 | 不是免费重置通道已发信用的理由；执行重申与市场新推进必须分账。 |
| 当前 CLOSE 才形成突破，next OPEN 涨停或大 gap | 原日线代理价不是可成交承诺；T+1、价格笼子/限价、排队、可卖数量和 partial/ACK 仍由执行链判断。 |
| 旧 exit pending 与新通道收据同日 | 保留旧退出和责任；新收据不能撤锁、预支卖款或把旧层 latefill 贴到新 generation。 |

`oldpeak−n*ATR` trail 必须与本轮 continuation 分开。若将来单独研究，其旧线触发先于当日 ratchet、max 不回撤和 next-action clock 都需明示；峰只能来自当时已完成且真实仍持有的 CLOSE，不能使用事后最高或 flat OPEN 后的当天 C。但即便如此，ATR 收缩也可能使新候选线高于当前 C：例如旧峰仍高、价格已回落、ATR 变小。先查旧线再无条件安装新线，会出现“新线已在价上却未退出”。必须冻结拒绝该次 ratchet、立即新线退出或次观察处理中的一种；三者不同，不能默默替换。此处不替父线程新增退出方案，本轮保原 CP 保护不变。

冻结后事实表至少保留：N、source/价格域、prior-channel 的值/极值发生日/该值已知日、rolloff、ATR/TR/参考冻结日、launch/generation、首次突破与每次前后 frontier/里程碑、原 I/CP/退出锁旁注、UNKNOWN 原因。原 CP 收据和原资金/收益只作并列，不成为通道输入。不计算新 q、成交、卖款或账户结果。

无新模型运行、信号递推、合成价格路径、账户、回测或参数搜索。本文的门槛建议需与最终 freeze 逐项协调；当前没有实现 PASS 或经济 PASS。
