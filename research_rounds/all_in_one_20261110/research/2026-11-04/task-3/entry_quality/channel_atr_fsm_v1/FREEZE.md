# 固定E0＋20日通道＋ATR14/N3：完整信号级V1

参数在批量运行前固定：L=20；Wilder ATR14；每1倍首次突破时冻结ATR一个净推进格；N=3。不得按盈新、海、银或半导体结果改参。本轮只市场事件/影子保护，不账户、不数量、资金、费用或新收益。旧纸面20/55/N2/3/4仅历史诊断，不用于选本参数。

## 母体与期间

原STOCK_MANIFEST1709股，1687 complete、22无本地观察按原状态报告，不当负样本。2022-01-01—2023-12-31及2024-09-01—12-31覆盖原母体全部适用股票，不仅已买；2025-01-01—2026-06-30覆盖原行业元数据全部半导体（固定名单/非PIT局限明示），不只原25层18股。每股从完整原source前缀递推，展示期才截断。当前源未涵盖2026下半年，不补未来。

## 特征与未知

沿PAPER_SPEC同源复权真实O/H/L/C、有效观察钟。首TR=H-L；首14TR均值种子，随后ATR=(13*oldATR+TR)/14；决策取ATRprev。U20=max此前20完成H，不含今日。数值tie沿原gamma4。

显式unknown Boolean不得bool(NaN)；观察/eligible/invalid/synthetic均须已知。已知invalid/synthetic断指标暖，源不可比另封存旧id；完全缺失session须上游日历识别，当前源不能把缺行当停牌，也不声称已验证无缺失。真实停牌/limit/ST/盘口/receive缺口逐项报告。旧可比保护线和退出责任不因未知清掉；未知期间不新发推进。

## 主市场FSM（不是实仓）

OFF遇原E0正event：新generation，START并发E0_START_ELIGIBILITY；原CORE入口不要求CP。hard=Lconfirmed；若ATRprev可用，P=max(hard,Cstart-3ATRprev)，否则P=hard、标ATR_UNPREPARED且禁止新成熟事件。shadow_peak初始化Cstart，不将启动前/当日H冒实际持仓峰。主轨迹是以E0收盘为观察起点的市场影子，绝不称真实持仓。

旧hard/P检查只要求当前C是真实已知、source可比；当日H/L/ATR缺失不能豁免已经知道的旧线。新ATR提线只用已知此前峰/ATR；未准备则不虚构，既有P保留，禁止新推进。main不能回接native旧I_target作许可；两者版本分开。

每个有效收盘：
1. active先检旧hard/P；C<=Pold发EXIT_STORED_LINE。未触才算Q=max(Pold,hard_old,shadow_peak_before-3ATRprev)；C<=Q发EXIT_NEW_ATR_PROPOSAL，不能默默安装已触线新P；否则Pnext=Q。原hard线失效也单列原因。
2. 退出旧gen封存；当日原+可记新START/newgen，旧exit责任不消失，实际意图以退出优先。新gen当天不得MATURE_ADD。
3. 原+在仍active时仅max抬hard至新已确认低点，不重置A/S/j；普通原负event不重锚活跃通道或清已用格（E0只launch）。source不可比封旧id并输出UNKNOWN，不跨单位max。
4. START后首次C>U20且ATRprev>0：CHANNEL_SEEN，冻结A=C、S=ATRprev、F=C、j=0。**仅首次突破不等于成熟。**
5. 之后F=max(oldF,C)，j_new为满足F-A>=j*S的最大非负整数；只有C>oldF且j_new>j_consumed才发一个CHANNEL_ADVANCE，首j>=1时MATURE。跳多格只发当天一事件并消费所有跨格，无未来补发；A/S不随ATR收缩变化。
6. 同close的E0/I/CP/通道推进归一个意图束；CP收据不再是新CHANNEL_ADVANCE的前置门，但CP保护更新可并存。无执行fill/ACK不声称原CORE或probe已成交，V5执行资格/锁仍是未来入场条件。
7. 更新shadow_peak：旧gen已active时用max(oldpeak,当日H)供以后；新gen首日只Cstart。ATR保护退出即结束该候选gen，后续E0+可新试，不设冷却；本地原E0原target仍active也不自动复活旧gen。

成熟是当前未退出影子内曾有真实1S净推进；回撤期间无新close-frontier格就没有新ADD事件。价格未重新越盘中U20仍可推进（已CHANNEL_SEEN），但从未越通道时只E0试探，不暗加2ATR早期OR臂。原Core/CP层不批量改保护，实际层须在grant显式标policy；本轮不迁入实仓。

## 与现行CP的同锚保护诊断

不拼接原持仓路径，更不合计策略收益。独立取展示期内**所有原raw CP receipt**作共同参考锚，未按是否获资筛选。P0=max(原candidate,原I_floor)，两影子初始P0相同。原CP/input/原I版本保持，不把新mature喂e0_valid。

从锚后首个真实观察开始：signalC为共同观察价格，次观察OPEN仅价参考、不宣称成交；若OPEN缺失/报价已<=P0，标ENTRY_QUOTE_INVALID/UNKNOWN，不假设开仓。两保护影子均服从相同原I_invalid hard退出；CP按旧线先检后max(I_floor,当日CPcandidate)，ATR按旧线先检及Q=max(oldP,I_floor,此前shadowpeak-3ATRprev)。峰从共同signalC开始，此后H只有完成收盘后供下一次使用。非真实账户层，不能冒充实际fill日起持仓峰。

各自第一次exit signal后吸收停止；另一影子继续到其退出、原共同I失效/source不可比/源末。配对不复制原ACT/NAV暂停或原资金卖出，也不假定信号后的OPEN确能成交；原CP是同输入下保护规则对照，不是原账户收益重演。

输出：exit日期/原因/有效观察持有长度；次观测OPEN与触线价差（只报价诊断）；第20观察排除锚日，第一个锚后真实观察计1。共同风险分母固定为锚日已知ATRprev>0，两影子全程同分母；缺失不可填0。第20两者存续/已退出/未成熟分类；20后在各自影子存续内最大close峰到close回撤；第20当时stop距离。20前退出、未满20、UNKNOWN、入场参考报价无效均分栏/分母，不记后风险0优越；另报早退失去后续强势路径的代价，右截尾不填未来。

共同后续截止预定为锚后的原native I首次已知失效、source不可比或本地源末三者最早；**不按任一保护分支exit截断这个价格标签**。强势诊断按该共同区间最大有利close excursion/锚日ATR的各窗口十分位，仅报告持有长度/提前截断，不用于信号、参数或策略盈亏。主FSM根不得截配对cohort，配对I失效也不得倒灌main。另完整列海、银、盈、半导体原真实赢家/强势段逐日例，固定N不因哪个案例好而晋升。

## 交付与限制

全母体市场事件/日状态、每个CP锚保护配对、覆盖/缺失/右截尾、20后风险分母、强势误伤原值。先5股smoke（源字段/同日退出重启/去重），再稳定分片并行；批量前代码/本卡SHA固定。允许修明确接线bug但需保前版和差异，不改经济规则救结果。独审源值/时钟/关键轨迹，不给经济PASS。
