# MATURE 入场的 S/F 结构来源归因
本报告只归因原冻结基线，不新增筛选、不扫参数、不运行策略。原49份诊断文件逐一哈希不变；新增文件全部以 STRUCTURE_ 开头。

## 关键结论
1. 「MATURE无ADD在行业false后退出」已经存在，不能重复提出。M4.current_trial_seed不看INITIAL/EXPANSION。
2. 晚期479个MATURE：393 S-only、40 F-only、46 both。快路径F并没有避开失败段。
3. 9/24 OPEN的28个MATURE全靠9/23 CLOSE的S-only；10/24光伏30个MATURE也全靠10/23 CLOSE的S-only，包含聚和、禾望、协鑫、钧达等。不能把慢路径一概称为过期残留。
4. 479个晚期MATURE中458属于同event首次M连续段；只有20属于同event明确退出M后恢复，另1个是UNKNOWN后恢复。大多数损失不是同event反复恢复造成。
5. S/F分组只是入场前已知结构标签，分组损益不构成删除某路径能改善账户的证据。

## A. 现有退出核实
源码 mainline_candidate_v4_known_sector_fix_v2/engine.py:80–88：
- current_trial_seed先检查当前所有lot均为SEED，再检查M=0、E已知、行业/个股/I/CP/报价/source状态可判定。
- 不检查capital_role，也不要求historical add_count=0。
- 若current_trial_seed成立且行业state=0，CLOSE锁定CURRENT_SEED_TRIAL_SECTOR_FALSE，原退出引擎在次OPEN执行，原I等退出可优先覆盖。
- 因而MATURE/EXPANSION新SEED只要当前全是SEED，也适用这条退出。
- mainline_candidate_v3_core_reference/engine.py:53–64另有未信息确认时行业false的TRIAL_SECTOR_FALSE后备逻辑。

实际原账：
- 全窗无ADD MATURE763轮：414 CURRENT_SEED_TRIAL_SECTOR_FALSE，148 MAINLINE_EXPANSION_SURPLUS，92 NON_MAINLINE_EXPANSION，5 I_OPEN_PROTECTION，104终点未闭。
- 晚期无ADD MATURE455轮：256 CURRENT_SEED_TRIAL_SECTOR_FALSE，62 NON_MAINLINE_EXPANSION，32 MAINLINE_EXPANSION_SURPLUS，1 I_OPEN_PROTECTION，104终点未闭。
- 资金迁移可能在后续行业false之前已清仓，不能要求所有无ADD都以同一reason退出。

## B. 可计算定义与核验
在计划CLOSE t使用原SECTOR_DAILY的直接导出S、F、Q、M，不用入场当天收盘：
- Q(t)=行业state真，且t及相邻前交易日的真个股数均至少N/2。未知按原上下界三值逻辑。
- S(t)=Q(t) AND RS10(t)>0 AND RS20(t)>0 AND 行业10日收益中位数(t)>0。
- F(t)=Q(t) AND RS5(t)>0 AND RS5(t)>RS5(t−1) AND 行业5日收益中位数(t)>0 AND B20(t)≥N/2。
- B20是复权C严格超过前20个交易日复权收盘最大值的股票数；原每股需21根有效、同source/segment的连续窗口。
- breakout未知按原count/coverage上下界；不能把已知突破数不够半数直接当false，因为未知成分股可能改变多数结论。
- M=三值OR(S,F)，若M真但RS5未知则M回到UNKNOWN。
- S-only严格指S=1/F=0；F-only指S=0/F=1；both指S=1/F=1；S=1/F=-1独立保留。
- F-only中F及多数新高是当前M成立的必要路径；both中多数新高确实出现，但S自身已足以令M真；S-only不依赖F。

核验：4650个行业日的S及M逐项重算一致；除首日外4600个Q一致；104个F真行业日全部满足多数新高及其余可核谓词。首日Q所需前日未在导出中，不伪称完整重算。F的false/unknown直接用冻结导出，缺breakout20_K时不自造覆盖上界。

## C. 分组结果
金额是原完整轮净利，包含原ADD/退出/费用/权益与终点估值，非可挽回收益。

| 窗口/来源 | 轮数 | 已闭 | 未闭 | 原净利 |
|---|---:|---:|---:|---:|
| 全窗 S-only | 659 | 553 | 106 | +18689.53 |
| 全窗 F-only | 68 | 68 | 0 | −16385.76 |
| 全窗 both | 100 | 100 | 0 | −37824.04 |
| 全窗 S真/F未知 | 6 | 6 | 0 | +2396.55 |
| 晚期 S-only | 393 | 287 | 106 | −75982.10 |
| 晚期 F-only | 40 | 40 | 0 | −17179.06 |
| 晚期 both | 46 | 46 | 0 | −26946.56 |

晚期S-only已闭287轮净−76593.14；106未闭净+611.05。F-only和both均已闭，不能用S-only大量新持仓的终点近零来推断其更安全。晚期F-only40轮全部无ADD，37负；both46轮45无ADD，42负。

全窗6个S真/F未知均为9/24 CLOSE→9/25 OPEN的金属行业成熟种子，不挪入S-only或F-only。

多数新高细分：
- F-only68、both100全部有已知多数突破，符合原式。
- S-only659中12个也有多数突破，但其他F条件不满足；647个不能建立已知多数突破。
- 晚期S-only393中5个有多数突破（原净−3032.35），388个未建立多数（−72949.75）。
- 「多数突破但F=0」不矛盾，例如RS5不继续改善；不能只看突破数量复写F。

## D. 954晚期新轮最大亏损行业
行业排名按全部954新轮，与479 MATURE子集明确分开，不能把旧持仓损失混入。

| 行业 | 全新轮净利 | MATURE结构 |
|---|---:|---|
| 金属钢铁 | −16795.05 | 54 S-only，−9235.70 |
| 游戏传媒 | −13650.30 | 52 S-only −6695.85；13 both −4116.40 |
| 医疗服务 | −13597.45 | 6 S-only −3408.52；8 F-only −5391.62 |
| 自动化与机器人 | −12008.79 | 25 S-only −5221.84 |
| 旅游酒店 | −10986.87 | 2 S-only −2661.70 |
| 证券保险 | −10054.07 | 13 both −9237.20 |
| 动力电池 | −10035.81 | 17 S-only −1727.60 |
| 互联网电商 | −9307.46 | 1 S-only +245.59 |
| 消费电子 | −9048.66 | 12 S-only −6028.49 |
| 轨交军工装备 | −8285.66 | 15 S-only −4362.71 |

因此亏损来源跨慢、快及同时成立的结构，不是一条慢路径独有。行业总损失还包含EVENT/RESIDUAL，不能强迫用MATURE分组解释全部损失。

## E. 同event首次进入M与恢复
使用每笔真实event_id及birth_day，仅看计划日之前的行业M历史：
1. 找包含当前计划CLOSE的连续M=1段起点。
2. 同event出生后此前未曾M=1：FIRST_M_IN_EVENT；若观察左边界缺历史或此前unknown则另列。
3. 同event此前已M=1，段起点前明确M=0：RECOVERY_AFTER_KNOWN_M_FALSE。
4. 前日M=UNKNOWN：恢复UNKNOWN单列，不能叫已失败后恢复。
5. 当前仍处首次M连续段的后续单，仍属于首次M段，而不是把每一天/每只股票称为新行业恢复。

晚期：
- 首次M段458轮：383 S-only、40 F-only、35 both，原净−106516.20。
- 明确Mfalse后恢复20轮：9 S-only原净−1900.22；11 both−11614.56。
- UNKNOWN后恢复1轮S-only，−76.74。
- 这些来源中「恢复后的计划日」与「恢复段首次CLOSE」可有不同S/F，逐轮同时保存两者，避免把S开始后来F跟上的段混同。

具体恢复事件：
- 电子元件材料event 2024-09-02，11/11恢复段起点both，11/12–11/14入8个成熟轮，原净−10239.46。
- 医药商业event 11/5，11/12恢复起点both，11/13入2轮，−661.11。
- 半导体event 9/26，11/8恢复起点S真/F未知，11/12–11/13实际成熟入3轮；计划CLOSE路径可能已变化，−1714.44。
- 自动化与机器人event 12/3，1/17恢复S-only，1/20入6轮，截至认证末日尚未闭合。
这些例子不是普遍的「S残留复活」：明确恢复20轮只占479的4.18%，其中计划日both比S-only还多。

## F. 三段真实日线，严格CLOSE→nextOPEN
逐日完整记录见STRUCTURE_THREE_SEQUENCES.json/csv；以下只摘关键节点。

### 1. 软件9/24启动
- 9/20 CLOSE：行业state=0，n16/67，M=0。
- 9/23 CLOSE：state=1、n51/67，但前一日不足半数，Q=0→S=F=M=0；B20=21/67。这一晚形成EVENT，最早9/24 OPEN买常山、拓维、银之杰3只。
- 9/24 CLOSE：n仍51/67，Q=1；RS5=1.9738pp较前日1.9024改善，RS10/20均正，B20=38/67≥34，S=F=M=1。这只能支持9/25 OPEN的5个MATURE，不可拿来说明9/24开盘已具F。
- 9/25 CLOSE：B20=33/67，F=UNKNOWN、S=1→M=1。不能把F未知当跌落false。
- 9/26 CLOSE：B20=55/67已多数，但RS5从2.4326降至1.5705pp，所以F=0，S=1仍M=1。
这段展示：初始小试、随后双路径确认、F短暂unknown/false和S维持可以共存。

### 2. 光伏10月主线
- 10/21 CLOSE：state=0、n3/40、M=0。
- 10/22 CLOSE：state=1、n27/40，但前日不足半数→Q=0、M=0；B20仅2。10/23 OPEN实际3个EVENT小试。
- 10/23 CLOSE：n34/40、Q=1，RS10=6.0889pp、RS20=15.8872pp、行业R10=+7.0260%；S=1。B20仅11/40<20，F=0，M=1。
- 10/24 OPEN实际30个MATURE，全S-only，原合计净+35358.06，包含聚和+21655.88、禾望+10845.52、协鑫+9410.52、钧达+9169.43，也包含20个亏损轮，不能事后只挑赢家。
- 10/25 CLOSE：S=1/F=UNKNOWN；10/29行业state和M未知；10/30行业state=0→M=0，即使RS10仍+14.0257pp、RS20+18.9857pp，Q仍会使S=0。
因此原慢路径并不会无视行业false持续为真；「老涨幅仍正」不等于S仍通行。

### 3. 金属11月失败段
- 11/4 CLOSE：event出生，state=1、n45/112不足半数，M=0。
- 11/5 CLOSE：n73/112，前日仍不足半数→Q=0，M=0；11/5 OPEN先前EVENT3单。
- 11/6 CLOSE：n81/112、Q=1，RS10/20正，S=1；B20=41/112<56，F=0，首次M段开始。
- 11/7 CLOSE：n87/112、S=1/F=0；RS5从3.7695降至2.5083pp，B20=39。该晚支持11/8 OPEN的金力永磁、包钢、北方稀土3个MATURE。
- 11/8 CLOSE：行业state仍1，但RS20转−1.1796pp，RS5−3.4998pp，S=F=M=0。
- 11/11 OPEN这3轮以NON_MAINLINE_EXPANSION融资迁出；原净分别−820.46、+215.96、−382.61。11/11 CLOSE行业state才变0。
此处不是漏了既有行业false退出，而是M先转弱、原资金迁移先发生；也不是同event旧M恢复，是该event第一次M段失败。

## G. 交付与边界
- STRUCTURE_ENTRY_ROWS：833笔计划CLOSE S/F、当前多数突破角色、event及M连续段来源。
- STRUCTURE_PATH_SUMMARY：全窗/晚期/启动/光伏各组ALL/CLOSED/OPEN。
- STRUCTURE_MAJORITY_SUMMARY：当前已知多数突破与F必要/冗余角色。
- STRUCTURE_EPISODE_SUMMARY、STRUCTURE_DISTINCT_M_EPISODES：按入场轮和独立行业段两种口径。
- STRUCTURE_SECTOR_SUMMARY、STRUCTURE_LATE_INDUSTRY_RANK：954行业总损失与479成熟子集。
- STRUCTURE_EXISTING_EXIT_SUMMARY：现成退出规则实际覆盖。
- STRUCTURE_QA、STRUCTURE_SOURCE_HASHES、STRUCTURE_PRIOR_OUTPUT_SEAL：核验与原49文件保全。

结论保持为来源归因：S在重大启动及错误新轮里均承担主要通路；F也会在晚期失败波段成立。没有理由仅按本分组净利直接发布新的S/F入场门槛。
