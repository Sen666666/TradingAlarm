"""Independent thin join/grid/overlap audit, reusing already audited inputs."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter,defaultdict
from itertools import product
import csv,json,hashlib,math
getcontext().prec=75
P=Path(__file__).resolve().parents[1];A=P/'analysis_summary';O=Path(__file__).resolve().parent;Z=D(0);C=Counter();S={}
def read(p):
 p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def eq(a,b,label):
 if a is None or b is None:assert a is None and b is None,(label,a,b)
 elif isinstance(a,bool) or isinstance(b,bool):assert a==b,(label,a,b)
 elif isinstance(a,(int,float,D)) or isinstance(b,(int,float,D)):
  assert abs(D(str(a))-D(str(b)))<D('1e-16')*max(D(1),abs(D(str(a))),abs(D(str(b)))),(label,a,b)
 else:assert a==b,(label,a,b)
 C[label]+=1
fields=['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']
features=['width_pct','gap_prior20close_pct','gap_prior20high_pct','r5_pct','r20_pct','decision_budget_pct_NAV','decision_cap_nominal_risk_pct_NAV','CP1_used_scale_over_current_z','CP1_freeze_to_decision_original_valid_observations','initial_width_over_current_z','held_close_observations','entry_to_primary_request_held_CLOSE_observations','peak_held_close_unrealized_per_own_buycash','comparable_price_MFE_ratio','calendar_days_to_actual_exit_or_cutoff']
def money(rr):
 d=dict(layers=len(rr),stocks=len({x['sid'] for x in rr}))
 d.update({k:sum((D(x[k]) for x in rr),Z) for k in fields})
 d.update(negative_net=sum((min(Z,D(x['net'])) for x in rr),Z),positive_net=sum((max(Z,D(x['net'])) for x in rr),Z),negative_layers=sum(D(x['net'])<0 for x in rr),positive_layers=sum(D(x['net'])>0 for x in rr),open_layers=sum(bool(x['qty']) for x in rr))
 return d
def checkmoney(rr,g):
 for k,v in money(rr).items():eq(v,g[k],'money_'+k)
def stats(rr,g):
 checkmoney(rr,g['money'])
 for k in features:
  v=sorted(float(x[k]) for x in rr if x.get(k) is not None);h=g['features'][k]
  eq(len(v),h['known'],'distribution_count');eq(len(rr)-len(v),h['unknown'],'distribution_count')
  if not v:assert h['quantiles'] is None;continue
  for q,actual in zip([0,.1,.25,.5,.75,.9,1],h['quantiles']):
   i=q*(len(v)-1);lo=math.floor(i);hi=math.ceil(i);expect=v[lo]+(v[hi]-v[lo])*(i-lo)
   assert math.isclose(expect,actual,rel_tol=1e-12,abs_tol=1e-12),(k,q,expect,actual);C['distribution_quantile']+=1
V=read(A/'JOIN_VALIDATION.json');assert hashlib.sha256((P/'summarize.py').read_bytes()).hexdigest()==V['script_sha256']
for p,h in V['sources'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;C['source_SHA']+=1
R={}
for ref in ['2022_2024','strong']:
 rr=read(A/(ref+'_JOINED_ROWS.json'));R[ref]=rr
 inputs=[{x['layer']:x for x in read(P/d/(ref+s))} for d,s in [('decision_features','_ROWS.json'),('holding_exit','_LAYERS.json'),('mechanism_review','_ACTUAL_ENTRY_SCALE_JOIN.json'),('holding_exit','_REQUEST_CLOCK_JOIN.json')]]
 assert len(rr)==len(inputs[0])==len({x['layer'] for x in rr})
 for x in rr:
  f,h,s,c=[d[x['layer']] for d in inputs]
  for k,v in x.items():
   if k=='outcome_label':assert v==('negative' if D(x['net'])<0 else 'positive' if D(x['net'])>0 else 'zero');continue
   provider=c if k in c and k.startswith(('primary_','entry_to_','request_','actual_exit_at','actual_exit_is_')) else s if k in s and (k.startswith(('initial_','CP1_'))) else h if k in h and k not in f else f
   assert k in provider,(k,x['layer']);eq(v,provider[k],'all_joined_field')
  eq(x['cost'],s['original_cost'],'scale_original_cost');eq(x['net'],s['original_net'],'scale_original_net');assert x['opened']==c['opened_at']==s['actual_fill_at']
  if x['qty']==0:assert x['held_close_observations']==x['entry_to_primary_request_held_CLOSE_observations']+x['request_to_fill_intervening_CLOSE_observations'];C['closed_request_holding_identity']+=1
  else:assert x['entry_to_primary_request_held_CLOSE_observations'] is None;C['open_request_unknown']+=1
scopes=dict(two_year=[x for x in R['2022_2024'] if x['opened'][:10]<'2024-01-01'],post303=[x for x in R['2022_2024'] if x['opened'][:10]>'2024-10-08'],post924_new320=[x for x in R['2022_2024'] if x['opened'][:10]>='2024-09-24'],strong=R['strong'])
assert {k:len(v) for k,v in scopes.items()}==dict(two_year=1557,post303=303,post924_new320=320,strong=1171)
dist=read(A/'DISTRIBUTIONS.json')
for scope,rr in scopes.items():
 stats(rr,dist[scope]['all'])
 for name,groups in dist[scope].items():
  if name=='all':continue
  member=[]
  for g in groups:
   sr=[x for x in rr if all(x[k]==v for k,v in g['labels'].items())];stats(sr,g);member.extend(x['layer'] for x in sr);C['distribution_group']+=1
  assert sorted(member)==sorted(x['layer'] for x in rr)
pairs=dict(width_r5=['width_pct_q','r5_pct_q'],width_r20=['width_pct_q','r20_pct_q'],break20_r20=['break20close','r20_pct_q'])
levels={k:['Q1','Q2','Q3','Q4','unknown'] for k in ['width_pct_q','r5_pct_q','r20_pct_q']};levels['break20close']=['above_prior20close','at_prior20close','below_prior20close','unknown'];actions=sorted({x['action'] for rr in R.values() for x in rr});roles=['core','mobile']
allscopes={'full_2022_2024':R['2022_2024'],**scopes};cells=list(csv.DictReader((A/'COMPLETE_PAIR_CELLS.csv').open()));assert len(cells)==2100;seen=set();empty=0
for g in cells:
 rr=allscopes[g['scope']];cols=['action','role']+pairs[g['pair']];key=(g['scope'],g['pair'],*(g[k] for k in cols));assert key not in seen;seen.add(key)
 sr=[x for x in rr if all(str(x[k])==g[k] for k in cols)];checkmoney(sr,g);m=money(rr);a=money(sr)
 for side in ['negative','positive']:eq(a[side+'_net']/m[side+'_net'] if m[side+'_net'] else None,None if g[side+'_money_share']=='' else D(g[side+'_money_share']),'cell_share')
 if not sr:empty+=1;assert all(D(g[k])==0 for k in fields+['negative_net','positive_net','layers','stocks','negative_layers','positive_layers','open_layers'])
 C['complete_pair_cell']+=1
expected={(name,pair,*key) for name in allscopes for pair,cols in pairs.items() for key in product(actions,roles,*[levels[k] for k in cols])};assert seen==expected
over=read(A/'MONEY_WEIGHTED_OVERLAP.json');assert len(over)==216;overkeys=set()
for g in over:
 key=tuple(g[k] for k in ['weak','strongstate','action','role','pair']);assert key not in overkeys;overkeys.add(key)
 def select(rr):return [x for x in rr if (g['action']=='ALL' or x['action']==g['action']) and (g['role']=='ALL' or x['role']==g['role'])]
 aa=[x for x in select(scopes[g['weak']]) if D(x['net'])<0];bb=[x for x in select(scopes['strong']) if D(x['net'])>0 and (g['strongstate']=='all_positive' or x['qty']==0)]
 wa=-money(aa)['negative_net'];wb=money(bb)['positive_net'];eq(wa,g['negative_money'],'overlap_denominator');eq(wb,g['positive_money'],'overlap_denominator');cols=pairs[g['pair']]
 ca=defaultdict(lambda:Z);cb=defaultdict(lambda:Z)
 for x in aa:ca[tuple(x[k] for k in cols)]-=D(x['net'])
 for x in bb:cb[tuple(x[k] for k in cols)]+=D(x['net'])
 val=sum((min(ca[k]/wa,cb[k]/wb) for k in ca.keys()|cb.keys()),Z) if wa and wb else None
 eq(val,None if g['normalized_money_overlap'] is None else D(g['normalized_money_overlap']),'normalized_overlap');assert val is None or 0<=val<=1
comps=read(A/'ALL_CELL_COMPARISONS.json');assert len(comps)==420
for g in comps:
 ar=[x for x in scopes[g['weak']] if all(x[k]==v for k,v in g['labels'].items())];br=[x for x in scopes['strong'] if all(x[k]==v for k,v in g['labels'].items()) and (g['strongstate']=='all_positive' or x['qty']==0)];checkmoney(ar,g['weak_money']);checkmoney(br,g['strong_money'])
 wa=-money(scopes[g['weak']])['negative_net'];wb=money([x for x in scopes['strong'] if g['strongstate']=='all_positive' or x['qty']==0])['positive_net']
 eq(-money(ar)['negative_net']/wa,g['weak_negative_share'],'comparison_share');eq(money(br)['positive_net']/wb,g['strong_positive_share'],'comparison_share');C['complete_comparison_cell']+=1
lit=read(A/'LITERAL_HYPOTHESIS_DESCRIPTIVE.json')
conditions={'tightest_width_Q1_hottest_r5_Q4':dict(width_pct_q='Q1',r5_pct_q='Q4'),'tightest_width_Q1_hottest_r20_Q4':dict(width_pct_q='Q1',r20_pct_q='Q4'),'tightest_width_Q1':dict(width_pct_q='Q1'),'hottest_r5_Q4':dict(r5_pct_q='Q4')}
for scope,rr in scopes.items():
 for label,labels in conditions.items():
  sr=[x for x in rr if all(x[k]==v for k,v in labels.items())];g=lit[scope][label];stats(sr,g);m=money(rr);a=money(sr)
  for side in ['negative','positive']:eq(a[side+'_net']/m[side+'_net'],g[side+'_money_share'],'literal_share')
  assert {g['labels']['action'] for g in g['by_action']}=={x['action'] for x in sr}
  for gg in g['by_action']:stats([x for x in sr if x['action']==gg['labels']['action']],gg)
tails=read(A/'FIXED_ORIGINAL_TAILS.json');tailcounts={}
for ref,rr in R.items():
 original=read(P.parent/'local_high'/(ref+'_FIXED_TAILS.json'));assert len(tails[ref])==len(original);bm={x['layer']:x for x in rr};matched=0
 for t,u in zip(tails[ref],original):
  assert t['original']==u['original'] and t['unmatched']==u['unmatched'];expect=[bm[x['layer']] for x in u['matched_actual_No60_rows']];assert t['matched_rows']==expect;matched+=bool(expect);C['fixed_tail_control']+=1
 tailcounts[ref]=dict(original=len(original),matched=matched)
assert tailcounts=={'2022_2024':dict(original=83,matched=45),'strong':dict(original=94,matched=67)}
csvrows=list(csv.DictReader((A/'ALL_ENTRY_EXIT_CONTEXT.csv').open()));flat=R['2022_2024']+R['strong'];assert len(csvrows)==len(flat)
for row,x in zip(csvrows,flat):
 for k,v in row.items():assert v==('' if x[k] is None else str(x[k])),(k,v,x[k]);C['flat_csv_cell']+=1
out=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(C),scope_sizes={k:len(v) for k,v in scopes.items()},complete_cells=len(cells),empty_cells=empty,overlap_rows=len(over),comparison_cells=len(comps),tail_controls=tailcounts,source_sha256=S,producer_source_hashes=V['sources'],limits=['Thin join reuses completed full feature and holding/request-clock source audits; no new rolling quote extraction.','Overlap is normalized monetary distribution intersection, not predictive separation or a counterfactual trading gain.','ALL_CELL_COMPARISONS strong_money contains both signs within the indicated terminal universe; its positive share uses positive contributions only.','Quartiles and literal hypotheses remain descriptive; no gate or alternate account executed.'],new_accounts=0)
(O/'SUMMARY_JOIN_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['source_sha256','producer_source_hashes']},ensure_ascii=False,indent=2))
