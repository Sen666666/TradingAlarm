"""Read-only source audit. Writes only this new audit directory; no engine replay."""
from pathlib import Path
import json,gzip,hashlib,math,collections
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
R=O.parent; W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
P=R/'act_only_ablation_continuous_v1/run/pair'; U=W/'universe-cp1-inputs-20261031'
D='2022-01-04'; FILL='2022-01-05'
sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def register(p):
 p=str(p);sources.setdefault(p,sha(p));return p
def js(p):return json.loads(Path(register(p)).read_text())
def par(p):return pd.read_parquet(register(p))
def norm(v):
 if isinstance(v,dict):return {str(k):norm(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [norm(x) for x in v]
 if isinstance(v,np.generic):return norm(v.item())
 if isinstance(v,pd.Timestamp):return str(v.date())
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def save(name,v): (O/name).write_text(json.dumps(norm(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csv(name,rows):pd.DataFrame(norm(rows)).to_csv(O/name,index=False)
def before_rows(fn,end=FILL):
 path=register(P/(fn+'.jsonl.gz'));out=[]
 with gzip.open(path,'rt') as f:
  for l in f:
   r=json.loads(l);day=r.get('day',r.get('at',''))[:10]
   if day>end:break
   if r.get('account')=='PVR':out.append(r)
 return out
def current_start(f,column,day=D):
 h=f.loc[:day];v=h[column].fillna(False).astype(bool)
 if not bool(v.iloc[-1]):return None
 seg=h.segment_id.iloc[-1] if 'segment_id' in h else None
 starts=v&(~v.shift(fill_value=False)|(h.segment_id.ne(h.segment_id.shift()) if 'segment_id' in h else False))
 return str(h.index[starts][-1].date())
def event_info(ev,day,prefix):
 if not day or pd.Timestamp(day) not in ev.index:return {}
 r=ev.loc[day]
 return {prefix+'observable_day':day,prefix+'sign':r.event,prefix+'confirmation':r.confirmation,prefix+'pivot_day':r.confirmed_pivot_date,prefix+'pivot_price':r.confirmed_pivot_price,prefix+'pivot_age_observations':r.pivot_age}
def last_event(ev,day,sign=None):
 h=ev.loc[:day];h=h[h.event.eq(sign)] if sign else h[h.event.isin([-1,1])]
 return str(h.index[-1].date()) if len(h) else None
def cp_anchor(z,day):
 h=z.loc[:day]
 # A receipt row uses the pre-receipt anchor; today's receipt resets only for the next observation.
 prior=h.iloc[:-1]
 reset=prior.reset_reason.isin(['start','E0_down_reset','lower_anchor','receipt_consumed'])
 return str(prior.index[reset][-1].date()) if reset.any() else None
raw=json.load(gzip.open(register(P/'PVR.json.gz'),'rt'))
fills=[r for r in raw['journal'] if r.get('kind')=='real_buy_fill' and r['at'].startswith(FILL)]
assert len(fills)==len({r['sid'] for r in fills})==52
decision=next(r for r in raw['decisions'] if r['at'].startswith(D))
intents={(r['sid'],r['role']):r for r in decision['intents']}
opps={r['sid']:r for r in before_rows('opportunities',D)}
rank={r['sid']:r for r in before_rows('rank-policy',D)}
funding=before_rows('funding');daily=before_rows('daily')
close=next(r for r in daily if r['at'].startswith(FILL))
clayer={r['sid']:r for r in close['layers']}
stage_events=before_rows('industry')
sm={r['symbol']:r for r in js(U/'STOCK_MANIFEST.json')}
im={r['series']:r for r in js(U/'INDUSTRY_MANIFEST.json')}
rm={r['sid']:r for r in js(W/'2022-normal-reference-20261031/inputs/MANIFEST.json')}
sectors=sorted({opps[r['sid']]['sector'] for r in fills})
sector_rows=[];sector_detail={}
for sector in sectors:
 m=im[sector];z=par(m['refs']['CP1']).loc[:FILL];q=par(m['refs']['CP1_input']).loc[:FILL]
 st=par(m['refs']['state']);st=st[st.day<=FILL].copy()
 evpath=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'))
 fxpath=next(p for p in m['source_sha256'] if '/industry-facts/' in p)
 ev=par(evpath).loc[:FILL];fx=par(fxpath).loc[:FILL]
 a=st[st.day==D].iloc[0];pre=st[st.day<'2022-01-01'].iloc[-1]
 ep=st[st.E0_episode==a.E0_episode];epstart=ep.day.iloc[0]
 attempt=st[st.attempt_id==a.attempt_id]
 first=attempt[attempt.action.eq('probe')].iloc[0]
 histories=attempt[attempt.new_receipt&attempt.receipt&(attempt.day<=D)]
 cpdays=histories.day.tolist()
 previous=fx.loc[fx.index<pd.Timestamp(D)].iloc[-1]; previous_day=str(fx.index[fx.index<pd.Timestamp(D)][-1].date())
 yearend=fx.loc[:'2021-12-31'].iloc[-1]; yearend_day=str(fx.loc[:'2021-12-31'].index[-1].date())
 row=dict(sector=sector,signal_close_original_coordinate=a.close,signal_raw_close=fx.loc[D,'raw_close'],
  signal_adjustment_factor=fx.loc[D,'factor'],previous_observable_day=previous_day,previous_close_original_coordinate=previous.close,
  year2021_last_observable_day=yearend_day,year2021_last_close_original_coordinate=yearend.close,
  signal_E0_floor_distance_fraction=1-a.E0_floor/a.close,
  signal_previous_mobile_line=a.mobile_before,
  signal_previous_mobile_line_distance_fraction=1-a.mobile_before/a.close,
  E0_ready=fx.loc[D,'e0_ready'],E0_valid=a.E0_valid,E0_floor=a.E0_floor,
  E0_episode=a.E0_episode,E0_episode_start_observable_day=epstart,
  prior_asof=pre.day,prior_stage=pre.stage_name,prior_attempt_id=pre.attempt_id,
  signal_stage=a.stage_name,signal_stage_number=a.stage,signal_action=a.action,
  signal_attempt_id=a.attempt_id,attempt_probe_observable_day=first.day,
  attempt_probe_receipt_id=first.receipt_id,attempt_confirmed_observable_day=next((r.day for _,r in attempt.iterrows() if r.stage==2 and r.day<=D),None),
  attempt_expanded_observable_day=next((r.day for _,r in attempt.iterrows() if r.stage==3 and r.day<=D),None),
  attempt_receipt_observable_days_through_signal='|'.join(cpdays),latest_attempt_receipt_observable_day=cpdays[-1],
  signal_CP1_receipt=bool(z.loc[D,'receipt']),signal_CP1_candidate=z.loc[D,'candidate'],
  signal_CP1_anchor_formation_day=cp_anchor(z,D),
  latest_CP1_formation_start_exclusive=cp_anchor(z,cpdays[-1]),latest_CP1_confirmed_day=cpdays[-1],
  industry_G='not_computed_not_used_by_original_strategy',industry_I='not_computed_not_used_by_original_strategy',
  signal_mobile_line=a.mobile_after,close_nextday_stage=st[st.day==FILL].iloc[0].stage_name,
  inherited_active_before_2022=pre.attempt_id is not None,
  facts_source=fxpath,state_source=m['refs']['state'],events_source=evpath,CP1_source=m['refs']['CP1'])
 row.update(event_info(ev,epstart,'E0_origin_'))
 row.update(event_info(ev,last_event(ev,D,1),'latest_up_event_'))
 for k in ['ready','phase','scale','credit','delta_frontier','displacement','r','s','B','u','v','m']:
  row['signal_CP1_'+k]=z.loc[D,k]
 sector_rows.append(row);sector_detail[sector]=row
 # Only evidence through 1/4, plus separate close snapshot, never future outcome labels.
csv('INDUSTRY_25_PRIOR_TRACE.csv',sector_rows);save('INDUSTRY_25_PRIOR_TRACE.json',sector_rows)
rows=[];detail=[]
for n,fill in enumerate(fills,1):
 sid=fill['sid'];m=sm[sid];sector=opps[sid]['sector'];i=intents[sid,fill['role']];rnk=rank[sid]
 f=par(m['refs']['facts']).loc[:D];z=par(m['refs']['CP1']).loc[:D];q=par(m['refs']['CP1_input']).loc[:D]
 evpath=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'))
 gx=next(p for p in m['source_sha256'] if '/ix-a-share-entry-' in p)
 ev=par(evpath).loc[:D];g=par(gx).loc[:D]
 fr=f.loc[D];zz=z.loc[D];gg=g.loc[D]
 receipts=js(rm[sid]['output_path']);cpr=next((r for r in receipts if r['confirmed_day']==D),None)
 sf=[r for r in funding if r.get('sid')==sid and r['at'].startswith(FILL)]
 corefail=next((r['result'] for r in sf if r['role']=='core' and r['result']!='reserved'),None)
 e0start=current_start(f,'e0_target');istart=current_start(f,'i_target')
 s=sector_detail[sector]
 row=dict(fill_sequence=n,sid=sid,sector=sector,signal_at=fill['signal_at'],fill_at=fill['at'],
  actual_role=fill['role'],actual_fill_pool=fill['pool'],next_close_pool=clayer[sid]['pool'],
  core_Q=opps[sid]['core_Q'],mobile_Q=opps[sid]['mobile_Q'],candidate_roles='|'.join(opps[sid]['roles']),
  actual_reason=i['reason'],core_pre_attempt_rejection=corefail,
  H1_score=i['score'],original_H1_rank=i['original_H1_rank'],PVR_score=i['PVR_score'],priority_rank=i['priority_rank'],
  original_candidate_slot=rnk['original_slot'],PVR_candidate_slot=rnk['final_slot'],
  E0_episode_start_observable_day=e0start,I_episode_start_observable_day=istart,
  G_phase=gg.phase,G_up_reasons=gg.up_reasons,G_z5=gg.z5,G_z21=gg.z21,G_acute_up=gg.acute_up,
  CP1_exists_today=cpr is not None,CP1_consumed_by_actual_order=fill['CP1_id'] is not None,
  actual_CP1_id=fill['CP1_id'],available_CP1_id=cpr['receipt_id'] if cpr else None,
  CP1_formation_start_exclusive=cpr['formation_start_exclusive'] if cpr else None,
  CP1_confirmation_observable_day=cpr['confirmed_day'] if cpr else None,
  CP1_scale_frozen_at=cpr['scale_frozen_at'] if cpr else None,
  CP1_original_E0_episode_id=cpr['original_E0_episode_id'] if cpr else None,
  protection_floor_adjusted=float(i['floor']),protection_floor_raw_at_signal=float(i['floor'])/fr.factor,
  protection_basis='I_floor' if fill['role']=='core' else 'max(I_floor,CP1_candidate)',
  protection_distance_at_signal=1-float(i['floor'])/fr.close,
  industry_E0_valid=s['E0_valid'],industry_E0_start_observable_day=s['E0_episode_start_observable_day'],
  industry_E0_origin_pivot_day=s.get('E0_origin_pivot_day'),industry_prior_stage=s['prior_stage'],
  industry_signal_stage=s['signal_stage'],industry_attempt_probe_observable_day=s['attempt_probe_observable_day'],
  industry_attempt_confirmed_observable_day=s['attempt_confirmed_observable_day'],
  industry_attempt_expanded_observable_day=s['attempt_expanded_observable_day'],
  industry_CP1_latest_confirmed_day=s['latest_CP1_confirmed_day'],
  industry_CP1_latest_formation_start_exclusive=s['latest_CP1_formation_start_exclusive'],
  industry_G=s['industry_G'],industry_I=s['industry_I'],
  facts_source=m['refs']['facts'],G_source=gx,CP1_source=m['refs']['CP1'],receipt_source=rm[sid]['output_path'])
 row.update({'fact_'+k:v for k,v in fr.items()})
 row.update({'CP1_'+k:v for k,v in zz.items()})
 row.update(event_info(ev,e0start,'E0_origin_'))
 row.update(event_info(ev,last_event(ev,D,1),'last_up_event_'))
 assert i['original_H1_rank']==rnk['original_H1_rank'] and i['priority_rank']==rnk['priority_rank'] and i['PVR_score']==rnk['PVR']
 assert row['fact_i_target']==1 and row['fact_e0_target']==1 and opps[sid]['mobile_Q'] is True
 assert fill['signal_at'].startswith(D)
 if fill['role']=='mobile':
  assert cpr and fill['CP1_id']==cpr['receipt_id'] and float(i['floor'])==max(float(fr.i_floor),float(zz.candidate))
  assert cpr['formation_start_exclusive']<cpr['confirmed_day']==D
 else:
  assert float(i['floor'])==float(fr.i_floor) and opps[sid]['core_Q'] is True
 assert bool(zz.receipt)==bool(cpr)
 rows.append(row);detail.append(dict(sid=sid,fill=fill,intent=i,opportunity=opps[sid],rank=rnk,funding=sf,receipt=cpr,industry=s))
csv('FIRST_DAY_52_SIGNAL_EVIDENCE.csv',rows);save('FIRST_DAY_52_SIGNAL_EVIDENCE.json',rows);save('FIRST_DAY_52_ORIGINAL_RECEIPTS.json',detail)
# Freeze source formula/semantics bytes without importing or running any strategy.
codepaths=[
 W/'case-stage-ledger-20261031/v3/joint_v3.py',W/'pvr-slot1-native-readiness-20261101/native_rank.py',
 R/'account_comparison_continuous_v1/inputs/continuous_inputs.py',
 Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py'),
 Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py'),
 W/'account-risk-ablation-20261031/route_without_account_check.py',
 W/'account-risk-ablation-20261031/model_without_account_check.py',
 W/'industry-mobile-stage-20261031/stage.py',W/'native-I-cache-interface-20261031/cache.py',
 W/'pvr-current-v3-information-capital-20261101/original_score_function.py',
 RR/'continuous-protection-lines-20261028/code/model.py',RR/'b5-g1-20261025/code/policies_g1.py',
 RR/'b5-g1-20261025/code/grade.py',RR/'pv-strength-b4-20261025/code/model.py',
 RR/'pv-strength-b5-20261025/code/evidence.py',RR/'pv-strength-b5-20261025/code/policy.py',
 RR/'lot-risk-allocation-20261029/code/study.py']
for p in codepaths:register(p)
checks=dict(fills=52,unique_stocks=52,industries=len(sectors),
 original_signal_date=D,fill_date=FILL,decision_intents=len(decision['intents']),
 decision_unique_stocks=len({i['sid'] for i in decision['intents']}),
 decision_roles=dict(collections.Counter(i['role'] for i in decision['intents'])),
 actual_roles=dict(collections.Counter(r['actual_role'] for r in rows)),
 actual_fill_pools=dict(collections.Counter(r['actual_fill_pool'] for r in rows)),
 next_close_pools=dict(collections.Counter(r['next_close_pool'] for r in rows)),
 G_grades=dict(collections.Counter(r['fact_g_grade'] for r in rows)),
 I_buy_counts=dict(collections.Counter(r['fact_i_buy'] for r in rows)),
 G_fresh_up_counts=dict(collections.Counter(r['fact_g_fresh_up'] for r in rows)),
 stock_CP1_today=sum(r['CP1_exists_today'] for r in rows),
 actual_CP1_used=sum(r['CP1_consumed_by_actual_order'] for r in rows),
 core_rejected_then_mobile=sum(r['actual_role']=='mobile' and r['core_pre_attempt_rejection'] is not None for r in rows),
 mobile_without_core=[r['sid'] for r in rows if r['actual_role']=='mobile' and r['core_pre_attempt_rejection'] is None],
 industry_prior_stages=dict(collections.Counter(r['prior_stage'] for r in sector_rows)),
 industry_signal_stages=dict(collections.Counter(r['signal_stage'] for r in sector_rows)),
 industry_E0_start_years=dict(collections.Counter(r['E0_episode_start_observable_day'][:4] for r in sector_rows)),
 industry_attempt_probe_years=dict(collections.Counter(r['attempt_probe_observable_day'][:4] for r in sector_rows)),
 all_52_I_E0_active=True,all_52_mobile_Q_true=True,rank_log_exact=True,actual_order_receipt_ID_exact=True,
 all_original_sources_unchanged=all(sha(p)==h for p,h in sources.items()),
 source_files_checked=len(sources),no_economic_runs=True,no_strategy_edits=True,no_future_return_labels=True,
 industry_G_I_not_in_original_input=True,
 date_warning='observable event/receipt day is distinct from pivot/formation start day',
 migration_warning='fill journal pools are pre-cancel_ack. Full-fill cancel_ack can migrate lot ownership during the same OPEN; CLOSE is a later verified snapshot, not proof of migration time.',
 PIT_warning='Original fixed 1709 universe, historical tradability UNKNOWN and action terms assumed preknown. Daily causal trace is not a full PIT investability claim.')
assert checks['all_original_sources_unchanged']
expected={}
for m in [sm[r['sid']] for r in fills]+[im[s] for s in sectors]:
 expected.update(m['source_sha256']);expected.update(m['output_sha256'])
for r in fills:
 m=rm[r['sid']];expected[m['output_path']]=m['output_sha256']
checked={p:h for p,h in expected.items() if p in sources}
assert all(sources[p]==h for p,h in checked.items()), 'frozen manifest hash mismatch'
checks['source_declared_hashes_verified']=len(checked)
checks['stock_all_52_E0_start_before_2022']=all(r['E0_episode_start_observable_day']<'2022-01-01' for r in rows)
checks['stock_all_52_I_start_before_2022']=all(r['I_episode_start_observable_day']<'2022-01-01' for r in rows)
save('CHECKS.json',checks);save('SOURCE_SHA256.json',sources)
print(json.dumps(norm(checks),ensure_ascii=False,indent=2))
