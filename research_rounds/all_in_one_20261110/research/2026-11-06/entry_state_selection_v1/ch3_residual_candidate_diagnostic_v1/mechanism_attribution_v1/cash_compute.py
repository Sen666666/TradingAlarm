#!/usr/bin/env python3
"""Sealed-output-only attribution. Never imports or invokes the economic engine."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal, getcontext
import csv, json, hashlib, itertools
getcontext().prec = 50
D = Decimal
ZERO = D(0)
ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / 'lifecycle_comparison_v1'
WINDOWS = ['2022', '2024_924']
ARMS = ['A_UNION_B', 'RAW_MOM11', 'CH3_RM']
COMPARISONS = [('CH3_RM','RAW_MOM11'), ('CH3_RM','A_UNION_B')]
CLOSED = 'COMPLETE_CONDITIONAL_STOCK_ROUND'
FIELDS = {
 'core': {'net':'core_net','raw':'core_gross_raw_open_pnl','slippage':'core_slippage_drag','gross':'core_gross_after_slippage_pnl','fees':'core_fees','net80':'core_dividend_net80','buy_cash':'core_buy_cash','return':'core_return'},
 'full': {'net':'net_pnl','raw':'full_gross_raw_open_pnl','slippage':'full_slippage_drag','gross':'full_gross_after_slippage_pnl','fees':'full_fees','net80':'full_dividend_net80','buy_cash':'total_buy_cash','return':'net_return_on_buy_cash'}
}
assert json.loads((ROOT/'cash_contract.json').read_text())['frozen_before_new_amount_calculations']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open() as h: return list(csv.DictReader(h))
def dec(v): return D(str(v)) if str(v) not in ('','None','nan') else None
def add(vals): return sum(vals, ZERO)
def usable(r): return r['evidence_usable_closed'] == 'True'
def nofill(r): return 'NOFILL' in r['status']
def resolved(r): return usable(r) or nofill(r)
def metric(r,layer,k):
 v=dec(r[FIELDS[layer][k]])
 assert v is not None, (r['round_id'],layer,k)
 return v
def dump_csv(name, rows):
 assert name.startswith('cash_')
 keys = list(dict.fromkeys(k for r in rows for k in r))
 with (ROOT/name).open('w', newline='') as h:
  w=csv.DictWriter(h,fieldnames=keys);w.writeheader();w.writerows(rows)
def dump_json(name,obj):
 assert name.startswith('cash_')
 (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n')
def close(a,b,tol=D('0.000001')): return abs(a-b) <= tol

def canonical(rows, keys):
 def val(v):
  if v is None: return ''
  try: return str(D(str(v)).normalize())
  except Exception: return str(v)
 return sorted(tuple(val(r.get(k,'')) for k in keys) for r in rows)

# Snapshot ALL sealed files, not merely a selected subset. Only cash_* outputs are written.
source_before={str(p.relative_to(SRC)):sha(p) for p in sorted(SRC.rglob('*')) if p.is_file()}
source_used=['report/CORE_AND_FULL_ROUNDS.csv','POST_ECONOMIC_INDEPENDENT_AUDIT.json']
rounds=read(SRC/'report/CORE_AND_FULL_ROUNDS.csv')
assert len({r['round_id'] for r in rounds})==len(rounds)
by=defaultdict(list)
for r in rounds: by[r['window'],r['arm'],r['sid']].append(r)
universe=defaultdict(dict); actions={}; ledgers={}; claims={}; permissions={}
for window in WINDOWS:
 events_by_arm=[]
 for arm in ARMS:
  base=SRC/window/arm
  for fn in ['DECISIONS.csv','ACTIONS.csv','CLAIM_LEDGER.csv','CLAIMS.json']: source_used.append(str((base/fn).relative_to(SRC)))
  decisions=read(base/'DECISIONS.csv')
  events_by_arm.append({r['event_id'] for r in decisions})
  selected={r['round_id'] for r in decisions if r['selected']=='True'}
  assert selected=={r['round_id'] for r in rounds if r['window']==window and r['arm']==arm}
  for r in decisions: universe[window][r['sid']]={'name':r['name'],'industry':r['industry']}
  permissions[window,arm]=selected
  actions[window,arm]=defaultdict(list)
  ledgers[window,arm]=defaultdict(list)
  claims[window,arm]=defaultdict(list)
  for r in read(base/'ACTIONS.csv'): actions[window,arm][r['round_id']].append(r)
  for r in read(base/'CLAIM_LEDGER.csv'): ledgers[window,arm][r['round_id']].append(r)
  for r in json.loads((base/'CLAIMS.json').read_text()): claims[window,arm][r['owner_round_id']].append(r)
 assert events_by_arm[0]==events_by_arm[1]==events_by_arm[2]

arm_stock=[]; stock_lookup={}; arm_metrics=[]; qa_errors=[]
for window in WINDOWS:
 for arm in ARMS:
  for sid in sorted(universe[window]):
   rr=by[window,arm,sid];uu=[r for r in rr if usable(r)]
   actual=[r for r in rr if r['entry_day']]
   unknown=[r for r in rr if not resolved(r)]
   row=dict(window=window,arm=arm,sid=sid,**universe[window][sid],permissions=len(rr),confirmed_entries=len(actual),usable_closed=len(uu),conditional_closed=sum(r['status']==CLOSED for r in rr),nofill=sum(nofill(r) for r in rr),execution_unknown=sum('UNKNOWN' in r['status'] for r in rr),closed_financial_unknown=sum(r['status']==CLOSED and not usable(r) for r in rr),other_unresolved=sum(not resolved(r) and 'UNKNOWN' not in r['status'] and r['status']!=CLOSED for r in rr),complete_known=not unknown,unresolved_round_ids=';'.join(r['round_id'] for r in unknown),all_round_ids=';'.join(r['round_id'] for r in rr))
   row['participation_status']='NO_PERMISSION' if not rr else ('ONLY_NOFILL' if all(nofill(r) for r in rr) else 'ACTUAL_ENTRY' if actual else 'ENTRY_UNKNOWN')
   for layer in FIELDS:
    for k in FIELDS[layer]:
     s=add(metric(r,layer,k) for r in uu)
     row[f'{layer}_observed_{k}']=s if uu else None
     if k not in ['return']: row[f'{layer}_complete_{k}']=s if not unknown else None
    nets=[metric(r,layer,'net') for r in uu]
    row[f'{layer}_wins']=sum(v>0 for v in nets); row[f'{layer}_losses']=sum(v<0 for v in nets);row[f'{layer}_zeros']=sum(v==0 for v in nets)
    row[f'{layer}_winner_net']=add(v for v in nets if v>0) if uu else None
    row[f'{layer}_loser_net']=add(v for v in nets if v<0) if uu else None
    row[f'{layer}_tail50']=sum(metric(r,layer,'return')>=D('.5') for r in uu)
    for r in uu:
     assert close(metric(r,layer,'net'),metric(r,layer,'raw')-metric(r,layer,'slippage')-metric(r,layer,'fees')+metric(r,layer,'net80')),(r['round_id'],layer,'gross identity')
   arm_stock.append(row);stock_lookup[window,arm,sid]=row
  rr=[r for r in rounds if r['window']==window and r['arm']==arm]; uu=[r for r in rr if usable(r)]
  for layer in FIELDS:
   nets=[metric(r,layer,'net') for r in uu]; wins=[v for v in nets if v>0];losses=[v for v in nets if v<0]
   row=dict(window=window,arm=arm,layer=layer,permissions=len(rr),confirmed_entries=sum(bool(r['entry_day']) for r in rr),usable_closed=len(uu),execution_unknown=sum('UNKNOWN' in r['status'] for r in rr),closed_financial_unknown=sum(r['status']==CLOSED and not usable(r) for r in rr),nofill=sum(nofill(r) for r in rr),winners=len(wins),losers=len(losses),zeros=sum(v==0 for v in nets),winner_net=add(wins),loser_net=add(losses),mean_win=add(wins)/len(wins),mean_loss=add(losses)/len(losses),mean_net=add(nets)/len(nets),mean_return=add(metric(r,layer,'return') for r in uu)/len(uu),win_rate=D(len(wins))/len(uu))
   for k in FIELDS[layer]: row['observed_'+k]=add(metric(r,layer,k) for r in uu)
   arm_metrics.append(row)

pairs=[]; coverage=[]; commonqa=[]; stockcomp=[]; summaries=[]; means=[]; concentration=[]; ranked=[]; deletion=[]
OUTCOME_KEYS=['status','entry_status','entry_day','entry_q','entry_price','entry_fee','entry_risk','entry_gross','entry_floor_raw','exit_day','exit_price','exit_reason','net_pnl','core_net','core_return','net_return_on_buy_cash','dividend_net80_total','added_q','total_buy_cash','financial_coverage_status','evidence_usable_closed'] + list(dict.fromkeys(f for fields in FIELDS.values() for f in fields.values()))
ACTION_KEYS=['day','side','q','price','fee','reason']
LEDGER_KEYS=['economic_event_id','evidence_version','day','event','cash_delta','receivable_delta','amount','record_q','core_record_q','available_from']
CLAIM_KEYS=['economic_event_id','record_q','core_record_q','amount','core_amount','recognized','settled']

def summarize_concentration(window,comparison,layer,scope,items,metadata=None):
 # Every member is included before sorting; no sample is defined from profits.
 items=sorted(items,key=lambda t:(-abs(t[1]),t[0]))
 total=add(v for _,v in items);abstotal=add(abs(v) for _,v in items)
 for n in [1,5,10]:
  head=items[:n]
  row=dict(window=window,comparison=comparison,layer=layer,scope=scope,population=len(items),positive=sum(v>0 for _,v in items),negative=sum(v<0 for _,v in items),zero=sum(v==0 for _,v in items),total_signed=total,total_absolute=abstotal,top_k=n,top_actual=len(head),top_signed=add(v for _,v in head),top_absolute=add(abs(v) for _,v in head),share_absolute=add(abs(v) for _,v in head)/abstotal if abstotal else None,top_ids=';'.join(sid for sid,_ in head),delete_one_min=min((total-v for _,v in items),default=None),delete_one_max=max((total-v for _,v in items),default=None))
  if metadata: row.update(metadata)
  concentration.append(row)
 for rank,(sid,val) in enumerate(items,1): ranked.append(dict(window=window,comparison=comparison,layer=layer,scope=scope,rank_abs=rank,sid=sid,contribution=val,absolute_contribution=abs(val)))

for window in WINDOWS:
 for ca,ra in COMPARISONS:
  comp=ca+'_MINUS_'+ra
  classby={}; pairlocal=[]; commonlocal=[]
  for sid in sorted(universe[window]):
   cr=by[window,ca,sid]; rr=by[window,ra,sid]; ce={r['event_id']:r for r in cr};re={r['event_id']:r for r in rr}
   assert len(ce)==len(cr) and len(re)==len(rr)
   common=set(ce)&set(re)
   for eid in sorted(common):
    c,r=ce[eid],re[eid]
    checks=dict(outcomes_identical=canonical([c],OUTCOME_KEYS)==canonical([r],OUTCOME_KEYS),actions_identical=canonical(actions[window,ca][c['round_id']],ACTION_KEYS)==canonical(actions[window,ra][r['round_id']],ACTION_KEYS),claim_ledger_identical=canonical(ledgers[window,ca][c['round_id']],LEDGER_KEYS)==canonical(ledgers[window,ra][r['round_id']],LEDGER_KEYS),claims_identical=canonical(claims[window,ca][c['round_id']],CLAIM_KEYS)==canonical(claims[window,ra][r['round_id']],CLAIM_KEYS))
    assert all(checks.values()),(comp,eid,checks)
    kind='SAME_EVENT_USABLE' if usable(c) else 'SAME_EVENT_NOFILL' if nofill(c) else 'SAME_EVENT_UNKNOWN'
    for arm,z in [(ca,c),(ra,r)]: classby[z['round_id']]=(kind,r['round_id'] if arm==ca else c['round_id'])
    row=dict(window=window,comparison=comp,sid=sid,event_id=eid,c_round_id=c['round_id'],r_round_id=r['round_id'],classification=kind,**checks)
    commonqa.append(row);commonlocal.append(row)
   c_exit=defaultdict(list);r_exit=defaultdict(list)
   for z in cr:
    if z['event_id'] not in common and z['exit_day']:c_exit[z['exit_day']].append(z)
   for z in rr:
    if z['event_id'] not in common and z['exit_day']:r_exit[z['exit_day']].append(z)
   for ex in sorted(set(c_exit)&set(r_exit)):
    cs,rs=c_exit[ex],r_exit[ex]
    if len(cs)!=1 or len(rs)!=1:
     for z in cs+rs:classby[z['round_id']]=('UNPAIRED_AMBIGUOUS_SAME_EXIT','')
     continue
    c,r=cs[0],rs[0]
    if not (usable(c) and usable(r)):
     for z in cs+rs:classby[z['round_id']]=('UNPAIRED_SAME_EXIT_EVIDENCE_UNKNOWN','')
     continue
    assert c['entry_day']!=r['entry_day'],(c['round_id'],r['round_id'],'different event but same entry')
    qC,qR=dec(c['entry_q']),dec(r['entry_q']);pC=metric(c,'core','net')/qC;pR=metric(r,'core','net')/qR
    qe=(qC-qR)*(pC+pR)/2;pe=(pC-pR)*(qC+qR)/2;delta=metric(c,'core','net')-metric(r,'core','net')
    residual=delta-qe-pe
    assert abs(residual)<D('1e-30'),(c['round_id'],r['round_id'],residual)
    row=dict(window=window,comparison=comp,sid=sid,**universe[window][sid],exit_day=ex,c_round_id=c['round_id'],r_round_id=r['round_id'],c_event_id=c['event_id'],r_event_id=r['event_id'],c_signal_day=c['signal_day'],r_signal_day=r['signal_day'],c_entry_day=c['entry_day'],r_entry_day=r['entry_day'],c_entry_q=qC,r_entry_q=qR,c_core_net_per_initial_share=pC,r_core_net_per_initial_share=pR,core_quantity_component=qe,core_per_share_component=pe,core_delta_net=delta,core_identity_residual=residual)
    for layer in FIELDS:
     for k in FIELDS[layer]:
      row[f'c_{layer}_{k}']=metric(c,layer,k);row[f'r_{layer}_{k}']=metric(r,layer,k);row[f'{layer}_delta_{k}']=metric(c,layer,k)-metric(r,layer,k)
    pairs.append(row);pairlocal.append(row)
    classby[c['round_id']]=('UNIQUE_SAME_EXIT_DIFFERENT_ENTRY',r['round_id']);classby[r['round_id']]=('UNIQUE_SAME_EXIT_DIFFERENT_ENTRY',c['round_id'])
   for arm,zlist,opp in [(ca,cr,rr),(ra,rr,cr)]:
    for z in zlist:
     if z['round_id'] not in classby:
      kind='UNPAIRED_EXPLICIT_NOFILL' if nofill(z) else 'UNPAIRED_EXECUTION_OR_FINANCIAL_UNKNOWN' if not usable(z) else 'UNPAIRED_OTHER_ARM_NO_PERMISSION' if not opp else 'UNPAIRED_OTHER_ARM_ONLY_NOFILL' if all(nofill(x) for x in opp) else 'UNPAIRED_DIFFERENT_EXIT_OR_NO_USABLE_COUNTERPART'
      classby[z['round_id']]=(kind,'')
     kind,otherid=classby[z['round_id']]
     coverage.append(dict(window=window,comparison=comp,arm=arm,sid=sid,name=z['name'],round_id=z['round_id'],event_id=z['event_id'],signal_day=z['signal_day'],entry_day=z['entry_day'],entry_q=z['entry_q'],exit_day=z['exit_day'],status=z['status'],financial_coverage_status=z['financial_coverage_status'],evidence_usable_closed=usable(z),classification=kind,paired_round_id=otherid,core_net_observed=metric(z,'core','net') if usable(z) else None,full_net_observed=metric(z,'full','net') if usable(z) else None))
   c,r=stock_lookup[window,ca,sid],stock_lookup[window,ra,sid]
   complete=c['complete_known'] and r['complete_known']
   if not cr and not rr: kind='BOTH_NO_PERMISSION'
   elif not cr: kind='C_NO_PERMISSION_R_ACTUAL_OR_UNRESOLVED'
   elif not rr: kind='R_NO_PERMISSION_C_ACTUAL_OR_UNRESOLVED'
   elif c['participation_status']=='ONLY_NOFILL' or r['participation_status']=='ONLY_NOFILL': kind='ONE_OR_BOTH_ONLY_NOFILL'
   elif set(ce)==set(re): kind='SAME_EVENT_SET'
   elif c['confirmed_entries'] and r['confirmed_entries']: kind='BOTH_ACTUAL_DIFFERENT_EVENT_SETS'
   else: kind='PARTICIPATION_UNKNOWN'
   row=dict(window=window,comparison=comp,sid=sid,**universe[window][sid],path_class=kind,complete_known=complete,complete_status='KNOWN' if complete else 'UNKNOWN',c_participation=c['participation_status'],r_participation=r['participation_status'],c_permissions=c['permissions'],r_permissions=r['permissions'],c_confirmed_entries=c['confirmed_entries'],r_confirmed_entries=r['confirmed_entries'],c_usable_closed=c['usable_closed'],r_usable_closed=r['usable_closed'],c_execution_unknown=c['execution_unknown'],r_execution_unknown=r['execution_unknown'],c_financial_unknown=c['closed_financial_unknown'],r_financial_unknown=r['closed_financial_unknown'],c_unresolved_round_ids=c['unresolved_round_ids'],r_unresolved_round_ids=r['unresolved_round_ids'],common_event_count=len(common),same_exit_unique_pairs=sum(p['sid']==sid for p in pairlocal))
   for layer in FIELDS:
    for k in ['net','raw','slippage','gross','fees','net80','buy_cash']:
     cv=c[f'{layer}_observed_{k}'];rv=r[f'{layer}_observed_{k}']
     row[f'c_{layer}_observed_{k}']=cv;row[f'r_{layer}_observed_{k}']=rv
     # This is only an additive reconciliation contribution of the OBSERVED ROW SETS.
     # Empty sums do not make unknown path outcomes zero; complete difference stays null.
     row[f'{layer}_observed_subtotal_bridge_{k}']=(cv or ZERO)-(rv or ZERO)
     row[f'{layer}_complete_delta_{k}']=c[f'{layer}_complete_{k}']-r[f'{layer}_complete_{k}'] if complete else None
    for label in ['wins','losses','zeros','winner_net','loser_net','tail50']:
     row[f'c_{layer}_{label}']=c[f'{layer}_{label}'];row[f'r_{layer}_{label}']=r[f'{layer}_{label}']
   stockcomp.append(row)
  loc=[x for x in stockcomp if x['window']==window and x['comparison']==comp]
  for layer in FIELDS:
   cc=[r for r in rounds if r['window']==window and r['arm']==ca and usable(r)];rr=[r for r in rounds if r['window']==window and r['arm']==ra and usable(r)]
   SC=add(metric(r,layer,'net') for r in cc);SR=add(metric(r,layer,'net') for r in rr);NC=len(cc);NR=len(rr);delta=SC-SR
   complete=[x for x in loc if x['complete_known']]; unknown=[x for x in loc if not x['complete_known']]
   assert close(add(x[f'{layer}_observed_subtotal_bridge_net'] for x in loc),delta)
   known_delta=add(x[f'{layer}_complete_delta_net'] for x in complete)
   known_obs=add(x[f'{layer}_observed_subtotal_bridge_net'] for x in complete)
   assert known_delta==known_obs
   unknown_bridge=add(x[f'{layer}_observed_subtotal_bridge_net'] for x in unknown)
   a=(D(1)/NC+D(1)/NR)/2;b=(D(1)/NC-D(1)/NR)/2
   q=add(p['core_quantity_component'] for p in pairlocal) if layer=='core' else None
   p=add(p['core_per_share_component'] for p in pairlocal) if layer=='core' else None
   same_exit=add(p[f'{layer}_delta_net'] for p in pairlocal)
   common_delta=ZERO
   unmatched=delta-same_exit-common_delta
   denom=b*(SC+SR)
   terms=dict(window=window,comparison=comp,layer=layer,c_usable_n=NC,r_usable_n=NR,c_sum=SC,r_sum=SR,observed_sum_delta=delta,c_mean=SC/NC,r_mean=SR/NR,mean_delta=SC/NC-SR/NR,mean_sum_coefficient=a,common_event_sum_delta=common_delta,same_exit_unique_pair_n=len(pairlocal),same_exit_sum_delta=same_exit,same_exit_quantity_sum=q,same_exit_per_share_sum=p,unmatched_observed_sum_delta=unmatched,same_exit_quantity_mean_component=q*a if q is not None else None,same_exit_per_share_mean_component=p*a if p is not None else None,same_exit_total_mean_component=same_exit*a,unmatched_mean_component=unmatched*a,observed_count_mean_component=denom,identity_residual=(SC/NC-SR/NR)-(same_exit+unmatched+common_delta)*a-denom)
   assert abs(terms['identity_residual'])<D('1e-30')
   means.append(terms)
   summaries.append(dict(window=window,comparison=comp,layer=layer,all_market_stocks=len(loc),stocks_any_permission=sum(x['c_permissions']>0 or x['r_permissions']>0 for x in loc),complete_stocks=len(complete),complete_stocks_any_permission=sum(x['c_permissions']>0 or x['r_permissions']>0 for x in complete),unknown_stocks=len(unknown),c_usable_n=NC,r_usable_n=NR,c_observed_net=SC,r_observed_net=SR,observed_subtotal_delta=delta,complete_stock_net_delta=known_delta,unknown_stock_observed_subtotal_bridge=unknown_bridge,complete_positive_stocks=sum(x[f'{layer}_complete_delta_net']>0 for x in complete),complete_negative_stocks=sum(x[f'{layer}_complete_delta_net']<0 for x in complete),complete_zero_stocks=sum(x[f'{layer}_complete_delta_net']==0 for x in complete),common_events=len(commonlocal),common_usable_events=sum(x['classification']=='SAME_EVENT_USABLE' for x in commonlocal),same_exit_unique_pairs=len(pairlocal),c_unmatched_usable=sum(classby[r['round_id']][0] not in ['SAME_EVENT_USABLE','UNIQUE_SAME_EXIT_DIFFERENT_ENTRY'] for r in cc),r_unmatched_usable=sum(classby[r['round_id']][0] not in ['SAME_EVENT_USABLE','UNIQUE_SAME_EXIT_DIFFERENT_ENTRY'] for r in rr)))
   summarize_concentration(window,comp,layer,'COMPLETE_STOCK_DELTA',[(x['sid'],x[f'{layer}_complete_delta_net']) for x in complete])
   summarize_concentration(window,comp,layer,'OBSERVED_SUBTOTAL_BRIDGE_NOT_FULL_STOCK_DELTA',[(x['sid'],x[f'{layer}_observed_subtotal_bridge_net']) for x in loc])
   summarize_concentration(window,comp,layer,'OBSERVED_MEAN_GAP_ADDITIVE_CONTRIBUTION',[(x['sid'],(x[f'c_{layer}_observed_net'] or ZERO)/NC-(x[f'r_{layer}_observed_net'] or ZERO)/NR) for x in loc])
   for x in loc:
    cs=x[f'c_{layer}_observed_net'] or ZERO;rs=x[f'r_{layer}_observed_net'] or ZERO
    cN=NC-x['c_usable_closed'];rN=NR-x['r_usable_closed']
    deletion.append(dict(window=window,comparison=comp,layer=layer,sid=x['sid'],name=x['name'],complete_known=x['complete_known'],complete_stock_delta_after_deletion=known_delta-x[f'{layer}_complete_delta_net'] if x['complete_known'] else None,observed_subtotal_delta_after_deletion=delta-cs+rs,observed_mean_gap_after_deletion=(SC-cs)/cN-(SR-rs)/rN if cN and rN else None,c_n_after=cN,r_n_after=rN))
  for effect in ['core_quantity_component','core_per_share_component','core_delta_net']:
   summarize_concentration(window,comp,'core','SAME_EXIT_PAIR_'+effect,[(x['c_round_id']+' vs '+x['r_round_id'],x[effect]) for x in pairlocal])

# No source writes, and verify immutable sources after the entire computation.
source_after={str(p.relative_to(SRC)):sha(p) for p in sorted(SRC.rglob('*')) if p.is_file()}
assert source_before==source_after,'sealed source mutation detected'
dump_csv('cash_arm_stock_totals.csv',arm_stock)
dump_csv('cash_arm_metrics.csv',arm_metrics)
dump_csv('cash_stock_comparison.csv',stockcomp)
dump_csv('cash_common_event_qa.csv',commonqa)
dump_csv('cash_unique_same_exit_decomposition.csv',pairs)
dump_csv('cash_round_coverage.csv',coverage)
dump_csv('cash_summary.csv',summaries)
dump_csv('cash_mean_decomposition.csv',means)
dump_csv('cash_concentration.csv',concentration)
dump_csv('cash_ranked_stock_deltas.csv',ranked)
dump_csv('cash_leave_one_stock_out.csv',deletion)
# Complete path-class breakdown, retaining unknown stock counts rather than assigning them a net.
classes=[]
for (window,ca,ra),layer in itertools.product([(w,c,r) for w in WINDOWS for c,r in COMPARISONS],FIELDS):
 comp=ca+'_MINUS_'+ra
 loc=[x for x in stockcomp if x['window']==window and x['comparison']==comp]
 for kind in sorted({x['path_class'] for x in loc}):
  ss=[x for x in loc if x['path_class']==kind]
  classes.append(dict(window=window,comparison=comp,layer=layer,path_class=kind,stocks=len(ss),complete_stocks=sum(x['complete_known'] for x in ss),unknown_stocks=sum(not x['complete_known'] for x in ss),observed_subtotal_bridge=add(x[f'{layer}_observed_subtotal_bridge_net'] for x in ss),known_complete_stock_net_delta=add(x[f'{layer}_complete_delta_net'] for x in ss if x['complete_known']),c_observed_n=sum(x['c_usable_closed'] for x in ss),r_observed_n=sum(x['r_usable_closed'] for x in ss)))
dump_csv('cash_path_class_summary.csv',classes)
qa=dict(status='PASS_READ_ONLY_CASH_ATTRIBUTION',contract_sha256=sha(ROOT/'cash_contract.json'),script_sha256=sha(Path(__file__)),source_files_checked=len(source_before),sources_unchanged=source_before==source_after,source_rounds=len(rounds),arm_stock_rows=len(arm_stock),comparison_stock_rows=len(stockcomp),all_common_event_checks=len(commonqa),common_event_checks_all_pass=True,unique_same_exit_pairs=len(pairs),round_coverage_rows=len(coverage),max_symmetric_residual=str(max(abs(x['core_identity_residual']) for x in pairs)),max_mean_residual=str(max(abs(x['identity_residual']) for x in means)),economic_engine_invoked=False,all_unknown_stock_deltas_null=all(x['core_complete_delta_net'] is None and x['full_complete_delta_net'] is None for x in stockcomp if not x['complete_known']),outputs=[p.name for p in sorted(ROOT.glob('cash_*.csv'))])
dump_json('cash_source_manifest.json',dict(files=source_before,explicit_inputs=source_used))
dump_json('cash_qa.json',qa)
print(json.dumps(qa,ensure_ascii=False,indent=2))
print('\nPRIMARY SUMMARIES')
for x in summaries:
 if x['comparison'].endswith('RAW_MOM11'):print(json.dumps(x,ensure_ascii=False,default=str))
print('\nPRIMARY MEAN DECOMPOSITION')
for x in means:
 if x['comparison'].endswith('RAW_MOM11'):print(json.dumps(x,ensure_ascii=False,default=str))
