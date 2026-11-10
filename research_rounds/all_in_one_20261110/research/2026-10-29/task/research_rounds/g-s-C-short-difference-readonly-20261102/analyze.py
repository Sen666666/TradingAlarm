"""Saved-JSON attribution only. Never imports or advances an account runner."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
from datetime import datetime
import json, hashlib, traceback
HERE=Path(__file__).resolve().parent;W=HERE.parent;R=W/'g-s-C-month-continuation-20261102';OLD=R/'short_window_analysis';Z=D(0);READS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);raw=p.read_bytes();READS[str(p)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
def save(name,x):
 p=HERE/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,default=str,ensure_ascii=False,sort_keys=True,indent=2)+'\n');t.replace(p)
def money(v):return f'{D(v):,.2f}'
def dt(s):return datetime.fromisoformat(s)
def same(a,b):return dt(a)==dt(b)
def eq(a,b):assert abs(a-b)<D('0.000000001'),(a,b)
def entry_key(z,a):
 m=a['capital_meta'][str(z['layer'])];s=a['supports'][m['order']];i=s['original_intent'];c=s.get('receipt') or {}
 return (z['sid'],z['signal_at'],z['opened'],z['role'],z['pool'],z['purpose'],json.dumps(i.get('epoch'),sort_keys=True),c.get('event_id'),c.get('source'))
def aggregate(rr):
 return {k:sum((D(z[k]) for z in rr),Z) for k in ('net','gross','realized_net','unrealized_net','buy_gross','buy_fee','sell_fee','buy_qty')}
def close_view(arm,clock):
 day=clock[:10];candidates=[R/'runs'/arm/(day+'-CLOSE.json'),W/'g-s-C-nextsession-native-20261102/runs'/arm/'full'/(day+'-CLOSE.json'),W/'g-s-C-two-day-finance-20261102/runs'/arm/(day+'-CLOSE.json')]
 if arm=='2022-C10':candidates.append(W/'g-s-C-two-day-finance-20261102/runs/2022-C10-recovered'/(day+'-CLOSE.json'))
 for p in candidates:
  if p.exists():return read(p),str(p)
 return None,None
def sell_leg(t,a):
 parts=[]
 for p in t['parts']:
  m=a['capital_meta'][str(p['layer'])];ds=[dict(id=k,**v) for k,v in a['exit_duties'].items() if v['layer']==p['layer'] and dt(v['earliest_at'])<=dt(t['at']) and dt(v['requested_at'])<dt(t['at']) and set(v['reasons'])&set(p['reason'].split(','))]
  parts.append(dict(**p,role=m['role'],pool=m['pool'],purpose=m['purpose'],request_evidence=ds))
 return dict(receipt=t['receipt_id'],at=t['at'],shares=t['shares'],gross=D(t['gross_cny']),fee=D(t['fees_cny']),parts=parts)
def buy_leg(t,a):
 m=a['capital_meta'][str(t['layer'])];s=a['supports'][m['order']];i=s['original_intent']
 return dict(receipt=t['receipt_id'],at=t['at'],layer=t['layer'],shares=t['shares'],gross=D(t['gross_cny']),fee=D(t['fees_cny']),role=m['role'],pool=m['pool'],purpose=m['purpose'],decision_at=t['signal_at'],order=m['order'],original_core_eligible_flag=i['core'],original_stock_Q=i['stock_q'],original_I_valid=i['i_valid'],original_priority=s['priority'],original_receipt=(s.get('receipt') or {}).get('event_id'),C_certificate=s.get('C_certificate'))
def known_together(arm,sid,b,sales):
 view,path=close_view(arm,b['decision_at']);proof=[]
 for s in sales:
  for p in s['parts']:
   clocks=sorted({x['requested_at'] for x in p['request_evidence']})
   proof.append(dict(sell_receipt=s['receipt'],layer=p['layer'],request_times=clocks,same_decision=any(same(c,b['decision_at']) for c in clocks),all_request_times_equal_decision=bool(clocks) and all(same(c,b['decision_at']) for c in clocks),buy_decision_after_actual_sale=dt(b['decision_at'])>dt(s['at'])))
 result=dict(each_sell_part=proof,both_directions_known_same_decision=bool(proof) and all(p['all_request_times_equal_decision'] for p in proof),saved_close=path)
 if view:
  raw=[p for p in view['pending'] if p['sid']==sid]
  plan=view['results'][-1]['projection'];a=view['account'];ids={p['layer'] for s in sales for p in s['parts']};floors=[]
  for z in a['layers']:
   if z['id'] not in ids:continue
   f=a['facts_floors'].get(z['sid']) if z['kind']=='core' else z['floor'];factor=a['market_factors'].get(z['sid']);floors.append(dict(layer=z['id'],qty=z['qty'],role=a['capital_meta'][str(z['id'])]['role'],raw_floor=D(f)/D(factor) if f is not None and factor is not None else None))
  result.update(raw_pending=[{k:i.get(k) for k in ('sid','core','i_valid','stock_q','priority','cp_floor','I_floor','clock','deadline')} for i in raw],planned_C_Q=plan['Q'].get(sid,0),planned_C_D=plan['D'].get(sid,0),known_old_floors=floors)
  if result['both_directions_known_same_decision']:assert raw and any(same(i['clock']['decision_at'],b['decision_at']) for i in raw)
 elif result['both_directions_known_same_decision']:raise AssertionError('same-batch claim needs original saved CLOSE')
 open_path=R/'runs'/arm/(b['at'][:10]+'-OPEN.json')
 if open_path.exists():
  op=read(open_path)['account'];layer=next(z for z in op['layers'] if z['id']==b['layer']);f=op['facts_floors'].get(sid) if b['role']=='core' else layer['floor'];factor=op['market_factors'].get(sid)
  result.update(actual_new_floor_raw_at_buy=D(f)/D(factor) if f is not None and factor is not None else None,saved_actual_open=str(open_path))
 return result
def main():
 index=read(OLD/'ARTIFACT_SHA256.json');assert sha(OLD/'ARTIFACT_SHA256.json')=='b2454c2930dde09cb687e2c2edd51d1be212c6e09bac626dbe15efbba330982f'
 all_layers=read(OLD/'ALL_LAYERS.json');results=read(OLD/'RESULTS.json')['rows'];endpoints=read(OLD/'CONTINUATION_CHECKPOINTS.json');names=read(R/'inputs/2022/metadata.json');accounts={};entries={};turns={};role_cycles={};cross_adds={}
 for arm,zz in all_layers.items():
  fixed=next(e for e in endpoints if e['arm']==arm);p=Path(fixed['checkpoint']).with_suffix('.json');assert sha(p)==index[str(p.relative_to(R))];x=read(p);assert x['last_completed'][:10]==fixed['cursor'][:10];a=x['account'];accounts[arm]=a;rr=[]
  for z in zz:
   buyfee=D(z['buy_fee']);sellfee=sum((D(s['fee_cny']) for s in z['actual_sell_parts']),Z);net=D(z['total_contribution']);rr.append(dict(key=entry_key(z,a),sid=z['sid'],name=names[z['sid']]['name'],opened=z['opened'],signal_at=z['signal_at'],role=z['role'],pool=z['pool'],purpose=z['purpose'],buy_qty=D(z['initial_qty']),buy_gross=D(z['buy_gross']),buy_fee=buyfee,sell_fee=sellfee,net=net,gross=net+buyfee+sellfee,realized_net=D(z['realized_trade_PNL']),unrealized_net=D(z['unrealized_net_buy_cost'])))
  entries[arm]=rr
  groups=defaultdict(list)
  for t in a['trades']:groups[(t['at'],t['security_id'])].append(t)
  both=[]
  for (at,sid),ts in groups.items():
   bb=[t for t in ts if t['side']=='buy'];ss=[t for t in ts if t['side']=='sell'];assert len(bb)<=1
   if not bb or not ss:continue
   b=buy_leg(bb[0],a);sales=[sell_leg(s,a) for s in ss]
   both.append(dict(sid=sid,name=names[sid]['name'],at=at,buy=b,sells=sales,cross_role=any(p['role']!=b['role'] for s in sales for p in s['parts']),gross_two_sided=sum((s['gross'] for s in sales),Z)+b['gross'],fees=sum((s['fee'] for s in sales),Z)+b['fee'],clock_evidence=known_together(arm,sid,b,sales)))
  turns[arm]=both
  pending=defaultdict(list);held=defaultdict(int);held_layers={};cycles=[];adds=[]
  for t in a['trades']:
   sid=t['security_id']
   if t['side']=='sell':
    held[sid]-=t['shares'];pending[sid].append(sell_leg(t,a))
    for p in t['parts']:held_layers[p['layer']]-=p['shares']
   else:
    b=buy_leg(t,a);ss=pending.pop(sid,[]);roles={p['role'] for s in ss for p in s['parts']};before=held[sid]
    if ss and any(r!=b['role'] for r in roles):
     cycles.append(dict(sid=sid,name=names[sid]['name'],buy=b,sells=ss,held_before_buy=before,flat_reentry=before==0,same_open=all(same(s['at'],b['at']) for s in ss),gross_two_sided=sum((s['gross'] for s in ss),Z)+b['gross'],fees=sum((s['fee'] for s in ss),Z)+b['fee'],clock_evidence=known_together(arm,sid,b,ss)))
    oldroles={a['capital_meta'][str(lid)]['role'] for lid,q in held_layers.items() if q and next(z['sid'] for z in a['layers'] if z['id']==lid)==sid}
    if before and b['role'] not in oldroles:adds.append(dict(sid=sid,at=b['at'],buy=b,existing_roles=sorted(oldroles),not_a_sell_buy_roundtrip=True))
    held[sid]+=t['shares'];held_layers[t['layer']]=t['shares']
  assert {s:q for s,q in held.items() if q}==a['balance']['quantities']
  role_cycles[arm]=cycles;cross_adds[arm]=adds
 attribution={}
 for win in ('2022','2025_26'):
  by={};sids={}
  for mode in ('C10','C_BATCH20'):
   by[mode]=defaultdict(list)
   for z in entries[win+'-'+mode]:by[mode][z['key']].append(z)
   sids[mode]={z['sid'] for z in entries[win+'-'+mode]}
  classes=defaultdict(lambda:dict(gross_delta=Z,keys=0));detail=[]
  for key in sorted(set(by['C10'])|set(by['C_BATCH20']),key=str):
   aa=by['C10'].get(key,[]);bb=by['C_BATCH20'].get(key,[]);A=aggregate(aa);B=aggregate(bb)
   if aa and bb:cat='same_entry_different_quantity' if A['buy_qty']!=B['buy_qty'] else 'same_entry_equal_quantity_different_holding_exit'
   else:cat='different_entry_or_role_same_stock' if key[0] in sids['C10']&sids['C_BATCH20'] else 'stock_exclusive_participation'
   delta=B['gross']-A['gross'];classes[cat]['gross_delta']+=delta;classes[cat]['keys']+=1
   detail.append(dict(key=key,name=names[key[0]]['name'],category=cat,C10=A,C20=B,net_delta=B['net']-A['net'],gross_delta=delta))
  A=aggregate(entries[win+'-C10']);B=aggregate(entries[win+'-C_BATCH20']);fee_saved=A['buy_fee']+A['sell_fee']-B['buy_fee']-B['sell_fee'];navA=D(accounts[win+'-C10']['balance']['nav']);navB=D(accounts[win+'-C_BATCH20']['balance']['nav'])
  eq(sum((v['gross_delta'] for v in classes.values()),Z)+fee_saved,navB-navA)
  eq(B['realized_net']-A['realized_net']+B['unrealized_net']-A['unrealized_net'],navB-navA)
  med={mode:sum((e['net'] for e in entries[win+'-'+mode] if e['opened'][:10]=='2022-01-07' and e['sid'] in {'600285.SH','600572.SH','600332.SH','600535.SH','600329.SH'}),Z) for mode in ('C10','C_BATCH20')}
  meddiff=med['C_BATCH20']-med['C10'];other=defaultdict(lambda:Z)
  for d in detail:
   ismed=d['key'][2][:10]=='2022-01-07' and d['key'][0] in {'600285.SH','600572.SH','600332.SH','600535.SH','600329.SH'}
   if not ismed:other[d['key'][0]]+=d['net_delta']
  eq(sum(other.values(),Z)+meddiff,navB-navA)
  attribution[win]=dict(wealth_delta_C20_minus_C10=navB-navA,gross_price_accounting_categories=dict(classes),fee_saved=fee_saved,buy_fee_saved=A['buy_fee']-B['buy_fee'],sell_fee_saved=A['sell_fee']-B['sell_fee'],net_realized_delta=B['realized_net']-A['realized_net'],net_unrealized_delta=B['unrealized_net']-A['unrealized_net'],Jan7_medicine_net_by_arm=med,Jan7_medicine_net_delta=meddiff,other_net_delta=navB-navA-meddiff,other_stock_net_deltas=[dict(sid=s,name=names[s]['name'],delta=v) for s,v in sorted(other.items(),key=lambda p:(p[1],p[0]))],entry_details=detail,interpretation='accounting partitions, NOT independent causal effects; fees already embedded in net table; do not add fee saving a second time; equal-entry differing quantity includes later exit/holding decisions')
 stats={}
 for arm in entries:
  def total(rr):return dict(episodes=len(rr),stocks=len({r['sid'] for r in rr}),gross_two_sided=sum((r['gross_two_sided'] for r in rr),Z),fees=sum((r['fees'] for r in rr),Z),same_decision_known=sum(r['clock_evidence']['both_directions_known_same_decision'] for r in rr))
  stats[arm]=dict(same_open_all_roles=total(turns[arm]),same_open_cross_role=total([r for r in turns[arm] if r['cross_role']]),sell_since_previous_buy_then_different_role=total(role_cycles[arm]),cross_role_add_without_liquidation_count=len(cross_adds[arm]))
 save('ATTRIBUTION.json',attribution);save('ROUNDTRIPS.json',dict(stats=stats,same_open=turns,cross_role_reentry_episodes=role_cycles,cross_role_adds=cross_adds,definitions='Each same-stock same-open group counted once; cross-day role episodes attach ALL actual sells since previous actual buy to the next actual buy, no sell reused. Gross/fees cover these sell+rebuy legs only, not original acquisition. Cross-arm instances are not independent opportunities. No hypothetical netting cost claimed.'))
 archive_path=R/'archives/grant002/ARCHIVE_MAP.json';archive=read(archive_path) if archive_path.exists() else {}
 for relative,h in index.items():
  p=Path(archive[relative]['archive']) if relative in archive else R/relative
  assert sha(p)==h,'old frozen artifact changed: '+relative
 bindings=read(OLD/'BINDINGS.json')
 for name,key in [('month_runtime.py','source_runtime_sha256'),('run_month.py','entry_sha256'),('POLICY_INPUT_IDENTITY.json','policy_input_identity_sha256')]:assert sha(R/name)==bindings[key]
 save('CHECKS.json',dict(passed=True,wealth_accounting_exact=True,realized_unrealized_bridge_exact=True,medicine_plus_all_others_exact=True,actual_share_rollforward_exact=True,same_batch_claims_checked_against_original_saved_CLOSE=True,old_214_frozen_artifact_hashes_exact=len(index),runtime_entry_input_identity_exact=True,account_events_executed=0,source_code_changed=False,financial_outputs_changed=False))
 save('READ_INPUTS.json',READS)
 print(json.dumps(dict(attribution={k:{x:v[x] for x in ('wealth_delta_C20_minus_C10','fee_saved','net_realized_delta','net_unrealized_delta','Jan7_medicine_net_delta','other_net_delta','gross_price_accounting_categories')} for k,v in attribution.items()},stats=stats),default=str,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),account_events=0));raise
