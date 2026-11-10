"""Bounded data repair: ten preselected, previously unfilled ex-cash entry permits only.
No selection rerun. All held corporate actions, absent raw bars, and source changes fail closed.
"""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent
OLD=E/'lifecycle_v1';AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=D('24000');SLOT=D('48000');RISK=D('3000');SLIP=D('.0005');END=pd.Timestamp('2026-06-30')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'BRIDGED_ROUNDS.csv').exists(), 'No overwrite'
z=pd.read_csv(OLD/'ROUNDS.csv');original_actions=pd.read_csv(OLD/'ACTIONS.csv')
u=z[z.arm.eq('A_UNION_B')&z.window.eq('2022')&z.status.str.contains('UNKNOWN')].copy()
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
panel_path=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
panel=pd.read_parquet(panel_path).sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));cal=cal[cal<=END]
sector={s:g.set_index('day').M3_candidate.to_dict() for s,g in panel.groupby('sector')}
raw={};facts={};cp={};capacity={};meta={};load_count=0;hashes={};closecache={}
rounds=[];decisions=[];actions=[];blocks=[];entry_bridges={}
source=(OLD/'simulate.py').read_text();tree=ast.parse(source)
names={'finite','true','false','lineage','flags','DayFrame','load','getmeta','fee','size','checkclose','act','record','freeze_unknown','mark','entry_open','held_open','held_close'}
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
  text=ast.get_source_segment(source,node)
  if node.name=='entry_open':
   needle=" if not finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):return freeze_unknown(states,sid,st,'FACTOR_AT_ENTRY_UNKNOWN',d)"
   repl=""" bridge=entry_bridges.get((sid,d))
 if bridge is not None:
  assert st.get('entry_status','NO_CONFIRMED_ENTRY')=='NO_CONFIRMED_ENTRY'
  assert bridge['split_ratio']==1 and bridge['cash_per_old_share']>0
  assert np.isclose(z['adjustment_factor'],bridge['factor_current'],rtol=1e-11)
  prev=dict(prev);prev['adjustment_factor']=bridge['factor_current']
 if not finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):return freeze_unknown(states,sid,st,'FACTOR_AT_ENTRY_UNKNOWN',d)"""
   assert text.count(needle)==1;text=text.replace(needle,repl)
  exec(compile(text,str(OLD/'simulate.py')+':bounded_definition','exec'),globals())
# Audit the first interruption only. Do not assign return labels from these snapshots.
aud=[];snapshots=[]
for rr in u.to_dict('records'):
 sid=rr['sid'];d=pd.Timestamp(rr['status_day']);load(sid);f=raw[sid].frame
 ap=AS/'inputs-v1/actions'/f'{sid}.json';a=read(ap);hashes[str(ap)]=sha(ap)
 es=[x for x in a['events'] if x['effective_date']==rr['status_day']];ev=es[0] if len(es)==1 else {}
 prev=f[f.index<d].iloc[-1];cur=f.loc[d] if d in f.index else None
 cash=float(ev.get('cash_per_old_share',0));ratio=float(ev.get('split_ratio',1))
 row={k:rr[k] for k in ['round_id','sid','name','signal_day','entry_day','status','status_day','entry_q','core_qty','add_qty','cashflow_to_date','last_mark_fraction']}
 row.update(action_count=len(es),classification=ev.get('classification'),raw_action_text=ev.get('raw_text'),cash_per_old_share=cash,split_ratio=ratio,paid_at=ev.get('paid_at'),new_shares_sellable_at=ev.get('new_shares_sellable_at'),announcement_date=ev.get('announcement_date'),record_date=ev.get('record_date'),action_source=str(ap),raw_rights_source=a['coverage_evidence'][0]['path'],previous_observation=str(prev.name.date()),raw_close_previous=float(prev.raw_close),factor_previous=float(prev.adjustment_factor),has_observation=cur is not None,raw_open_current=float(cur.raw_open) if cur is not None else None,factor_current=float(cur.adjustment_factor) if cur is not None else None,original_status_retained=True)
 if len(es)==1 and ev.get('classification')=='ordinary_cash_and_pro_rata_bonus' and cur is not None:
  pred=float(prev.adjustment_factor)*float(prev.raw_close)*ratio/(float(prev.raw_close)-cash)
  row.update(factor_predicted_from_previous_close_and_explicit_terms=pred,factor_relative_error=float(cur.adjustment_factor)/pred-1,signal_factor_matches=np.isclose(cur.adjustment_factor,pred,rtol=1e-11,atol=1e-12))
  q=int(rr['core_qty']+rr['add_qty']) if pd.notna(rr['core_qty']) else 0
  if q:
   snapshots.append(dict(round_id=rr['round_id'],sid=sid,day=rr['status_day'],old_total_shares=q,new_total_shares_exact=q*ratio,fractional_entitlement=(D(q)*D(str(ratio)))%1,gross_cash_entitlement=q*cash,naive_raw_open_inventory=q*float(cur.raw_open),bridged_gross_open_equity_before_fees_tax=q*ratio*float(cur.raw_open)+q*cash,naive_missing_entitlement=q*(ratio-1)*float(cur.raw_open)+q*cash,strict_ledger_status='UNKNOWN_PAY_TAX_ENTITLEMENT_AND_OR_SHARE_TRADABILITY_CLOCK'))
  if rr['status']=='FACTOR_AT_ENTRY_UNKNOWN':
   assert row['signal_factor_matches'] and ratio==1 and cash>0
   assert rr['entry_status']=='NO_CONFIRMED_ENTRY'
   entry_bridges[sid,d]=dict(factor_current=pred,cash_per_old_share=cash,split_ratio=ratio)
 aud.append(row)
au=pd.DataFrame(aud);au.to_csv(O/'UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv',index=False)
pd.DataFrame(snapshots).to_csv(O/'GROSS_ENTITLEMENT_SNAPSHOTS_NOT_RESULTS.csv',index=False)
target=u[u.status.eq('FACTOR_AT_ENTRY_UNKNOWN')].copy();assert len(target)==10
# Controls are fixed by sorted identity before outcomes; no corporate-action modification.
controls=z[z.arm.eq('A_UNION_B')&z.window.eq('2022')&z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].sort_values('round_id').head(3)
events=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day','previous_common_day'],low_memory=False).set_index('event_id')
for rr in pd.concat([target,controls]).to_dict('records'):load(rr['sid'])
for p in [Path(__file__),OLD/'simulate.py',OLD/'PROTOCOL.json',OLD/'ROUNDS.csv',OLD/'ACTIONS.csv',E/'SEALED_ALL_BIRTH_EVENTS.csv',U/'STOCK_MANIFEST.json',panel_path,B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']:hashes[str(p)]=sha(p)
protocol=dict(scope='Ten original 2022 A_UNION_B permits: only FACTOR_AT_ENTRY_UNKNOWN, all ordinary cash-only distributions. Three frozen closed controls.',entry_gate_patch='Replace previous factor for prior signal floor translation with F_previous*C_previous/(C_previous-cash_per_old_share). Original raw OPEN, fees, sizing and later logic unchanged.',no_existing_holdings_at_ex=True,dividend_entitlement_to_new_buyer=0,entry_formula_uses_current_close_high_low=False,selection_rerun=False,account_run=False,no_new_permits_after_repaired_exit=True,all_held_action_factor_changes_still_unknown=True,source_and_missing_open_still_unknown=True,tax_and_paydate_not_imputed=True,full_result_validity='Fixed-original-permit cohort only, not a recomputed A_UNION_B strategy; repaired exits may free stocks and affect later selection in a full rerun.',targets=target.round_id.tolist(),controls=controls.round_id.tolist(),source_hashes=hashes)
save('PRE_RUN_SEAL.json',protocol)
for rr in pd.concat([target,controls]).to_dict('records'):
 r=events.loc[rr['event_id']].to_dict();r['event_id']=rr['event_id'];d=pd.Timestamp(rr['signal_day']);r['day']=d
 ck=checkclose(r);assert ck['close_check']=='PASS'
 st=dict(r,state='BUY_PENDING',arm='A_UNION_B',round_id=rr['round_id'],signal_day=d,birth_end=pd.Timestamp('2022-12-31'),close_q=ck['close_q'],prior20_capacity=ck['prior20_capacity'])
 states={rr['sid']:st}
 for k,t in enumerate(cal):
  if t<=d:continue
  if rr['sid'] not in states or states[rr['sid']]['state']=='UNKNOWN':break
  st=states[rr['sid']]
  if st['state']=='BUY_PENDING':entry_open(states,rr['sid'],st,t)
  elif st['state']=='HELD':held_open(states,rr['sid'],st,t,cal[k-1])
  if rr['sid'] in states and states[rr['sid']]['state']=='HELD':held_close(states,rr['sid'],states[rr['sid']],t)
 if rr['sid'] in states and states[rr['sid']]['state']=='HELD':record(states[rr['sid']],'OPEN_CENSORED_AT_2026_06_30',END)
 if rr['sid'] in states and states[rr['sid']]['state']=='BUY_PENDING':record(states[rr['sid']],'BUY_PENDING_CENSORED_AT_DATA_END',END)
rz=pd.DataFrame(rounds);ac=pd.DataFrame(actions)
rz.to_csv(O/'BRIDGED_ROUNDS.csv',index=False);ac.to_csv(O/'BRIDGED_ACTIONS.csv',index=False)
# Verify original controls and independently sum action cash, counts and original source immutability.
qa=[]
for rr in rz.to_dict('records'):
 aa=ac[ac.round_id.eq(rr['round_id'])];q=0;cash=D(0);spent=D(0)
 for a in aa.to_dict('records'):
  n=int(a['q']);p=D(str(a['price']));fee_=D(str(a['fee']));buy=a['side'].startswith('buy')
  if buy:q+=n;cash-=n*p+fee_;spent+=n*p+fee_
  else:q-=n;cash+=n*p-fee_
  assert q>=0
 assert abs(float(cash)-rr['cashflow_to_date'])<1e-8
 assert abs(float(spent)-rr['total_buy_cash'])<1e-8
 if rr['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':assert q==0
 qa.append(dict(round_id=rr['round_id'],inventory=q,cash_error=float(cash)-rr['cashflow_to_date'],spent_error=float(spent)-rr['total_buy_cash']))
for rr in controls.to_dict('records'):
 actual=rz[rz.round_id.eq(rr['round_id'])].iloc[0]
 for col in ['status','entry_day','exit_day']:
  assert str(actual[col])[:10]==str(rr[col])[:10],(rr['round_id'],col,actual[col],rr[col])
 assert abs(actual.net_pnl-rr['net_pnl'])<1e-8
 a=ac[ac.round_id.eq(rr['round_id'])].reset_index(drop=True);b=original_actions[original_actions.round_id.eq(rr['round_id'])].reset_index(drop=True)
 for col in ['side','q','price','fee']:
  assert a[col].equals(b[col]) or (col in ['price','fee'] and np.allclose(a[col],b[col],rtol=0,atol=1e-10)),(rr['round_id'],col)
assert all(sha(p)==h for p,h in hashes.items()),'Source mutated'
patched=rz[rz.round_id.isin(target.round_id)];closed=patched[patched.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
base=z[z.arm.eq('A_UNION_B')&z.window.eq('2022')&z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')]
combined=pd.concat([base,closed],ignore_index=True)
def stats(f):
 wins=f[f.net_pnl>0];losses=f[f.net_pnl<0];return dict(closed=len(f),wins=len(wins),losses=len(losses),win_rate=len(wins)/len(f),mean_win_loss_yuan=wins.net_pnl.mean()/(-losses.net_pnl.mean()),mean_return_on_buy_cash=f.net_return_on_buy_cash.mean())
summary=dict(original_unknown=len(u),status_counts=u.status.value_counts().to_dict(),factor_interruption_matched_explicit_terms=int(au[au.status.str.startswith('FACTOR')].action_count.eq(1).sum()),factor_formula_matches=int(au[au.status.str.startswith('FACTOR')].signal_factor_matches.fillna(False).sum()),factor_class_counts=au[au.status.str.startswith('FACTOR')].groupby(['split_ratio']).size().to_dict(),original_birth_quarters=u.signal_day.map(lambda x:str(pd.Timestamp(x).to_period('Q'))).value_counts().to_dict(),bridged_permits=len(patched),bridged_status_counts=patched.status.value_counts().to_dict(),remaining_original_unknown=len(u)-len(closed)-int(patched.status.str.endswith('NOFILL').sum()),original_closed_distribution=stats(base),fixed_original_permit_distribution_if_appended=stats(combined),full_lifecycle_result_not_recomputed=True,control_exact_count=len(controls),source_hashes_unchanged=True,account_runs=0,new_selection_runs=0,round_cash_reconciliation=qa)
save('SUMMARY.json',summary)
save('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
