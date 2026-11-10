"""Independent native audit-order classifier and post-Oct8 held/new money bridge.
No imported analysis reader/price engine. Ending inventory is zero in both books.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0);EPS=D('.000001')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def near(a,b,l):assert abs(a-b)<EPS,(l,a,b)
def ser(x):
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {k:ser(v) for k,v in x.items()}
 if isinstance(x,list):return [ser(v) for v in x]
 return x
out={'status':'PASS_POST_OCT8_NATIVE_ORDER_CLASSIFICATION_AND_GROUP_MONEY','scope':'Independent saved native audit fill-order + original split per-security aggregate quantity; zero analysis helper imports, zero new marks/accounts. First/add/reentry covers all actual fills since2022. Post new all end qty0; held-boundary money uses saved whole original inventory, not new marks. Does not independently review industry/name metadata or per-stock boundary marks.','cases':{},'source_sha256':{}}
summary=json.load(open(T/'attribution_2024_chain_v2/SUMMARY.json'))
for arm,p,name in [('No60','capacity_cost_guard_v1/runs/long-v1/arms/B/pair','B'),('D_GROSS10','market_gross_admission_native_v1/full-long-v1/pair','D_GROSS10')]:
 bp=T/p/(name+'.json.gz');dp=T/p/'daily.jsonl.gz';book=json.load(gzip.open(bp,'rt'));ds=[json.loads(l) for l in gzip.open(dp,'rt')];oct8=next(r for r in ds if r['at'][:10]=='2024-10-08');end=ds[-1];assert D(end['inventory'])==0
 tx={r['receipt_id']:r for r in book['trades']}; layer={r['id']:r for r in book['layers']};q=defaultdict(int);seen=set();actions={};orderids=[]
 for e in book['audit']:
  if e['kind'] in ('split','split_fraction_floor_proxy'):q[e['sid']]=int(D(q[e['sid']])*D(e['ratio']))
  if e['kind']!='fill':continue
  r=tx[e['receipt']['receipt_id']];sid=r['security_id'];n=int(r['shares']);orderids.append(r['receipt_id'])
  if r['side']=='buy':
   action='add_to_existing_stock' if q[sid]>0 else ('fresh_reentry_after_actual_flat' if sid in seen else 'first_actual_participation')
   actions[r['layer']]=action;seen.add(sid);q[sid]+=n
  else:q[sid]-=n;assert q[sid]>=0,(arm,e['at'],sid,q[sid])
 assert len(orderids)==len(book['trades']) and len(set(orderids))==len(orderids)
 assert all(v==0 for v in q.values())
 derived_actions=json.load(open(T/'attribution_2024_chain_v2'/(arm+'_ALL_HISTORICAL_ENTRY_ACTIONS.json')))
 assert len(derived_actions)==len(actions)
 for r in derived_actions:assert actions[r['layer']]==r['action'],(arm,r['layer'],'all history action mismatch')
 new=[r for r in book['trades'] if r['side']=='buy' and r['at'][:10]>'2024-10-08'];groups={}
 for action in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']:
  ls=[layer[t['layer']] for t in new if actions[t['layer']]==action];assert all(l['qty']==0 for l in ls)
  value=sum((D(l['cash'])+D(l['dividend']) for l in ls),Z);old=summary[arm]['post_oct8']['newfill_actions'][action]
  assert len(ls)==old['layers'];near(value,D(old['wealth']),(arm,action,'original final cash/div money'))
  pos=sum((max(Z,D(l['cash'])+D(l['dividend'])) for l in ls),Z);neg=sum((min(Z,D(l['cash'])+D(l['dividend'])) for l in ls),Z)
  near(pos,D(old['positive']),(arm,action,'positive'));near(neg,D(old['negative']),(arm,action,'negative'))
  groups[action]=dict(layers=len(ls),wealth=value,positive=pos,negative=neg)
 held=oct8['layers'];assert all(layer[l['id']]['qty']==0 for l in held)
 heldwealth=sum((D(layer[l['id']]['cash'])+D(layer[l['id']]['dividend'])-D(l['cash'])-D(l['dividend']) for l in held),Z)-D(oct8['inventory'])
 newwealth=sum((D(layer[t['layer']]['cash'])+D(layer[t['layer']]['dividend']) for t in new),Z)
 near(heldwealth+newwealth,D(end['nav'])-D(oct8['nav']),(arm,'held + new whole post NAV'))
 oldgroups=summary[arm]['post_oct8']['layer_groups']
 near(heldwealth,D(oldgroups['held_at_start_CLOSE']['wealth']),(arm,'held group'));assert len(held)==oldgroups['held_at_start_CLOSE']['layers']
 near(newwealth,D(oldgroups['new_actual_fill_in_phase']['wealth']),(arm,'new group'));assert len(new)==oldgroups['new_actual_fill_in_phase']['layers']
 out['cases'][arm]=dict(all_historical_actual_buy_actions_independently_matched=len(actions),post_new_actions=groups,post_held_layers=len(held),post_held_wealth=heldwealth,post_new_layers=len(new),post_new_wealth=newwealth,post_total_NAV_change=heldwealth+newwealth)
 for p1 in (bp,dp):out['source_sha256'][str(p1)]=sha(p1)
out['attribution_summary_sha256']=sha(T/'attribution_2024_chain_v2/SUMMARY.json');out['checker_sha256']=sha(__file__)
(O/'POST_OCT8_CLASSIFICATION_REVIEW.json').write_text(json.dumps(ser(out),ensure_ascii=False,indent=2))
print(json.dumps(ser(out['cases']),ensure_ascii=False,indent=2))
