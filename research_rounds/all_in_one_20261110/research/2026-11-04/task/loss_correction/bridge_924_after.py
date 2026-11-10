"""Fixed 924 boundary wealth bridge; no peak search or economic policy."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip
import analyze_pvr_no60 as L
P=Path(__file__).resolve().parent;O=P/'continuation2024_layers';F=P.parent/'risk_constraints/continuation2024_finance';B=P.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024';Z=D(0);BOUND='2024-10-08';END='2024-12-31';SRC={}
def n(x):return D(str(x))
def read(p):SRC[str(p)]=L.sha(p);return json.loads(Path(p).read_text())
def gz(p):
 SRC[str(p)]=L.sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 SRC[str(p)]=L.sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def agg(ll):return dict(layers=len(ll),stocks=len({x['sid'] for x in ll}),boundary_wealth=sum((x['boundary_wealth'] for x in ll),Z),terminal_lifecycle_net=sum((x['terminal_lifecycle_net'] for x in ll),Z),after_boundary_wealth_change=sum((x['after_boundary_wealth_change'] for x in ll),Z),original_buycash=sum((x['buycash'] for x in ll),Z))
def main():
 out={}
 for ref,side,finance in [('PVR_BASELINE','original','PVR_SLOT1'),('PVR_NO60','no60','PVR_NO_CONFIRMED60')]:
  root=B/side/'run-2024/pair';b=gz(root/'B.json.gz');ds=rows(root/'daily.jsonl.gz');r=next(x for x in ds if x['at'][:10]==BOUND);active={x['id']:x for x in r['layers']};ls=read(F/'analysis/2022_2024'/finance/'LAYERS.json');raw={x['id']:x for x in b['layers']};acts=read(O/(ref+'-ENTRY_ACTIONS.json'));am={x['layer']:x for x in acts};rr=[]
  for l in ls:
   lid=l['layer'];x=raw[lid];before=Z
   if l['opened'][:10]<=BOUND:
    if lid in active:
     a=active[lid];before=n(a['cash'])+n(a['dividend'])+D(a['qty'])*L.A.price(l['sid'],BOUND)
    else:
     assert l['closed'] and l['closed'][:10]<=BOUND;before=n(x['cash'])+n(x['dividend'])
   rr.append(dict(layer=lid,sid=l['sid'],name=l['name'],industry=l['industry'],role=l['role'],action=am[lid]['action'],opened=l['opened'],closed=l['closed'],boundary_wealth=before,terminal_lifecycle_net=n(l['net']),after_boundary_wealth_change=n(l['net'])-before,buycash=n(l['cost']),cohort='new_fill_after_boundary' if l['opened'][:10]>BOUND else 'actually_held_at_boundary' if lid in active else 'already_closed_at_boundary'))
  assert abs(sum((x['boundary_wealth'] for x in rr),Z)-(n(r['nav'])-D(1000000)))<D('.00000001')
  change=n(b['ending_NAV'])-n(r['nav']);assert abs(sum((x['after_boundary_wealth_change'] for x in rr),Z)-change)<D('.00000001')
  groups={k:agg([x for x in rr if x['cohort']==k]) for k in ['actually_held_at_boundary','new_fill_after_boundary','already_closed_at_boundary']};new=[x for x in rr if x['cohort']=='new_fill_after_boundary'];st=defaultdict(lambda:Z)
  for x in rr:st[x['sid']]+=x['after_boundary_wealth_change']
  out[ref]=dict(boundary=BOUND,end=END,boundary_NAV=r['nav'],end_NAV=b['ending_NAV'],actual_after_wealth_change=change,groups=groups,newfill_actions={k:agg([x for x in new if x['action']==k]) for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']},stock_wealth_changes=sorted([dict(sid=s,name=L.META[s]['name'],change=v) for s,v in st.items()],key=lambda x:x['change']),all_layer_rows=rr,scope='Fixed risk-agent 924 six-close boundary, not a future peak selected as a trading rule; actual old-layer wealth subtracts boundary value, new-fill lifecycle valid only because bought strictly after boundary')
 L.save(O/'AFTER_924_LAYER_WEALTH_BRIDGE.json',out)
 for sid in L.A.frames:
  p=Path(L.A.SM[sid]['refs']['facts']);assert L.sha(p)==L.A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=L.sha(p)
 L.save(O/'AFTER_924_LAYER_WEALTH_SOURCE.json',dict(sources=SRC,script_sha256=L.sha(__file__),account_events=0,financial_reader_shared=True))
 print(json.dumps({k:{q:v for q,v in z.items() if q not in ['all_layer_rows','stock_wealth_changes']} for k,z in out.items()},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
