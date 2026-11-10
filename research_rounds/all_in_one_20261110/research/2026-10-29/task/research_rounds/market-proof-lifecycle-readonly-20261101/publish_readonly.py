"""Publish bounded evidence from existing export and books; no signal/model run."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
def read(n):return json.loads((O/n).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def num(x):return D(str(x))
def fmt(x,n=2):return 'NA' if x is None else f'{float(x):,.{n}f}'
records=read('CHECKPOINT_LIFECYCLE.json');phase=read('PHASE_SUMMARY.json');spec=read('FIXED_CASES_BEFORE_COMPONENT_EXPORT.json');src=read('SOURCE_SHA256.json')
# Old cached sector components must reproduce the exact old recovery breadth.
old=read('OLD407_CACHED_INDUSTRY_BREADTH.json');group=defaultdict(list)
for x in old:
 if x['breadth'] is not None:group[x['day']].append(x['breadth'])
errors=[]
for r in records:
 if r['domain']=='OLD407':
  expected=sum(group[r['day']])/len(group[r['day']]);difference=expected-r['market']['breadth'];assert abs(difference)<1e-12;errors.append(abs(difference))
save('OLD_CACHED_COMPONENT_GATE.json',dict(passed=True,stock_pool=407,industries=11,max_abs_csv_roundtrip_difference=max(errors),reused_cached_signed_m=True,old_fast_on='original .4/.6 hysteresis latch, retained only as observed field; BREAK still breadth>.6',native_fast_on='direct original breadth>.6'))
# Full fixed identities remain visible, including absent/not-yet-prepared stocks.
SM={x['symbol']:x for x in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};meta=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text());fixed=Counter(meta[s]['sector_id'] for s in SM)
stock=read('STOCK_M_SELECTED.json');industry=read('INDUSTRY_M_BREADTH_SELECTED.json');coverage=[]
for d in sorted({x['day'] for x in stock}):
 ss=[x for x in stock if x['day']==d];values=[x['m_signed_EWM21'] for x in ss];ii=[x for x in industry if x['day']==d]
 assert len(ss)==1709 and len({x['sid'] for x in ss})==1709
 coverage.append(dict(day=d,fixed_stock_identities=1709,ready_signed_m=sum(x is not None for x in values),unknown=sum(x is None for x in values),positive=sum(x is not None and x>0 for x in values),negative=sum(x is not None and x<0 for x in values),zero=sum(x==0 for x in values if x is not None),
  industry_roster_identities=len(ii),industries_meeting_original_min5=sum(x['breadth'] is not None for x in ii),
  industry_denominators=[dict(sector=x['sector'],fixed_stock_identities=fixed[x['sector']],original_function_nonempty_source_roster=x['identities'],ready=x['ready'],positive=x['positive'],negative=x['negative'],zero=x['zero'],breadth=x['breadth']) for x in ii]))
save('READY_COVERAGE_AT_FIXED_POINTS.json',coverage)
# Did the original system merely keep the same weak layers, or recycle risk?
cohorts=[];cache={}
def price(sid,d):
 if sid not in cache:cache[sid]=pd.read_parquet(SM[sid]['refs']['facts'],columns=['raw_close'])
 f=cache[sid];i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0
 return num(f.iloc[i].raw_close)
for s in spec:
 if s['name'] not in ['BDIAG2022','BDIAG2023']:continue
 p=Path(s['path']);daily=rows(p/'daily.jsonl.gz');dd={x['at'][:10]:x for x in daily};give=s['giveback10']['at'][:10];pause=s['pause']['at'][:10];initial={x['id'] for x in dd[give]['layers']};after={x['id'] for x in dd[pause]['layers']};parts=defaultdict(lambda:Z);roles=defaultdict(lambda:Z)
 for x in dd[pause]['layers']:
  v=D(x['qty'])*price(x['sid'],pause);kind='held_at_first10_and_still_live' if x['id'] in initial else 'new_actual_fill_after_first10';parts[kind]+=v;roles[kind+'|'+x['role']+'|'+x['pool']]+=v
 assert abs(sum(parts.values(),Z)-num(dd[pause]['inventory']))<D('.00001')
 cohorts.append(dict(case=s['name'],first10=give,ACT_pause=pause,first10_live_layers=len(initial),first10_layers_absent_by_pause=len(initial-after),first10_layers_still_live=len(initial&after),pause_inventory=dd[pause]['inventory'],marked_capital_by_actual_fill_cohort=dict(parts),by_role_pool=dict(roles),
  does_not_imply_new_layers_were_bad_at_entry=True,no_counterfactual_PnL=True))
save('LIVE_CAPITAL_COHORTS_AFTER_GIVEBACK10.json',cohorts)
verified={p:h for p,h in src.items() if p.endswith('/B.json.gz') or p.endswith('/daily.jsonl.gz') or p.endswith('/I__S0_base.json')}
for p,h in verified.items():assert sha(p)==h
lines=['原BREAK：启动→持续有效→撤销→重入｜固定案例只读核查',
'未改策略/阈值/预算/退出，无账户回放。仅复用旧407缓存，并从原compute_recovery导出当前1709的原signed-m及行业分项。',
'm_signed=EWMA21(logret*min(1,sqrt(amount/此前21金额中位数)))，不是涨跌家数、净资金流、成交额份额或CP1/PVR量能乘子。行业广度=ready股票m>0占比，至少5股；整体等权行业且至少8行业。',
'BREAK=原等行业价格超过此前63高点＋当日价格上升＋breadth>.6。它是恢复事件，不是每天必须为真的持续资格。advance的on分支只看账户phaseDD，breadth/fast/BREAK减弱不撤on；个股原I/CP1退出照常。',
'旧924 fast_on来自原.4/.6锁存，现1709 fast_on为breadth>.6，两者只当原字段描述，未统一成新规则。',
'源/覆盖门：原函数只把return z改为return z,mom,sector_b；15固定日期整体market/prior63逐值同，breadth最大差5.55e-17，BREAK exact；3工程股物理前缀同。原1709身份全保留，至最大检查点1687有源/22无源；逐日ready与行业有效分母另表，22不等于某一年不可投总数。旧407/11缓存也复原原广度，未知不填0。',
'导出原组件加载12.66秒、原函数计算及选点导出/前缀核对3.34秒；首轮含全部病例读取36.13秒。分析输出修正复用组件缓存，未重算账户。',
'', '一、原Bdiag的两个失败回吐阶段，不是恢复时立刻错误',
'case｜恢复｜阶段峰值(较恢复)｜首次运行峰值回吐10%｜ACT暂停→实际全清｜全清较恢复']
for x in phase:
 if x['domain']=='NATIVE1709':lines.append(f"{x['case']}｜{x['resume']}｜{x['actual_phase_peak']} +{fmt(x['peak_return_from_resume_pct'])}%｜{x['first_running_giveback10']}｜{x['pause']}→{x['first_actual_flat']}｜{fmt(x['flat_return_from_resume_pct'])}%")
lines+=['10%只是预声明的后视镜检查点，非候选止损；resume日志的episode_drawdown仍带旧phase值，恢复日按新peak=恢复NAV解释为0，不误认成当日已回吐10%。',
'日期｜整体breadth｜持仓m正市值占比｜持有行业广度市值加权｜原G1暖市值占比｜实际曝险']
for r in records:
 if r['case'] in ['BDIAG2022','BDIAG2023'] and any(x in r['labels'] for x in ['actual_full_phase_peak','first_running_phase_giveback10','ACT_pause']):
  v=float(r['held_capital']);pct=lambda k:float(r[k])/v*100 if v else None;lines.append(f"{r['day']}｜{fmt(r['market']['breadth']*100)}%｜{fmt(pct('stock_m_positive_capital'))}%｜{fmt(float(r['industry_breadth_capital_weighted'])*100) if r['industry_breadth_capital_weighted'] is not None else 'NA'}%｜{fmt(pct('original_G1_warm_capital'))}%｜{fmt(r['exposure_pct'])}%")
for x in phase:
 if x['domain']=='NATIVE1709':lines.append(f"{x['case']}：first10以后仍有实际新买现金{fmt(float(x['after_first10_actual_buy_cash'])/1e4)}万元；全phase按原信号收盘fast=False的真实买款{fmt(float(x['buy_cash_signal_fast_false'])/1e4)}万元。均为累计周转，非额外同时仓位，也不是这些买入的可避免损失。")
for x in cohorts:
 new=float(x['marked_capital_by_actual_fill_cohort'].get('new_actual_fill_after_first10',0));total=float(x['pause_inventory']);lines.append(f"{x['case']}：first10时{x['first10_live_layers']}层，到ACT暂停{x['first10_layers_absent_by_pause']}层已不在真实持仓；暂停市值中{new/total*100:.2f}%来自first10后的新fill。不能把全部回吐归成一直不卖同一批旧仓。")
lines+=['2022的首次fast=False在7/6，阶段新高却在8/18；2023首次fast=False在2/16，阶段新高却在5/4。它们否定“第一次整体转弱就必然结束”的解释，不提供更早卖出可获利的反事实。',
'', '二、924旧版是快且大投入的正控制，不是当前PVR_SLOT1',
'旧407科技/11行业，RS和旧PVR都9/27 BREAK恢复，9/30六笔实买；日末曝险90.37%/89.13%。9/24广度78.73%、9/27为99.42%，没有强制等待五个新高日。',
'10/11已达到首次10%运行回吐，但breadth仍97.28%，两账户持仓m正市值均100%。这个账户回撤不是已观测市场证据普遍失败。',
'11/18广度32.25%，旧RS持仓m正市值0%、旧PVR36.8%；之后真实退出/新入路径仍恢复，12/26两账户再到2024窗口新高。故连“宏观和持仓都弱一次便永久撤销”也不能从失败年份直接推出。',
'截至12/31，相对9/27恢复NAV，旧RS+46.98%、旧PVR+18.49%。这不是6/30当前策略收益，也不证明单独持住11/18的每只股票会赚钱。',
'旧阶段完整峰/退在窗口外，作为既有后续context单列，不当924单次行情收益：']
for x in phase:
 if x['domain']=='OLD407':lines.append(f"{x['case']} full phase峰{x['actual_phase_peak']}（较恢复+{fmt(x['peak_return_from_resume_pct'])}%），ACT暂停{x['pause']}，实际flat{x['first_actual_flat']}；不是当前1709/90路径或新运行。")
lines+=['首次10%旧924发生在2024/10/11，早于后来的full-phase峰；没有把未来最终峰倒填为当时已知。',
'', '三、2026局部主题：宏观弱，不等于该主题弱',
'日期｜整体breadth｜半导体m正/ready及广度｜电子化学品m正/ready及广度｜组合持仓m正市值']
ind=read('INDUSTRY_M_BREADTH_SELECTED.json')
for d in ['2026-04-30','2026-05-07','2026-06-30']:
 r=next(r for r in records if r['case']=='PVR_SLOT1_2026_LOCAL' and r['day']==d);a=next(x for x in ind if x['day']==d and x['sector']=='URFI881121');b=next(x for x in ind if x['day']==d and x['sector']=='URFI881172');lines.append(f"{d}｜{fmt(r['market']['breadth']*100)}%｜{a['positive']}/{a['ready']}={fmt(a['breadth']*100)}%｜{b['positive']}/{b['ready']}={fmt(b['breadth']*100)}%｜{float(r['stock_m_positive_capital'])/float(r['held_capital'])*100:.2f}%")
lines+=['固定半导体身份126、电子化学品26；原函数有非空源的roster分别120/25，ready分母114..115/24，不将IPO/未知当负方向。当前半导体实际4/30、5/7均零持仓，6/30仅4.01%，已通过独审的前包说明是证据→合法尺寸/共享池/迁池→资金承接多处断点。',
'全市场一刀切risk-off会与这些局部强度冲突；单纯多加时间证明也不会释放被占预算。当前两池10/60、行业2/10/20仍是研究选择，不是用户偏好。',
'', '唯一待证的因果假说（不是新交易规则）',
'原BREAK完成了风险许可的CREATION，却把continued validity/withdrawal主要委托给个股原保护与账户20%phaseDD。资金因此可在旧信号退出后继续被新局部信号反复装满，直到累计回吐触发账户暂停；这和旧仓完全不退出不同。',
'下一设计问题是：许可的市场/行业域、持续证据、撤销及新凭据重开应明确分开；撤销新增扩张与实际旧仓退出也应分开，资金必须仍有真实可达容量。当前不规定何种弱度/持续多久就撤，不用.4/21低点等新增门，也不把宏观失败等同局部主题失败。',
'最强失败控制：2023峰值整体breadth仅43.53%，持仓m正却95.9%；924的首次10%回吐breadth还97.28%，且11月弱化后仍有真实恢复。若候选把这些直接全退/长期锁死，它不能仅凭2022少亏通过。',
'预金融验收：先用固定快宽正例、回吐负例、局部主题与失败试仓检查同一因果时钟/续证-撤销-重开身份、真实角色保护与资源守恒；它们能否区分目前证据未知，不据此宣称已找到有效撤销指标。无新指标/政策收益路径获授权。',
'', '限制：价格/行业/股池为当时冻结的当前快照回看，非PIT；日线最终OHLCV执行代理、未知权息时点限制不变；当前PVR_SLOT1 Jul--Oct仍未经济验证。旧full-phase2026 context不填补该缺口。38→37检查点的分析修正去除了未预注册local-May14点（其组件未导出），旧输出留档；原m组件不重算、金融账不变。']
(O/'CORE_READOUT.txt').write_text('\n'.join(lines)+'\n')
save('AUDIT_READINESS.json',dict(analysis_only=True,new_account_replays=0,new_thresholds=0,new_policy_or_indicator_formula=False,original_m_return_only_export=True,original_m_global_prefix_gate='ORIGINAL_M_EXPORT_GATE.json',old_cached_components_gate='OLD_CACHED_COMPONENT_GATE.json',fixed_cases=5,checkpoints=37,
 original_financial_objects_unchanged=verified,capital_cohort_scope='only actual lots at fixed first10 and ACT pause; no counterfactual PnL',analysis_error_history='analysis-v0-extra-local-point',
 primary='CORE_READOUT.txt',hypothesis='risk permission creation does not specify continued market validity/withdrawal; resource recycling can maintain exposure; no simple macro exit established'))
save('ARTIFACT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
print('PACKET_READY',sha(O/'CORE_READOUT.txt'),'nativecohorts',json.dumps(cohorts,default=str))
