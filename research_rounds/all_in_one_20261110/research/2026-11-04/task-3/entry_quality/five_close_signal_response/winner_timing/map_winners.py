"""Frozen original winner control timing over the completed five-close view.

No new gate, no account, no return-label recomputation. Cross-arm monetary
correspondence is verified by decision/sid/role/receipt/core epoch, never local id.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
from datetime import datetime
import json,hashlib,csv
import pandas as pd

getcontext().prec=60
O=Path(__file__).resolve().parent;P=O.parent;E=P.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={};FACTS={}
VIEWS={'2022_weak':('2022-01-04','2022-12-30','2022_2024'),'2024_recovery':('2024-09-02','2024-11-29','2022_2024'),'strong':('2025-07-01','2026-06-30','strong')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def rows(p):p=Path(p);SRC[str(p)]=sha(p);return [json.loads(x) for x in p.open()]
def save(n,z):
 with (O/n).open('x') as f:json.dump(z,f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
def key(x):return (x['sid'],x['decision_at'],x['role'],x.get('receipt'),tuple(x.get('watch_epoch') or []) if x['role']=='core' else ())
def money(z):
 out=dict(rows=len(z),stocks=len({x['sid'] for x in z}),cost=sum((D(x['cost']) for x in z),D(0)),net=sum((D(x['net']) for x in z),D(0)),open_layers=sum(bool(x['qty']) for x in z))
 for field in ['strict_realized','open_unrealized','recognized_dividend_AR']:
  out[field]=None if any(field not in x for x in z) else sum((D(x[field]) for x in z),D(0))
 return out
def grouped(z,fn):
 groups=defaultdict(list)
 for x in z:groups[fn(x)].append(x)
 return [dict(group=k,original_members=len(v),original_money=money([x['original'] for x in v]),matched_original_members=sum(bool(x['matched_actual_No60_rows']) for x in v),matched_actual_No60_money=money([m for x in v for m in x['matched_actual_No60_rows']])) for k,v in sorted(groups.items(),key=lambda kv:str(kv[0]))]
def feedback_groups(z):
 existing={x['group']:x for x in grouped(z,lambda x:x['market_feedback_state'])}
 return [existing.get(k,dict(group=k,original_members=0,original_money=money([]),matched_original_members=0,matched_actual_No60_money=money([]))) for k in ['positive','negative','zero','NO_DATA','outsidewindow']]

def main():
 O.mkdir(parents=True,exist_ok=True)
 save('PROTOCOL.json',dict(frozen_at=datetime.now().astimezone().isoformat(),cohorts='all original fixed83 and94, including all unmatched and outside-analysis dates',root='same confirmed original I root, from unmodified original cached i_target/source segment/full warm; no E0 substitution',market_clock='main view DAILY_FEEDBACK exact original tail decision CLOSE; no forward fill outside view',own_clock='main event valid-close dates/maturity filtered to <=tail decision; left roots have historical first and maturity unknown',money='original contribution and exact corresponding No60 contribution separate; never layer-id cross arm',prohibited=['new gate','new account','winner selection of market mother','new five-close label','deleted money counterfactual']))
 mm=read(P/'SOURCE_MANIFEST.json');assert mm['script_sha256']==sha(P/'analyze.py')
 assert 'FIVE_CLOSE_COMPLETE' in (P/'run.log').read_text();SRC[str(P/'run.log')]=sha(P/'run.log')
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 primary=rows(P/'input_readiness/SIGNALS.jsonl');left=rows(P/'input_readiness/LEFT_CENSORED_FIRST_OBSERVED.jsonl')
 primap={(x['window'],x['original_I_root']):x for x in primary};leftmap={(x['window'],x['original_I_root']):x for x in left};assert len(primap)==len(primary) and len(leftmap)==len(left)
 events={};feedback={};eventmax={}
 for view,(_,_,ref) in VIEWS.items():
  ev=read(P/view/'EVENTS.json');events[view]={x['signal_id']:x for x in ev};feedback[view]={x['day']:x for x in read(P/view/'DAILY_FEEDBACK.json')};eventmax[view]=max(x['day'] for x in ev)
 def lineage(sid,day):
  if sid not in FACTS:
   m=sm[sid];p=Path(m['refs']['facts']);assert sha(p)==m['output_sha256'][str(p)];SRC[str(p)]=sha(p);f=pd.read_parquet(p,columns=['i_target','segment_id']);on=f.i_target.eq(1);opening=on&~on.groupby(f.segment_id).shift(fill_value=False);start=pd.Series(pd.NaT,index=f.index,dtype='datetime64[ns]');start.loc[opening]=f.index[opening];f['I_root_start']=start.groupby(f.segment_id,sort=False).ffill().where(on);FACTS[sid]=f
  f=FACTS[sid];d=pd.Timestamp(day)
  if d not in f.index:return dict(status='no_exact_original_fact_on_decision',I_root=None)
  r=f.loc[d]
  if r.i_target!=1 or pd.isna(r.I_root_start):return dict(status='original_I_not_active_or_root_start_unknown',I_root=None,original_I_target=bool(r.i_target))
  seg=int(r.segment_id);start=str(r.I_root_start.date());return dict(status='exact_original_I_root',I_root=f'{sid}|{seg}|I|{start}',I_root_start=start,source_segment=seg,original_I_target=True,source_max_used_day=day)
 allout={};summary={};checks={}
 for ref in ['2022_2024','strong']:
  source=read(E/'local_high'/(ref+'_FIXED_TAILS.json'));assert len(source)==(83 if ref=='2022_2024' else 94)
  assert len({key(c['original']) for c in source})==len(source)
  out=[];matched_keys=[]
  for c in source:
   original=c['original'];matches=c['matched_actual_No60_rows'];d=original['decision_at'][:10]
   for m in matches:assert key(m)==key(original);matched_keys.append(key(m))
   lin=lineage(original['sid'],d);root=lin['I_root'];k=(ref,root);p=primap.get(k);l=leftmap.get(k);assert not(p and l)
   view=next((v for v,(lo,hi,r) in VIEWS.items() if r==ref and lo<=d<=hi),None)
   daily=None if view is None else feedback[view].get(d)
   fb='outsidewindow' if view is None else 'NO_DATA' if daily is None or daily['feedback_state']=='NO_MATURE_DATA' else daily['feedback_state']
   if p:first_status='primary_complete_root_first';first_day=p['day'];observed_day=p['day'];sid=p['signal_id']
   elif l:first_status='left_censored_historical_first_unknown';first_day=None;observed_day=l['day'];sid=l['signal_id']
   else:first_status='first_not_in_input';first_day=None;observed_day=None;sid=None
   event=None;event_view=None
   if p:
    # The 2024 view deliberately contains previous full-source warmup events.
    order=[view] if view else []
    order += [v for v in (['2024_recovery','2022_weak'] if ref=='2022_2024' else ['strong']) if v not in order]
    for vv in order:
     if sid in events[vv]:event=events[vv][sid];event_view=vv;break
   own=dict(first_status=first_status,primary_first_signal_day=first_day,first_observed_signal_day=observed_day,signal_id=sid,left_censored=bool(l),label_source_view=event_view)
   if l:
    own.update(maturity_state_asof='UNKNOWN_HISTORICAL_FIRST_LEFT_CENSORED',maturity_day_known_asof=None,valid_closes_known_asof=None,remaining_valid_closes_to_five=None,reason='No qualified-opportunity history before this source starts; warm price/I data cannot certify historical first Q or its fifth close.')
   elif p and first_day>d:
    own.update(maturity_state_asof='FIRST_QUALIFIED_SIGNAL_AFTER_TAIL_DECISION',maturity_day_known_asof=None,valid_closes_known_asof=0,remaining_valid_closes_to_five=None,reason='Market-source first Q is later than original decision; retained as explicit discrepancy, not remapped by layer id.')
   elif event:
    known=[q for q in event['valid_close_days'] if q<=d];bad=event['first_bad_day'] is not None and event['first_bad_day']<=d;known_mature=event['maturity_day'] is not None and event['maturity_day']<=d
    state='MATURED_KNOWN_AT_DECISION' if known_mature else 'CLOCK_AMBIGUOUS_KNOWN_AT_DECISION' if bad else 'NOT_YET_FIVE_AT_DECISION'
    own.update(maturity_state_asof=state,maturity_day_known_asof=event['maturity_day'] if known_mature else None,valid_close_days_known_asof=known,valid_closes_known_asof=len(known),remaining_valid_closes_to_five=0 if known_mature else None if bad else 5-len(known),first_bad_day_known_asof=event['first_bad_day'] if bad else None,first_bad_reason_known_asof=event['first_bad_reason'] if bad else None,
     label_observation_end=event['label_observation_end'],reason='Uses only main-event observation dates no later than decision; future maturity/return is never an as-of input.')
   else:
    own.update(maturity_state_asof='UNKNOWN_NO_MAIN_EVENT_LABEL',maturity_day_known_asof=None,valid_closes_known_asof=None,remaining_valid_closes_to_five=None,
     reason='Original I root missing from confirmed signal input.' if not p else 'Complete-root first exists in SIGNALS but is outside every computed main EVENTS cutoff; no new label computed here.')
   fbrow=None if daily is None else {k:daily[k] for k in ['view','day','feedback_state','lookback_first','lookback_last','batch_count','events','median','positive_fraction','p10','negative_mean','mean','effective_weighted_events','latest_batch_day','information_age_market_sessions']}
   out.append(dict(original=original,matched_actual_No60_rows=matches,unmatched=c['unmatched'],decision_day=d,analysis_view=view,market_feedback_state=fb,market_feedback=fbrow,original_I_lineage=lin,own_first_signal_clock=own,winner_is_expost_control_only=True,original_contribution_not_policy_loss=original['net']))
  assert len(matched_keys)==len(set(matched_keys)),'No60 amount would be double-counted across original members'
  assert sum(bool(x['matched_actual_No60_rows']) for x in out)==(45 if ref=='2022_2024' else 67)
  allout[ref]=out;summary[ref]=dict(all_original_members=len(out),all_original_money=money([x['original'] for x in out]),all_matched_original_members=sum(bool(x['matched_actual_No60_rows']) for x in out),all_matched_actual_No60_money=money([m for x in out for m in x['matched_actual_No60_rows']]),
   by_market_feedback=feedback_groups(out),by_own_maturity=grouped(out,lambda x:x['own_first_signal_clock']['maturity_state_asof']),by_market_feedback_and_own_maturity=grouped(out,lambda x:(x['market_feedback_state'],x['own_first_signal_clock']['maturity_state_asof'])),by_view=grouped(out,lambda x:x['analysis_view'] or 'outsidewindow'))
  checks[ref]=dict(original_members=len(out),exact_original_I_lineage=sum(x['original_I_lineage']['status']=='exact_original_I_root' for x in out),own_first_statuses=dict(Counter(x['own_first_signal_clock']['first_status'] for x in out)),no_cross_arm_layer_id_match=True,exact_decision_sid_role_receipt_core_epoch_correspondence=True,matched_No60_keys_unique=True,own_valid_close_asof_dates_not_after_decision=True,
   feedback_exact_day_rows=sum(x['market_feedback'] is not None for x in out),outside_analysis_windows=sum(x['analysis_view'] is None for x in out),new_main_labels_computed=0)
  save(ref+'_WINNER_TIMING.json',out)
  print(ref,json.dumps(summary[ref],ensure_ascii=False,default=str),flush=True)
 flat=[]
 for ref,zs in allout.items():
  for x in zs:
   o=x['original'];c=x['own_first_signal_clock'];flat.append(dict(window=ref,sid=o['sid'],name=o['name'],original_local_layer_id_for_trace=o['layer'],decision_at=o['decision_at'],role=o['role'],original_cost=o['cost'],original_net=o['net'],matched_No60_rows=len(x['matched_actual_No60_rows']),matched_No60_net=str(money(x['matched_actual_No60_rows'])['net']),analysis_view=x['analysis_view'],market_feedback_state=x['market_feedback_state'],I_root=x['original_I_lineage']['I_root'],first_status=c['first_status'],primary_first_signal_day=c['primary_first_signal_day'],first_observed_signal_day=c['first_observed_signal_day'],maturity_state_asof=c['maturity_state_asof'],maturity_day_known_asof=c['maturity_day_known_asof'],valid_closes_known_asof=c['valid_closes_known_asof'],remaining_valid_closes_to_five=c['remaining_valid_closes_to_five']))
 with (O/'ALL_WINNER_TIMING.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 save('SUMMARY.json',summary);save('VALIDATION.json',checks)
 assert all(sha(path)==h for path,h in SRC.items()),'Parent or input output changed during mapping'
 save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),parent_main_manifest_sha256=sha(P/'SOURCE_MANIFEST.json'),new_accounts=0,new_gates=0,new_5close_labels=0,full_market_mother_unchanged=True))
 print('COMPLETE',flush=True)
if __name__=='__main__':main()
