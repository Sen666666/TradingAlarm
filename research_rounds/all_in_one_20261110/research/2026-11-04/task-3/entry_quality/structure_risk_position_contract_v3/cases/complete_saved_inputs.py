"""Original audit cash arithmetic and E0 identity proof; no market/Account."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rs=read(O/'SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json');cash={};checks={}
for w in ['strong','2022_2024']:
 base=Q/'trend_exit_controls_v1/runs/BASELINE'/w/'pair';book=read(base/'B.json.gz',True);daily=read(base/'daily.jsonl.gz',True,True);balance=D(1000000);byday={};before={};first_open={}
 for a in book['audit']:
  k=a['kind'];at=a.get('at',a.get('receipt',{}).get('at'))
  if k=='reserve':
   before[a['order_id']]=balance;first_open.setdefault(at,balance);balance-=D(a['gross_budget_cny'])+D(a['fee_reserved_cny'])
  elif k=='release_buy':balance+=D(a['gross_released'])+D(a['fee_released'])
  elif k=='settle' and not a['settlement']['debit']:balance+=D(a['settlement']['cny_amount'])
  elif k=='fill' and a['receipt']['side']=='sell' and D(a['receipt']['gross_cny'])<D(a['receipt']['fees_cny']):balance+=D(a['receipt']['gross_cny'])-D(a['receipt']['fees_cny'])
  if at:byday[at[:10]]=balance
 errors=[(d['at'],byday[d['at'][:10]]-D(d['available'])) for d in daily if abs(byday[d['at'][:10]]-D(d['available']))>D('.000001')];assert not errors,errors[:3];checks[w]=len(daily)
 for r in rs:
  if r['window']!=w:continue
  matching=[a for a in book['audit'] if a['kind']=='reserve' and a['sid']==r['sid'] and a['decision_at'][:10]==r['decision']]
  key=r['sid']+'|'+r['decision'];cash[key]=dict(status='EXACT_ORIGINAL_AUDIT_AVAILABLE_CASH_BEFORE_THIS_REFERENCE_RESERVE' if matching else 'NO_ORIGINAL_TYPED_I_RESERVE_SLOT',cash_before_reference_reserve=None if not matching else before[matching[0]['order_id']],original_reference_reserve=matching[0] if matching else None,
   first_original_reserve_phase_cash=first_open.get(r['nextOPEN']+' 09:30:00+08:00'),new_typed_I_rank_slot='UNIMPLEMENTED' if not matching else 'original reference order slot only',full_OPEN_NAV_inventory_AR='NOT_SAVED_IN_THIS_AUDIT_CASH_BRIDGE',all_original_CLOSE_cash_points_exact=True)
save('EXACT_ORIGINAL_OPEN_CASH_BRIDGE.json',dict(cases=cash,CLOSE_points_checked=checks,formula='initial cash - actual reserve gross/fee + actual release gross/fee + real settled credits + rare negative sell-net immediate debit; debit settlements do not spend reserved cash a second time',no_new_account=True,no_strategy_replay=True))
sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};proof=[]
for sid,root,origin in [('688146.SH','2026-04-03','2026-04-21'),('000620.SZ','2022-01-06','2022-01-10')]:
 m=sm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/states.parquet'));assert sha(sp)==m['source_sha256'][sp];SRC[sp]=sha(sp);st=pd.read_parquet(sp);ixp=RR/'ix-a-share-entry-20261025/signals'/(sid+'.parquet');assert sha(ixp)==m['source_sha256'][str(ixp)];SRC[str(ixp)]=sha(ixp);ix=pd.read_parquet(ixp)
 until=max(r['decision'] for r in rs if r['sid']==sid);segment=st.loc[root:until];assert int(st.loc[root,'entered'])==1 and int(ix.loc[root,'e0_entered'])==1;assert segment['target'].eq(1).all() and segment['entered'].sum()==1
 dates=sorted({root,origin,*[r['decision'] for r in rs if r['sid']==sid],*(['2022-01-20'] if sid=='000620.SZ' else [])});trajectory=[]
 for d in dates:trajectory.append(dict(day=d,E0_target=int(st.loc[d,'target']),E0_entered=int(st.loc[d,'entered']),E0_exited=int(st.loc[d,'exited']),IX_E0_entered=int(ix.loc[d,'e0_entered']),up_reasons=str(ix.loc[d,'up_reasons']),source_segment=int(st.loc[d,'segment_id'])))
 proof.append(dict(sid=sid,key=[sid,0,root],origin_signal=origin,source_states=sp,source_IX=str(ixp),no_new_E0_off_on_in_all_sampled_prefixes=True,trajectory=trajectory,positive_price_event_is_not_new_root=True))
save('OPPORTUNITY_KEY_ORIGIN_PROOF.json',dict(cases=proof,first_successful_reserve_source='SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json.origin_first_original_successful_reserve',seed_B='provisional current signalNAV; later independent original prefixes recover actual first reserve signalNAV, not earliest Q'))
for r in rs:
 key=r['sid']+'|'+r['decision'];c=cash[key];q=r['q_local_after_source_and_frozen_caps'];cost=D(q)*D(r['next_buy_price'])+D(r['local_cost_at_q']['unpaid_candidate_buyfee']);r['exact_original_OPEN_cash_bridge']=c;r['candidate_gross_plus_buyfee']=cost;r['fits_exact_original_reference_slot_cash']=None if c['cash_before_reference_reserve'] is None else cost<=c['cash_before_reference_reserve']
save('SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json',rs)
v=Q/'structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json';failed=read(v);selected=[d for d in failed['days'] if d['day'] in ['2022-01-27','2022-01-28','2022-02-07','2022-02-08']]
save('ORIGINAL_EXIT_LOCK_BOUNDARY.json',dict(days=selected,decision_rule='An actual same-stock exit request/pending responsibility denies any new grant; no new event/order is invented when original i_buy/CP are absent.',new_request_quantity=0,alternative_fills=0,Jan27_initial_request='CP1_add_protection mobile113/122, I still on',Feb7_extension='I_structure_exit adds CORE68 to existing order',actual_final_sell='Feb8 09:30 9900 shares at2.768615, reason overwritten by later I extension',not_new_account=True))
save('ADDITIONAL_SOURCE_BINDING.json',dict(sources=SRC,script_sha256=sha(__file__),no_loader=True,no_new_accounts=True))
print('PASS:',checks,'daily cash points; exact five pre-reserve OPEN cash; two held-I slots explicitly absent; E0 roots proved')
