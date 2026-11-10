"""Read fixed saved market shadows only. No FSM, accounts, sizing or new returns."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,csv
import pandas as pd
O=Path(__file__).resolve().parent;R=O/'run_v1';A=O/'analysis_v1';A.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(A/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def describe(vals):
 v=[float(x) for x in vals if x is not None and math.isfinite(float(x))]
 if not v:return dict(n=0)
 s=pd.Series(v);return dict(n=len(v),min=s.min(),median=s.median(),p90=s.quantile(.9),max=s.max(),mean=s.mean())
def counter(vals):return dict(Counter(vals))
run=json.loads((R/'RUN_RECEIPT.json').read_text());assert run['status']=='COMPLETE' and run['errors']==0
for p,h in run['code_sha256'].items():assert sha(p)==h,(p,'code changed after run')
cohort=json.loads((O/'COHORT126_FIXED.json').read_text());names={r['sid']:r['name'] for r in cohort['members']}
pairs=[];gens=[];events=[];daily={};sources={str(R/'RUN_RECEIPT.json'):sha(R/'RUN_RECEIPT.json')}
for d in sorted(R.iterdir()):
 if not d.is_dir():continue
 for fn in ['CP_ANCHOR_PAIRS.json','MARKET_GENERATIONS.json','MARKET_EVENTS.json']:
  p=d/fn
  if not p.exists():continue
  sources[str(p)]=sha(p);x=json.loads(p.read_text())
  if fn=='CP_ANCHOR_PAIRS.json':pairs.extend(x)
  elif fn=='MARKET_GENERATIONS.json':gens.extend(dict(sid=d.name.replace('_','.'),**r) for r in x)
  else:events.extend(x)
 p=d/'MARKET_DAILY.parquet'
 if p.exists():daily[d.name.replace('_','.')]=pd.read_parquet(p)
assert len(pairs)==2901 and len({r['anchor_id'] for r in pairs})==2901
paired=[r for r in pairs if r['status']=='PAIRED_SHADOWS']
assert len(paired)==2867

def exit_relation(p):
 c,a=p['CP'],p['ATR3'];ce,ae=c['exit_day'],a['exit_day']
 if c['outcome']=='EXIT_SIGNAL' and a['outcome']=='EXIT_SIGNAL':
  return 'BOTH_EXIT_ATR_EARLIER' if ae<ce else 'BOTH_EXIT_CP_EARLIER' if ce<ae else 'BOTH_EXIT_SAME_DAY'
 if c['outcome']=='RIGHT_CENSORED' and a['outcome']=='EXIT_SIGNAL':return 'CP_CENSORED_ATR_EXIT_KNOWN'
 if a['outcome']=='RIGHT_CENSORED' and c['outcome']=='EXIT_SIGNAL':return 'ATR_CENSORED_CP_EXIT_KNOWN'
 if c['outcome']=='RIGHT_CENSORED' and a['outcome']=='RIGHT_CENSORED':return 'BOTH_RIGHT_CENSORED'
 return 'UNKNOWN_NOT_ORDERED'

matrix=Counter((r['CP']['status_at20'],r['ATR3']['status_at20']) for r in paired)
same20=[r for r in paired if r['CP']['status_at20']=='ALIVE_AT_20' and r['ATR3']['status_at20']=='ALIVE_AT_20']
policy={};same_policy={}
for label in ['CP','ATR3']:
 b=[r[label] for r in paired]
 policy[label]=dict(status_at20=counter(x['status_at20'] for x in b),outcomes=counter(x['outcome'] for x in b),exit_reasons=counter(x['exit_reason'] or 'NO_EXIT' for x in b),post20_risk=describe(x['post20_max_close_drawdown_ATR'] for x in b),post20_observations=describe(x['post20_observations'] for x in b if x['post20_max_close_drawdown_ATR'] is not None),stop_distance_at20=describe(x['twentieth_observation']['stop_distance_ATR'] for x in b if x['twentieth_observation'] and x['status_at20']=='ALIVE_AT_20'))
 b=[r[label] for r in same20];same_policy[label]=dict(n=len(b),post20_risk=describe(x['post20_max_close_drawdown_ATR'] for x in b),effective_observations_held=describe(x['effective_observations_held'] for x in b),stop_distance_at20=describe(x['twentieth_observation']['stop_distance_ATR'] for x in b))
mother=dict(raw_CP_anchors=len(pairs),all_pair_status=counter(r['status'] for r in pairs),paired=len(paired),common_following_observations_ge20=sum(r['common_observations']>=20 for r in paired),common_following_observations_gt20=sum(r['common_observations']>20 for r in paired),status_at20_matrix=[dict(CP_status=k[0],ATR3_status=k[1],n=v) for k,v in sorted(matrix.items())],exit_comparisons_split_censor=counter(exit_relation(r) for r in paired),rule='No exit-before20/right-censored/unknown row receives zero post20 risk; these have no risk estimate.',common_horizon='From raw anchor until original I invalid/source unknown/source end, not either protection exit.')
save('MOTHER_CENSOR_AND_20STATUS.json',mother)
save('POST20_RISK_DESCRIPTIVE.json',dict(per_policy_own_survivors=policy,both_alive_at20_same_anchor_subset=dict(n=len(same20),policy=same_policy),limits=['Even same-anchor survivors have different policy observation lengths; lower recorded risk can be earlier truncation.','Anchor ATR is fixed ex ante; long-horizon volatility expansion can produce large ATR-normalized drawdowns.','No equity/position weighting, fills, cash, fee, capital reuse or portfolio return.']))

# Cohort-wide descriptive top decile. It is computed only after all signals exist.
q90=float(pd.Series([r['common_favorable_excursion_ATR'] for r in paired]).quantile(.9,interpolation='linear'))
tail=[r for r in paired if r['common_favorable_excursion_ATR']>=q90]
tail_summary=dict(definition='Top decile by common-horizon max favorable close excursion divided by anchor prior ATR; post-signal diagnostic only.',cutoff_q90=q90,quantile_method='pandas linear quantile .9; inclusive ties',n=len(tail),stocks=len({r['sid'] for r in tail}),denominator=len(paired),not_signal_input=True,exit_comparisons_split_censor=counter(exit_relation(r) for r in tail),at20_matrix=[dict(CP_status=k[0],ATR3_status=k[1],n=v) for k,v in sorted(Counter((r['CP']['status_at20'],r['ATR3']['status_at20']) for r in tail).items())],ATR_known_exit_before_CP_observed_end=sum(exit_relation(r) in ['BOTH_EXIT_ATR_EARLIER','CP_CENSORED_ATR_EXIT_KNOWN'] for r in tail),same_comparison_distinct_stocks=len({r['sid'] for r in tail if exit_relation(r) in ['BOTH_EXIT_ATR_EARLIER','CP_CENSORED_ATR_EXIT_KNOWN']}),extra_common_new_peak_after_ATR_truncation_n=sum(exit_relation(r) in ['BOTH_EXIT_ATR_EARLIER','CP_CENSORED_ATR_EXIT_KNOWN'] and r['ATR3']['common_peak_after_shadow_truncation_ATR']>0 for r in tail),limits=['Raw anchors overlap within a stock: these are not independent trades.','Common horizon length varies by original-I lifetime and source censor; this is not fixed20-day future return.','Censored CP/ATR branches do not have an observed later exit date.','Subsequent main-FSM restart may rejoin the price path; pair early exit is not whole-strategy permanent exclusion.'])
save('TAIL_DECILE_SUMMARY.json',tail_summary);save('TAIL_DECILE_ALL_ANCHORS.json',tail)
flat=[]
for r in pairs:
 f={k:r.get(k) for k in ['sid','anchor_day','anchor_id','status','anchor_C','anchor_ATR_prior','P0','common_observations','common_end_reason','common_end_day','common_favorable_excursion_ATR']};f['name']=names[r['sid']];f['tail_top_decile']=r['status']=='PAIRED_SHADOWS' and r['common_favorable_excursion_ATR']>=q90
 f['exit_relation']=exit_relation(r) if r['status']=='PAIRED_SHADOWS' else 'NO_PAIRED_RESULT'
 for label in ['CP','ATR3']:
  b=r.get(label) or {}
  for k in ['outcome','exit_day','exit_reason','effective_observations_held','status_at20','post20_observations','post20_max_close_drawdown_ATR','common_peak_after_shadow_truncation_ATR']:
   f[label+'__'+k]=b.get(k)
 flat.append(f)
save('ALL2901_CP_PAIR_INDEX.json',flat)
with (A/'ALL2901_CP_PAIR_INDEX.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(clean(flat))

main=dict(display_rows=run['display_observations'],event_counts=counter(r['kind'] for r in events),visible_generations=len(gens),window_started_generations=sum(r['start_day']>='2025-01-01' for r in gens),prior_window_origins_retained=sum(r['start_day']<'2025-01-01' for r in gens),visible_generations_with_channel=sum(r['channel_day'] is not None for r in gens),visible_generations_mature=sum(r['mature'] for r in gens),generation_end_reasons=counter(r['end_reason'] for r in gens),seen_but_not_mature_end_reasons=counter(r['end_reason'] for r in gens if r['channel_day'] is not None and not r['mature']),scope='Market observation shadows only; not positions/fills or capital permissions.')
save('MAIN_FSM_SUMMARY.json',main)

orig=json.loads((O/'ORIGINAL25_IDENTITY_ANNOTATIONS_ONLY.json').read_text());annotations=[]
for r in orig['layers']:
 t=pd.Timestamp(r['decision_at'][:10]);d=daily[r['sid']];assert t in d.index;x=d.loc[t]
 annotations.append(dict(original=r,market_shadow_on_original_decision={k:x.get(k) for k in ['mode','generation_id','current_mature','channel_day','A','S','j_consumed','CHANNEL_seen','CHANNEL_advance','exit_event_count','bundle_priority','C','raw_C']},not_claimed='No new trade/size/fill/held/probe qualification or old-position inheritance inferred.'))
save('ORIGINAL25_MARKET_ANNOTATIONS_ONLY.json',annotations)

# Source-backed full-universe fat-tail case, including main restart separately.
sid='688498.SH';gs=[r for r in gens if r['sid']==sid];de=daily[sid];pe=next(r for r in pairs if r['sid']==sid and r['anchor_day']=='2025-05-28');case_days=['2025-05-06','2025-05-28','2025-09-05','2025-09-08','2025-09-11','2025-09-30','2025-10-21','2026-06-30'];case_rows=[]
for day in case_days:
 x=de.loc[pd.Timestamp(day)];case_rows.append(dict(day=day,**{k:x.get(k) for k in ['C','raw_C','mode','generation_id','channel_day','A','S','j_consumed','hard_old','P_old','shadow_peak_before','ATR14_prior','P_next','CHANNEL_seen','CHANNEL_advance','exit_event_count','current_mature']}))
save('YUANJIE_688498_PAIR_AND_MAIN_RESTART.json',dict(sid=sid,name=names[sid],common_anchor_pair=pe,main_generations=gs,selected_main_rows=case_rows,selected_main_events=[r for r in events if r['sid']==sid and r['day'] in case_days],interpretation='The same-anchor ATR3 shadow exits2025Sep08 while CP remains censored at2026Jun30. Independent main FSM restarts2025Sep11, sees channelSep30, first1S-advanceOct21 and remains mature at source end. Neither can be converted to actual fills or strategy return.'))

summary=dict(status='SAVED_OUTPUT_POSTPROCESS_COMPLETE',raw_anchors=len(pairs),paired=len(paired),market_display_rows=run['display_observations'],main_fsm=main,paired_mother=mother,post20_risk_sample_sizes={k:policy[k]['post20_risk']['n'] for k in policy},tail_summary=tail_summary,source_sha256=sources,script_sha256=sha(__file__),parameter_or_code_changes=False,new_FSM_runs=0,new_accounts=0,new_quantities=0,new_returns=0)
save('POSTPROCESS_RECEIPT.json',summary)
print(json.dumps(clean(dict(raw_anchors=len(pairs),paired=len(paired),main_event_counts=main['event_counts'],post20_sample_sizes=summary['post20_risk_sample_sizes'],exit_relations=mother['exit_comparisons_split_censor'],tail_exit_relations=tail_summary['exit_comparisons_split_censor'])),ensure_ascii=False))
