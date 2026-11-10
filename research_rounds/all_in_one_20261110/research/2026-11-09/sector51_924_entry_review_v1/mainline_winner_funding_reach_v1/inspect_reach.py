"""Read sealed artifacts only. No strategy imports, history, candidates, internet, or source modifications."""
from pathlib import Path
import json, csv, hashlib, sys
from collections import defaultdict, Counter
from decimal import Decimal as D
sys.dont_write_bytecode=True
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
PARSER=ROOT/'mainline_winner_funding_design_v1/inspect_saved_paths.py'
# Execute only sealed research parser setup and pure helper definitions, before all case/output statements.
ns={}
exec(compile(PARSER.read_text().split('\ncases=')[0],str(PARSER)+'#definitions_only','exec'),ns)
for k in ['B','A','orders','caps','holds','info','cp','trans','data','rounds','roundmap','fee','frames','checked','inputs','is_true','sm','Z','np','sha']:
 globals()[k]=ns[k]
OUT=ROOT/'mainline_winner_funding_reach_v1'
inputs[str(PARSER)]=sha(PARSER)
for name in ['DESIGN.md','READOUT.md','PV_1108_LOT_CHECKS.json','STARTUP_0925_CONFIRMED_DONORS.json']:
 checked(PARSER.parent/name)
for p in [ROOT/'joint51_candidate_v9_facts/engine.py',ROOT/'mainline_candidate_v3_core_reference/engine.py',ROOT/'mainline_candidate_v4_known_sector_fix_v2/engine.py']:
 checked(p,ns['sources'][str(p)])
def write(name,rows):
 (OUT/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(rows,list) and rows:
  fields=list(dict.fromkeys(k for r in rows for k in r))
  with (OUT/(name+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(list,dict)) else v for k,v in r.items()})
ledger=data['DAY_LEDGER'];days=[x['day'] for x in ledger];prev={d:days[i-1] for i,d in enumerate(days) if i};led={x['day']:x for x in ledger}
capmap={(x['day'],x['lot_id']):x for x in caps};holdmap={(x['day'],x['lot_id']):x for x in holds}
ordersday=defaultdict(list);ordersround=defaultdict(list);roundhold=defaultdict(list);infobyround=defaultdict(list);cpbyid={};equitybyround=defaultdict(list)
for x in orders:ordersday[x['day']].append(x);ordersround[x['round_id']].append(x)
for x in holds:roundhold[(x['day'],x['round_id'])].append(x)
for x in info:infobyround[x['round_id']].append(x)
for x in cp:
 if x['event']=='CREATED_AFTER_SEED':cpbyid[(x['round_id'],x['cp_id'])]=x
for x in data['EQUITY_EVENTS']:
 if x.get('round_id'):equitybyround[x['round_id']].append(x)
planmap={(x['day'],x['event']):x for x in trans if x['event'] in ['TRANSFER_CASH','DEMAND_PLAN','RECEIVER_FUNDING']}
def prove(rid,asof,cpf):
 out=[]
 for p in infobyround[rid]:
  if p['day']>asof or p['phase']!='OPEN' or p['decision']!='INFORMATION_CONFIRMED' or not is_true(p['confirmed_history']):continue
  cr=cpbyid[(rid,p['cp_id'])];f=cpf.loc[cr['day']]
  assert is_true(f['receipt']) and D(str(f['candidate']))==D(cr['candidate'])
  assert roundmap[rid]['actual_seed_OPEN']<=cr['day']<p['day']<=asof
  out.append(dict(cp_id=p['cp_id'],receipt_CLOSE=cr['day'],confirmation_OPEN=p['day'],floor=cr['candidate']))
 return out
def inspect(o):
 op=o['day'];close=prev[op];rid=o['round_id'];lid=o['lots'][0];c=capmap[(close,lid)];h=holdmap[(close,lid)]
 # Exact copied design helper retains its CLOSE and no-same-day-accrual OPEN columns for comparison.
 row=ns['snapshot_lot'](c,close,op)
 raw,cpf,facts=frames(o['sid']);rc=raw.loc[close];ro=raw.loc[op]
 prior=[x for x in ordersround[rid] if x['order_seq']<o['order_seq']]
 sameopen=[x for x in prior if x['day']==op]
 assert all(x['side'].startswith('SELL') for x in sameopen), 'BUY_BEFORE_DONOR_UNEXPECTED'
 qclose=sum(x['qty'] for x in roundhold[(close,rid)])
 qopen=qclose-sum(x['qty'] for x in sameopen)
 cash=sm(prior,'cash_delta')
 div=sum((D(x['receivable_delta']) for x in equitybyround[rid] if x['day']<=op and D(x.get('receivable_delta',0))>0),Z)
 p=D(str(ro['raw_open']))*D('.9995')
 exactopen=cash+div+qopen*p-fee(o['sid'],op,qopen,p,'sell')
 # Primary proposal snapshot: all mandatory exits/accrual/info_open completed, before ANY optional financing.
 mandatory=[x for x in ordersround[rid] if x['day']==op and x['side'].startswith('SELL') and not x.get('transfer_rank')]
 assert all(x['order_seq']<o['order_seq'] for x in mandatory)
 commonq=qclose-sum(x['qty'] for x in mandatory)
 commoncash=sm([x for x in ordersround[rid] if x['day']<=close],'cash_delta')+sm(mandatory,'cash_delta')
 commonnet=commoncash+div+commonq*p-fee(o['sid'],op,commonq,p,'sell')
 proof=prove(rid,op,cpf);assert bool(prove(rid,close,cpf))==is_true(c['confirmed_history'])
 issues=[]
 for f in ['raw_close','raw_open','adjustment_factor']:
  v=rc[f] if f=='raw_close' else ro[f]
  if not ns['finite'](v) or D(str(v))<=0:issues.append('INVALID_'+f)
 for f in ['source_kind','source_path','segment_id']:
  if f not in raw.columns or str(rc[f])!=str(ro[f]):issues.append('SOURCE_LINEAGE_'+f)
 assert D(h['factor'])==D(str(rc['adjustment_factor']))
 factor_changed=abs(D(str(ro['adjustment_factor']))/D(h['factor'])-1)>D('1e-11')
 bridge=[x for x in data['EQUITY_EVENTS'] if x['sid']==o['sid'] and x['day']==op and x['event']=='FACTOR_BRIDGE']
 if factor_changed and len(bridge)!=1:issues.append('MISSING_RECORDED_FACTOR_BRIDGE')
 ik=row['current_i_target']
 cpknown=isinstance(cpf.loc[close,'receipt'],(bool,np.bool_))
 if c['unknown']:issues.extend(c['unknown'])
 if ik is None:issues.append('I_UNKNOWN')
 if not cpknown:issues.append('CP_STATE_UNKNOWN')
 # Prior CLOSE state is the only legal OPEN state. No current day's CLOSE I/M/CP read.
 failed=bool(c['locked'] or h['locked_exit'] is not None or ik==0 or not row['unbroken_OPEN'])
 known=not issues
 healthy=bool(known and not failed and proof and exactopen>0)
 commonhealthy=bool(known and not failed and proof and commonnet>0)
 commonstatus='UNKNOWN' if not known else 'STRUCTURE_FAILED' if failed else 'VERIFIED_HEALTHY_POSITIVE' if commonhealthy else 'KNOWN_NOT_QUALIFIED'
 status='UNKNOWN' if not known else 'STRUCTURE_FAILED' if failed else 'VERIFIED_HEALTHY_POSITIVE' if healthy else 'KNOWN_NOT_QUALIFIED'
 row.update(open_day=op,previous_close=close,order_seq=o['order_seq'],sector51=o['sector51'],actual_sold_qty=o['qty'],actual_sold_net=D(o['cash_delta']),actual_reason=o['reason'],original_mobile_qty=c['mobile_qty'],actual_round_qty_before_donor=qopen,actual_round_cashflow_before_donor=cash,actual_dividend_entitlement_to_OPEN=div,round_liquidation_net_at_actual_donor_OPEN=exactopen,actual_OPEN_postseed_proofs=proof,first_confirmed_at_this_OPEN=bool(proof and not c['confirmed_history']),same_OPEN_prior_round_sells=[x['order_seq'] for x in sameopen],factor_changed_at_OPEN=factor_changed,recorded_factor_bridge=bridge,H_at_actual_OPEN=healthy,H_status_at_actual_OPEN=status,H_at_common_prefunding_OPEN=commonhealthy,H_status_common_prefunding_OPEN=commonstatus,round_liquidation_net_common_prefunding_OPEN=commonnet,round_qty_common_prefunding_OPEN=commonq,round_cashflow_common_prefunding_OPEN=commoncash,mandatory_round_orders_before_common_snapshot=[x['order_seq'] for x in mandatory],H_unknown_reasons=issues,baseline_round_final_PnL=D(roundmap[rid]['marked_net_pnl']),baseline_round_open_at_cutoff=roundmap[rid]['open_at_cutoff'])
 return row
all_donors=[o for o in orders if o.get('transfer_rank')]
observations=[];failures=[]
for i,o in enumerate(all_donors):
 try:observations.append(inspect(o))
 except Exception as ex:
  failures.append(dict(open_day=o['day'],order_seq=o['order_seq'],sid=o['sid'],round_id=o['round_id'],lot_id=o['lots'][0],actual_sold_net=o['cash_delta'],H_status_at_actual_OPEN='UNKNOWN',H_at_actual_OPEN=False,H_at_common_prefunding_OPEN=False,H_status_common_prefunding_OPEN='UNKNOWN',H_unknown_reasons=[type(ex).__name__+': '+str(ex)]))
 if (i+1)%100==0:print('donors_verified',i+1,'unknown_errors',len(failures),flush=True)
observations+=failures;observations.sort(key=lambda x:x['order_seq']);write('DONOR_LOT_OBSERVATIONS',observations);write('DONOR_UNKNOWN_ERRORS',failures)
donorday=defaultdict(list)
for x in observations:donorday[x['open_day']].append(x)
daily=[]
for day in days:
 os=ordersday[day];buy=[o for o in os if o['side'].startswith('BUY')];ds=donorday[day]
 def bc(kind,phase=None):return [o for o in buy if o['side']=='BUY_'+kind and (phase is None or o.get('allocation_phase')==phase)]
 row=dict(open_day=day,previous_close=prev.get(day),funding_order_count=len(ds),funding_net=sm(ds,'actual_sold_net'),H_OPEN_funding_order_count=sum(x['H_at_common_prefunding_OPEN'] for x in ds),H_OPEN_funding_net=sm([x for x in ds if x['H_at_common_prefunding_OPEN']],'actual_sold_net'),H_both_funding_order_count=sum(x.get('healthy_verified_positive_OPEN',False) for x in ds),H_both_funding_net=sm([x for x in ds if x.get('healthy_verified_positive_OPEN',False)],'actual_sold_net'),newly_confirmed_OPEN_H_count=sum(x.get('first_confirmed_at_this_OPEN',False) and x['H_at_common_prefunding_OPEN'] for x in ds),unknown_donor_count=sum(x['H_status_common_prefunding_OPEN']=='UNKNOWN' for x in ds))
 row['H_sequential_actual_funding_count']=sum(x['H_at_actual_OPEN'] for x in ds)
 row['H_sequential_actual_funding_net']=sm([x for x in ds if x['H_at_actual_OPEN']],'actual_sold_net')
 row['H_primary_snapshot']='COMMON_OPEN_AFTER_MANDATORY_EXITS_ACCRUAL_INFO_BEFORE_OPTIONAL_FINANCING'
 for label,bs in [('MATURE_SEED',bc('SEED','MATURE')),('ADD',bc('ADD')),('EVENT_SEED',bc('SEED','EVENT')),('RESIDUAL_SEED',bc('SEED','RESIDUAL'))]:row[label+'_count']=len(bs);row[label+'_buy_cost']=-sm(bs,'cash_delta')
 row['total_actual_buy_cost']=-sm(buy,'cash_delta');row['actual_ADD_EVENT_buy_cost']=row['ADD_buy_cost']+row['EVENT_SEED_buy_cost']
 tr=planmap[(day,'TRANSFER_CASH')];rf=planmap[(day,'RECEIVER_FUNDING')]
 assert row['funding_net']==D(tr['net_cash_released'])==D(rf['released_cash'])
 reserve=D(rf['cash_after_all_buys'])-D(rf['cash_above_frozen_reserve'])
 pre_cash=D(rf['cash_after_all_buys'])+row['total_actual_buy_cost']-row['funding_net']
 free=pre_cash-reserve
 row.update(saved_OPEN_frozen_reserve=reserve,reconciled_OPEN_cash_after_protection_before_optional_funding=pre_cash,reconciled_OPEN_cash_above_reserve_before_optional_funding=free,cash_alone_covers_actual_ADD_EVENT=free>=row['actual_ADD_EVENT_buy_cost'],cash_alone_covers_all_actual_buys=free>=row['total_actual_buy_cost'],cash_comparison_scope='Observed quantities and saved full-M7 reserve, not no-N shadow feasibility')
 pay=sum((D(x.get('cash_delta',0)) for x in data['EQUITY_EVENTS'] if x['day']==day),Z)
 assert D(rf['cash_after_all_buys'])+pay==D(led[day]['cash']),('OPEN_TO_CLOSE_CASH_RECONCILIATION',day)
 if day in prev:
  protection=sm([o for o in os if o['side'].startswith('SELL') and not o.get('transfer_rank')],'cash_delta')
  assert D(led[prev[day]]['cash'])+protection==pre_cash,('PRE_FUND_CASH_RECONCILIATION',day)
  row['mandatory_or_other_nonfunding_sell_net']=protection
  dp=planmap[(prev[day],'DEMAND_PLAN')]
  ae=[r for r in dp['receivers'] if r['kind']=='ADD' or r.get('allocation_phase')=='EVENT']
  row['saved_CLOSE_cash_after_known_protection_less_reserve']=D(dp['cash_after_known_protection'])-D(dp['reserve'])
  row['saved_CLOSE_ADD_EVENT_request_count']=len(ae)
  row['saved_CLOSE_ADD_EVENT_planned_cost']=sm(ae,'cost')
  row['same_snapshot_no_financing_and_no_A_requests']=not ds and not ae and row['MATURE_SEED_count']>0
  row['saved_CLOSE_cash_covers_planned_ADD_EVENT']=row['saved_CLOSE_cash_after_known_protection_less_reserve']>=row['saved_CLOSE_ADD_EVENT_planned_cost']
 if not ds:group='NO_OPTIONAL_FUNDING'
 elif row['H_OPEN_funding_order_count']:
  group='H_FUNDING_WITH_NEW_MATURE' if row['MATURE_SEED_count'] else 'H_FUNDING_WITHOUT_NEW_MATURE'
 elif row['unknown_donor_count']:group='FUNDING_H_UNKNOWN'
 else:group='FUNDING_NO_H'
 row['observed_day_group']=group
 daily.append(row)
write('DAILY_OPEN_FLOWS',daily);daymap={x['open_day']:x for x in daily}
classified=[]
for r in rounds:
 dd=daymap[r['actual_seed_OPEN']];os=ordersround[r['round_id']]
 cs=[]
 if '2024-09-23'<=r['actual_seed_OPEN']<='2024-09-30':cs.append('SEPT_STARTUP_SEED_OPEN_0923_0930')
 if r['sector51']=='光伏风电设备' and '2024-10-23'<=r['actual_seed_OPEN']<='2024-10-29':cs.append('PV_SEED_OPEN_1023_1029')
 if r['actual_seed_OPEN']>='2024-11-07':cs.append('NEW_SEED_OPEN_FROM_1107')
 if not cs:continue
 row=dict(r,cohorts=cs,observed_day_group=dd['observed_day_group'],seed_day_H_OPEN_funding_net=dd['H_OPEN_funding_net'],seed_day_H_both_funding_net=dd['H_both_funding_net'],seed_day_unknown_donor_count=dd['unknown_donor_count'],seed_day_total_funding_net=dd['funding_net'],seed_day_cash_covers_actual_ADD_EVENT=dd['cash_alone_covers_actual_ADD_EVENT'],round_all_buy_cost=-sm([o for o in os if o['side'].startswith('BUY')],'cash_delta'),round_ADD_buy_cost=-sm([o for o in os if o['side']=='BUY_ADD'],'cash_delta'),not_counterfactual=True)
 classified.append(row)
write('FIXED_ROUND_CLASSIFICATION',classified)
summary=[]
for cohort in ['SEPT_STARTUP_SEED_OPEN_0923_0930','PV_SEED_OPEN_1023_1029','NEW_SEED_OPEN_FROM_1107']:
 for phase in ['ALL','MATURE','EVENT','RESIDUAL','EVENT_OR_RESIDUAL']:
  selected=[r for r in classified if cohort in r['cohorts'] and (phase=='ALL' or r['seed_phase']==phase or phase=='EVENT_OR_RESIDUAL' and r['seed_phase'] in ['EVENT','RESIDUAL'])]
  for group in ['ALL','NO_OPTIONAL_FUNDING','FUNDING_NO_H','H_FUNDING_WITH_NEW_MATURE','H_FUNDING_WITHOUT_NEW_MATURE','FUNDING_H_UNKNOWN']:
   rs=[r for r in selected if group=='ALL' or r['observed_day_group']==group]
   summary.append(dict(cohort=cohort,original_seed_phase=phase,observed_day_group=group,rounds=len(rs),seed_buy_cost=sm(rs,'seed_all_in'),all_round_buy_cost=sm(rs,'round_all_buy_cost'),later_ADD_buy_cost=sm(rs,'round_ADD_buy_cost'),whole_round_PnL_at_common_cutoff=sm(rs,'marked_net_pnl'),positive_rounds=sum(D(r['marked_net_pnl'])>0 for r in rs),positive_whole_round_PnL=sum((D(r['marked_net_pnl']) for r in rs if D(r['marked_net_pnl'])>0),Z),negative_rounds=sum(D(r['marked_net_pnl'])<0 for r in rs),negative_whole_round_PnL=sum((D(r['marked_net_pnl']) for r in rs if D(r['marked_net_pnl'])<0),Z),open_at_cutoff=sum(r['open_at_cutoff'] for r in rs),H_unknown_rounds=sum(r['seed_day_unknown_donor_count']>0 for r in rs),PnL_unknown_rounds=sum(r['marked_net_pnl'] is None for r in rs)))
write('FIXED_COHORT_GROUPS',summary)
# Baseline path givebacks only, not estimates of keeping sold stock. No future buys makes stock/qty path less confounded.
givebacks=[]
for d in observations:
 if not d['H_at_actual_OPEN']:continue
 r=roundmap[d['round_id']];futurebuys=[o for o in ordersround[d['round_id']] if o['order_seq']>d['order_seq'] and o['side'].startswith('BUY')]
 if D(r['marked_net_pnl'])<d['round_liquidation_net_at_actual_donor_OPEN']:
  afterqty=d['actual_round_qty_before_donor']-d['actual_sold_qty']
  givebacks.append(dict(open_day=d['open_day'],sid=d['sid'],name=d['name'],sector51=d['sector51'],round_id=d['round_id'],lot_id=d['lot_id'],seed_OPEN=r['actual_seed_OPEN'],actual_donor_order_seq=d['order_seq'],H_OPEN_liquidation_net=d['round_liquidation_net_at_actual_donor_OPEN'],actual_sold_qty=d['actual_sold_qty'],actual_sold_net=d['actual_sold_net'],round_qty_after_sale=afterqty,future_buy_count=len(futurebuys),future_buy_cost=-sm(futurebuys,'cash_delta'),baseline_final_round_PnL=D(r['marked_net_pnl']),baseline_path_change_from_H_OPEN=D(r['marked_net_pnl'])-d['round_liquidation_net_at_actual_donor_OPEN'],closed=not r['open_at_cutoff'],exit_day=r['exit_day'],exit_reasons=r['exit_reasons'],strict_no_future_buy_remaining_position=not futurebuys and afterqty>0,not_unsold_counterfactual=True))
givebacks.sort(key=lambda r:r['baseline_path_change_from_H_OPEN']);write('ACTUAL_HEALTHY_DONOR_GIVEBACKS',givebacks)
noH=[r for r in classified if 'NEW_SEED_OPEN_FROM_1107' in r['cohorts'] and r['seed_phase']=='MATURE' and r['observed_day_group'] in ['NO_OPTIONAL_FUNDING','FUNDING_NO_H']]
write('LATE_NO_H_MATURE_ROUNDS',sorted(noH,key=lambda r:D(r['marked_net_pnl'])))
# Verify copied design's 22 PV donors and 6 carried-confirmation startup donors exactly.
oldpv=json.loads((PARSER.parent/'PV_1108_LOT_CHECKS.json').read_text())
for old in oldpv:
 new=next(r for r in observations if r['order_seq']==old['actual_order_seq'])
 for f in ['round_liquidation_net_CLOSE','round_liquidation_net_OPEN','healthy_verified_positive_OPEN']:
  assert str(new[f])==str(old[f]),('SEALED_PV_RECHECK',f,new['order_seq'])
oldst=json.loads((PARSER.parent/'STARTUP_0925_CONFIRMED_DONORS.json').read_text())
assert {x['lot_id'] for x in oldst if x['healthy_verified_positive_OPEN']}=={x['lot_id'] for x in observations if x['open_day']=='2024-09-25' and x.get('healthy_verified_positive_OPEN')}
assert len([r for r in classified if 'NEW_SEED_OPEN_FROM_1107' in r['cohorts']])==954
assert sm([r for r in classified if 'NEW_SEED_OPEN_FROM_1107' in r['cohorts']],'marked_net_pnl')==D('-183704.0578492558175')
qa=dict(no_strategy_import=True,no_history=True,no_new_candidate=True,no_network=True,common_cutoff=days[-1],days=len(days),donor_orders=len(all_donors),donor_unknown_errors=len(failures),fixed_late_rounds=954,sealed_design_PV_and_startup_rechecked=True,all_daily_cash_reconciliations_pass=True,H_OPEN_counts=dict(Counter(r['H_status_common_prefunding_OPEN'] for r in observations)),primary_H_snapshot='COMMON_OPEN_AFTER_MANDATORY_EXITS_ACCRUAL_INFO_BEFORE_OPTIONAL_FINANCING',sequential_H_diff_orders=[r['order_seq'] for r in observations if r['H_at_common_prefunding_OPEN']!=r['H_at_actual_OPEN']],H_both_count=sum(r.get('healthy_verified_positive_OPEN',False) for r in observations),newly_confirmed_OPEN_H_count=sum(r.get('first_confirmed_at_this_OPEN',False) and r['H_at_common_prefunding_OPEN'] for r in observations),cash_semantics='Cash is pooled. Daily overlap is mechanism scope upper bound only. No-N shadow not run; no blocked tickets, savings or returns attributed.',pnl_semantics='Whole-round actual final PnL includes later ADDs, funding and exits; open rounds marked at 2025-01-20, not all realized.')
write('QA',qa)
# Recheck every read input remains unchanged.
for p,h in inputs.items():assert sha(p)==h,('INPUT_CHANGED',p)
write('SOURCE_HASHES',inputs)
write('ARTIFACT_SEAL',{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='ARTIFACT_SEAL.json'})
print(json.dumps(qa,ensure_ascii=False,default=str),flush=True)
print(json.dumps([s for s in summary if s['cohort']=='NEW_SEED_OPEN_FROM_1107' and s['original_seed_phase'] in ['ALL','MATURE','EVENT_OR_RESIDUAL']],ensure_ascii=False,default=str),flush=True)
