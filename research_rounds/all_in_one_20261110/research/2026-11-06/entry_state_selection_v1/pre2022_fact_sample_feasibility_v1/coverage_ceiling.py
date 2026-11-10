"""Pre-request stop gate. Deterministic year/type/industry sample; no returns, models or external requests."""
from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;P=R/'pre2022_candidate_feasibility_v1'
SEED='PRE2022_FACTS_60_FIXED_STRATA_V1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,v):(O/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'FREEZE.json').exists()
paths=[P/'ACTION_REQUIREMENTS_WITH_MATURITY.csv',P/'EXTENDED_POTENTIAL_120D_SOURCE_COVERAGE.csv',P/'CANDIDATE_ACTION_OVERLAP.csv',P/'MATURE_COMPETITION_SUPPORT.csv',R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv']
sources={str(p):sha(p) for p in paths}
delivery=json.load(open(P/'FINAL_DELIVERY_HASHES.json'))
for p in paths:
 if p.parent==P:assert sources[str(p)]==delivery[p.name]
save('FREEZE.json',dict(scope='Evaluate whether the requested bounded60-security fact sample can materially improve mature competition-group source coverage before any external query. No strategy outcomes, fit or account.',source_hashes=sources,code_sha256=sha(__file__),seed=SEED,
 sample='Exactly10 distinct securities in each ex-year2019/2020/2021 times pure-cash/share-action stratum where available; global securities without replacement. Iterate chronological year, cash before shares. In each stratum round-robin industry buckets ordered by SHA256(seed|year|type|industry); each bucket has one earliest event per sid, ordered by SHA256(seed|year|type|sid|action_id). No candidate count, ranking, payoff or coverage-gain variables used for selection.',
 benefit='A source-supported competitive group requires every mature t-close-PASS candidate in the same day/industry, with>2 candidates, to have data support. This is still not an economic-label or tradability certificate.',
 material_gate='Before seeing draw gains, require at least5 percentage points of all mature competitive groups (ceil(.05*N)) as optimistic incremental complete groups in either direct repair scenario or a scenario granting all existing cached action facts perfect resolution. This is an operational stop threshold, not a statistical or investment threshold. Also report1percentage-point benchmark.',
 optimistic='Assume every sampled security gets perfect facts for ALL its missing historical events, including cash/share precision, pay/listed dates and factor explanations, not just its nominated event. Keep existing raw missing/source/core/CP-field gaps unresolved. No requests or parsing time assumed. Thus improvements are optimistic source-support ceilings, not expected actual gains.',
 existing_cache_scenario='All current cached action matches, including duplicate rows, assumed fully resolved for free before measuring the incremental60-security benefit. This generous scenario is not actual admission.',
 stop='If even optimistic incremental coverage is below the frozen threshold, stop with zero external requests. Do not change sample, threshold, expand securities or run queries just to estimate API success.',
 network_requests_before_gate=0))
a=pd.read_csv(paths[0]);q=pd.read_csv(paths[1],parse_dates=['day']);links=pd.read_csv(paths[2]);groups=pd.read_csv(paths[3],parse_dates=['day']);roster=pd.read_csv(paths[4]).set_index('sid')
q=q[q.mature_by_20211231].copy()
a=a[a.intersects_at_least_one_mature_candidate].copy()
missing=a[a.current_public_matches.eq(0)].copy()
assert len(missing)==1633
missing['year']=pd.to_datetime(missing.effective_date).dt.year
missing['type']=np.where(missing.pure_cash,'CASH','SHARE')
missing['sector']=[roster.loc[s,'sector_id'] for s in missing.sid]
missing['industry']=[roster.loc[s,'industry'] for s in missing.sid]
def h(x):return hashlib.sha256((SEED+'|'+x).encode()).hexdigest()
used=set();chosen=[];allocation=[]
for year in [2019,2020,2021]:
 for typ in ['CASH','SHARE']:
  z=missing[missing.year.eq(year)&missing.type.eq(typ)&~missing.sid.isin(used)].copy()
  z=z.sort_values(['effective_date','action_id']).drop_duplicates('sid')
  buckets={}
  for sec,g in z.groupby('sector'):
   g=g.copy();g['draw_key']=[h(f'{year}|{typ}|{r.sid}|{r.action_id}') for r in g.itertuples()]
   buckets[sec]=g.sort_values('draw_key').to_dict('records')
  order=sorted(buckets,key=lambda sec:h(f'{year}|{typ}|{sec}'))
  take=[]
  while len(take)<10 and any(buckets.values()):
   for sec in order:
    if len(take)>=10:break
    if buckets[sec]:
     r=buckets[sec].pop(0);take.append(r);used.add(r['sid'])
  chosen.extend(take)
  allocation.append(dict(year=year,type=typ,eligible_events=len(missing[missing.year.eq(year)&missing.type.eq(typ)]),eligible_unique_securities_before_exclusion=missing[missing.year.eq(year)&missing.type.eq(typ)].sid.nunique(),drawn_securities=len(take),drawn_industries=len(set(r['sector'] for r in take))))
sample=pd.DataFrame(chosen);assert sample.sid.is_unique and len(sample)<=60
sample['selection_order']=range(1,len(sample)+1)
sample.to_csv(O/'FIXED_SAMPLE_60.csv',index=False)
pd.DataFrame(allocation).to_csv(O/'STRATUM_ALLOCATION.csv',index=False)
save('SAMPLE_SEAL.json',dict(sample_sha256=sha(O/'FIXED_SAMPLE_60.csv'),stratum_sha256=sha(O/'STRATUM_ALLOCATION.csv'),selected_securities=len(sample),selected_industries=sample.sector.nunique(),selected_missing_source_events_total=int(missing.sid.isin(used).sum()),no_gain_computation_before_seal=True,no_external_requests=True))
# Only now calculate sample-specific optimistic gains.
basic=q.full120_observed_price_open_valid&q.full120_one_source_segment&q.full120_original_core_fields_ready&q.full120_CP_fields_ready&q.full120_active_I_floor_ready
zero=q.extended_zero_action_source_support
q['selected_sample_security']=q.sid.isin(used)
q['basic_path_supported']=basic
sample_perfect=basic&q.sid.isin(used)
q['direct_before']=zero
q['direct_after']=zero|sample_perfect
known_action_ids=set(a[a.current_public_matches.gt(0)].action_id)
needed=links[links.event_id.isin(set(q.event_id))].groupby('event_id').action_id.apply(set).to_dict()
has_all_cached=pd.Series([bool(needed.get(e)) and needed[e].issubset(known_action_ids) for e in q.event_id],index=q.index)
q['cache_perfect_before']=zero|(basic&has_all_cached)
q['cache_perfect_after']=q.cache_perfect_before|sample_perfect
q['all_facts_perfect']=zero|(basic&q.potential_interval_source_events.gt(0))
g=q.groupby(['day','sector']).agg(candidates=('event_id','size'),
 direct_before=('direct_before','all'),direct_after=('direct_after','all'),
 cache_perfect_before=('cache_perfect_before','all'),cache_perfect_after=('cache_perfect_after','all'),
 all_facts_perfect=('all_facts_perfect','all')).reset_index()
g['competitive']=g.candidates.gt(2);g['year']=g.day.dt.year
gg=g[g.competitive].copy();N=len(gg);assert N==2112
threshold=math.ceil(.05*N);onepct=math.ceil(.01*N)
rows=[]
for y,t in [('ALL',gg)]+list(gg.groupby('year')):
 for scenario in ['direct','cache_perfect']:
  before=scenario+'_before';after=scenario+'_after';gain=int((~t[before]&t[after]).sum())
  rows.append(dict(year=y,scenario=scenario,competitive_groups=len(t),before_groups=int(t[before].sum()),after_groups=int(t[after].sum()),incremental_groups=gain,incremental_percentage_points=100*gain/len(t)))
s=pd.DataFrame(rows);s.to_csv(O/'GROUP_COVERAGE_CEILING.csv',index=False)
g.to_csv(O/'ALL_GROUP_SUPPORT_CEILING.csv',index=False)
q[['event_id','sid','day','sector','selected_sample_security','basic_path_supported','direct_before','direct_after','cache_perfect_before','cache_perfect_after','all_facts_perfect']].to_csv(O/'CANDIDATE_SUPPORT_CEILING.csv',index=False)
overall=s[s.year.eq('ALL')];best=int(overall.incremental_groups.max())
stop=best<threshold
summary=dict(status='STOP_BEFORE_EXTERNAL_REQUESTS' if stop else 'BOUNDED_SAMPLE_COLLECTION_MAY_PROCEED',
 selected_securities=len(sample),selected_industries=sample.sector.nunique(),
 missing_source_events_in_requested_frame=len(missing),missing_securities=missing.sid.nunique(),
 selected_missing_source_events_total=int(missing.sid.isin(used).sum()),
 mature_competitive_groups=N,material_threshold_groups=threshold,one_percentage_point_groups=onepct,
 strongest_optimistic_incremental_groups=best,strongest_optimistic_incremental_percentage_points=100*best/N,
 original_zero_action_complete_groups=int(gg.direct_before.sum()),
 all_current_cache_perfect_complete_groups=int(gg.cache_perfect_before.sum()),
 all_missing_facts_perfect_complete_groups=int(gg.all_facts_perfect.sum()),
 external_requests=0,request_success_rate=None,actual_fact_admission_rate=None,
 actual_rates_status='NOT_MEASURED: stopped before query' if stop else 'Not yet measured',
 forecast_limits='Only this frozen stratified sample, not proof that no other data recovery could help. Upper bounds forgive all economic issues on sampled securities but do not imply labels. No gains from actual lifecycle exits are estimated.',
 source_hashes_unchanged=all(sha(p)==v for p,v in sources.items()),
 no_outcomes_or_models_or_accounts=True)
assert summary['source_hashes_unchanged']
save('SUMMARY.json',summary)
save('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,ensure_ascii=False,indent=2))
print(s.to_string(index=False))
