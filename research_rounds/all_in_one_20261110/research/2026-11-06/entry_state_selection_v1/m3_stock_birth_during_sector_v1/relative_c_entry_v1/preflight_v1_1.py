"""Frozen C scope preflight. No new economic lifecycle or return calculation."""
from pathlib import Path
from decimal import Decimal as D
import ast, json, sys, hashlib, time
import numpy as np, pandas as pd
O=Path(__file__).resolve().parent; E=O.parent; R=E.parent
C=E/'relative_m3_cache_v1'; V=C/'coverage_upper_bound_v1'; BASE=E/'relative_priority_v1/baseline'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
M=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
END=pd.Timestamp('2026-06-30')
sys.path.insert(0,str(C));sys.path.insert(0,str(B/'code'))
from clock_model import relative_clock
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(name,x): (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def boolknown(x): return pd.notna(x) and x in (False,True,0,1)
def true(x): return pd.notna(x) and x in (True,1)
def finite(x):
 try:return bool(np.isfinite(x))
 except (ValueError,TypeError):return False
def marker_step(mark,unknown,iq,epoch,entered,loss,d):
 # UNKNOWN is dominant: an AB loss at this close must not immediately re-arm.
 if unknown or not iq or entered: return None
 if mark is not None and mark['epoch']!=epoch:mark=None
 if loss:mark={'day':d,'epoch':epoch}
 return mark
def synthetic():
 a={'day':0,'epoch':1}
 assert marker_step(a,True,True,1,False,True,1) is None
 assert marker_step(a,False,True,1,True,True,1) is None
 assert marker_step(a,False,False,1,False,True,1) is None
 assert marker_step(a,False,True,2,False,False,1) is None
 assert marker_step(a,False,True,1,False,False,1)==a
 assert marker_step(None,False,True,1,False,True,1)=={'day':1,'epoch':1}
 # PVR and known-false S/M do not appear in marker update: they block C but not marker.
 return ['UNKNOWN_same_day_loss_cannot_rearm','entry_clears','I_invalid_clears','I_epoch_change_clears','invitation_nofill_does_not_consume','fresh_legal_loss_seeds','PVR_unknown_and_known_false_S_M_do_not_clear']
def prepare():
 assert not (O/'FREEZE.json').exists()
 inputs=[E/'lifecycle_v1/simulate.py',E/'SEALED_ALL_BIRTH_EVENTS.csv',C/'clock_model.py',V/'FROZEN_SCOPE.json',V/'ALL_RECEIPTS.csv',BASE/'DECISIONS.csv',BASE/'ROUNDS.csv',BASE/'ACTIONS.csv',E/'relative_priority_v1/EARLIER_SAME_EXIT_2022.csv',C/'FIXED_SCOPE.json',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',M/'COMMON_K_COMPARISON.parquet',M/'KNOWN3.parquet',M/'RIGHT3.parquet',M/'WARM_PREFIX_M_K.parquet',M/'WARM_PREFIX_M_R.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py',O/'PROTOCOL.json',Path(__file__)]
 inputs += [E/'relative_priority_v1/TAIL_HOLDING_OVERLAP_SUMMARY.csv',E/'relative_priority_v1/TAIL_SAME_STOCK_ROUNDS.csv',E/'FIXED_NAMED_DAILY.csv',O/'FIXED_CASE_DEFINITIONS.csv']
 inputs += list(V.glob('DAILY_PATHS_*.csv'))+list(V.glob('RELATIVE_EVENTS_*.csv'))
 hashes=read(V/'SOURCE_HASHES.json')
 # The prior coverage seal includes old code/inputs. Verify all without changing them.
 for p,h in hashes.items(): assert sha(p)==h,('SOURCE_DRIFT',p)
 hashes.update({str(p):sha(p) for p in inputs})
 save('SYNTHETIC_QA.json',{'passed':True,'tests':synthetic()})
 save('FREEZE.json',{'created_utc':str(pd.Timestamp.now(tz='UTC')),'no_new_economic_results':True,'preflight_only':True,'hashes':hashes})
 print('FROZEN',len(hashes),flush=True)
def init():
 global spec,sm,im,member,cal,enginecal,panel,K,RIGHT,pvr,dec,rounds,receipts,old_daily,old_rel,helpers,fixed,actions
 spec=read(V/'FROZEN_SCOPE.json');sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};im={x['series']:x for x in read(U/'INDUSTRY_MANIFEST.json')}
 member=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid')
 cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input'],columns=[]).index) for x in im.values()])));cal=cal[cal<=END]
 p=pd.read_parquet(M/'COMMON_K_COMPARISON.parquet');enginecal=pd.DatetimeIndex(sorted(p.day.unique()));panel=p.set_index(['sector','day'])
 K=pd.concat([pd.read_parquet(M/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(M/'KNOWN3.parquet')]).sort_index()
 RIGHT=pd.concat([pd.read_parquet(M/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(M/'RIGHT3.parquet')]).sort_index()
 assert K.index.equals(RIGHT.index) and not K.index.duplicated().any()
 assert len(cal)==4595 and len(enginecal)==1085 and len(K.index)==1088
 pvr=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet').set_index(['sid','day'])
 dec=pd.read_csv(BASE/'DECISIONS.csv',parse_dates=['day'],dtype={'window':str})
 assert len(dec)==20445 and set(dec.arm)=={'A_UNION_B'}
 rounds=pd.read_csv(BASE/'ROUNDS.csv',parse_dates=['signal_day','entry_day','status_day','exit_day'],dtype={'window':str})
 actions=pd.read_csv(BASE/'ACTIONS.csv',parse_dates=['day'],dtype={'window':str})
 receipts=pd.read_csv(V/'ALL_RECEIPTS.csv',parse_dates=['day'],dtype={'window':str})
 receipts=receipts[receipts.arm.eq('SAME_DAY')&receipts.old_birth_type.eq('NONE')]
 old_daily=pd.concat([pd.read_csv(p,parse_dates=['day'],dtype={'window':str}) for p in sorted(V.glob('DAILY_PATHS_*.csv'))],ignore_index=True)
 old_rel=pd.concat([pd.read_csv(p,parse_dates=['day'],dtype={'window':str}) for p in sorted(V.glob('RELATIVE_EVENTS_*.csv'))],ignore_index=True)
 prior=read(C/'FIXED_SCOPE.json');early=pd.read_csv(E/'relative_priority_v1/EARLIER_SAME_EXIT_2022.csv')
 fixed=set(map(tuple,pd.read_csv(O/'FIXED_CASE_DEFINITIONS.csv',dtype={'window':str})[['window','sid']].to_numpy()))
 tree=ast.parse((E/'lifecycle_v1/simulate.py').read_text())
 wanted=['finite','true','false','lineage','flags','fee','getmeta','size','checkclose','load','DayFrame']
 nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in wanted]
 helpers=dict(Path=Path,D=D,np=np,pd=pd,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,version_on=version_on,market_identity_on=market_identity_on,
 NAV=D('1200000'),INIT=D('24000'),SLOT=D('48000'),RISK=D('3000'),SLIP=D('.0005'),END=END,manifest=sm,
 rules=read(B/'inputs-v2/market-rules.json'),proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'],
 raw={},facts={},cp={},capacity={},meta={},closecache={},hashes={},load_count=0,sha=sha)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),'ORIGINAL_AST_HELPERS','exec'),helpers)
def baseline_state(w,sid,days):
 z=pd.Series('FLAT',index=days,dtype='object')
 rr=rounds[rounds.window.eq(w)&rounds.sid.eq(sid)].sort_values('signal_day')
 for r in rr.itertuples():
  sd,ed,td=r.signal_day,r.entry_day,r.status_day
  status=r.status
  # Prequeue state: selected at this close is not pending until after this query.
  pending=(days>sd)&((days<ed) if pd.notna(ed) else ((days<td) if pd.notna(td) else True))
  z.loc[days[pending]]='BUY_PENDING'
  if pd.notna(ed):
   z.loc[days[(days>=ed)&(days<td if pd.notna(td) else True)]]='HELD'
  if 'UNKNOWN' in status:z.loc[days>=td]='UNKNOWN'
  elif status=='OPEN_CENSORED_AT_2026_06_30':z.loc[days>=ed]='HELD'
  elif status=='BUY_PENDING_CENSORED_AT_DATA_END':z.loc[days>sd]='BUY_PENDING'
  # COMPLETE / known NOFILL are FLAT at their open. Subsequent rounds handled in order.
  elif status in ('COMPLETE_CONDITIONAL_STOCK_ROUND','NEXT_OPEN_BELOW_PROTECTION_NOFILL','MINIMUM_LOT_NOT_FUNDED_NOFILL'):z.loc[days>=td]='FLAT'
  else:raise AssertionError(('UNKNOWN_ROUND_STATUS',status))
 return z
def next_open_proxy(sid,d,fl,cap):
 k=enginecal.get_loc(d)
 if k+1>=len(enginecal):return {'next_open_status':'BUY_PENDING_AT_DATA_END'}
 nd=enginecal[k+1];z=helpers['raw'][sid].get(nd,{});p=helpers['raw'][sid].get(d,{})
 out={'next_common_day':nd,'historical_orderability':'UNKNOWN','account_run':False}
 if not finite(z.get('raw_open')) or z['raw_open']<=0:return dict(out,next_open_status='MISSING_NEXT_OPEN_UNKNOWN')
 if helpers['lineage'](z)!=helpers['lineage'](p):return dict(out,next_open_status='SOURCE_CHANGED_AT_ENTRY_UNKNOWN')
 if not finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],p['adjustment_factor'],rtol=1e-11):return dict(out,next_open_status='FACTOR_AT_ENTRY_UNKNOWN')
 op=D(str(z['raw_open']));floor=D(str(fl))/D(str(p['adjustment_factor']))
 if op<=floor:return dict(out,next_open_status='NEXT_OPEN_BELOW_PROTECTION_NOFILL')
 try:q,bf,risk,_,_=helpers['size'](sid,nd,op*(1+helpers['SLIP']),floor,helpers['INIT'],helpers['RISK'],int(cap))
 except (RuleUnavailable,KeyError,ValueError):return dict(out,next_open_status='DATED_RULE_AT_ENTRY_UNKNOWN')
 return dict(out,next_open_status='CONDITIONAL_OPEN_PROXY' if q else 'MINIMUM_LOT_NOT_FUNDED_NOFILL',next_open_raw=float(op),next_open_q=q,next_buy_fee=float(bf),next_planned_risk=float(risk),next_open_price=float(op*(1+helpers['SLIP'])))
def run(shard,nshards):
 assert (O/'FREEZE.json').exists() and not (O/f'QA_{shard}.json').exists()
 frozen=read(O/'FREEZE_PREFLIGHT_REPAIR.json')['hashes']
 for p in [O/'PROTOCOL.json',Path(__file__),E/'lifecycle_v1/simulate.py',C/'clock_model.py']:assert sha(p)==frozen[str(p)]
 init();start=time.monotonic();stocks=sorted(set().union(*(set(x['stocks']) for x in spec.values())))[shard::nshards]
 cand=[];daily=[];features=[];marks=[];qa=[];risk=[];ind={}
 groups_dec={(w,s):g for (w,s),g in dec.groupby(['window','sid'])}
 groups_rec={(w,s):g for (w,s),g in receipts.groupby(['window','sid'])}
 groups_od={s:g for s,g in old_daily.groupby('sid')};groups_or={s:g for s,g in old_rel.groupby('sid')}
 slots=dec[dec.selected.eq(True)].groupby(['window','day','sector']).size().to_dict()
 for num,sid in enumerate(stocks):
  m=sm[sid];sec=member.loc[sid,'sector_id'];name=member.loc[sid,'name'];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));fp=m['refs']['facts']
  raw=pd.read_parquet(sp).loc[:END];f=pd.read_parquet(fp).loc[:END].reindex(cal);p=raw.reindex(cal)
  for pp in [sp,fp]:assert sha(pp)==frozen[pp],('SOURCE_DRIFT',pp)
  if sec not in ind:
   ip=next(p for p in im[sec]['source_sha256'] if p.endswith('/signal.parquet'))
   assert sha(ip)==frozen[ip]
   ind[sec]=pd.read_parquet(ip).loc[:END].reindex(cal)
  ip=ind[sec]
  ident=p.source_kind.astype('string')+'|'+p.source_path.astype('string')+'|'+p.segment_id.astype('string')
  ii=ip.source_kind.astype('string')+'|'+ip.source_path.astype('string')+'|'+ip.segment_id.astype('string')
  pv=p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&p.source_invalid.eq(False)&p.synthetic_event_bar.eq(False)&p.close.gt(0)&np.isfinite(p.close)
  sv=ip.observed_bar.eq(True)&ip.price_eligible.eq(True)&ip.volume_eligible.eq(True)&ip.source_invalid.eq(False)&ip.synthetic_event_bar.eq(False)&ip.close.gt(0)&np.isfinite(ip.close)
  comp=pv&sv&pv.shift(1,fill_value=False)&sv.shift(1,fill_value=False)&ident.eq(ident.shift()).fillna(False)&ii.eq(ii.shift()).fillna(False)
  out=relative_clock(p.close.to_numpy(),ip.close.to_numpy(),comp.to_numpy(dtype=bool));out.index=cal
  epoch=pd.Series(np.nan,index=cal);e=0;active=False;bad=False;prev_f=None;prev_source=None
  for d,fr in f.iterrows():
   ident0=ident.loc[d];iq=true(fr.i_target) and finite(fr.i_floor) and fr.i_floor>0 and finite(fr.close)
   if not iq:active=False;bad=False;prev_f=fr;prev_source=ident0;continue
   same=prev_source is not None and pd.notna(ident0) and pd.notna(prev_source) and ident0==prev_source
   if not same:active=False;bad=False
   if active and same and prev_f is not None and true(prev_f.i_target):
    if fr.i_floor<prev_f.i_floor or fr.close<=prev_f.i_floor:bad=True
   if not active:e+=1;active=True
   if not bad:epoch.loc[d]=e
   prev_f=fr;prev_source=ident0
  ss=panel.loc[sec,'M3_candidate'].reindex(cal)
  mk=K[sid].reindex(cal).fillna(False).astype(bool);mr=RIGHT[sid].reindex(cal).fillna(False).astype(bool)
  iq=f.e0_ready.eq(1)&f.g_ready.eq(True)&f.i_target.eq(1)&np.isfinite(f.i_floor)&f.i_floor.gt(0)
  ik=f.e0_ready.isin([0,1])&f.g_ready.isin([False,True,0,1])&f.i_target.isin([0,1])&(~f.i_target.eq(1)|(np.isfinite(f.i_floor)&f.i_floor.gt(0)))
  vv=pvr.loc[sid].reindex(cal)
  pk=vv.state.ge(0)&vv.valid_observation.eq(True)&np.isfinite(vv.score)
  fr=pd.DataFrame(dict(sectorS=ss,M3_known=mk,M3=mr,I_qualified=iq,I_known=ik,I_continuity_epoch=epoch,i_target=f.i_target,i_floor=f.i_floor,PVR_known=pk,PVR_score=vv.score,source_known=comp),index=cal).join(out)
  fr['qualification_unknown']=~comp|~out.relative_known|~ik|~ss.isin([0,1])|~mk|(iq&epoch.isna())
  fr['persistent']=ss.eq(1)&ss.shift().eq(1)&mk&mk.shift(fill_value=False)&mr&mr.shift(fill_value=False)
  od=groups_od.get(sid,pd.DataFrame());checks=0
  if len(od):
   z=fr.reindex(pd.DatetimeIndex(od.day))
   np.testing.assert_allclose(z.I_continuity_epoch,od.I_continuity_epoch,rtol=0,atol=0,equal_nan=True)
   assert np.array_equal(z.relative_event.to_numpy(),od.relative_event.to_numpy())
   assert np.array_equal(z.relative_known.to_numpy(),od.relative_known.to_numpy())
   checks=len(od)
  ore=groups_or.get(sid,pd.DataFrame(columns=['day','relative_event','window']))
  for w,x in spec.items():
   if sid not in x['stocks']:continue
   st,en=pd.Timestamp(x['start']),pd.Timestamp(x['end']);days=enginecal[(enginecal>=st)&(enginecal<=en)]
   ff=fr.reindex(days).copy();ff['window']=w;ff['sid']=sid;ff['name']=name;ff['sector']=sec;ff['day']=ff.index
   dd=groups_dec.get((w,sid),pd.DataFrame());bs=baseline_state(w,sid,days)
   if len(dd):
    assert np.array_equal(bs.reindex(pd.DatetimeIndex(dd.day)).to_numpy(),dd.stock_state_before.to_numpy()),(w,sid,'BASELINE_STATE')
   # Verify all cached nonzero clock dates, not only candidates.
   oo=ore[ore.window.eq(w)] if len(ore) else ore
   actual=ff[ff.relative_event.ne(0)]
   assert set(zip(actual.index,actual.relative_event))==set(zip(oo.day,oo.relative_event)),(w,sid,'CLOCK_EVENTS')
   features.append(ff.reset_index(drop=True))
   # Provision the original read-only close helpers from already loaded exact inputs.
   helpers['raw'][sid]=helpers['DayFrame'](raw)
   vol=raw.raw_volume[raw.raw_volume.gt(0)]
   helpers['capacity'][sid]=(vol.rolling(20,min_periods=20).mean()*.01).reindex(raw.index).ffill().to_dict()
   for rr in (dd.to_dict('records') if len(dd) else []):
    if pd.notna(rr.get('close_check')):
     fl=f.at[rr['day'],'i_floor'];cc=helpers['checkclose'](dict(sid=sid,day=rr['day'],i_floor=fl))
     assert cc['close_check']==rr['close_check'],(w,sid,rr['day'],'CLOSE')
     for key in ['close_q','close_fee','close_plan_risk','close_floor_raw','prior20_capacity']:
      if key in cc:assert np.isclose(cc[key],rr[key],rtol=1e-12,atol=1e-8),(key,cc[key],rr[key])
   dmap={r['day']:r for r in dd.to_dict('records')} if len(dd) else {}
   entrydays=set(actions[actions.window.eq(w)&actions.sid.eq(sid)&actions.side.eq('buy_core')].day)
   rc=groups_rec.get((w,sid),pd.DataFrame());receipt_days=set(rc.day) if len(rc) else set()
   calc=set(ff.index[ff.persistent&ff.relative_known&ff.relative_event.eq(1)&ff.I_qualified&ff.I_continuity_epoch.notna()])
   calc-={d for d,r0 in dmap.items()} # Any A/B same-day excludes C.
   assert calc==receipt_days,(w,sid,'PERSISTENT_RECEIPTS',calc^receipt_days)
   mark=None;losses=[];trace=[]
   for d,r in ff.iterrows():
    prior=mark;dr=dmap.get(d);loss=dr is not None and dr['decision']=='PASS_NOT_TOP2'
    if loss:losses.append((d,r.I_continuity_epoch))
    mark=marker_step(mark,bool(r.qualification_unknown) or bs.loc[d]=='UNKNOWN',bool(r.I_qualified),r.I_continuity_epoch,d in entrydays,loss,d)
    if prior!=mark:
     reason='SEED_AB_LOSS' if mark is not None else ('ACTUAL_ENTRY' if d in entrydays else 'EXECUTION_UNKNOWN' if bs.loc[d]=='UNKNOWN' else 'QUALIFICATION_UNKNOWN' if r.qualification_unknown else 'I_INVALID_OR_EPOCH_END')
     marks.append(dict(window=w,sid=sid,name=name,day=d,reason=reason,old_mark_day=prior['day'] if prior else None,new_mark_day=mark['day'] if mark else None,epoch=r.I_continuity_epoch,baseline_state=bs.loc[d],AB_decision=dr['decision'] if dr else None))
    selected_ab=int(slots.get((w,d,sec),0));assert selected_ab<=2
    tt=dict(window=w,sid=sid,name=name,sector=sec,day=d,baseline_state=bs.loc[d],marker_active=mark is not None,marker_day=mark['day'] if mark else None,AB_decision=dr['decision'] if dr else None,AB_awards=selected_ab,C_slots=2-selected_ab,**{k:r[k] for k in ['sectorS','M3_known','M3','I_known','I_qualified','I_continuity_epoch','source_known','relative_known','relative_event','relative_reason','qualification_unknown','persistent','PVR_known','PVR_score']})
    if (w,sid) in fixed:trace.append(tt)
    if d not in receipt_days:continue
    z=dict(tt,same_I_prior_AB_loss=any(ld<d and ep==r.I_continuity_epoch for ld,ep in losses),old_AB_same_day=dr is not None,current_FLAT=bs.loc[d]=='FLAT',unconsumed_marker=mark is not None,current_i_floor=r.i_floor,preflight_model='BASELINE_STATE_DIAGNOSTIC_NOT_ABC')
    if z['unconsumed_marker'] and z['current_FLAT'] and z['PVR_known']:
     z.update(helpers['checkclose'](dict(sid=sid,day=d,i_floor=r.i_floor)))
     if z['close_check']=='PASS':z.update(next_open_proxy(sid,d,r.i_floor,z['prior20_capacity']))
    cand.append(z)
   if trace:daily.append(pd.DataFrame(trace))
  # Release stock data and helper close-cache; all output features retain only needed columns.
  helpers['raw'].pop(sid,None);helpers['capacity'].pop(sid,None)
  helpers['closecache'].clear()
  qa.append(dict(sid=sid,original_AB_feature_checks=checks,baseline_state_exact=True,original_close_exact=True,full_clock_exact=True))
  if num%20==0:print('PREFLIGHT',shard,num+1,len(stocks),round(time.monotonic()-start,1),flush=True)
 pd.DataFrame(cand).to_csv(O/f'CANDIDATES_{shard}.csv',index=False)
 pd.DataFrame(marks).to_csv(O/f'MARK_TRANSITIONS_{shard}.csv',index=False)
 pd.concat(daily,ignore_index=True).to_csv(O/f'FIXED_DAILY_{shard}.csv',index=False)
 pd.concat(features,ignore_index=True).to_parquet(O/f'DAILY_FEATURES_{shard}.parquet',index=False)
 pd.DataFrame(qa).to_csv(O/f'SOURCE_QA_{shard}.csv',index=False)
 save(f'QA_{shard}.json',{'stocks':len(stocks),'old_AB_checks':sum(q['original_AB_feature_checks'] for q in qa),'candidate_rows':len(cand),'seconds':time.monotonic()-start,'no_economic_run':True})
 print('DONE',shard,len(cand),round(time.monotonic()-start,1),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 else:run(int(sys.argv[1]),int(sys.argv[2]))
