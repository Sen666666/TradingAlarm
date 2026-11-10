"""Join existing modifier flags to B actual fills only. No feature calculation."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import gzip,json,importlib.util
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
sp=importlib.util.spec_from_file_location('reused_outcome_helpers',T/'capacity_cost_guard_analysis_v1/analyze_completed_v1.py');H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H)
n=H.n;day=H.day;read=H.read;save=H.save;sha=H.sha
root=T/'trend_confirmation_native_v1/full-long-v1';P=root/'pair';flags={};support=defaultdict(set);role_support=defaultdict(set)
with gzip.open(P/'confirmation-size-events.jsonl.gz','rt') as f:
 for line in f:
  r=json.loads(line)
  if r['account'] not in ('A_ONLY','A_OR_B'):continue
  k=(day(r['at']),r['sid']);v={a:r['flags'].get(a) for a in ('A','B','A_known','B_known','price_known')}
  if k in flags:assert flags[k]==v,(k,flags[k],v)
  flags[k]=v;support[k].add(r['account']);role_support[k].add(r['role'])
with gzip.open(P/'B.json.gz','rt') as f:b=json.load(f)
layers=read(O/'full_long_v1/analysis/long/B/LAYERS.json');tx={t['layer']:t for t in b['trades'] if t['side']=='buy'};meta=b['metadata']
with gzip.open(P/'daily.jsonl.gz','rt') as f:
 snap=next(json.loads(line) for line in f if (r:=json.loads(line))['account']=='B' and day(r['at'])=='2023-12-29')
active={l['id']:l for l in snap['layers']}

def group(v):
 if v is None:return 'UNMATCHED_existing_modifier_log'
 if v['A_known'] and v['A'] is True:return 'A_TRUE'
 if v['A_known'] and v['A'] is False and v['B_known'] and v['B'] is True:return 'A_FALSE_B_ONLY_TRUE'
 if v['A_known'] and v['A'] is False and v['B_known'] and v['B'] is False:return 'A_FALSE_B_FALSE'
 return 'UNKNOWN_A_OR_B'

detail=[];totals={}
for cohort,lo,hi,cut in [('entry2022_2023_through2023','2022-01-04','2023-12-29','2023-12-29'),('post924_new303_through2024','2024-10-09','2024-12-31','2024-12-31')]:
 groups=defaultdict(lambda:dict(actual_buy_layers=0,actual_buy_cash=Z,actual_buy_gross=Z,contribution_through_cutoff=Z,negative_layer_contribution=Z,positive_layer_contribution=Z,negative_layers=0,positive_layers=0,open_at_cutoff_layers=0))
 for l in layers:
  if not lo<=day(l['opened'])<=hi:continue
  t=tx[l['layer']];k=(l['signal_day'],l['sid']);v=flags.get(k);g=group(v)
  if cut=='2023-12-29' and l['layer'] in active:
   x=active[l['layer']];net=n(x['cash'])+n(x['dividend'])+D(x['qty'])*H.A.price(l['sid'],cut);isopen=bool(x['qty'])
  else:
   assert cut=='2024-12-31' or (l['closed'] and day(l['closed'])<=cut)
   net=n(l['net']);isopen=bool(l['qty']) if cut=='2024-12-31' else False
  d=dict(cohort=cohort,cutoff=cut,layer=l['layer'],sid=l['sid'],name=l['name'],role=l['role'],actual_fill_at=t['at'],signal_day=l['signal_day'],budget_order=meta[str(l['layer'])].get('budget_order'),flags=v,group=g,support_accounts=sorted(support[k]),exact_same_role_flag_observed=l['role'] in role_support[k],actual_buy_cash=n(t['gross_cny'])+n(t['fees_cny']),actual_buy_gross=n(t['gross_cny']),contribution_through_cutoff=net,open_at_cutoff=isopen)
  detail.append(d);z=groups[g];z['actual_buy_layers']+=1;z['actual_buy_cash']+=d['actual_buy_cash'];z['actual_buy_gross']+=d['actual_buy_gross'];z['contribution_through_cutoff']+=net;z['open_at_cutoff_layers']+=isopen
  if net<0:z['negative_layers']+=1;z['negative_layer_contribution']+=net
  elif net>0:z['positive_layers']+=1;z['positive_layer_contribution']+=net
 total=sum((x['contribution_through_cutoff'] for x in groups.values()),Z)
 target=n(snap['nav'])-D(1000000) if cut=='2023-12-29' else n(read(O/'full_long_v1/FIXED_PHASE_WEALTH.json')['B']['post924_old_vs_new_layers']['groups']['new_fill_after_boundary']['wealth'])
 H.expect(total,target,'original_entry_cohort_contribution')
 totals[cohort]=dict(groups=dict(groups),total_actual_buy_layers=sum(x['actual_buy_layers'] for x in groups.values()),total_contribution=total,independent_review='PENDING',scope='Existing other-arm modifier logs supply account-independent sid/day features only; unmatched and unknown retained. Own B actual fills and cutoff-native layer cash/dividend/quantity. Entry-cohort contribution is association, never achievable avoided loss.')
save(O/'ORIGINAL_B_BUY_CONFIRMATION_COVERAGE.json',dict(totals=totals,existing_observed_sid_days=len(flags),detail=detail,source_book_sha256=sha(P/'B.json.gz'),source_modifier_log_sha256=sha(P/'confirmation-size-events.jsonl.gz'),analysis_sha256=sha(__file__),new_features=0,new_account_events=0,strict_math='Frozen pandas classification only; known equality-boundary FAIL scope retained.'))
for k,v in totals.items():print(k,{g:(x['actual_buy_layers'],str(x['actual_buy_cash']),str(x['contribution_through_cutoff'])) for g,x in v['groups'].items()},flush=True)
