"""Bind repeated plan-zero events to original actual fills; no counterfactual."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import gzip,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
def read(p):return json.loads(p.read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def n(x):return D(str(x))
def norm(s):return s.split('|',1)[1] if s and '|' in s else s
out={}
for win in ['long','strong']:
 root=T/'trend_confirmation_native_v1'/f'full-{win}-v1/pair';B=book(root/'B.json.gz');U=book(root/'UNIFORM50.json.gz');ls=read(O/f'full_{win}_v1/analysis/{win}/B/LAYERS.json');lay={x['layer']:x for x in ls};ej=defaultdict(list);umap=defaultdict(list)
 for r in rows(root/'confirmation-size-events.jsonl.gz'):
  if r['account']=='UNIFORM50' and r['result']=='confirmation_half_below_minimum':ej[(f"{r['at']}|{r['sid']}|{r['role']}",r['CP1_id'])].append(r)
 uj={r['layer']:r for r in U['journal'] if r['kind']=='real_buy_fill'}
 for t in U['trades']:
  if t['side']=='buy':umap[(norm(U['metadata'][str(t['layer'])]['budget_order']),uj[t['layer']]['CP1_id'])].append(t)
 detail=[]
 for l in ls:
  k=(norm(B['metadata'][str(l['layer'])]['budget_order']),l['receipt'])
  if k not in ej:continue
  detail.append(dict(baseline_actual_layer=l,original_plan_zero_events=ej[k],UNIFORM50_actual_fill_same_order=umap.get(k,[]),UNIFORM50_other_actual_buys_same_sid_and_fillday=[t for t in U['trades'] if t['side']=='buy' and t['security_id']==l['sid'] and t['at'][:10]==l['opened'][:10]]))
 first=B['trades'][0]['at'][:10];fb=[t for t in B['trades'] if t['side']=='buy' and t['at'][:10]==first];fu=[t for t in U['trades'] if t['side']=='buy' and t['at'][:10]==first];bids={t['security_id'] for t in fb}
 out[win]=dict(repeated_plan_zero_events=sum(len(v) for v in ej.values()),unique_zero_keys=len(ej),original_B_actual_buy_layers_matching_zero=len(detail),B_actual_buy_cash_for_matched_layers=sum((n(r['baseline_actual_layer']['cost']) for r in detail),Z),B_original_life_contribution_for_matched_layers=sum((n(r['baseline_actual_layer']['net']) for r in detail),Z),zero_key_same_order_U50_actual_fill_layers=sum(len(r['UNIFORM50_actual_fill_same_order']) for r in detail),same_sid_fillday_other_U50_buys_for_affected_Blayers=sum(bool(r['UNIFORM50_other_actual_buys_same_sid_and_fillday']) for r in detail),details=detail,first_actual_fillday=dict(day=first,B_buy_fills=len(fb),U50_buy_fills=len(fu),B_gross=sum((n(t['gross_cny']) for t in fb),Z),U50_gross=sum((n(t['gross_cny']) for t in fu),Z),U50_funded_sids_not_B_on_day=sorted({t['security_id'] for t in fu}-bids),actual_U50_replacement_buys=[t for t in fu if t['security_id'] not in bids]))
out['scope']='Original B fills matched by exact normalized budget_order + CP1 receipt to already-saved U50 minimum-lot-zero logs. Actual U50 fills are reported, not counterfactual. Repeated zero events are not independent lost opportunities; original contribution is not achievable avoided loss. First-day different-stock funding is observed reallocation, not per-order causal attribution. Derived join PENDING independent audit.'
out['analysis_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(O/'NATIVE_REPLACEMENT_EVIDENCE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
for win in ['long','strong']:
 v=out[win];print(win,{k:v[k] for k in ['repeated_plan_zero_events','unique_zero_keys','original_B_actual_buy_layers_matching_zero','zero_key_same_order_U50_actual_fill_layers','same_sid_fillday_other_U50_buys_for_affected_Blayers']},'firstday',v['first_actual_fillday']['day'],v['first_actual_fillday']['B_buy_fills'],v['first_actual_fillday']['U50_buy_fills'],flush=True)
