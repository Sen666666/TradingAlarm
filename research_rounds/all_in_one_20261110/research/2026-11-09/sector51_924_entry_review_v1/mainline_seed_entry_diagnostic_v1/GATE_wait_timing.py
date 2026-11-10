from pathlib import Path
import hashlib,json,copy
O=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1/mainline_seed_entry_diagnostic_v1')
src=(O/'GATE_diagnose.py').read_text()
# Reuse only local loading and CP-state functions, never import a strategy engine.
exec(compile(src[:src.index('results=[];life=[];states={}')],'FIXED_GATE_LOCAL_HELPERS','exec'))
contract=ROOT/'mainline_structural_maturity_design_v1/DESIGN.md'
assert hashlib.sha256(contract.read_bytes()).hexdigest()=='79ebeb73457914656eb70e4ecb59a58008e57d7cb92dd1296dd86d3577efbe12'
hashes[str(contract)]=hashlib.sha256(contract.read_bytes()).hexdigest()
results=rd(O/'GATE_ACTUAL_ENTRY_ROWS.json')
names={'新华保险','禾望电气','爱旭股份','新强联','大名城','浦东金桥','新城控股','新国都','先导智能','东方明珠','中文在线','金力永磁','西部矿业','太极实业','金龙鱼','神农集团','沪农商行'}
chosen=[r for r in results if r['gate_status']!='PASS' and r['name'] in names]
worst=sorted([r for r in results if r['gate_status']=='STRUCTURE_WAIT' and r['seed_day']>'2024-11-06' and not r['final_qty']],key=lambda r:D(r['net']))[:4]
openfailed=[r for r in results if r['gate_status']=='PASS' and not r['actual_next_OPEN_gate_pass']]
selected={r['round_id']:r for r in chosen+worst+openfailed}
timing=[]
for r in selected.values():
 st,out=trace_to_plan(r);path=[];first_G=None;first_residual=None;cancel_day=None;blocked_day=None;eligible=None;prior=None
 basepx=frames[r['sid']].loc[pd.Timestamp(r['seed_day'])]
 original_open=dec(basepx.raw_open)*dec(basepx.adjustment_factor)
 for ds in [d for d in days if d>=r['plan_day']]:
  if ds>r['plan_day']:
   op=at_open(st,ds)
   if op['base'] in ['CANCEL','BLOCKED']:
    path.append(dict(day=ds,phase='OPEN',**op))
    if op['base']=='CANCEL':cancel_day=ds
    else:blocked_day=ds
    break
   # Prior CLOSE freezes F and selected CP; never look at today's new receipt.
   if prior and prior['ready'] and op['base']=='PASS':
    gate_ok=prior['scope']=='RESIDUAL' or OR(prior['F'],op.get('CP_state',-1))==1
    path.append(dict(day=ds,phase='OPEN',prior_close=prior['day'],prior_scope=prior['scope'],frozen_F=prior['F'],open_CP_state=op.get('CP_state'),gate_and_I_source_pass=gate_ok,adjusted_open=op.get('adjusted_open')))
    if gate_ok and eligible is None:
     eligible=dict(close_day=prior['day'],next_OPEN=ds,scope=prior['scope'],via=prior['via'],CP_receipt_day=prior.get('CP_receipt_day'),CP_floor=prior.get('CP_floor'),adjusted_open=op['adjusted_open'],open_vs_original_pct=str(100*(D(op['adjusted_open'])/original_open-1)),not_executed=True)
   out=at_close(st,ds,r['sector51'])
  if out['base'] in ['CANCEL','BLOCKED']:
   path.append(dict(day=ds,phase='CLOSE',**out))
   if out['base']=='CANCEL':cancel_day=ds
   else:blocked_day=ds
   break
  s=sec[(ds,r['sector51'])]
  scope='MATURE' if s['M']==1 and finite(s['E']) and s['E']>0 and s['state']==1 else 'RESIDUAL' if s['M']==0 and s['state']==1 else 'PAUSED_OR_UNKNOWN'
  if out['base']=='PASS' and out['gate']==1 and first_G is None:first_G=ds
  if out['base']=='PASS' and scope=='RESIDUAL' and first_residual is None:first_residual=ds
  ready=out['base']=='PASS' and (scope=='RESIDUAL' or scope=='MATURE' and out['gate']==1)
  via='ORIGINAL_RESIDUAL_SCOPE' if scope=='RESIDUAL' else 'F_AND_CP' if out['F']==out['CP_state']==1 else 'F' if out['F']==1 else 'CP' if out['CP_state']==1 else None
  path.append(dict(day=ds,phase='CLOSE',scope=scope,ready_for_original_eligibility_review=ready,**out))
  prior=dict(day=ds,scope=scope,ready=ready,F=out['F'],via=via,CP_receipt_day=out.get('CP_receipt_day'),CP_floor=out.get('CP_floor'))
 timing.append(dict(round_id=r['round_id'],sid=r['sid'],name=r['name'],sector51=r['sector51'],original_signal_day=r['signal_day'],baseline_plan_CLOSE=r['plan_day'],baseline_actual_OPEN=r['seed_day'],baseline_original_net=r['net'],initial_gate_status=r['gate_status'],initial_next_OPEN_gate_pass=r['actual_next_OPEN_gate_pass'],first_G_true_CLOSE=first_G,first_reclassified_RESIDUAL_CLOSE=first_residual,first_original_false_cancellation=cancel_day,blocked_day=blocked_day,first_quote_I_source_and_gate_eligible_OPEN=eligible,path=path,cp_events=st['log'],input_audit_through_cancel=st['audit'],notes=['Continues as a hypothetical unfilled original ticket only to distinguish first G, first RESIDUAL scope, and original false cancellation. It does not place an order at the first candidate opportunity.','RESIDUAL removes only this new gate; original event_cap, event identity/spend, legal quantity, capacity, fees, cash and funding still apply.','Shown nextOPEN is the earliest quote/source/I/CP check pass, not an executable funded fill; baseline price differences are not returns.']))
# Highlight source-proof opens and exact same-day CP receipts separately.
passed=[r for r in results if r['gate_status']=='PASS']
via=[]
for label,aa in [('ALL',passed),('LATE',[r for r in passed if r['seed_day']>'2024-11-06'])]:
 for kind in ['F_AND_CP','F','CP']:
  a=[r for r in aa if r['gate_via']==kind]
  via.append(dict(cohort=label,via=kind,n=len(a),net=sum((D(r['net']) for r in a),Z),same_signal_receipt=sum(r['CP_receipt_day']==r['signal_day'] for r in a)))
# Formula and lifecycle sanity without market replay.
assert OR(1,-1)==1 and OR(-1,0)==-1 and OR(0,0)==0 and OR(-1,1)==1
for r in results:
 o=r['CP_observation']
 if r['CP_state']==1:
  assert r['CP_receipt_day']>=r['signal_day'] and D(o['adjusted_close'])>D(r['CP_floor']) and not o['CP_invalid'] and not o['CP_history_unknown']
assert not any(r['gate_status'] in ['BLOCKED_SOURCE_BRIDGE','CANCEL_ORIGINAL_REQUEST'] for r in results)
save('WAIT_TIMING_FOCUS',timing);save('PASS_ROUTE_SUMMARY',via);save('NEXT_OPEN_FAILED_ROWS',openfailed);save('WAIT_SOURCE_HASHES',hashes)
print(json.dumps(dict(routes=via,focus=[{k:r[k] for k in ['round_id','name','baseline_plan_CLOSE','baseline_actual_OPEN','baseline_original_net','initial_gate_status','first_G_true_CLOSE','first_reclassified_RESIDUAL_CLOSE','first_original_false_cancellation','blocked_day','first_quote_I_source_and_gate_eligible_OPEN']} for r in timing],open_failed=[{k:r[k] for k in ['round_id','name','plan_day','seed_day','net','CP_receipt_day','CP_floor','actual_next_OPEN_check']} for r in openfailed]),ensure_ascii=False,default=str))
