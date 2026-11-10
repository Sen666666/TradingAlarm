"""Descriptive saved-path check only; no new strategy, replay, history, network or thresholds."""
from pathlib import Path
from collections import defaultdict
import json,csv,hashlib,sys
sys.dont_write_bytecode=True
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
OUT=ROOT/'mainline_event_leader_evidence_v1'
PARSER=ROOT/'mainline_winner_funding_design_v1/inspect_saved_paths.py'
ns={}
# Inspected prefix: loads sealed files and defines pure helpers. Output/case statements excluded.
exec(compile(PARSER.read_text().split('\ncases=')[0],str(PARSER)+'#definitions_only','exec'),ns)
D=ns['D'];Z=ns['Z'];sha=ns['sha'];checked=ns['checked'];inputs=ns['inputs']
inputs[str(PARSER)]=sha(PARSER)
B=ns['B']
def load(n):
 p=B/(n+'.json');checked(p,ns['hashes'][n+'.json']);return json.loads(p.read_text())
eventlog=load('EVENT_LOG'); registry=load('EVENT_REGISTRY')
seedrisk=load('SEED_FLOOR_RISK');addrisk=load('ADD_FLOOR_RISK')
for p in [ROOT/'joint51_candidate_v9_facts/engine.py',ROOT/'mainline_candidate_v3_core_reference/engine.py',ROOT/'mainline_candidate_v4_known_sector_fix_v2/engine.py']:
 checked(p,ns['sources'][str(p)])
gpath=checked(ROOT/'mainline_daily_industry_evidence_v1/DAILY_EVIDENCE.json')
grows=json.loads(gpath.read_text())
cases=[('2024-09-20','证券保险'),('2024-09-23','证券保险'),('2024-09-23','房地产开发'),('2024-09-23','汽车整车'),('2024-09-24','软件与IT服务'),('2024-10-23','光伏风电设备'),('2024-12-04','自动化与机器人'),('2024-12-10','自动化与机器人'),('2024-11-07','证券保险'),('2024-11-07','医疗服务'),('2024-11-12','医疗服务'),('2024-12-02','游戏传媒'),('2024-12-10','游戏传媒')]
orders=ns['orders'];caps=ns['caps'];holds=ns['holds'];info=ns['info'];cp=ns['cp'];data=ns['data']
seeds={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
holdmap={(x['day'],x['lot_id']):x for x in holds}
lots=[];summary=[];roster=[];timing=[]
KEEP=['sid','name','round_id','lot_id','kind','capital_role','qty','bought','M','stock_state','sector_state','unknown','locked','round_liquidation_net_CLOSE','confirmed_history','verified_postseed_CP','current_i_target','current_CP_receipt_type','effective_protection_signal','original_lot_CP','raw_CLOSE','adjusted_CLOSE','unbroken_CLOSE']
for day,sector in cases:
 es=[x for x in eventlog if x['day']==day and x.get('sector51')==sector and x['event']=='CLOSE_EVENT_STATUS'];assert len(es)==1
 event=es[0];eid=event['event_id'];assert eid in registry and event['birth_day']==registry[eid]['birth_day']
 cs=[c for c in caps if c['day']==day and c['sector51']==sector]
 hs=[h for h in holds if h['day']==day and h['sector51']==sector]
 assert {x['lot_id'] for x in cs}=={x['lot_id'] for x in hs}
 case_rows=[]
 for c in cs:
  rid=c['round_id'];seed=seeds[rid];h=holdmap[(day,c['lot_id'])]
  assert seed['day']<=day and seed['event_id'] in registry and seed['sector51']==sector
  evt=[x for x in eventlog if x.get('sid')==seed['sid'] and x['day']==seed['day'] and x['event_id']==seed['event_id'] and x['event'] in ['ACTUAL_SEED_CAPITAL_CONSUMED','MATURE_SEED_NO_EVENT_DEBIT'] and x.get('qty')==seed['qty'] and D(x['actual_cost'])==D(seed['all_in_cost'])]
  assert len(evt)==1
  full=ns['snapshot_lot'](c,day,day)
  r={k:full[k] for k in KEEP}
  raw,cpf,facts=ns['frames'](c['sid']);z=raw.loc[day]
  source_known=all(ns['finite'](z[k]) and D(str(z[k]))>0 for k in ['raw_close','adjustment_factor'])
  assert D(h['factor'])==D(str(z['adjustment_factor'])) and D(h['raw_mark'])==D(str(z['raw_close']))
  cp_known=isinstance(cpf.loc[day,'receipt'],(bool,ns['np'].bool_))
  # M and stock M3 are annotations only, never structural predicates.
  intact=bool(source_known and full['current_i_target']==1 and cp_known and not c['locked'] and h['locked_exit'] is None and full['unbroken_CLOSE'])
  confirmed=bool(full['verified_postseed_CP'])
  healthy=bool(intact and confirmed and full['round_liquidation_net_CLOSE']>0)
  same=seed['event_id']==eid
  initial=bool(same and seed['allocation_phase'] in ['EVENT','RESIDUAL'] and seed['capital_role']=='INITIAL')
  prior_orders=[x for x in orders if x['round_id']==rid and x['day']<=day]
  round_hs=[x for x in hs if x['round_id']==rid]
  q=sum(x['qty'] for x in round_hs)
  assert q==sum(x['qty'] if x['side'].startswith('BUY') else -x['qty'] for x in prior_orders)
  div=ns['sm']([x for x in data['EQUITY_EVENTS'] if x.get('round_id')==rid and x['day']<=day and D(x.get('receivable_delta',0))>0],'receivable_delta')
  for p in full['verified_postseed_CP']:
   op=[x for x in info if x['round_id']==rid and x['day']==p['confirmation_OPEN'] and x.get('cp_id')==p['cp_id'] and x['decision']=='INFORMATION_CONFIRMED']
   assert len(op)==1
   closeproof=[x for x in info if x['round_id']==rid and x.get('proof_id')==op[0]['proof_id'] and x['phase']=='CLOSE']
   assert len(closeproof)==1 and p['receipt_CLOSE']<=closeproof[0]['day']<op[0]['day']<=day
   p.update(information_CLOSE_pass=closeproof[0]['day'],proof_id=op[0]['proof_id'],actual_add_count_at_confirmation=op[0]['actual_add_count'])
  buys=[x for x in prior_orders if x['side']=='BUY_ADD']
  r.update(close_day=day,sector51=sector,active_event_id=eid,seed_event_id=seed['event_id'],seed_event_mapping='BUY_SEED explicit event_id + exact same sid/day/qty/cost EVENT_LOG + EVENT_REGISTRY birth',seed_order_seq=seed['order_seq'],original_seed_signal_day=seed['signal_day'],actual_seed_OPEN=seed['day'],seed_phase=seed['allocation_phase'],seed_capital_role=seed['capital_role'],same_event=same,A_initial_round=initial,B_same_event=same,C_other_event=not same,A_original_seed_lot=bool(initial and c['kind']=='SEED'),current_lot_locked_exit=h['locked_exit'],current_I_floor_fact=str(facts.loc[day,'i_floor']),current_CP_receipt=bool(cpf.loc[day,'receipt']) if cp_known else None,current_CP_candidate=str(cpf.loc[day,'candidate']),structurally_unbroken_current_lot=intact,descriptive_positive_confirmed_unbroken=healthy,round_qty_at_CLOSE=q,round_cashflow_to_CLOSE=ns['sm'](prior_orders,'cash_delta'),round_dividend_entitlement_to_CLOSE=div,liquidation_model='whole round cashflow + accrued net80 entitlement + current qty * raw_CLOSE * 0.9995 - dated sell fee',current_sell_fee=ns['fee'](seed['sid'],day,q,D(str(z['raw_close']))*D('.9995'),'sell'),actual_ADD_orders_to_CLOSE=[x['order_seq'] for x in buys],actual_ADD_count_to_CLOSE=len(buys),current_protection_source='Saved HOLDINGS protection_signal: SEED is current round I floor; ADD is recorded layer protection. Source-of-every-ratchet reconstruction not completed.',seed_open_known_protection=[x['known_protection'] for x in seedrisk if x['round_id']==rid],add_open_known_protection=[x for x in addrisk if x['round_id']==rid and x['day']<=day],raw_source_kind=str(z.get('source_kind')),raw_source_path=str(z.get('source_path')),raw_segment_id=str(z.get('segment_id')),factor_bridge_rows_to_CLOSE=[x for x in data['EQUITY_EVENTS'] if x['sid']==seed['sid'] and seed['day']<=x['day']<=day and x['event']=='FACTOR_BRIDGE'])
  lots.append(r);case_rows.append(r)
 for group,rs in [('A_INITIAL_EVENT_RESIDUAL_ROUNDS',[r for r in case_rows if r['A_initial_round']]),('A_ORIGINAL_SEED_LOTS_ONLY',[r for r in case_rows if r['A_original_seed_lot']]),('B_ALL_SAME_EVENT_HOLDINGS',[r for r in case_rows if r['B_same_event']]),('C_OTHER_EVENT_TRANSPARENT_CONTROL',[r for r in case_rows if r['C_other_event']])]:
  ids={r['round_id'] for r in rs}
  def count(pred):return len({r['round_id'] for r in rs if pred(r)})
  qual={r['round_id']:r for r in rs if r['descriptive_positive_confirmed_unbroken']}
  gg=[x for x in grows if x['close_day']==day and x['sector51']==sector and x['event_id']==eid and x['cohort']=='ALL_FIXED']
  summary.append(dict(close_day=day,sector51=sector,event_id=eid,group=group,held_rounds=len(ids),held_lots=len(rs),positive_rounds=count(lambda r:r['round_liquidation_net_CLOSE']>0),postseed_confirmed_rounds=count(lambda r:bool(r['verified_postseed_CP'])),structurally_unbroken_rounds=count(lambda r:r['structurally_unbroken_current_lot']),positive_unbroken_rounds_without_confirmation_requirement=count(lambda r:r['round_liquidation_net_CLOSE']>0 and r['structurally_unbroken_current_lot']),positive_confirmed_unbroken_rounds=len(qual),positive_confirmed_unbroken_lots=sum(r['descriptive_positive_confirmed_unbroken'] for r in rs),qualified_names=[r['name'] for r in qual.values()],qualified_sids=[r['sid'] for r in qual.values()],qualified_round_current_net={r['sid']:r['round_liquidation_net_CLOSE'] for r in qual.values()},observed_G=gg[0]['G'] if len(gg)==1 else None))
 # Original event seeds, including already sold out, make a zero-held result auditable.
 for rid,seed in seeds.items():
  if seed['event_id']!=eid or seed['day']>day:continue
  os=[x for x in orders if x['round_id']==rid and x['day']<=day]
  held=any(r['round_id']==rid for r in case_rows)
  ps=[x for x in info if x['round_id']==rid and x['day']<=day and x['phase']=='OPEN' and x['decision']=='INFORMATION_CONFIRMED']
  roster.append(dict(close_day=day,sector51=sector,event_id=eid,round_id=rid,sid=seed['sid'],name=seed['name'],seed_phase=seed['allocation_phase'],seed_role=seed['capital_role'],seed_OPEN=seed['day'],currently_held=held,postseed_confirmation_OPENs_available=[x['day'] for x in ps],orders_to_CLOSE=[dict(day=x['day'],side=x['side'],qty=x['qty'],reason=x['reason'],order_seq=x['order_seq']) for x in os]))
  if seed['capital_role']=='INITIAL' and seed['allocation_phase'] in ['EVENT','RESIDUAL']:
   allp=[x for x in info if x['round_id']==rid and x['phase']=='OPEN' and x['decision']=='INFORMATION_CONFIRMED']
   allc=[x for x in cp if x['round_id']==rid and x['event']=='CREATED_AFTER_SEED']
   timing.append(dict(decision_CLOSE=day,sector51=sector,event_id=eid,sid=seed['sid'],name=seed['name'],round_id=rid,seed_OPEN=seed['day'],first_postseed_receipt_CLOSE=min((x['day'] for x in allc),default=None),first_INFORMATION_CONFIRMED_OPEN=min((x['day'] for x in allp),default=None),available_at_decision=bool(ps),scope='TIMING_AUDIT_ONLY: dates after decision excluded from all counts; no future ADD or PnL used'))
def write(name,obj):
 (OUT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(obj,list) and obj:
  with (OUT/(name+'.csv')).open('w',newline='') as f:
   fields=list(dict.fromkeys(k for r in obj for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for r in obj:w.writerow({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list)) else v for k,v in r.items()})
write('CLOSE_SUMMARY',summary);write('ALL_HELD_LOTS',lots);write('EVENT_SEED_ROSTER',roster);write('CONFIRMATION_TIMING_AUDIT',timing)
qa=dict(cases=len(cases),lot_observations=len(lots),round_observations=len({(r['close_day'],r['sector51'],r['round_id']) for r in lots}),all_selected_sector_holdings_enumerated=True,all_seed_event_ids_explicit_and_registry_log_verified=True,all_profit_reconciled_to_original_CAPITAL_LOTS_round_net=True,all_current_qty_reconciled_to_saved_orders=True,all_information_proofs_postseed_receipt_and_CLOSE_pass_and_real_OPEN_verified=True,no_future_OPEN_used_at_prior_CLOSE=True,no_future_ADD_or_final_PnL_in_descriptive_counts=True,no_M_or_stock_M3_requirement=True,no_profit_coverage_requirement=True,no_strategy_import=True,no_strategy_replay=True,no_history=True,no_network=True,no_new_rule=True,all_C_other_event_counts_zero=True,current_protection_checked='saved HOLDINGS signal plus raw factor/mark, I_target, CP knownness and exit locks; not a new protection rule',not_completed=['Per-ratchet independent reconstruction of every current I/CP floor origin','Independent fee schedule reimplementation: dated fee helper reused and net exactly reconciled','Independent independent-source corporate-action review: original sealed bridge rows retained; no new external verification'],limits=['Selected 13 decision CLOSEs only, not exhaustive signal or failure sample','Same industry taxonomy from original research is not point-in-time','Current profitable/confirmed/unbroken is descriptive, not proof of future returns','A uses original INITIAL EVENT/RESIDUAL rounds; stricter original-SEED-lot-only count separately available'])
assert all(r['positive_confirmed_unbroken_rounds']==0 for r in summary if r['group'].startswith('C_'))
for p,h in inputs.items():assert sha(p)==h,('INPUT_CHANGED',p)
write('QA',qa);write('SOURCE_HASHES',inputs)
lines=['# 同事件先行持仓事实核验（收尾版）','','只读原M7路径，13个指定CLOSE，未新建规则、未重跑策略、未联网。','',
'## 结论','',
'- 不支持“924前证券/地产已有真实post-SEED确认先行仓”的假设。证券9/20、9/23及地产9/23，全部同event实际持仓的真实确认数均为0。',
'- 中国人寿、华创云信：最早post-SEED receipt为9/24 CLOSE，真实确认是9/25 OPEN。滨江集团、中国国贸同为9/24→9/25；招商蛇口为9/26→9/27。均不能提前给9/23 CLOSE使用。',
'- 机器人12/4也没有这类证明；但不能以此与924作有效区分，因为924前同样没有。',
'- 机器人12/10：原INITIAL均普智能满足；全同event再加MATURE入场的雷赛智能。医疗11/12原INITIAL三博脑科也满足，保留为反例，不把确认等同于主线成功。',
'- 证券11/7无实际持仓：该event三笔INITIAL已于11/6因CURRENT_NON_MAINLINE_SEED_RETIREMENT退出，不能把不在场仓位当晚的先行证明。',
'- C其他旧event在全部13个截面均为0。所有归属由原BUY_SEED event_id、event log与registry核对，没有按日期推断。','',
'## 简表','',
'日期 | 行业 | A持有轮数 | A净利正且结构未破（未要求确认） | A真实确认且净利正/结构未破 | B同event轮数 | B三项同时满足','---|---|---:|---:|---:|---:|---:']
for d,s in cases:
 a=next(x for x in summary if x['close_day']==d and x['sector51']==s and x['group']=='A_INITIAL_EVENT_RESIDUAL_ROUNDS');b=next(x for x in summary if x['close_day']==d and x['sector51']==s and x['group']=='B_ALL_SAME_EVENT_HOLDINGS')
 lines.append(f"{d} | {s} | {a['held_rounds']} | {a['positive_unbroken_rounds_without_confirmation_requirement']} | {a['positive_confirmed_unbroken_rounds']} | {b['held_rounds']} | {b['positive_confirmed_unbroken_rounds']}")
lines+=['','## 已核与未完成','',
'已核：全部指定行业持仓（不是donor子集）；原SEED角色/阶段/实际OPEN/event_id；post-SEED receipt→information CLOSE pass→真实确认OPEN链；整轮净清算利逐lot对原CAPITAL_LOTS核等；数量逐轮对原订单核等；当前原HOLDINGS保护阈值与价格/因子、I/CP状态、退出锁；读入源SHA256并结束前复核不变。','',
'未完成：每次I/CP保护抬升来源的独立逐日重建；费率函数独立另写一套复验；公司行动桥原始公告重新复核。沿用原封存费用和桥逻辑，并保留原来源、保护值、费用分解与桥行。','',
'局限：只有指定截面，行业分类不是PIT。净利>0仅描述，不要求覆盖后续风险或本金。M/stock state只列注释，不当结构替代条件。未用后来ADD或最终利润选股票。CONFIRMATION_TIMING_AUDIT里决策日之后的日期只解释时间差，不进入当晚计数。','',
'## 文件','',
'- CLOSE_SUMMARY：A原INITIAL轮、A原SEED lot、B全部同event、C旧event的完整分组计数。','- ALL_HELD_LOTS：全部实际持仓、证明链、净清算/费用/保护及来源字段。','- EVENT_SEED_ROSTER：该event已买过的各轮，截至CLOSE的订单与是否仍持仓。','- CONFIRMATION_TIMING_AUDIT：只作时点核对的首次receipt/确认。','- QA、SOURCE_HASHES：核实范围、未完成项和原来源哈希。','']
(OUT/'READOUT.md').write_text('\n'.join(lines))
write('OUTPUT_SEAL',{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'})
print(json.dumps(qa,ensure_ascii=False))
print('\n'.join(lines[13:32]))
