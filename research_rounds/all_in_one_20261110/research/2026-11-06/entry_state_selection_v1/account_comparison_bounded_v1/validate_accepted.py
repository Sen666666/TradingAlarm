"""Read-only financial/event checks of saved arms; writes only verification artifacts."""
import json,hashlib,math
from pathlib import Path
from decimal import Decimal as D
O=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 p=O/name;assert not p.exists(),'Do not overwrite completed validation'
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def buys(r):return {x['sid']:x for x in r['journal'] if x['kind']=='real_buy_fill'}
allchecks=[];diff=[]
for day in ['2024-09-24','2026-01-15']:
 root=O/'bounded'/day;s=read(root/'SUMMARY.json');assert s['passed']
 resume=read(root/'RESUME_DECLARED.json')
 assert all(sha(p)==h for p,h in resume['reused_files'].items())
 assert all(sha(p)==h for p,h in resume['original_source_freeze'].items())
 roles=[]
 for rank in ['PVR','E31']:
  for mode in ['OPEN_PROXY','UNKNOWN_NO_FILL']:
   p=root/(rank+'__'+mode+'.json');r=read(p)
   t=r['trades'];bef=r['before'];aft=r['after_open'];exp=r['after_expiry_only'];at=r['open_at']
   grossb=sum((D(x['gross_cny']) for x in t if x['side']=='buy'),D(0));grosss=sum((D(x['gross_cny']) for x in t if x['side']=='sell'),D(0));fees=sum((D(x['fees_cny']) for x in t),D(0))
   cashgap=D(aft['available'])+D(aft['order_reserved'])-D(bef['available'])-D(bef['order_reserved'])-grosss+grossb+fees
   assert cashgap==0
   delta=sum(((D(x['raw_open'])*x['shares']-D(x['gross_cny']) if x['side']=='buy' else D(x['gross_cny'])-D(x['raw_open'])*x['shares'])-D(x['fees_cny']) for x in t),D(0))
   assert D(aft['nav'])-D(bef['nav'])==delta
   assert D(exp['available'])==D(aft['available'])+D(aft['order_reserved']) and D(exp['order_reserved'])==0
   assert D(exp['nav'])==D(aft['nav'])
   ji=r['journal'];sellidx=[i for i,x in enumerate(ji) if x['kind']=='real_sell_fill'];reserveidx=[i for i,x in enumerate(ji) if x['kind']=='real_reserve'];buyidx=[i for i,x in enumerate(ji) if x['kind']=='real_buy_fill']
   assert not sellidx or not reserveidx or max(sellidx)<min(reserveidx)
   assert not reserveidx or not buyidx or max(reserveidx)<min(buyidx)
   for x in t:
    w=next(w for w in r['execution_audit'] if w['sid']==x['security_id'] and w['side']==x['side'])
    assert x['shares']<=w['capacity'] and w['volume_source_last']<at[:10]
    if x['side']=='buy':
     newlots=[l for l in r['state_after_open']['positions'][x['security_id']]['lots'] if l['sellable_at']>at]
     assert sum(l['shares'] for l in newlots)==x['shares']
   if mode=='UNKNOWN_NO_FILL':
    assert not t
    for field in ['positions','exits']:
     assert r['state_before'][field]==r['state_after_open'][field]==r['state_after_expiry'][field]
   if rank=='E31':
    q=r['rank_audit'];assert len(q)==len(set(x['sid'] for x in q))==r['counts']['pending_stocks']
    assert sorted(x['original_rank'] for x in q)==sorted(x['new_rank'] for x in q)
    assert sorted(x['original_slot'] for x in q)==sorted(x['final_slot'] for x in q)==list(range(len(q)))
    assert sum(len(x['roles']) for x in q)==r['counts']['pending_intents']
   allchecks.append(dict(day=day,rank=rank,mode=mode,passed=True,cash_residual=str(cashgap),NAV_residual='0',sell_before_funding=True,all_reservations_before_buys=True,T_plus_1=True,prior_volume_capacity=True,unknown_preserves_positions_and_exits=True if mode=='UNKNOWN_NO_FILL' else None,source_sha256=sha(p)))
 for mode in ['OPEN_PROXY','UNKNOWN_NO_FILL']:
  a=read(root/('PVR__'+mode+'.json'));b=read(root/('E31__'+mode+'.json'));x,y=buys(a),buys(b)
  assert [t for t in a['trades']if t['side']=='sell']==[t for t in b['trades']if t['side']=='sell']
  fa={(r['sid'],r['role']):r for r in a['funding']};fb={(r['sid'],r['role']):r for r in b['funding']}
  q=sorted(b['rank_audit'],key=lambda x:x['final_slot']);items=[]
  for stock in q:
   sid=stock['sid'];rows=[]
   for role in stock['roles']:rows.append(dict(role=role,PVR_funding=fa.get((sid,role)),E31_funding=fb.get((sid,role)),no_record_explanation='Native skips already accepted stock, pending buy or latched exit'))
   items.append(dict(**stock,roles_funding=rows,PVR_buy=x.get(sid),E31_buy=y.get(sid)))
  diff.append(dict(day=day,mode=mode,PVR_counts=a['counts'],E31_counts=b['counts'],gross_buy_change=str(D(b['flows']['gross_buy'])-D(a['flows']['gross_buy'])),fees_change=str(D(b['flows']['fees'])-D(a['flows']['fees'])),open_cash_change=str(D(b['after_open']['available'])-D(a['after_open']['available'])),immediate_marked_NAV_change=str(D(b['after_open']['nav'])-D(a['after_open']['nav'])),immediate_NAV_interpretation='Only fees and modeled spread differ here; NOT investment performance',dropped_buys=[x[s] for s in sorted(x.keys()-y.keys())],added_buys=[y[s] for s in sorted(y.keys()-x.keys())],common_changed=[dict(sid=s,PVR=x[s],E31=y[s]) for s in sorted(x.keys()&y.keys()) if (x[s]['shares'],x[s]['role'])!=(y[s]['shares'],y[s]['role'])],complete_stock_trace=items))
save('ACCEPTED_VALIDATION.json',dict(passed=True,arms=allchecks,research_only=True,original_sources_unchanged=True,new_orders_external=False))
save('FULL_ALLOCATION_ATTRIBUTION.json',diff)
print('PASS',len(allchecks),'arms',len(diff),'complete comparisons')
