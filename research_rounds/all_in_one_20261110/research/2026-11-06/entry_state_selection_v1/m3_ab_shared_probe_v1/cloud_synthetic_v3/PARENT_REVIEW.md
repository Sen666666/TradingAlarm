# M3 A+B 共享账户接口：父级审阅冻结
记录性质：云端离线设计，不是原生接入、真实数据复验或收益结果。原 Mac 离线，依据断连前已读取的源码；本文未重新读取或核验原文件 hash。

## 保留的策略本体
- M3 为原 common-known 分母；A 为行业 FALSE→TRUE 且股票M3真，B为行业持续真且股票M3 FALSE→TRUE。UNKNOWN、左截断不能当FALSE。
- 原股票I许可、PVR已知与行业内PVR降序/sid排序、每行业每日最多两个初始机会原样；机会不是持股数上限。
- 原首次I退出、唯一一次盈利fresh-CP ADD、ADD独立CP保护、真实卖清后新A/B票重入。没有原PVR/MOBILE替代入口，没有分钟数据。
- 不把native行业E0/CP额外AND回M3。原native资金门只能是明确对照，不是A/B已验证资格。
- 基准no_budget适配必须原样复现旧固定120万参考、初层24000/ADD24000/槽48000/整轮风险3000及原OPEN sizing。不能在该回归模式启用新冻结量或动态资金。

## 明确的新共享资金合同
单轮 r 的 Nd 为首次信号CLOSE已认证共享NAV，此轮固定不随后续净值增大：
B_initial=0.02*Nd；B_add_max=0.02*Nd；slot=0.04*Nd；R_round=0.0025*Nd。
比例是沿旧实验的研究参数，不是声称用户亲自指定这些数字。
保留AB预算包含买费：q*p+buy_fee<=B。ADD预算为min(B_add_max, max(0,slot-held_q*known_raw_open))。
初始计划风险为max(0,q*(buy_px-floor*(1-sell_slip))+buy_fee+dated_sell_fee_at_floor)，不等于实际最坏亏损。跳空、缺价与成交代理仍有限制。
初层收盘数量冻结且OPEN只可缩是共享模式新增执行限制，不伪称AB旧行为；no_budget仍按旧OPEN已知价重算。
ADD仍沿AB既有初层I护线的风险占用及剩余R_round，不将native多次MOBILE或新的独立0.25%每追加额度塞入。

账户总额使用该阶段已认证 N：现金+库存已知原价MTM+已认应收。盈利判断不是这个gross NAV。
所有probe库存及真正live/cancel_pending订单：资金<=0.10*N，名义护线风险<=0.005*N。
池风险采用sum q*max(mark_or_reserved_buy_price-floor,0)，与每单含费风险独立记账；绝不叫0.5%保证最大损失。
行业资本/行业风险、现金保留和其他上限作为显式冻结配置传入；不得通过缺省native active/level改变M3资格。旧行业ALL<=2%（含confirmed）会挡新probe，必须保留反例而不是偷偷放松。

## 唯一时钟与责任边界
1. t CLOSE产生当日A/B候选、排行业两个机会、冻结意图/风险/期望下一共同OPEN。CLOSE意图不假扮真实broker order，不立即扣共享现金。
2. 下一共同OPEN：只读当时已知O、日期规则、来源、factor和权益事实。全部可知卖出先处理，已到可用时点的款项结算后形成共同snapshot。
3. 晋升资格从这一post-sell/pre-buy快照计算；各股先统一prepare、后commit，禁止逐股晋升改变别股资格。
4. 买入按必须提供并封存的全市场队列处理。不能把原无共享资金的sector字典迭代顺序当有经济依据的跨行业策略。跨行业调度未获真实源比对前不运行经济。
5. OPEN实际目标/订单登记后才占用资本和风险；live与cancel_pending都占用。请求取消不释放，terminal ACK与fill对账才释放。条件代理和合成证据域明确，不能伪造真实ACK。
6. OPEN资金拒绝、缺价或护线拒绝，不回补行业第3名，不把旧票留给更晚日期。原后续新A/B票仍可重入。
7. T+1按每次fill日期核可卖量，不仅看round第一次买入日期；卖清和订单责任解除前都不是FLAT。

## 晋升、盈利和权益
- 同一原AB round_id，健康已持有probe、首探已完成且无待买/待卖冲突。
- 原fresh CP的known_at严格晚于首探完成；原信号CLOSE及执行OPEN本轮净清算权益都>0，行业M3严格TRUE。
- 本轮净清算权益 = 本轮累计cashflow + 本轮已认receivable + 剩余core/add数量*known_open*(1-slip) - dated整体卖费。
- 保留原AB本轮利润定义，不能换成native剩余成本利润，也不能借其他股票、同股旧轮股息或旧轮利润。
- 晋升只换本轮相应层的pool；不改股数/买入成本/持有日/保护线/现金/整体NAV，不是卖出或再次买入。
- 登记日仅该臂该轮实际已填库存享有已审权益；ex确认应收，不变可用现金；pay CLOSE现金与应收等额转移，次共同OPEN可用。pay不是第二次收益。
- 历史claims在其旧round持续结算，不能归给重入的新round。多层清算整体卖费不能按每层重复收最低费。
- 云端服务必须记录证据域SYNTHETIC；真实canonical CP ID与权益source seal待Mac恢复核验，不制造真实凭证。

## UNKNOWN
保留未知仓位、订单和claims责任，不释资、不填零盈亏，不用后来价格回填选择。
任一无法认证的资产使共享NAV不能完整认证时，新首买/ADD/晋升停止；可知资产的既有保护退出和已确认权益结算继续。
这是数据证据不足的工程边界，不是ACT策略冷却。若将来要按保守NAV下界继续买入，必须另列风险合同，不在本版暗加。
固定1709/90名单NON-PIT、有限NET80权益情景、历史真实可成交UNKNOWN均保留。

## 非空首日与完整性
已读freeze_events源码按sector面板shift求prevS，首行可能只有OTHER_UNKNOWN_OR_LEFT。恢复时先核首个真正合法A/B事件/执行日，再冻结非空首日fixture；不能用空首日通过宣称接入成功。
现成事件只涵盖2022、2024秋、2026半导体三窗，不足以称2022–2026连续全市场新入。需要另行按同式重建缺失年份市场票，不能把三窗拼接。

## 已读源码依据
- m3_stock_birth_during_sector_v1/PROTOCOL.json、freeze_events.py：common-known、A/B身份、UNKNOWN与初始前缀。
- relative_priority_v1/simulate.py:45–59队列；100–123原size/checkclose；143–157原entry；158–190原ADD；191–214原持有管理；229–246两行业机会。
- relative_priority_equity_run_2022_v1/engine.py 与 cash_equity_baseline_2024_v1/engine.py：登记、ex、pay、bridge、NET80及原mark包装。
- unified_probe_account_contract_v1/unified_probe.py（此前已读755547版）：首探/共享池及逐股晋升的对照，不直接作为AB策略引擎。

## 合成验证预期
验证资金和名义/含费风险分离、顺序共享与取消责任、同股同轮证明、close/open双利润、pool迁移不造现金、旧轮claim隔离、ex/pay时钟、T+1分层及UNKNOWN不释资。
源码实际桥接、原事件回归、真实非空首日、权益source hash与全期收益均未由合成测试证明。
