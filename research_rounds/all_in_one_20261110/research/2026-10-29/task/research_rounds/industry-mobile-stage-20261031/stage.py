"""Research-only market authorization trace; owns no cash, orders or positions."""
from pathlib import Path
import math,json,hashlib,importlib.util,sys,time,collections
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;P=W/'cp1-evidence-trace-20261031'
spec=importlib.util.spec_from_file_location('stage_read_original_trace',P/'trace.py');T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)
def save(n,x):
 x=T.norm(x);(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if isinstance(x,list) and x:pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
class Stage:
 def __init__(self,sid):self.sid=sid;self.attempt=None;self.stage=0;self.line=None;self.auth=None;self.seen=set();self.last=None;self.fingerprint=None;self.cached=None;self.segment=None;self.ep=None;self.attempt_count=0
 def step(self,day,close,valid,floor,receipt,candidate,rid,episode,segment):
  data=(str(day),close,valid,floor,receipt,candidate,rid,episode,str(segment));fp=T.ident(T.norm(data))
  if self.last==str(day):
   if fp!=self.fingerprint:raise ValueError('conflicting same-observation input')
   return self.cached.copy()
  if self.last is not None and str(day)<self.last:raise ValueError('noncausal clock')
  old_stage=self.stage;old_attempt=self.attempt;old_line=self.line;old_auth=self.auth;action='hold';reason=None;usable=False;new=False
  if receipt:
   if not rid:raise ValueError('receipt identity missing')
   new=rid not in self.seen;self.seen.add(rid)
  source_change=self.segment is not None and str(segment)!=self.segment
  ep_change=self.attempt is not None and episode!=self.ep
  known=valid is not None and close is not None and math.isfinite(close) and close>0 and (not valid or floor is not None and math.isfinite(floor))
  invalid=valid is False or source_change or ep_change
  line_hit=bool(known and valid and self.attempt is not None and T.M.ge(self.line,close))
  if invalid or line_hit:
   reason='E0_invalid' if valid is False else 'source_change' if source_change else 'episode_change' if ep_change else 'mobile_line'
   action='end_attempt' if self.attempt else 'observe';self.attempt=None;self.stage=0;self.line=None;self.auth=None
  elif not known or receipt and (candidate is None or not math.isfinite(candidate)):
   action='unknown';reason='market_input_unknown';self.auth=None
  elif self.attempt is None:
   if receipt and new:
    self.attempt=T.ident('industry-attempt',self.sid,episode,rid);self.attempt_count+=1;self.stage=1;self.line=max(candidate,floor);self.auth=rid;action='probe';usable=True
  else:
   self.line=max(self.line,floor)
   if receipt and new:
    self.line=max(self.line,candidate);self.stage=min(3,self.stage+1);self.auth=rid;action='confirmed' if self.stage==2 else 'expanded' if old_stage<3 else 'replace_at_expanded'
   usable=self.auth is not None
  self.segment=str(segment);self.ep=episode
  row=dict(day=str(day),close=close,E0_valid=valid,E0_episode=episode,E0_floor=floor,receipt=receipt,receipt_id=rid,new_receipt=new,candidate_floor=candidate,attempt_before=old_attempt,attempt_id=self.attempt,attempt_number=self.attempt_count,stage_before=old_stage,stage=self.stage,stage_name=['observe','probe','confirmed','expanded'][self.stage],mobile_before=old_line,mobile_after=self.line,action=action,reason=reason,authorization_before=old_auth,authorization_id=self.auth,authorization_usable=usable,unused_old_authorization_revoked=old_auth is not None and old_auth!=self.auth,receipt_ignored_same_observation=bool(receipt and new and (invalid or line_hit)),financial_state_owned=False,existing_exposure_or_loss_reset=False)
  self.last=str(day);self.fingerprint=fp;self.cached=row.copy();return row
def run(sid,f,z,receipt_ids,start=None):
 ep=(f.e0_valid&~f.e0_valid.shift(fill_value=False)).cumsum();state=Stage(sid);rows=[]
 for d,r in f.iterrows():
  day=str(d.date())
  if start and day<start:continue
  q=z.loc[d];rid=receipt_ids.get(day) if bool(q.receipt) else None
  episode=T.ident('E0',sid,str(r.segment_id),str(f.index[ep.eq(ep.loc[d])][0].date())) if r.e0_valid else None
  rows.append(state.step(day,float(r.close),bool(r.e0_valid),float(r.i_floor) if pd.notna(r.i_floor) else None,bool(q.receipt),float(q.candidate) if pd.notna(q.candidate) else None,rid,episode,r.segment_id))
 return rows
def tests():
 s=Stage('TEST');step=lambda day,c,fl=80.,rec=False,ca=None,rid=None,ep='e1',v=True:s.step(day,c,v,fl,rec,ca,rid,ep,0)
 checks=[]
 a=step('01',100,rec=True,ca=90,rid='r1');assert a['stage']==1;checks.append('first_receipt_probe')
 assert step('01',100,rec=True,ca=90,rid='r1')==a;checks.append('same_observation_idempotent')
 try:step('01',101,rec=True,ca=90,rid='r1');raise AssertionError('not rejected')
 except ValueError:checks.append('same_observation_conflict_rejected')
 a=step('02',101,rec=True,ca=91,rid='r1');assert a['stage']==1 and not a['new_receipt'];checks.append('old_receipt_cannot_promote')
 a=step('03',102,rec=True,ca=92,rid='r2');assert a['stage']==2;checks.append('new_observation_confirmed')
 a=step('04',103,rec=True,ca=93,rid='r3');assert a['stage']==3;checks.append('new_observation_expanded')
 a=step('05',92,rec=True,ca=90,rid='r4');assert a['stage']==0 and a['receipt_ignored_same_observation'];checks.append('old_line_first_no_same_bar_restart')
 a=step('06',94,rec=True,ca=90,rid='r5');assert a['stage']==1 and a['attempt_number']==2;checks.append('later_receipt_new_probe')
 a=step('07',95,fl=91,rec=False);assert a['mobile_after']==91;checks.append('floor_monotone_without_receipt')
 a=step('08',None);assert not a['authorization_usable'] and a['attempt_id'] is not None;checks.append('missing_freezes_authority_retains_responsibility')
 a=step('09',94,v=False,ep=None,rec=True,ca=90,rid='r6');assert a['stage']==0 and not a['authorization_usable'];checks.append('E0_invalid_first')
 assert all(not a[k] for k in ['financial_state_owned','existing_exposure_or_loss_reset']);checks.append('no_financial_reset_or_fake_fills')
 return checks
def main():
 t=time.monotonic();sources=[Path(__file__),O/'PROTOCOL.txt',P/'trace.py',T.ORIG/'code/model.py',P/'SIX_PATHS_INPUT_FROZEN.json'];save('FREEZE',dict(before_run=True,sha256={str(p):T.sha(p) for p in sources},new_economic_paths=0));checks=tests();synth={};ss=[];ridrows=T.read(P/'SIX_PATHS_RECEIPTS.json')
 for path in sorted(P.glob('SYNTH6_*.parquet')):
  name=path.stem[7:];f=pd.read_parquet(path);before=f.copy(deep=True);start=str(f.index[f.tail_observation.eq(1)][0].date());ids={r['confirmed_day']:r['receipt_id'] for r in ridrows if r['path']==name};rows=run('SYNTH6:'+name,f,f,ids,start);pd.testing.assert_frame_equal(f,before,check_exact=True);synth[name]=rows;save('SYNTH_'+name,rows);events=[r for r in rows if r['action']!='hold' and r['action']!='observe'];ss.append(dict(path=name,attempts=max(r['attempt_number'] for r in rows),mobile_resets=sum(r['reason']=='mobile_line' for r in rows),E0_ends=sum(r['reason']=='E0_invalid' and r['attempt_before'] is not None for r in rows),stage_observations=dict(collections.Counter(r['stage_name'] for r in rows)),events=events))
 for a,b,n in [('normal_pullback_advance','start_continuous_failure',28),('failure_recovery','start_continuous_failure',52)]:
  # Identity fields differ across canonical series, behavior must still match.
  fields=['close','stage','mobile_before','mobile_after','action','reason','authorization_usable','attempt_number']
  assert [{k:r[k] for k in fields} for r in synth[a][:n]]==[{k:r[k] for k in fields} for r in synth[b][:n]];checks.append('shared_prefix_'+a+'_'+str(n))
 # Verify behavior requirements on the fixed fixtures, without changing paths.
 assert all(r['stage']<=1 for r in synth['single_jump_flat']);checks.append('single_jump_never_self_promotes')
 down=synth['lower_highs_lows'];assert down[20]['action']=='end_attempt' and down[20]['stage']==0;assert down[30]['action']=='probe' and down[31]['action']=='confirmed' and down[32]['action']=='expanded';checks.append('down_rebound_old_attempt_end21_new_probe31_confirm32_expand33')
 for name in ['slow_no_pullback','normal_pullback_advance']:assert any(r['action']=='expanded' for r in synth[name]);checks.append(name+'_can_expand')
 records={r['series_id']:r for r in T.read(T.OLD/'manifest.json')['series']};T.BEGIN='1900-01-01';real={};serieschecks=[]
 for sid in ['URFI881107','URFI881128','URFI881155','URFI881267','URFI881276']:
  f,ev,ep,ref=T.source_frame(sid,records);z=pd.read_parquet(P/f'{sid}.original-CP1.parquet');before=z.copy(deep=True);rr,_,_=T.trace(sid,f,z,ev,ep);ids={r['confirmed_day']:r['receipt_id'] for r in rr};rows=run(sid,f,z,ids);cut='2025-12-31';small=f.loc[:cut];past=run(sid,small,z.loc[:cut],ids);assert past==[r for r in rows if r['day']<=cut];pd.testing.assert_frame_equal(z,before,check_exact=True);real[sid]=rows;save(sid+'_STATE',rows);serieschecks.append(dict(series=sid,rows=len(rows),original_CP1_unchanged=True,physical_state_prefix_equal=True,unknown_rows=sum(r['action']=='unknown' for r in rows)))
 cases=[c for c in T.read(W/'behavior-contract-20261031/CANDIDATES_PENDING_REVIEW.json') if 'sector' in c];summ=[]
 for case in cases:
  sid=case['sector'];allr=real[sid];rows=[r for r in allr if case['start']<=r['day']<=case['end']];start=pd.Timestamp(case['start']);fx=pd.read_parquet(W/'mainline-absolute-Q4-20261031/industry-facts'/f'{sid}.parquet');base=float(fx.loc[fx.index<start].close.iloc[-1]);events=[]
  for r in rows:
   if r['action'] in ['probe','confirmed','expanded','end_attempt']:
    future=fx.loc[(fx.index>pd.Timestamp(r['day']))&(fx.index<=pd.Timestamp(case['end']))];same=future.loc[future.e0_target.astype(bool)]
    before=[x['close'] for x in allr if x['attempt_id']==r['attempt_before'] and x['day']<r['day']] if r['attempt_before'] else []
    # Do not bridge an E0 ending then restart: restrict to original episode boundary.
    for d in future.index:
     if not bool(future.loc[d,'e0_target']):same=same.loc[same.index<d];break
    recovered=bool(r['reason']=='mobile_line' and before and not same.empty and float(same.close.max())>=max(before))
    events.append(dict(**r,return_from_case_baseline=r['close']/base-1,later_recovered_attempt_peak_within_original_E0_and_case=recovered,retrospective_only=True))
  summ.append(dict(review_id=case['review_id'],industry=case['industry'],case_start_state=rows[0],stage_observations=dict(collections.Counter(r['stage_name'] for r in rows)),new_attempts=sum(r['action']=='probe' for r in rows),mobile_resets_while_E0_valid=sum(r['reason']=='mobile_line' for r in rows),of_these_later_recovered_attempt_peak=sum(e['later_recovered_attempt_peak_within_original_E0_and_case'] for e in events),E0_attempt_ends=sum(r['reason']=='E0_invalid' and r['attempt_before'] is not None for r in rows),quarter_price_endpoint=case['end_return'],quarter_closeMFE=case['closeMFE'],events=events))
 save('SYNTHETIC_SUMMARY',ss);save('REAL_CASE_SUMMARY',summ);save('VERIFICATION',dict(passed=True,checks=checks,series=serieschecks,seconds=time.monotonic()-t,new_economic_paths=0,financial_controller_not_connected=True));print('DONE',round(time.monotonic()-t,3),'tests',len(checks),flush=True)
 for r in ss:print('SYNTH',r['path'],r['attempts'],r['mobile_resets'],r['stage_observations'],flush=True)
 for r in summ:print('CASE',r['review_id'],'resets',r['mobile_resets_while_E0_valid'],'recovered',r['of_these_later_recovered_attempt_peak'],'stages',r['stage_observations'],flush=True)
if __name__=='__main__':main()
