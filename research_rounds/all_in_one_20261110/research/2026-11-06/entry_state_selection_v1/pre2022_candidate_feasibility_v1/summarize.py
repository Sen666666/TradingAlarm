"""Pure coverage aggregation plus CP/core-field readiness; no returns or lifecycle simulation."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,v):(O/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'SUPPLEMENT_QA.json').exists()
initial=json.load(open(O/'OUTPUT_HASHES.json'))
assert all(sha(O/p)==h for p,h in initial.items())
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}
c=pd.read_csv(O/'ALL_AB_CANDIDATES.csv',parse_dates=['day'])
q=pd.read_csv(O/'ALL_FEASIBLE_120D_DATA_COVERAGE.csv',parse_dates=['day','entry_proxy_day','horizon_day'])
a=pd.read_csv(O/'POTENTIAL_ACTION_REQUIREMENTS.csv')
ov=pd.read_csv(O/'CANDIDATE_ACTION_OVERLAP.csv')
cal=pd.DatetimeIndex(pd.read_csv(O/'DAILY_SOURCE_COVERAGE.csv',usecols=['day']).day).sort_values()
q['full120_CP_fields_ready']=False;q['full120_active_I_floor_ready']=False
sources={}
for sid,g in q[q.mature_by_20211231].groupby('sid'):
 m=sm[sid];p=m['refs']['CP1'];fp=m['refs']['facts']
 for pp in [p,fp]:
  sources[pp]=sha(pp);assert sources[pp]==m['output_sha256'][pp]
 cp=pd.read_parquet(p,columns=['ready','receipt','candidate']).loc[:'2021-12-31'].reindex(cal)
 f=pd.read_parquet(fp,columns=['i_target','i_floor']).loc[:'2021-12-31'].reindex(cal)
 cpvalid=cp.ready.eq(True)&(cp.receipt.eq(False)|(cp.receipt.eq(True)&np.isfinite(cp.candidate)&cp.candidate.gt(0)))
 ifloor=f.i_target.eq(0)|(f.i_target.eq(1)&np.isfinite(f.i_floor)&f.i_floor.gt(0))
 for row in g.itertuples():
  w=cal[(cal>=row.entry_proxy_day)&(cal<=row.horizon_day)];assert len(w)==120
  q.loc[row.Index,'full120_CP_fields_ready']=bool(cpvalid.reindex(w).all())
  q.loc[row.Index,'full120_active_I_floor_ready']=bool(ifloor.reindex(w).all())
q['extended_zero_action_source_support']=q.zero_action_conditional_proxy_data_available&q.full120_CP_fields_ready&q.full120_active_I_floor_ready
q=q.merge(c[['event_id','sector','event_type']],on='event_id',validate='one_to_one')
q.to_csv(O/'EXTENDED_POTENTIAL_120D_SOURCE_COVERAGE.csv',index=False)
m=q[q.mature_by_20211231].copy()
rows=[]
for year,g in [('ALL',m)]+list(m.groupby('year')):
 for arm,z in [('ALL',g),('PVR_TOPK',g[g.potential_flat_selected]),('UNSELECTED',g[~g.potential_flat_selected])]:
  ids=set(z.event_id);links=ov[ov.event_id.isin(ids)];actions=a[a.action_id.isin(links.action_id)]
  n=len(z);ok=z.extended_zero_action_source_support
  rows.append(dict(year=year,arm=arm,mature_candidates=n,signal_days=z.day.nunique(),stocks=z.sid.nunique(),industries=z.sector.nunique(),full_price_path=int(z.full120_observed_price_open_valid.sum()),CP_fields_ready=int(z.full120_CP_fields_ready.sum()),active_I_floor_ready=int(z.full120_active_I_floor_ready.sum()),extended_zero_action_support=int(ok.sum()),support_fraction_of_mature=float(ok.mean()),supported_signal_days=z[ok].day.nunique(),supported_stocks=z[ok].sid.nunique(),supported_industries=z[ok].sector.nunique(),unique_potential_actions=len(actions),share_actions=int((~actions.pure_cash).sum()),minimum_public_fields_events=int(actions.public_minimum_dates_present.sum()),matched_multiple_events=int(actions.current_public_matches.gt(1).sum()),with_interval_actions=int(z.potential_interval_source_events.gt(0).sum()),potential_action_overlaps=len(links)))
pd.DataFrame(rows).to_csv(O/'MATURE_COVERAGE_SUMMARY.csv',index=False)
groups=m.groupby(['day','sector']).agg(feasible=('event_id','size'),supported=('extended_zero_action_source_support','sum'),topK=('potential_flat_selected','sum')).reset_index()
groups['competitive']=groups.feasible.gt(2);groups['all_source_supported']=groups.supported.eq(groups.feasible);groups['year']=groups.day.dt.year
groups.to_csv(O/'MATURE_COMPETITION_SUPPORT.csv',index=False)
gs=groups.groupby('year').agg(groups=('day','size'),competitive=('competitive','sum'),all_supported=('all_source_supported','sum'))
gs['competitive_and_all_supported']=groups[groups.competitive&groups.all_source_supported].groupby('year').size()
gs.fillna(0).to_csv(O/'MATURE_COMPETITION_SUPPORT_YEAR.csv')
action_mature_ids=set(ov[ov.event_id.isin(set(m.event_id))].action_id)
a['intersects_at_least_one_mature_candidate']=a.action_id.isin(action_mature_ids)
a.to_csv(O/'ACTION_REQUIREMENTS_WITH_MATURITY.csv',index=False)
assert all(sha(O/p)==h for p,h in initial.items())
assert all(sha(p)==h for p,h in sources.items())
save('SUPPLEMENT_SOURCE_HASHES.json',sources)
save('SUPPLEMENT_QA.json',dict(status='PASS',main_outputs_unchanged=True,additional_source_hashes_unchanged=True,CP_field_checks=len(m),no_return_or_label_or_trade_simulation=True,total_mature=len(m),extended_zero_action_source_support=int(m.extended_zero_action_source_support.sum()),latest_mature_signal=str(m.day.max()),latest_mature_entry=str(m.entry_proxy_day.max()),source_support_not_economic_labels=True,CP_scope='Ready plus explicit receipt False or True with positive finite candidate; active original I requires positive finite floor. This checks fields, not profit-gated additions, fills, actual entitlements or tradability.'))
print(pd.DataFrame(rows).to_string(index=False))
