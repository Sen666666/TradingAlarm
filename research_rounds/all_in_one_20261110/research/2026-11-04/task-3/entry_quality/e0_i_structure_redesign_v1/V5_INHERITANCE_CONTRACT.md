# V5补充：同一结构内由有效层继承执行资格

本件替换V5主卡“必须原probe本人还有存量”和“任一层保护退出即全链失效”的限制。继承的是可追溯的执行资格，不是永久mature、资金额度、原试探未用额度或退出责任。未运行账户、策略/价格路径、新数量或收益。

**原账没有找到所要求的最终赢家实例。** 规则在逻辑上可定义；现有证据仅证明不同保护线会造成局部层退出、后层存续，不能称赢家继承已被验证。

## 1 单一结构身份

`structure_id=(V3_policy_version,sid,comparable_source_segment,I_hold_generation)`。

- 原负E0/down只更新R与恢复cycle、撤当前mature；旧P未破时不换structure_id，健康层的历史证明保留但当前不可用于ADD。
- 同结构重新up/收复R后，必须重新读当前I_mature；不能继承旧的mature=True。
- 旧P破、该版本结构I_hold真正失效或source不可比时，旧id永久退役。新generation不得收养旧层、旧latefill或旧证书；旧仓和退出责任仍保留。
- UP slot、旧原E0 stock_structure、行业epoch/confirmed pool不是同一个id。特别不能把旧G1-I off当全局换根、却仍沿用没有增代的V3 id。原账旧I/root仅作原始对照，本轮未映射成V3 generation。

每个grant在发出时绑定structure_id；fill回报沿原grant归属，不按回报到达时的当前结构重新贴标签。

## 2 当前可承接的层

对实际层l，在t收盘用t−1已生效的原层保护线F_l：

```
healthy(l,t) = 实际可核的剩余持仓qty>0
             AND l.structure_id == 当前有效structure_id
             AND C_t及F_l已知可比 AND C_t>F_l
             AND 本层未触发/未被指定退出，也未retire

Carrier(t) = {l: healthy(l,t) AND Certified(l)}
```

CORE仍用所选同版本I保护，MOBILE用自己的原CP保护；不能用全股min floor假装都健康，也不能用全股max floor一层触发杀全部资格。触线层立即排除，即使尚未卖出；其它层逐个检查后仍可承接。反弹或撤单不能默默复活已退役层。

Certified只有两类：

1. 事前批准target、真实累计成交完成、子单/terminal ACK对账完成的probe seed。cap或held=100不能代替；它仅证明执行完成。
2. 实际正成交的ADD，其原grant保存了当时合格carrier/证书见证、同structure_id、当时I_mature与新鲜CP、无未结责任等条件。认证只引用当时已经知道的过去事实，不能两个旧add互相自证。

ADD在合法授予并真实成交后拥有自己的认证谱系。原probe或父carrier后来退出，不回溯删除这个合法历史；其自身若仍健康，可继续作为carrier。**不再要求原probe的股份仍在。** 但当前未完成parent、partial/cancel/replace/exit锁仍阻止新目标，不能借别的健康层绕开。

旧原账没有这些V5见证字段。`role=mobile/kind=add/pool=confirmed`均不自动认证。本轮不自动签发legacy adoption；若将来迁入，须明确原真实加层前已有仓位、真实CP/批准/成交、结构映射、当前健康与责任清楚，且不能按最终盈亏挑选。

## 3 ADD入口与退出顺序

```
ADD_ready = 当前结构alive AND I_hold is True AND I_mature is True
            AND 存在当前健康Certified carrier
            AND 当前新CP未消费
            AND CP确认晚于所用证明known_at及退出解锁的真实获知时刻
            AND 全sid无buy/exit/cancel/replace/partial未结责任
            AND source、保护及执行context全部已知
```

每个收盘：

1. 先检查旧结构P。结构失效则全旧id不可继承，保留未完成退出。
2. 逐层以各自旧floor检查，触线只退役该层的carrier资格并提退出；不能用本日新CP抬线遮掉旧触线。
3. 未触线层按原规则max抬线、不回撤。保留其它健康层证书，不需要先重建probe。
4. 任一同股退出尚未完成时全sid不ADD。健康carrier可保留资格记录，但不能绕开卖单责任。
5. 真实退出完结并对账解锁后，等下一份新CP，以当前mature与重新检查的carrier决定。被锁期间出现的旧CP不能之后重放。

这不新发UP信用、不返还历史已用试探、不更改target_Q/F，也不把旧层保护线复制/降低给其它层。任何新ADD仍独立经过原数量、行业、现金与组合风险约束，不能从“可继承”推出可给大仓。

## 4 核实的原账事实

### 2022—24：只有两条分层存续类比，均不是最终赢家

覆盖1677个campaign、2265层、788个CP卖receipt/1081个parts。严格筛选早层因CP全平、更晚ADD在此前已入场且卖后仍持有，只有以下2例，正终值campaign为0。

以下C及floor全部为同源复权单位，另列原收盘供核对；不混为原成交报价。

|原事件|收盘C|早层旧线|晚层旧线|原实际路径|
|---|---:|---:|---:|---|
|虹软2023-04-13（raw37.04）|37.57837039|1156：38.17688627|1213：36.57639140|只提1156退出380股；4/14代理成交37.28135。晚层1213仍377股且无本股待卖，旧I持续至4/18。|
|杭州银行2024-11-22（raw13.45）|33.89035360|1998：33.93043523|2037：33.88841287|只提1998退出900股；11/25代理成交13.45327。晚层2037仍100股且无本股待卖，旧I持续至12/24。|

原根分别为688088.SH|0|2023-03-15、600926.SH|0|2024-09-23。两例触发日和卖后日原E0 event均0、原CP均无receipt；旧I_target真不能替代新I_mature真，V3 generation/mature本轮未计算，明确UNKNOWN。原最终campaign净贡献分别−2074.29、−692.59，只作旧路径注释。

进一步检查旧层卖出后的全部原收盘：虹软4/14—4/18共3日、杭州银行11/25—12/24共22日，**均没有新的原CP receipt**。因此这两例甚至不能证明“继承后实际出现过新CP扩张机会”。它们只证明分层保护存续在原账中确实存在，不能包装成赢家/成熟层继承验证。

原数值、exit指定层、真实卖parts、前后快照、原I/CP/E0及源索引见[v5_inheritance/original_hist](v5_inheritance/original_hist/READOUT.md)。原日线proxy成交不是券商真实ACK。

### 2025—26强窗：合格实例0

范围2025-07-01—2026-06-30，242个收盘快照、1171层/867 MOBILE；492个CP卖事件/666 MOBILE卖parts。174个早层parts卖前已有更晚MOBILE，但晚层也在同OPEN退出。卖后407次flat、85次只剩CORE，0次仍存MOBILE；放开同root限制仍0。

真实反例000711：2026-03-24 adjusted C10.714441低于四个MOBILE共同旧CP10.819796；3/25四层723/733/761/769共38400股全部代理卖出，只余CORE713=100。原I真、G1−3不证明新mature，更不能因“曾有ADD且还有100股CORE”自动认证。详见[strong原账筛选](v5_inheritance/original_strong/READOUT.md)。

## 5 必须拒绝的错误继承

- 有健康晚层但旧层卖单未完成：记录资格，不ADD；不能用同OPEN卖款/日线代理假定已解锁。
- down未破P：id不变、证书保留，但当前mature=False时不ADD；恢复需当前确认与新CP。
- P破后尚有未卖仓：旧id已退休；新E0启动不重贴旧层或latefill，必须新资格。
- 只剩未认证tinyCORE或任意旧add名义：不能按qty/role/pool自证。
- 当前carrier全部清空：不能凭历史证书在flat时自动ADD；历史F不退，按V5新的合法probe/UP规则重启。
- 被触线的层即使反弹、撤单ACK，也不自动重新成为carrier；其它独立健康层可按当前规则继续。
- 继承不得继承旧mature=True、旧资金level、未用probe额度或提高target上限；只继承同结构合法执行谱系。

当前仅是无新价格/金额阈值的明确规则。原样本缺V5认证谱系与真实赢家继承案，不能宣称收益改善、适用覆盖大或已具备实盘执行证据。
