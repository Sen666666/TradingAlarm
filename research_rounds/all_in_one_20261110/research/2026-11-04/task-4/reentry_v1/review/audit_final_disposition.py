from pathlib import Path
from decimal import Decimal, localcontext
from collections import Counter
import json, hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/reentry_v1');P=O/'funding_agent/private_projection';read=lambda p:json.loads(p.read_text());D=Decimal
entries_path=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/loss_correction/entry_risk_commitment_review/strong_ENTRIES.json')
entries=read(entries_path);context=read(O/'OLD50_ORIGINAL_OUTCOME_CONTEXT.json')['rows'];assert len(context)==50
by={(x['OPEN'],x['sid']):x for x in context};seen=set();changes=Counter();oldgross=D(0);newgross=D(0);oldfee=D(0);newfee=D(0);positive_shrunk=[];lost=[];no_fills=0
with localcontext() as ctx:
 ctx.prec=70
 for f in sorted(P.glob('OFF_2026*.json')):
  day=f.stem[4:];a=read(f)['orders'];b=read(P/f'ON_{day}.json')['orders'];bm={x['sid']:x for x in b}
  for x in a:
   c=by[day,x['sid']];seen.add((day,x['sid']));es=[e for e in entries if e['budget_order']==x['key']]
   assert [e['layer'] for e in es]==c['original_fill_layers']
   net=sum((D(e['net']) for e in es),D(0));cost=sum((D(e['cost']) for e in es),D(0))
   assert abs(net-D(c['original_lifecycle_net']))<D('1e-19') and abs(cost-D(c['original_cost']))<D('1e-19')
   q=bm[x['sid']]['quantity'] if x['sid'] in bm else 0
   change='lost' if not q else 'shrunk' if q<x['quantity'] else 'increased' if q>x['quantity'] else 'unchanged'
   assert c['oldq']==x['quantity'] and c['newq']==q and c['change']==change
   if x['sid'] in bm:assert x['role']==bm[x['sid']]['role']
   changes[change]+=1
   if not es:no_fills+=1
   if change=='shrunk' and net>0:positive_shrunk.append({'day':day,'sid':x['sid'],'oldq':x['quantity'],'newq':q,'original_net':str(net)})
   if change=='lost':lost.append({'day':day,'sid':x['sid'],'original_net':str(net)})
  oldgross+=sum((D(x['gross']) for x in a),D(0));newgross+=sum((D(x['gross']) for x in b),D(0));oldfee+=sum((D(x['fee']) for x in a),D(0));newfee+=sum((D(x['fee']) for x in b),D(0))
 assert len(seen)==50 and changes=={'shrunk':28,'lost':5,'increased':3,'unchanged':14}
 features=read(O/'ALL_FEATURES_PRE_OUTCOME.json');long=[x for x in features if x['window']=='long' and x['role']=='mobile'];strong=[x for x in features if x['window']=='strong' and x['role']=='mobile']
 paused=sum('ACT_paused' in x['original_barriers'] for x in long);clear=[x for x in long if not x['original_barriers']]
 assert paused==4429 and len(clear)==8307
 assert Counter(x['local_high_status'] for x in clear)=={'PASS':2600,'FAIL':5393,'UNKNOWN_PRICE_OR_SOURCE':284,'UNFORMED_FIRST_CLOSE':30}
 assert all(not x['original_barriers'] for x in strong)
 result={'status':'FINAL_PASS_STOP_ACCOUNT','files_reviewed':['REENTRY_FINDINGS.txt','OLD50_ORIGINAL_OUTCOME_CONTEXT.json'],'old50_original_outcome_associations_exact':True,'original_orders_with_no_actual_fill':no_fills,'original_order_changes':dict(changes),'common_stock_role_changes':0,'original_positive_layers_with_shrunk_orders':positive_shrunk,'lost_original_orders':lost,'gross_reservation_13_original_states':[str(oldgross),str(newgross)],'buy_fee_13_original_states':[str(oldfee),str(newfee)],'extra_buy_fee':str(newfee-oldfee),'scope':'Original lifecycle outcomes are attached to original OFF budget-order IDs only; no new strategy outcomes or proportional lost-profit estimates. All13 are independent original-state projections, not a new continuous account.','judgment':'Both local-high/risk-cap combination and confirmed-min-first stop before continuous account. The allocation component has valid observable resource response but rescues only1 of15 specific original rejected receipts and materially cuts some original profitable orders; this limited evidence does not establish a major-trend participation repair or economic advantage. Broader research objective remains unresolved.','new_accounts':0,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'REENTRY_FINDINGS.txt',O/'OLD50_ORIGINAL_OUTCOME_CONTEXT.json',entries_path,O/'review/PRIVATE_ON_13OPEN_RESULT_AUDIT.json']}}
 (O/'review/FINAL_REENTRY_AND_ALLOCATION_DISPOSITION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k not in ['source_sha256','original_positive_layers_with_shrunk_orders','lost_original_orders']},ensure_ascii=False,indent=2))
