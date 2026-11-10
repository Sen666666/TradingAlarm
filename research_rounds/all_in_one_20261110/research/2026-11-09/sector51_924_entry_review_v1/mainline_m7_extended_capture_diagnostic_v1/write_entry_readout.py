from pathlib import Path
from decimal import Decimal as D
from statistics import median
from collections import Counter
import json,hashlib
O=Path(__file__).resolve().parent
rd=lambda n:json.loads((O/(n+'.json')).read_text())
rows=rd('ENTRY_TIME_SEQUENCE_ROWS');sec=rd('MATURE_SECTOR_FAILURES');summ=rd('ENTRY_TIME_SEQUENCE_SUMMARY');m=[r for r in rows if r['allocation_phase']=='MATURE'];f=[r for r in rows if r['prior_known_same_sid_loss']]
def sm(rs,k):return sum((D(r[k]) for r in rs),D(0))
def fmt(x):return f'{D(x):,.2f}'
line='| 板块 | MATURE轮数 | MATURE净损益 | 无ADD轮数 | 无ADD净损益 | 实际入场聚集 |\n| --- | --- | --- | --- | --- | --- |\n'
line+='\n'.join('| '+r['sector51']+' | '+str(r['rounds'])+' | '+fmt(r['net'])+' | '+str(r['no_ADD_rounds'])+' | '+fmt(r['no_ADD_net'])+' | '+', '.join(d[5:]+'×'+str(n) for d,n in r['entry_days'].items())+' |' for r in sec)
sg=[]
for flag in ['prior_known_same_sid_loss','sector_latest_batch_negative','same_event_known_closed_net_negative','retained_after_previous_OPEN_rejection']:
 for val in [False,True]:
  rs=[r for r in m if r[flag]==val];closed=[r for r in rs if not r['outcome_final_qty']]
  sg.append(dict(label=flag,value=val,count=len(rs),net=sm(rs,'outcome_marked_pnl'),closed_count=len(closed),closed_net=sm(closed,'outcome_marked_pnl'),closed_mean=sm(closed,'outcome_marked_pnl')/len(closed) if closed else None))
(O/'MATURE_CAUSAL_LABEL_CLOSED_CHECK.json').write_text(json.dumps(sg,ensure_ascii=False,indent=2,default=str))
t='''# 新954轮入场与已知失败序列

## 先排除几个不充分的解释

1. MATURE479轮的前一plan CLOSE，sector_state与stock_state全部为1，M全部为1，sector return5_median全部为正。不能说这些订单使用了“已知行业为0”入场，也不能指望仅增加“行业近5日中位收益>0”区分此新窗的失败。另有19轮strength=False，最终全部无ADD、净−7,510.14；此字段与M并不等价。
2. 479轮中412轮由此前因资本约束未成交的票据保留到后来OPEN再入，净−90,049.90；67轮在信号后的首个OPEN即入，净−30,057.82。“retained”值得核查，但两组都亏，且412组含99个末日未闭合，不可只按总额宣布滞留是唯一问题。
3. MATURE有385轮入场时M_streak=1（其中106轮未闭合），62轮streak2，10轮streak3，22轮streak4。增加等待会改变早行情捕获，不能从该分组直接挑最佳天数。
4. 同股上一轮已知亏损后再入有335次，但退出至再入中位16个交易间隔，最短1、最长87；只有10个不超过3间隔，且全部EVENT。333/335已有退出以后新A/B信号。损失并非主要由“没有新信号、立即原地再试”解释。简单“等新A/B”基本不会解决。

这些标签来自当时已知信息，后续净收益只用于诊断；尚未模拟任何候选规则。

## MATURE按板块及实际入场日期

'''+line+'''

排名是11/6以后实际新开的MATURE轮整轮结果，截至认证1/20，既含已闭合也含未闭合；NO_ADD仍是后验发生标签，不是入场可用判断。金属/机械/通信等包含1/17–20极短持仓，收益尚受截断影响。

主要聚集点：
- 游戏传媒65轮分11/12的13轮、12/3的18轮、12/11的34轮，MATURE整体−10,812.25；其中无ADD62轮−13,483.77，有ADD3轮合计为正。不能把整个传媒行业简单封死而不顾少数真实赢家。
- 证券13轮全在11/8开启，全部无ADD、净−9,237.20。出生来自11/4及11/6，入场集中在11/7晚M首次成为1后。
- 医疗14轮在11/8开8轮、11/13开6轮，全无ADD、净−8,800.13。
- 11/8、11/11、11/12的MATURE新开首笔总额分别55.40万、56.63万、23.98万，均用后续供资反复部署，不是三份不同的本金。详细逐笔事件birth、signal、plan、fill四种日期均单列，不能混用。

## 已闭合失败如何进入后续新开序列

所有历史结果只纳入exit_day ≤ plan_day的完整旧轮，以前CLOSE已知为准。同日OPEN才完成的退出没有偷放到前晚。本批新轮没有发现同sid同日先退出再入情形。

- 同sid上一完整轮净亏：全部新轮335次，净−72,208.41；MATURE146次，净−49,108.81。对应无此前已知同股亏损的333个MATURE也净−70,998.91，故不能把所有损失归咎“重复失败”。
- 同sid已知连续亏损1轮后的MATURE118次−41,367.76；连续2轮23次−4,210.65；至少3轮5次−3,530.40。失败计数越大并没有简单单调对应更大的未来损失，本诊断不据此挑次数阈值。
- 同行业最近一个已知平仓日的整批实际轮合计为负后，仍开MATURE269轮，净−56,192.62；该批次并非负的210轮也−63,915.10。这只是最近已知退出信息，不意味着板块所有机会均失败。
- 更窄的同event口径：在当前行业event已有完整闭合轮且小计为负的前提下，继续开65个MATURE，净−24,109.82，其中61个后来无ADD、净−18,398.06。这是**当时已知的已闭合小计**，并未使用将来才知道的event最终结果；也不能直接推导全行业冻结，更不能变成共享试错风险池。

逐例：
- 掌阅科技12/3轮12/5退出−615.99；12/9出现新的A类出生信号，12/10计划、12/11 MATURE重入，前轮已失败4个交易间隔；后轮12/19退出−2,246.16。
- 光环新网12/2轮12/4退出−85.98，12/13 MATURE再入，后轮1/6退出−3,050.28；1/17 EVENT又试、1/20退−83.71。两次再入均已有新信号，分别距前次退出7、9交易间隔。
- 长沙银行12/9 MATURE入场前已知连续两次完整轮亏损，12/12再退−40.87；12/27 MATURE重入时已知连续三轮亏损，后轮1/13退−2,942.19。重入间隔分别22、11交易间隔，不能说没等新结构就隔天重买。
- 行云科技11/13 EVENT前一轮11/7已亏−833.92，11/13新轮后来加仓、11/21退−5,316.49；12/9另一个新EVENT再试，12/11退−753.90。应分别检查小试、扩张及新结构，不能用一个“无ADD试仓”概念覆盖。

## 数据可用范围与设计衔接

ENTRY_TIME_SEQUENCE_ROWS为954个新轮的完整入场标签，含：首笔role/phase、birth_type、event_birth_day、signal_day、plan_day、entry_day、M/E/M_streak、sector state/strength/Q/S/F、stock_state及true streak、行业5日/10日中位收益、此前OPEN资本拒绝明细、同sid历史与同event已知闭合结果。

个股state从运行SOURCE_HASHES匹配的KNOWN3、RIGHT3及PVR STOCK_DAILY重建，完全使用joint51_candidate_v9_facts/engine.py同一公式。没有构造Data或执行history，没有用entry当晚状态冒充前晚。

可执行区分规则交由独立入场设计审查，当前实证要求它解释至少三件事：成熟行业批量新票的集中入场、同股失败后虽然有新信号但结构是否真的改善，以及不要误杀9/24之后真实大行情。简单行业收益正值、仅等新A/B、亏损次数阈值，均缺乏本诊断支持。任何新规则都应先封存，再做真实资金闭合对照，不能把过滤组原历史亏损直接称为将追回的收益。

文件：MATURE_SECTOR_FAILURES、ENTRY_TIME_SEQUENCE_ROWS、ENTRY_TIME_SEQUENCE_SUMMARY、KNOWN_LOSS_SID_REENTRIES、MATURE_ENTRY_LABELS、MATURE_CAUSAL_LABEL_CLOSED_CHECK、STOCK_STATE_SOURCE_HASHES、ENTRY_SEQUENCE_SOURCE_HASHES。均为本地只读输入的新增分析产物。
'''
(O/'ENTRY_SEQUENCE_READOUT.md').write_text(t)
(O/'OUTPUT_SEAL.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SEAL.json'},ensure_ascii=False,indent=2))
print(json.dumps({'closed_label_check':sg,'report':str(O/'ENTRY_SEQUENCE_READOUT.md')},ensure_ascii=False,default=str))
