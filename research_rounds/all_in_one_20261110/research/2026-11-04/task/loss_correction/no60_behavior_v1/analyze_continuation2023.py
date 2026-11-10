"""Thin continuous saved-book stock/campaign attribution. No account events."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import sys,json,importlib.util,time,gzip,hashlib
P=Path(__file__).resolve().parent;OUT=P/'continuation2023';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path[:0]=[str(P.parent),str(W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness')]
import analyze_pvr_no60 as L
q=W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/analyze_continuation.py'
s=importlib.util.spec_from_file_location('original_continuation_saved_reader',q);C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
A,M,B=L.A,L.M,L.B;Z=D(0)
ROOTS={'PVR_BASELINE':W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/run-2023','PVR_NO60':P.parent.parent/'pvr_pool_feasibility/continuation2023/run-2023'}
PARENTS={'PVR_BASELINE':W/'pvr-slot1-native-readiness-20261101/runs/2022','PVR_NO60':P.parent.parent/'pvr_pool_feasibility/runs/2022'}
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def save(name,x):L.save(OUT/name,x)
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def main():
 start=time.monotonic();assert not OUT.exists();OUT.mkdir();A.O=M.O=B.O=C.A.O=OUT
 data={};out={};stocks={};sources={str(q):L.sha(q),str(Path(__file__)):L.sha(__file__)}
 for policy,root in ROOTS.items():
  assert json.loads((root/'DONE.json').read_text())['completed'];a=C.account484('2023',policy,root);data[policy]=a;b=a['book'];old=book(PARENTS[policy]/'pair/B.json.gz')
  assert len(a['daily'])==484 and day(a['daily'][-1]['at'])=='2023-12-29'
  assert all(day(t['at'])<='2023-12-29' for t in b['trades'])
  oldvalue={x['id']:n(x['cash'])+n(x['dividend'])+(D(x['qty'])*A.price(x['sid'],'2022-12-30') if x['qty'] else Z) for x in old['layers']}
  layerchange={l['layer']:l['net']-oldvalue.get(l['layer'],Z) for l in a['layers']}
  netyear=n(b['ending_NAV'])-n(old['ending_NAV']);assert abs(sum(layerchange.values(),Z)-netyear)<D('.00000001')
  acts=L.entry_actions(a);exits=B.exit_chain(a);cc=L.campaign_rows(a,acts)
  for c in cc:
   c['year2023_wealth_change']=sum((layerchange[lid] for lid in c['layer_ids']),Z)
   c['year2023_carry_start_wealth']=sum((oldvalue.get(lid,Z) for lid in c['layer_ids']),Z)
   c['started_2023']=day(c['opened']).startswith('2023')
  assert abs(sum((c['year2023_wealth_change'] for c in cc),Z)-netyear)<D('.00000001')
  cg={}
  for vintage in ['new2023','carry2022']:
   for k in ['cash_closed_tail','cash_closed_ordinary','position_flat_claim','active_position']:
    vv=[c for c in cc if c['started_2023']==(vintage=='new2023') and ('cash_closed_tail' if c['cash_closed_tail30'] else 'cash_closed_ordinary' if c['cash_closed'] else 'position_flat_claim' if c['position_closed'] else 'active_position')==k]
    cg[vintage+'|'+k]=dict(campaigns=len(vv),year_wealth_change=sum((c['year2023_wealth_change'] for c in vv),Z),cumulative_lifecycle_net=sum((c['net'] for c in vv),Z),cumulative_buy_cash=sum((c['buy_cash'] for c in vv),Z))
  new=[x for x in a['layers'] if day(x['opened']).startswith('2023')];act23=[x for x in acts if day(x['at']).startswith('2023')];ex23=[x for x in exits if day(x['request_at']).startswith('2023')]
  st=defaultdict(lambda:Z)
  for l in a['layers']:st[l['sid']]+=layerchange[l['layer']]
  stocks[policy]=dict(st)
  out[policy]=dict(start_own2022_NAV=old['ending_NAV'],end_2023_NAV=b['ending_NAV'],year_wealth_change=netyear,cumulative_lifecycle=M.contribution(a['layers']),cumulative_campaign_buckets=L.campaign_summary(cc),vintage_campaign_buckets=cg,new2023_layers=M.contribution(new),new2023_entry_actions={k:M.contribution([l for l in new if l['layer'] in {x['layer'] for x in act23 if x['action']==k}]) for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']},actual2023_exit_reason_counts=dict(Counter(x['reason'] for x in ex23)),actual2023_closed_negative_layers_by_reason={k:M.contribution([l for l in a['layers'] if l['layer'] in {x['layer'] for x in ex23 if x['reason']==k} and not l['qty'] and l['net']<0]) for k in sorted({x['reason'] for x in ex23})},carry_layer2023_wealth_change=sum((layerchange[l['layer']] for l in a['layers'] if l['layer'] in oldvalue),Z),claims=L.claims(a))
  save(policy+'-SUMMARY.json',out[policy]);save(policy+'-CAMPAIGNS.json',cc);save(policy+'-ENTRY_ACTIONS.json',acts);save(policy+'-EXIT_CHAIN.json',exits);save(policy+'-LAYER_YEAR_CHANGE.json',[dict(layer=l['layer'],sid=l['sid'],old_boundary_wealth=oldvalue.get(l['layer'],Z),year_change=layerchange[l['layer']],new2023=day(l['opened']).startswith('2023')) for l in a['layers']])
  for pp in [root/'pair/B.json.gz',PARENTS[policy]/'pair/B.json.gz',root/'pair/daily.jsonl.gz']:sources[str(pp)]=L.sha(pp)
 oldst,newst=stocks['PVR_BASELINE'],stocks['PVR_NO60'];deltas=[dict(sid=sid,name=L.META[sid]['name'],industry=L.META[sid]['industry'],old_year=oldst.get(sid,Z),NO60_year=newst.get(sid,Z),delta=newst.get(sid,Z)-oldst.get(sid,Z)) for sid in set(oldst)|set(newst)]
 diff=out['PVR_NO60']['year_wealth_change']-out['PVR_BASELINE']['year_wealth_change'];assert abs(sum((x['delta'] for x in deltas),Z)-diff)<D('.00000001')
 ordered=sorted(oldst,key=oldst.get,reverse=True);selected=list(dict.fromkeys(ordered[:10]+ordered[-3:]+[x['sid'] for x in sorted(deltas,key=lambda x:-x['delta'])[:3]]+[x['sid'] for x in sorted(deltas,key=lambda x:x['delta'])[:3]]+['300308.SZ','300502.SZ']))
 for policy,a in data.items():save(policy+'-FIXED_AND_DELTA_PATHS.json',[L.path(a,sid,L.entry_actions(a),B.exit_chain(a)) for sid in selected])
 save('STOCK_YEAR_DELTA.json',sorted(deltas,key=lambda x:-x['delta']));save('COMPARISON.json',dict(year_wealth_difference=diff,terminal_continuous_wealth_difference=n(data['PVR_NO60']['book']['ending_NAV'])-n(data['PVR_BASELINE']['book']['ending_NAV']),sides=out,first_ten_original_year_winners=[next(x for x in deltas if x['sid']==sid) for sid in ordered[:10]],scope='Each policy inherits its own complete 2022 book; no reset, Jan3 included; outcome buckets are descriptive at Dec29, not real-time labels or pure calendar alpha',account_events=0))
 save('SOURCE_BINDING.json',dict(sources=sources,readers={str(L.__file__):L.sha(L.__file__),str(C.__file__):L.sha(C.__file__)},seconds=time.monotonic()-start,account_events=0))
 print(json.dumps(dict(year_wealth_difference=diff,sides=out),ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
