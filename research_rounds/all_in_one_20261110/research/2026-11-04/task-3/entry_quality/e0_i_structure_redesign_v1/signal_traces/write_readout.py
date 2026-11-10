"""Summarize saved V2 traces only. No state rerun, account or return calculation."""
from pathlib import Path
from collections import Counter
import hashlib,json
O=Path(__file__).resolve().parent;OUT=O/'v2_all7'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((OUT/n).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
rows=read('ALL_DAILY_TRACES.json');entry=read('ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.json');keys=read('KEY_DATES.json');run=read('RUN_RECEIPT.json');checks=read('PREFIX_CHECKS.json');fix=read('UNKNOWN_HOLD_FIX_DISPLAY_COMPARISON.json')
for p,h in run['source_sha256'].items():assert sha(p)==h,('source changed',p)
counts=[]
for sid in dict.fromkeys(r['sid'] for r in rows):
 rr=[r for r in rows if r['sid']==sid]
 counts.append(dict(sid=sid,display_rows=len(rr),modes=dict(Counter(r['mode'] for r in rr)),first_day=rr[0]['day'],last_day=rr[-1]['day'],known_C_missing_volume_rows=sum(r['price_close_valid'] and not r['volume_valid'] for r in rr),source_changes_in_display=sum(r['source_segment_changed'] for r in rr),same_day_old_exit_and_new_START=sum(bool(r['support_exit_events']) and r['launch_event'] is not None for r in rr)))
save('DISPLAY_COVERAGE.json',counts)
lines=['# E0/I V2：唯一A OR B逐日信号演绎','',
'已按SIGNAL_FREEZE_V2.md（SHA400f6b78…dfc78）实现唯一A OR B，未运行旧U_OR/S_PAIR草稿。原E0 event只读，未重算其RMS/量能或CP；7股从原source完整历史前缀递推后截既定区间，共2103行。0账户、订单、候选数量、现金路径或候选收益。','',
'## 当前可用结论与未解决反例','',
'**所选28个原实际获资层，在其原signal CLOSE的新I_expand全部仍为True。** 包含盈新六层、山东8层、太保3层、海3层、金海通4层、新洁能两层和捷捷两层。失败入场没有被这层成熟许可直接挡住，不能称问题已经修好。该结论仅来自同一原时点的权限注释，不代表新账户交易路径不变；CORE启动消费、新I下CP及资金/执行均未接线。','',
'盈新是必须保留的反例：Jan6确认的L2=2.2550550489低于前L1=2.3689467181；当日C2.5739517225<KA2.6081192232，只START。Jan7 C2.8359025615越KA，A独立确认。Jan20虽有HL L2=3.4053609072>L1=2.2550550489，但C3.7470359146<H12=4.3051050934，B=false；**旧KA仍2.6081192232，A=true，I_expand仍真**。Jan21原新增信号仍A真，Jan24 C4.5328884317再高于H12，两路皆真。直到Feb7 C3.2800800712破旧P3.4053609072才退出该结构。没有为此临时新增A失效门。','',
'|路径/日|C|KA|P_old→P_new|A/B→mode|','|---|---:|---:|---|---|']
selected={('000620.SZ','2022-01-06'),('000620.SZ','2022-01-07'),('000620.SZ','2022-01-20'),('000620.SZ','2022-01-21'),('000620.SZ','2022-01-24'),('601019.SH','2022-12-12'),('601019.SH','2023-02-10'),('601019.SH','2023-06-19'),('601019.SH','2023-06-26'),('601601.SH','2024-08-30'),('601601.SH','2024-09-24'),('002583.SZ','2024-09-20'),('002583.SZ','2024-11-04'),('002583.SZ','2024-11-25'),('002583.SZ','2024-11-26')}
for r in keys:
 if (r['sid'],r['day']) in selected:lines.append(f'|{r["sid"]} {r["day"]}|{r["C"]}|{r["KA"]}|{r["P_old"]}→{r["P_new"]}|{r["A_active"]}/{r["B_active"]}→{r["mode"]}|')
lines+=['',
'太保Aug30为B独立：L1=39.3635393082（pivot Aug8 / confirmed Aug19）、H12=42.0692371320（Aug26 / Aug29）、L2=40.3672659203（Aug29 / Aug30）。C43.1166040316>H12、但<KA43.3638989940，所以A假B真。Sep24 C47.6697406921，两路真。','',
'海Sep20为A独立：L2=20.1193538191（pivot Sep18 / confirmed Sep19）<L1=21.0747421290，B_base为假；C24.3343022449>KA22.8731201240（高pivot Aug7 / confirmed Aug12），A真。Nov4原高pivot158.4820608101（发生Oct31、Nov4才确认）并非LH，原较低KA不自动抬升，当日仍成熟；Nov25确认lower-high140.4982808600，修复KA升至158.4820608101、清B，才退START；Nov26破P111.2746384411退出。','',
'山东显示B可绕开较远A：2022Dec12新LH将KA从8.0022731405升至8.5247281447，撤B而退START；2023Feb10 C8.2614644815尚未越KA，但最新HL三点的H12较低，B独立恢复。Jun19再次LH退START；Jun26破P11.9095466728退出。详细L/H、发生日/确认日、初始KA及修订来源见KEY_DATES.json和逐日表。','',
'## 因果时序与输出','',
'signal_trace.py逐日只消费原已发布pivot：先用有效可比C检查旧P（不依赖当日量），再登记原event、启动/更新P、更新相邻L1-H12-L2、处理active LH修复KA，最后三值OR。HL/LH/支撑/突破/所有max都采用原numeric.compare gamma4 tie，tie保留旧值/来源。','',
'A取START时此前最后两个已确认H的max，一个可用则SINGLE_HIGH，无则unknown；LH只可抬修复KA，initial_KA与current_KA/provenance分开。B取最新相邻已确认三点并核pivot次序与H12此前确认，不要求收复A。回落仅撤对应分支，B的HL基础不因单纯价格回落消失，重新越线可恢复。','',
'缺当前C时I_hold/I_expand为unknown，历史mode仅memory。source换段封存旧代，不跨单位max；not-active且event未ready的current_hold已按独审修为None。7股完整前缀只有7个initial source变化，之后实际换段0，展示期影响0；修正前后2103行展示逐字节一致（UNKNOWN_HOLD_FIX_DISPLAY_COMPARISON.json）。这是定义合规修正，不是新增机制或案例调参。','',
'每股做两个隔离prefix-cut：展示中点与倒数第二展示日，给短run的输入确实截在cut，不只跑最后日。14个逐字段exact通过；原对照在完成state之后加入，且不修改prefix对象。没有另外新增场景或测试矩阵。','',
'|股票|展示区间|行数|当前mode计数|有效C缺量行|','|---|---|---:|---|---:|']
for r in counts:lines.append(f'|{r["sid"]}|{r["first_day"]}→{r["last_day"]}|{r["display_rows"]}|{r["modes"]}|{r["known_C_missing_volume_rows"]}|')
lines+=['',
'本展示无实际不可比换段；缺量旧P分支是否覆盖以DISPLAY_COVERAGE.json的实际计数为准，不将未出现的数据分支冒称已由真实路径验证。旧代support_exit与同日新START在结构内分别保存，不表示任何旧订单或旧仓已成交/责任释放。','',
'## 独立原信号注释与审查','',
'ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.csv/json：按原INPUT_INDEX的28个实际层及原signal日期，单独join C/rawC、P、KA、A/B/I_expand、旧I/G1/CP与层号/实际fill日。ORIGINAL_INTENT_SIGNAL_JOIN.csv/json保351个原intent注释（含未获资者）。这些原信息**不进入状态机**；不生成新数量/资金/收益，不把原CP当成新I下仍有效的凭证。','',
'原pivot发生日与确认可知日分列；source_event_id是对原row的本地稳定引用，没有制造新E0事件。所有sigma字段明确原E0 RMS未持久化/未重算，未以CP MAD尺度代替。','',
'实现与统一输出：../signal_trace.py；ALL_DAILY_TRACES.json、DAILY_TRACES.csv、7份*_TRACE.json；TRANSITIONS.json；KEY_DATES.json；PREFIX_CHECKS.json；RUN_RECEIPT.json。旧first4与before_unknown_hold_fix仅保存开发历史，不作为另一条候选臂。独立审查由review目录另出收据，本件不代其宣布通过。']
(OUT/'READOUT.md').write_text('\n'.join(lines)+'\n')
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_V2_SINGLE_A_OR_B_PURE_SIGNAL_TRACE',core_code_sha256=sha(O/'signal_trace.py'),freeze_sha256=sha(O.parent/'SIGNAL_FREEZE_V2.md'),readout_sha256=sha(OUT/'READOUT.md'),daily_trace_sha256=sha(OUT/'ALL_DAILY_TRACES.json'),prefix_checks_sha256=sha(OUT/'PREFIX_CHECKS.json'),actual_original_join_sha256=sha(OUT/'ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.json'),deliverable_sha256=sha(OUT/'DELIVERABLE_SHA256.json'),stocks=7,display_rows=2103,prefix_checks=14,original_actual_entry_comparisons=28,all_original_actual_entry_expand_permissions_true=all(r['I_expand'] is True for r in entry),new_accounts=0,new_orders=0,new_quantities=0,new_cash_paths=0,new_returns=0)
save('SEAL_RECEIPT.json',seal);print(json.dumps(seal,ensure_ascii=False))
