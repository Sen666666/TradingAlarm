"""Presentation and independent static QA. Does not run an account."""
from pathlib import Path
from decimal import Decimal as D
import json,csv,hashlib,collections
O=Path(__file__).resolve().parent;Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((O/(n+'.json')).read_text())
def write(n,a):
 (O/(n+'.json')).write_text(json.dumps(a,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(a,list) and a:
  keys=list(dict.fromkeys(k for r in a for k in r))
  with (O/(n+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
   for r in a:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
S=lambda xs:sum(xs,Z)
a=read('FOUR_DAY_ACCOUNT_SUMMARY');bs=read('B_CAPITAL_BOUNDS');ts=read('B_ALL50_CORE_TARGETS');lots=read('LOT_CAPITAL_CLASSIFICATION_ASOF');rounds=read('ROUND_CLASSIFICATION_ASOF');se=read('A_ALL50_RAW_E_NORMALIZATION');req=read('ORIGINAL_CLOSE_LEGAL_REQUESTS')
for b in bs:
 b['full_legal_demand_required_transfer']=max(Z,D(b['actual_legal_lot_demand_within_T'])+D(b['cash_floor'])-D(b['cash']))
 b['cash_shortage_to_cover_T_demand']=b['full_legal_demand_required_transfer']
 b['sell_upper_is_not_recommended_sell_amount']=True
 b['no_transfer_needed_for_this_legal_demand']=b['full_legal_demand_required_transfer']==0
 b['fee_stress_budget_is_conservative_not_exact_rebalance_cost']=True
 day=b['day'];sc=b['scheme'];ll=[x for x in lots if x['day']==day];rr=[x for x in rounds if x['day']==day]
 b['unknown_held_value']=S(D(x['market_value']) for x in ll if x['unknown_reasons'])
 b['current_close_T1_locked_value']=S(D(x['market_value']) for x in ll if x['current_close_T1_sellable_qty']==0)
 b['next_OPEN_T1_unavailable_value']=S(D(x['market_value']) for x in ll if x['next_open_T1_conditional_sellable_qty']==0)
 b['mandatory_exit_locked_value']=S(D(x['market_value']) for x in ll if x['exit_priority'])
 b['actual_seed_donor_mobile_mark']=S(D(x[sc+'_mobile_mark']) for x in ll if x['kind']=='SEED')
 b['actual_ADD_donor_mobile_mark']=S(D(x[sc+'_mobile_mark']) for x in ll if x['kind']=='ADD')
 b['actual_seed_donor_net_cash']=S(D(x[sc+'_mobile_net_cash']) for x in ll if x['kind']=='SEED')
 b['actual_ADD_donor_net_cash']=S(D(x[sc+'_mobile_net_cash']) for x in ll if x['kind']=='ADD')
 b['confirmed_nonpositive_value']=S(D(x['market_value']) for x in rr if x['category']=='CONFIRMED_CURRENT_NET_NONPOSITIVE')
 b['current_winner_value']=S(D(x['market_value']) for x in rr if x['current_mainline_winner'])
 b['actual_buy_joint_upper_not_exact_fills']=True
write('B_CAPITAL_BOUNDS',bs)
checks=[]
for d in [x['day'] for x in a]:
 ar=next(x for x in a if x['day']==d);ss=[x for x in se if x['day']==d];ll=[x for x in lots if x['day']==d];rr=[x for x in rounds if x['day']==d]
 assert len(ss)==50 and len({x['sector51'] for x in ss})==50
 assert S(D(x['current_market_value']) for x in ss)==D(ar['market_value'])
 assert S(D(x['market_value']) for x in ll)==D(ar['market_value'])
 assert S(D(x['market_value']) for x in rr)==D(ar['market_value'])
 assert abs(S(D(x['raw_E_90pct_NAV_T']) for x in ss)-D(ar['NAV'])*D('.9'))<D('1e-15')
 for b in [x for x in bs if x['day']==d]:
  t=[x for x in ts if x['day']==d and x['scheme']==b['scheme']];sc=b['scheme']
  assert len(t)==50
  assert S(D(x['core_lower']) for x in t)==D(b['core_total'])
  assert S(D(x['other_fixed']) for x in t)==D(b['other_fixed_total'])
  assert S(D(x['mobile_mark']) for x in t)==D(b['all_mobile_mark'])
  assert abs(S(D(x['T_gross']) for x in t)-(D(ar['NAV'])*D('.9')-D(ar['receivable_unavailable'])))<D('1e-15')
  assert all(D(x['T_gross'])>=D(x['total_fixed_lower']) for x in t)
  assert all(D(x['legal_demand_upper'])<=D(x['legal_request_cost']) and D(x['legal_demand_upper'])<=D(x['positive_T_gap']) for x in t)
  assert all(D(x['legal_lot_demand_within_T'])<=D(x['legal_demand_upper']) for x in t)
  assert S(D(x['legal_lot_demand_within_T']) for x in t)==D(b['actual_legal_lot_demand_within_T'])
  assert all(D(x['legal_demand_upper'])==0 for x in t if x['legal_request_count']==0)
  assert D(b['all_fixed_total'])+D(b['all_mobile_mark'])==D(ar['market_value'])
  assert D(b['full_legal_demand_required_transfer'])<=D(b['target_surplus_legal_sale_net'])
  # No claimed core is synthesized from old profit or cash flow: exact remaining lot mark only.
  assert S(D(x[sc+'_core_value']) for x in ll)==D(b['core_total'])
  checks.append(dict(day=d,scheme=sc,result='PASS',target_capital_conservation=True,no_core_double_count=True,legal_request_cap=True,no_request_no_demand=True,core_equals_actual_remaining_lot_mark=True,needed_transfer_below_legal_donor_witness=True))
q=read('QA');q.pop('future_OPEN_prices_read',None);q['future_OPEN_values_used']=0;q['physical_parquet_reads']='Frozen source files were read then selected to the four CLOSE dates; no subsequent OPEN value entered any calculation.';q['independent_aggregate_checks']=checks;q['readout_correction']='UNKNOWN=0 applies to actually held source/I/CP/M3 fields. Some unheld sectors remain M UNKNOWN and are retained explicitly.'
write('QA',q)
sources=read('SOURCE_HASHES');assert all(sha(p)==h for p,h in sources.items())
f=lambda x:f'{D(str(x))/D(10000):.4f}'
lines=['# 四个事前CLOSE截面的资本诊断（静态，非新策略）','',
'仅复用M2真实账的2024-09-20、23、26、27收盘快照。没有策略重放、没有调未来收益参数、没有使用后续OPEN价格。当前1692股/50有效行业仍非PIT。',
'',
'## 可直接用于选择的结论',
'1. 单纯90%净值按E归一不能自动抓住主线。9/27会给旅游11.32%、美容7.25%、建材6.71%，软件只有3.06%。200行原式反证表保留全部50行业及M未知、M真但E零，未删除非焦点方向。',
'2. 两个待选核心定义都能保护真实lot，但仍不是主线选择器。核心一保护全部真实SEED，不称它们全是成熟赢家；核心二只把当前M真、截至当日OPEN已独立确认且当前整轮费后净清算利润正的轮，其SEED+当前最早剩余ADD列为核心。其余试仓、已确认非M、当前亏损另列。',
'3. 核心二中非赢家SEED并非全可卖：只有原规则已允许的未确认、无历史ADD/当日确认、明确非M且证据已知的试仓可供出，其余是“非核心但暂不供出”冻结资本。零ADD不补造ADD，已卖出的历史首ADD不会复活。',
'4. 9/20和9/23现金已足够覆盖全部原合法M请求，任何供出上界都不应变成卖出计划。9/26核心一现金也足够覆盖本公式允许的合法量；核心二需净供出约1.04万元。9/27两方案需要约25.00万/23.72万元净供出，不是把61.49万/44.63万元可卖上界全部卖光。',
'',
'## 四日金额，单位万元',
'日期 | 试仓资本 | 当前赢家资本 | 全部SEED | 赢家SEED | 赢家最早剩余ADD | 现金 | 10%底线',
'---|---:|---:|---:|---:|---:|---:|---:']
for r in a:lines.append(' | '.join([r['day']]+[f(r.get(k,0)) for k in ['TRIAL_UNCONFIRMED','CURRENT_MAINLINE_WINNER','all_actual_seed','winner_seed','winner_earliest_surviving_ADD','cash','cash_floor']]))
lines+=['','方案 | 日期 | 核心 | 其他冻结 | ADD可供净款上界 | 试仓SEED可供净款上界 | 现金+全部可供净款扣底线上界 | T约束合法买量全成本 | 为该买量所需净供出','---|---|---:|---:|---:|---:|---:|---:|---:']
for r in bs:lines.append(' | '.join([r['scheme'],r['day']]+[f(r[k]) for k in ['core_total','other_fixed_total','actual_ADD_donor_net_cash','actual_seed_donor_net_cash','all_mobile_sale_new_buy_upper','actual_legal_lot_demand_within_T','full_legal_demand_required_transfer']]))
lines+=['','## 9/27行业比较，单位万元','所有其他行业见B_ALL50_CORE_TARGETS.csv，50行业×4日期×2核心定义共400行。','方案 | 行业 | 原持仓 | 核心 | 其他冻结 | T参考额 | 原合法请求 | T缺口与法定量后需求','---|---|---:|---:|---:|---:|---:|---:']
for r in ts:
 if r['day']=='2024-09-27' and r['sector51'] in ['软件与IT服务','证券保险','白酒','动力电池','半导体','旅游酒店','美容护理','建筑建材']:
  lines.append(' | '.join([r['scheme'],r['sector51']]+[f(r[k]) for k in ['current_market_value','core_lower','other_fixed','T_gross','legal_request_cost','legal_lot_demand_within_T']]))
lines+=['',
'## T与现金口径',
'- J仅包括当前M=TRUE且E>0。J外不能供出的实际持仓和全部未到账应收款先扣除；四日应收余额均零。10%底线按原合同收盘规划NAV冻结，不因规划卖费降低。',
'- 对J内，每行业lower=真实核心+与核心不重叠的其他冻结持仓；解T_s=max(lower_s, lambda*E_s)，sum(T)=NAV-10%NAV-应收-集合外冻结。不是先扣核心再给核心加一次钱。J外只记录冻结持仓，不分配E目标。',
'- T_gross是忽略潜在卖费的静态参考上界；T_net_stress再扣“所有机动lot全卖”的精确卖费与5bp滑点，是保守规划压力界，不是精确换仓成本、也不要求全卖。八个截面预算均可解，没有掩盖核心超预算。',
'- 先算min(max(T-当前持仓,0),真实合法请求全成本)，再用原请求顺序、原SEED法定最小量/ADD法定量向下取整。无合法请求时需求为零，不能为纸面T卖出留现金。',
'- TARGET_SURPLUS_LOT_SALE_WITNESS只给不穿过T下界的合法可卖量见证。它不是成交计划，不应用超出真实缺口的数量；同日T+1不可卖与次日条件可卖量分别列出。所有卖款按已知CLOSE×(1−5bp)减下一交易日已知费率，真实下一OPEN只能重核、缩量或取消。',
'- UNKNOWN、无报价、来源/I/CP不明或无合法量均冻结。四截面实际持仓这些项为零，但50行业中仍有M UNKNOWN；例如9/26建材仍未知，不获目标。',
'- 原账户全部持仓、现金、core、机动层、请求和净利均对账。852个当日轮的净清算利润用截至当日成交现金流+已计权益+当日净卖款重建，最大差0。四日共1276条lot记录。',
'',
'## 文件',
'- A_ALL50_RAW_E_NORMALIZATION.csv/json：四日全行业E、M/Q/S/F、真实持仓、请求和原90%净值E归一反证。',
'- B_ALL50_CORE_TARGETS.csv/json：两核心定义下全部行业冻结/机动/T上下规划界/合法需求/供出。',
'- B_CAPITAL_BOUNDS.csv/json：八个全账户可供上下界、费用、T+1、必要供款和现金底线。',
'- ROUND_CLASSIFICATION_ASOF与LOT_CAPITAL_CLASSIFICATION_ASOF：当前赢家/试仓/非M/亏损及真实lot身份；历史首ADD与当前最早剩余ADD明确分列。',
'- ORIGINAL_CLOSE_LEGAL_REQUESTS：原合同已经生成的收盘合法请求，非新请求。',
'- QA.json、SOURCE_HASHES.json、OUTPUT_HASHES.json：独立聚合检查与源/产物封印。',
'',
'结论：这些仅是选择候选前的资金约束诊断，不能称账户可达路径或收益验证。尤其9/27半导体在有核心约束的E式里仍只获约1.66万—1.79万元法定买量，而美容约5.42万元；是否符合“抓主线”的目标仍需明确裁决，不能据此默认实施T。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
write('OUTPUT_HASHES',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps({'result':'PASS','aggregate_checks':len(checks),'source_files_unchanged':len(sources),'report':str(O/'READOUT.md')},ensure_ascii=False))
