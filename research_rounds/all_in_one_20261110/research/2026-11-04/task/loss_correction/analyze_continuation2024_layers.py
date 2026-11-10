"""Consume finance agent's already-derived layers; no account construction."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import json,gzip,sys
import analyze_pvr_no60 as L
P=Path(__file__).resolve().parent;O=P/'continuation2024_layers';Z=D(0)
BASE=P.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
F=P.parent/'risk_constraints/continuation2024_finance';SOURCE={}
def read(p):SOURCE[str(p)]=L.sha(p);return json.loads(Path(p).read_text())
def book(p):
 SOURCE[str(p)]=L.sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 SOURCE[str(p)]=L.sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def save(name,x):L.save(O/name,x)
def main():
 assert not O.exists();O.mkdir();read(F/'SOURCE_MANIFEST.json');out={};stocks={};sides={}
 for label,finance,side,parent in [('PVR_BASELINE','PVR_SLOT1','original',L.OLD/'continuation-2023-readiness/run-2023'),('PVR_NO60','PVR_NO_CONFIRMED60','no60',P.parent/'pvr_pool_feasibility/continuation2023/run-2023')]:
  root=BASE/side/'run-2024';assert read(root/'DONE.json')['completed'];b=book(root/'pair/B.json.gz');old=book(parent/'pair/B.json.gz');ds=rows(root/'pair/daily.jsonl.gz');assert len(ds)==726 and day(ds[-1]['at'])=='2024-12-31';assert not [x for x in old['layers'] if x['qty']]
  ls=read(F/'analysis/2022_2024'/finance/'LAYERS.json')
  for x in ls:
   for k in ['cost','net','value']:x[k]=n(x[k])
  a=dict(book=b,daily=ds,layers=ls,byday={day(r['at']):r for r in ds});acts=L.entry_actions(a);exits=L.B.exit_chain(a);cc=L.campaign_rows(a,acts);oldwealth={x['id']:n(x['cash'])+n(x['dividend']) for x in old['layers']};change={x['layer']:x['net']-oldwealth.get(x['layer'],Z) for x in ls};net=n(b['ending_NAV'])-n(old['ending_NAV']);assert abs(sum(change.values(),Z)-net)<D('.00000001')
  st=defaultdict(lambda:Z)
  for x in ls:st[x['sid']]+=change[x['layer']]
  stocks[label]=dict(st);sides[label]=a
  for c in cc:c['year2024_wealth_change']=sum((change[lid] for lid in c['layer_ids']),Z);c['started2024']=day(c['opened']).startswith('2024')
  new=[x for x in ls if day(x['opened']).startswith('2024')];act24=[x for x in acts if day(x['at']).startswith('2024')];ex24=[x for x in exits if day(x['request_at']).startswith('2024')];cnew=[x for x in cc if x['started2024']]
  out[label]=dict(start_own2023_NAV=old['ending_NAV'],ending2024_NAV=b['ending_NAV'],year_wealth_change=net,cumulative_layers=L.M.contribution(ls),new2024_layers=L.M.contribution(new),new2024_campaign_buckets=L.campaign_summary(cnew),cumulative_campaign_buckets=L.campaign_summary(cc),carry_prior_layers_2024_wealth_change=sum((change[x['layer']] for x in ls if x['layer'] in oldwealth),Z),entry_actions_2024={k:L.M.contribution([x for x in new if x['layer'] in {a['layer'] for a in act24 if a['action']==k}]) for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']},actual_exit_request_counts2024=dict(Counter(x['reason'] for x in ex24)),claims=L.claims(a))
  save(label+'-CAMPAIGNS.json',cc);save(label+'-ENTRY_ACTIONS.json',acts);save(label+'-EXIT_CHAIN.json',exits);save(label+'-LAYER_YEAR_CHANGE.json',[dict(layer=x['layer'],sid=x['sid'],year_wealth_change=change[x['layer']],old_boundary_wealth=oldwealth.get(x['layer'],Z)) for x in ls])
 diff=out['PVR_NO60']['year_wealth_change']-out['PVR_BASELINE']['year_wealth_change'];delta=[dict(sid=s,name=L.META[s]['name'],industry=L.META[s]['industry'],baseline_year=stocks['PVR_BASELINE'].get(s,Z),NO60_year=stocks['PVR_NO60'].get(s,Z),year_difference=stocks['PVR_NO60'].get(s,Z)-stocks['PVR_BASELINE'].get(s,Z)) for s in set(stocks['PVR_BASELINE'])|set(stocks['PVR_NO60'])];assert abs(sum((x['year_difference'] for x in delta),Z)-diff)<D('.00000001')
 ranked=sorted(stocks['PVR_BASELINE'],key=stocks['PVR_BASELINE'].get,reverse=True);save('STOCK_YEAR_DELTA.json',sorted(delta,key=lambda x:-x['year_difference']));save('COMPARISON.json',dict(sides=out,year_wealth_difference=diff,terminal_cumulative_NAV_difference=n(sides['PVR_NO60']['book']['ending_NAV'])-n(sides['PVR_BASELINE']['book']['ending_NAV']),first_ten_original_year_winners=[next(x for x in delta if x['sid']==s) for s in ranked[:10]],scope='Own-state inherited 2023; year wealth subtracts each own prior cash/div/inventory. Terminal cumulative NAV difference is not 2024 alpha; source layers are shared finance output, not independently reconstructed basis.',account_events=0));save('SOURCE_BINDING.json',dict(sources=SOURCE,script_sha256=L.sha(__file__),reused_readers={str(L.__file__):L.sha(L.__file__)},account_events=0));print(json.dumps(dict(diff=diff,sides=out),ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
