from pathlib import Path
import sys,json,hashlib,math,time,importlib.util,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';ORIG=RR/'continuous-protection-lines-20261028';OLD=RR/'a-share-selection-e0-20261024/prepared-v2';BEGIN='2025-07-01';END='2026-03-31';CUT='2025-12-31'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
M=load('trace_original_cp1_model',ORIG/'code/model.py');COM=load('trace_original_cp1_common',ORIG/'code/common.py')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
SCALE='CP1-original:'+sha(ORIG/'code/model.py')[:16]
def ident(*v):return hashlib.sha256(json.dumps(v,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def norm(x):
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(tuple,list,set)):return [norm(v) for v in x]
 if isinstance(x,np.generic):return norm(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,(pd.Timestamp,)):return x.isoformat()
 return x
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 if isinstance(x,list) and x:pd.DataFrame(norm(x)).to_csv(O/(n+'.csv'),index=False)
def source_frame(sid,records):
 rec=records[sid];sig=pd.read_parquet(OLD/rec['files']['signal']['path']).loc[:END];ev=pd.read_parquet(OLD/rec['files']['events']['path']).loc[:END]
 if sid.startswith('URFI'):
  facts=pd.read_parquet(W/'mainline-absolute-Q4-20261031/industry-facts'/f'{sid}.parquet').loc[:END];raw=sig.reindex(facts.index);assert raw.close.equals(facts.close);f=facts[['close','segment_id']].copy();f['amount']=raw.amount;f['e0_valid']=facts.e0_target.astype(bool);f['e0_down']=ev.event.reindex(f.index).eq(-1);f['i_floor']=facts.e0_floor;episode=facts.e0_target.astype(bool);reference='original model on frozen industry E0 input domain; no old industry CP1 cache'
 else:
  f=COM.frame(sid,END);facts=pd.read_parquet(COM.PREP/'facts'/f'{sid}.parquet').loc[f.index];episode=facts.e0_target.astype(bool);ev=pd.read_parquet(COM.PH/'events/TECH'/f'{sid}.parquet').reindex(f.index);reference='original common.frame and original CP1 cache';raw=None
 assert np.isfinite(f[['close','amount']]).all().all() and (f[['close','amount']]>0).all().all()
 e=ev.reindex(f.index);return f,e,episode,reference
def trace(canonical,f,z,events,episode,alias=None):
 assert f.index.equals(z.index);out=[];points=[];anchor_at=anchor_obs=frontier_obs=scale_at=None;anchor_idx=None;last_receipt=None;global_last=None;consumed=set();ep=None;prevtarget=None;seg=None;epknown=True;checks=collections.Counter();allinc=[]
 dates=list(f.index);fr=f.to_dict('records');zr=z.to_dict('records');ev=events.reindex(f.index);epvals=episode.reindex(f.index)
 for i,(day,r,q) in enumerate(zip(dates,fr,zr)):
  d=str(day.date());segment=str(int(r['segment_id']));obs=ident('price-observation',canonical,segment,d);target=bool(epvals.iloc[i]) if pd.notna(epvals.iloc[i]) else None
  if segment!=seg:seg=segment;prevtarget=None;ep=None;last_receipt=None
  if target is None:epknown=False;ep=None
  elif not target:ep=None;epknown=True
  elif prevtarget is False:ep=ident('original-E0-episode',canonical,segment,obs);epknown=True;last_receipt=None
  elif prevtarget is None:epknown=False;ep=None
  prevtarget=target;reason=q['reset_reason'] if pd.notna(q['reset_reason']) else None
  if reason in ['unprepared','E0_invalid']:
   points=[];anchor_at=anchor_obs=frontier_obs=scale_at=None;anchor_idx=None
  elif reason in ['start','E0_down_reset','lower_anchor']:
   points=[];anchor_at=d;anchor_obs=frontier_obs=obs;scale_at=d;anchor_idx=i
  fresh=float(q['delta_frontier']) if pd.notna(q['delta_frontier']) else 0.
  if fresh>0:
   event=ev.iloc[i];native_sign=int(event.event) if pd.notna(event.get('event')) else None;point=dict(price_event_id=obs,day=d,from_observation_id=frontier_obs,to_observation_id=obs,log_displacement=fresh,log_frontier_to=math.log(r['close']),volume_multiplier=float(q['m']),native_event_known=native_sign is not None,native_event_sign=native_sign,derived_native_event_id=ident('cached-native-event-derived',canonical,segment,d,native_sign) if native_sign in [-1,1] else None,amount_background_start=str(dates[max(0,i-21)].date()),amount_background_end=str(dates[i-1].date()) if i else None);points.append(point);frontier_obs=obs
  if bool(q['receipt']):
   rid=ident('market-CP1-receipt',canonical,SCALE,segment,ep,anchor_obs,obs);unknown=[]
   if not epknown:unknown.append('original_E0_episode_start_unknown')
   if anchor_at is None or anchor_idx is None:unknown.append('CP1_anchor_origin_unknown')
   if any(not p['native_event_known'] for p in points):unknown.append('native_event_row_missing_in_advances')
   assert points and points[-1]['day']==d and fresh>0;assert all(p['price_event_id'] not in consumed for p in points),(canonical,d,'old impulse reused');assert all(p['day']>anchor_at for p in points)
   if last_receipt:assert all(p['day']>last_receipt['confirmed_day'] for p in points)
   checks['new_unconsumed_advance_receipts']+=1;used_ids=[p['price_event_id'] for p in points];signature=ident(canonical,segment,anchor_obs,obs,[(p['price_event_id'],p['log_displacement'],p['volume_multiplier']) for p in points]);row=dict(canonical_series=canonical,source_alias=alias or canonical,scale_id=SCALE,source_segment=segment,original_E0_episode_id=ep,confirmed_day=d,receipt_id=rid,decision_evidence_key=ident('one-series-scale-observation',canonical,SCALE,obs),formation_start_exclusive=anchor_at,formation_end_inclusive=d,anchor_observation_id=anchor_obs,confirmation_observation_id=obs,previous_market_receipt_id=last_receipt['receipt_id'] if last_receipt else None,previous_market_confirmed_day=last_receipt['confirmed_day'] if last_receipt else None,previous_global_market_receipt_id=global_last['receipt_id'] if global_last else None,previous_consumed_frontier_log=last_receipt['frontier_log'] if last_receipt else None,original_candidate=float(q['candidate']),original_scale=float(q['scale']),scale_frozen_at=scale_at,scale_old_return_end_observations=[ident('price-observation',canonical,segment,str(t.date())) for t in dates[max(1,anchor_idx-63):anchor_idx]] if anchor_idx is not None else [],new_advance_price_event_ids=used_ids,new_advance_observations=len(points),new_log_price_displacement=float(q['displacement']),original_credit=float(q['credit']),evidence_signature=signature,trace_unknown=unknown,native_event_id_note='derived from cached event observation; provider supplies no original eventID',live_publication_time='unknown; confirmation day only',stage_controller_consumed=False)
   if BEGIN<=d<=END:out.append(row);allinc.extend(dict(receipt_id=rid,canonical_series=canonical,**p) for p in points)
   consumed.update(used_ids);last_receipt=global_last=dict(receipt_id=rid,confirmed_day=d,frontier_log=math.log(r['close']));points=[];anchor_at=d;anchor_obs=frontier_obs=obs;scale_at=d;anchor_idx=i
 return out,allinc,dict(checks)
def dedup(rows):
 used={};decisions={}
 for r in rows:
  k=r['receipt_id'];dk=r['decision_evidence_key']
  if k in used:assert used[k]['evidence_signature']==r['evidence_signature'];continue
  assert dk not in decisions or decisions[dk]==k,'same underlying decision evidence has conflicting source receipts';decisions[dk]=k;used[k]=r
 return list(used.values())
def main():
 start=time.monotonic();records={r['series_id']:r for r in read(OLD/'manifest.json')['series']};sectors=['URFI881107','URFI881128','URFI881155','URFI881267','URFI881276'];stocks=['000021.SZ','000034.SZ','000050.SZ'];files=[O/'PROTOCOL.txt',O/'trace.py',ORIG/'code/model.py',ORIG/'code/common.py',OLD/'manifest.json'];save('FREEZE',dict(before_trace=True,sectors=sectors,stocks=stocks,fixed_stock_selection='lexically first3 in original407 CP1 cache, technical validation only',no_new_economics=True,sha256={str(p):sha(p) for p in files}));receipts=[];increments=[];checks=[]
 for sid in sectors+stocks:
  f,ev,ep,reference=source_frame(sid,records);z=M.calculate(f);cached=False
  if sid in stocks:
   old=pd.read_parquet(ORIG/'signals'/f'{sid}.parquet').loc[:END];pd.testing.assert_frame_equal(z,old,check_exact=True,check_dtype=False,check_freq=False);cached=True
  before=z.copy(deep=True);rr,inc,ch=trace(sid,f,z,ev,ep);pd.testing.assert_frame_equal(z,before,check_exact=True);small=f.loc[:CUT];zs=M.calculate(small);pd.testing.assert_frame_equal(z.loc[:CUT],zs,check_exact=True,check_freq=False);pr,_,_=trace(sid,small,zs,ev.loc[:CUT],ep.loc[:CUT]);expected=[r for r in rr if r['confirmed_day']<=CUT];assert pr==expected;alias,_,_=trace(sid,f,z,ev,ep,'same canonical series from another retained source alias');assert len(dedup(rr+alias+rr))==len(rr);z.to_parquet(O/f'{sid}.original-CP1.parquet');receipts.extend(rr);increments.extend(inc);checks.append(dict(series=sid,reference=reference,reference_cache_full_fields_exact=cached,original_output_unchanged=True,physical_prefix_exact=True,receipt_ID_and_interval_prefix_exact=True,alias_and_repeat_dedup=True,receipt_count=len(rr),unknown_receipts=sum(bool(r['trace_unknown']) for r in rr),all_history_new_advance_receipts_checked=ch['new_unconsumed_advance_receipts']));print('TRACE_OK',sid,len(rr),time.monotonic()-start,flush=True)
 # Same original two market paths, with trace prefix and no repeated impulse.
 synth=[]
 for name,tail in [('slow',200*np.exp(.0015*np.arange(1,91))),('jump_flat',np.repeat(220.,90))]:
  close=np.r_[np.repeat(200.,150),tail];f=pd.DataFrame(dict(close=close,amount=1e8,segment_id=0,e0_valid=True,e0_down=False),index=pd.bdate_range('2025-01-02',periods=240));z=M.calculate(f);ev=pd.DataFrame(dict(event=0),index=f.index);episode=pd.Series(False,index=f.index);episode.iloc[1:]=True;rr,_,ch=trace('SYNTH:'+name,f,z,ev,episode);expected=int(z.receipt.iloc[150:].sum());assert expected==(31 if name=='slow' else 1);assert len(dedup(rr+rr))==len(rr);synth.append(dict(name=name,tail_receipts=expected,pass_original_semantics=True,trace_no_impulse_reuse=True))
 # Different canonical series are not merged merely for the same day.
 if receipts:
  a=receipts[0];b=dict(a,receipt_id=ident('different-series',a['receipt_id']),decision_evidence_key=ident('different-series',a['decision_evidence_key']),canonical_series='DIFFERENT');assert len(dedup([a,b]))==2
 save('RECEIPTS',receipts);save('NEW_ADVANCE_SOURCES',increments);save('VERIFICATION',dict(passed=True,series=checks,synthetics=synth,all_fields_original=True,stage_consumption_not_executed=True,receipt_count=len(receipts),new_economic_paths=0,seconds=time.monotonic()-start));print('DONE',len(receipts),time.monotonic()-start,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR',dict(error=repr(e),traceback=__import__('traceback').format_exc()));raise
