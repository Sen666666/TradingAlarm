# 盈新六次获资：原账字段与状态记忆

范围：000620.SZ，Jan10—Jan25信号/成交；附Jan7→Jan10及Jan25→Jan26边界。只读既有原账、daily和已封证据，0模型、0账户、0回测、0新反事实。索引均从0起。

|层|信号→实际OPEN|role / 实际pool|原cap→reserve/filled|信号NAV / available|原gross预算 / CORE risk预算|初始raw保护线|
|---|---|---|---:|---:|---:|---:|
|68|2022-01-10→2022-01-11|core / probe|3200→100/100|995,688.15 / 98,284.77|8,804.37 / 2,489.22|1.979999999999999859515624618|
|69|2022-01-11→2022-01-12|mobile / confirmed|6500→6300/6300|980,931.86 / 99,755.25|19,618.64 / 缺失|2.696783114302186790939003270|
|75|2022-01-12→2022-01-13|mobile / confirmed|5900→5700/5700|983,200.24 / 98,108.98|19,664.00 / 缺失|2.963799766429140503387627174|
|78|2022-01-13→2022-01-14|mobile / confirmed|5300→4200/4200|975,021.45 / 98,630.20|19,500.43 / 缺失|3.259284335287634634016387313|
|113|2022-01-21→2022-01-24|mobile / confirmed|5200→5100/5100|954,350.44 / 97,886.56|19,087.01 / 缺失|3.120404405634801719785893253|
|122|2022-01-24→2022-01-25|mobile / confirmed|4800→4700/4700|960,203.68 / 95,643.44|19,204.07 / 缺失|3.427922325927401819163579548|

六笔pool由原real_reserve、real_buy_fill和funding reserved三方逐值对齐；不使用期末layer metadata的pool回填。逐笔价格/费用、OPEN该槽位现金的既有审计桥、原CP全文和原索引在SIX_FUNDING_ORIGINAL_FIELDS.json / CSV。现金桥是已封旧审计结果，不是reserve原行中的现金字段，本次没有复算。

六笔预算episode相同：`4fea5d5ed03a2a92162f3599613e869890b5b1032faa4b21208fa80acbdea6a4`；六笔预算attempt相同：`4fea5d5ed03a2a92162f3599613e869890b5b1032faa4b21208fa80acbdea6a4:0625200ec6d4dcbbcd7d006cc808066b44636b406b10e2530c3d6014ee362ebb`。上游market attempt另为`5695314f80418e0466fcb738db1f7e2e23528e40fdbf5bfc24a1e470bbac1f60`，不是同一个字段；上游authorization为`ce7cebb69515c4284b7f42739212f1758c25da65df13f12ede291952009abb73`。

六笔信号时market stage原字段均confirmed；截至各信号日最后一条原金融变更事件均是2022-01-07：result=confirmed、financial_level=1（industry原行61）。这是最后已记录变更，不等于逐reserve现场完整快照。reserve/fill/funding行没有financial_level、active/status、各池试算q和成功获资约束向量，全部标NOT_RECORDED；不以期末budget.sectors补写。

为何68为probe、之后为confirmed：原日志证明结果。有效route源码限定core只有probe候选；mobile且expand、金融level>0并migrate成功才追加confirmed，比较两池可买量、probe同量优先。这解释机制许可，不证明每次confirmed的另一池具体q或哪一道门约束了数量，原日志未存。No60实际route仅对probe保pool_capital，不误引旧confirmed60上限。

Jan10 CLOSE原opportunity roles=[core,mobile]，decision同时保存CORE cap3200/gross预算8804.37与MOBILE cap7200/gross预算19913.762962110280090（CP ca675c13…）。Jan11 OPEN core先reserved 100，J.opening先按rank再core优先，成功后done.add(sid)，同股后续mobile命中continue；没有mobile拒单记录，不能称被拒。CORE本身CP1_id=None，不能把当日市场CP贴成CORE用过的凭证。

原decision在Jan14、17、18、19均没有该股intent；这只表示原保存列表为空，不追加后验失败状态。Jan7 CLOSE的core/mobile请求在Jan10上午均有cash_or_original_reserve,probe_risk拒绝，属于Jan7信号，和Jan10 CLOSE的两请求分开。Jan20 CLOSE mobile cap5900在Jan21 OPEN原记录拒绝cash_or_original_reserve,sector_capital；Jan21 CLOSE是另一个新CP mobile，Jan24 OPEN成交5100。

## 1/19退出请求、1/20卖出、1/21再次申请的已存损耗

|原CLOSE日期|原daily index|全账户shared_loss|该股intent|
|---|---:|---:|---|
|2022-01-19|11|28811.87150252008|[]|
|2022-01-20|12|37365.253523610576|[('mobile', 5900)]|
|2022-01-21|13|43231.31570911908|[('mobile', 5200)]|

Jan19 CLOSE原pending_sells含000620.SZ；Jan20 09:30 journal[230]真实卖出69/75/78共16200股，价2.948525、费用61.5561795135000。Jan21 CLOSE又有fresh_CP1_mobile原intent。上表shared_loss是全账户累计原字段，不能把日间增量归给盈新一股，也不能当作该行业或该attempt损耗。所选原daily/journal/funding没有同股/行业/attempt当时累计loss快照；期末budget.losses不回填。

Jan25 09:30先成交122（来自Jan24 CLOSE）；Jan25 CLOSE行业市场controller才发生confirmed→observe、action=end_attempt、reason=mobile_line、authorization撤销，原industry金融变更行412为invalidated（level字段仍1）。同一个Jan25 CLOSE原规划仍保存一笔mobile cap4200；Jan26 OPEN原funding以industry_invalidated拒绝。不能把Jan25晚间失效倒填至Jan25早上，亦不能把level仍1理解为active仍真。

## 源码与原记录入口

- joint_v3.py:195–212：行业market记录驱动预算observe，且只在result不为unchanged时写金融变更事件。
- joint_v3.py:241–259：原roles、barriers、CORE/MOBILE intent、frozen cap；:259保存daily.shared_loss与pool总量。
- joint_v3.py:302–324：先退出/结算，再按rank与core优先，done/pending阻止同股第二reserve，之后调用fill。
- route_without_account_check.py:3–10、24–29 + component.py:17–34：真实No60路由来源、pool候选及最大合法量选择；NO60_ACTIVE_ROUTE_SOURCE.txt是已封有效文本。
- model_without_account_check.py:73–90、210–262：loss桶的sector+original episode键、shared_loss求和、request；record_only不把损耗记忆清零。这里只解释源码，不生成历史桶快照。

逐笔原对象及索引：SIX_FUNDING_ORIGINAL_FIELDS.json；完整原请求/边界：ORIGINAL_CLOSE_TIMELINE.json与ALL_RECORDED_FUNDING_AND_REJECTIONS.json；原金融变更：INDUSTRY_FINANCIAL_CHANGE_EVENTS.json；1/19—21：LOSS_MEMORY_ORIGINAL_FIELDS.json。SOURCE_MANIFEST.json绑定输入与源码sha。
