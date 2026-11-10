from pathlib import Path
from decimal import Decimal as D
import ast,json,hashlib,sys,time
import pandas as pd,numpy as np
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent;P=R/'nested_consolidation_probe_preflight_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=NAV*D('.02');SLIP=D('.0005');END=pd.Timestamp('2026-06-30')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];names=rules['security_metadata'];meta={}
# Only audited function definitions. No imports, mkdir, simulator, selection or evaluation from original module.
helper=R/'breadth_pvr3_priority_v1/simulate.py';src=helper.read_text();tree=ast.parse(src);keep=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['fee','getmeta','size']];assert len(keep)==3
exec(compile(ast.Module(body=keep,type_ignores=[]),str(helper)+':three_pure_helpers','exec'),globals())

def identity(r):return tuple(str(r[c]) for c in ['source_kind','source_path','segment_id'])
def valid_prices(x):
 cols=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','adjustment_factor']
 if not np.isfinite(x[cols].to_numpy(float)).all() or not x[cols].gt(0).all().all():return 'PRICE_MISSING_INVALID'
 for c in ['observed_bar','is_observed_bar','price_eligible']:
  if not x[c].eq(True).all():return 'PRICE_INELIGIBLE'
 for c in ['source_invalid','synthetic_event_bar']:
  if not x[c].eq(False).all():return 'SOURCE_INVALID_SYNTHETIC'
 for c in ['source_kind','source_path','segment_id']:
  if x[c].isna().any() or x[c].nunique()!=1:return 'SOURCE_CHANGE'
 if not np.isclose(x.adjustment_factor,x.adjustment_factor.iloc[-1],rtol=1e-12,atol=1e-12).all():return 'FACTOR_CHANGE'
 for c in ['open','high','low','close']:
  if not np.allclose(x[c],x['raw_'+c]*x.adjustment_factor,rtol=1e-12,atol=1e-8):return 'COORDINATE_MISMATCH'
 if not (x.high.ge(x[['open','close']].max(axis=1))&x.low.le(x[['open','close']].min(axis=1))&x.high.ge(x.low)).all():return 'OHLC_INVALID'
 return None

def features(p,k):
 out={'price_known':False,'local_known':False,'control':False,'local':False}
 if k<20:return out|{'reason':'SHORT_HISTORY'}
 x=p.iloc[k-20:k+1];bad=valid_prices(x)
 if bad:return out|{'reason':bad}
 old=x.iloc[:10];recent=x.iloc[10:20];z=x.iloc[-1];factor=z.adjustment_factor
 u0=old.high.max();l0=old.low.min();u1=recent.high.max();l1=recent.low.min();prior=x.iloc[:20]
 anchor=np.flatnonzero(prior.close.to_numpy()==prior.close.min())[-1]
 out.update(price_known=True,control=bool(z.close>max(u0,u1)),control_floor_native=float(x.low.iloc[anchor:].min()),l1_native=float(l1),control_floor=float(x.low.iloc[anchor:].min()/factor),anchor_day=str(x.index[anchor].date()),u0=float(u0/factor),u1=float(u1/factor),l1=float(l1/factor),close=float(z.raw_close),factor=float(factor),reason=None)
 amount_known=(prior.amount.gt(0)&np.isfinite(prior.amount)&prior.volume_eligible.eq(True)).all()
 if not amount_known:return out|{'reason':'AMOUNT_UNKNOWN'}
 nested=u1<=u0 and l1>=l0 and u1-l1<u0-l0;dry=recent.amount.median()<old.amount.median()
 return out|dict(local_known=True,local=bool(nested and dry and z.close>u1),nested=bool(nested),dry=bool(dry),early=bool(nested and dry and z.close>u1 and z.close<=max(u0,u1)),amount_ratio=float(recent.amount.median()/old.amount.median()))

def open_check(z,root):
 if not np.isfinite(z.raw_open) or z.raw_open<=0:return 'OPEN_MISSING'
 if identity(z)!=root['identity']:return 'SOURCE_CHANGE'
 if not np.isfinite(z.adjustment_factor) or not np.isclose(z.adjustment_factor,root['factor'],rtol=1e-12,atol=1e-12):return 'FACTOR_ACTION_CHANGE'
 return None

def e0_floor(f,p,d):
 if d not in f.index:return None,'E0_FACT_MISSING'
 z=f.loc[d];r=p.loc[d]
 if not all(np.isfinite(z[c]) for c in ['factor','raw_close','close']) or not np.isclose(z.factor,r.adjustment_factor,rtol=1e-12,atol=1e-12) or not np.isclose(z.raw_close,r.raw_close,rtol=1e-12,atol=1e-8) or not np.isclose(z.close,r.close,rtol=1e-12,atol=1e-8) or z.segment_id!=r.segment_id:return None,'E0_COORDINATE_UNKNOWN'
 if pd.isna(z.e0_ready) or pd.isna(z.e0_target):return None,'E0_STATE_UNKNOWN'
 if z.e0_ready!=1 or z.e0_target!=1:return None,None
 if not np.isfinite(z.e0_floor) or not 0<z.e0_floor<z.close:return None,'E0_FLOOR_UNKNOWN'
 return float(z.e0_floor),None

rounds=[];paths=[];signals=[];coverage=[]
def run_stock(sid,window,start,finish,arm,p,f,featuremap):
 root=None;coverage_row=dict(sid=sid,window=window,arm=arm,known_signal_days=0,unknown_signal_days=0,suppressed_signals=0,stopped_unknown=False)
 for k in range(cal.get_indexer([cal[cal>=pd.Timestamp(start)][0]])[0],len(cal)):
  d=cal[k]
  if d>END:break
  z=p.iloc[k];inside=d<=pd.Timestamp(finish);exited=False
  if root is None and not inside:break
  if root is not None:
   out=root['out'];bad=open_check(z,root)
   if bad:
    out.update(status='UNKNOWN_'+bad,unknown_day=d);coverage_row['stopped_unknown']=True;break
   if root['exit_pending']:
    if root['q']:
     assert k>root['entry_k'],'T_PLUS_1_VIOLATION'
     try:qr,fs,par=getmeta(sid,d)
     except (RuleUnavailable,KeyError,ValueError) as ex:out.update(status='UNKNOWN_EXIT_DATED_RULE',unknown_day=d,error=str(ex));coverage_row['stopped_unknown']=True;break
     if qr.sell_floor(root['q'],root['q'])!=root['q']:out.update(status='UNKNOWN_EXIT_LOT',unknown_day=d);break
     px=D(str(z.raw_open))*(1-SLIP);sf=fee(root['q'],px,fs,'sell',par);net=D(root['q'])*px-sf-root['spent']
     out.update(status='COMPLETE',exit_day=d,exit_price=float(px),exit_fee=float(sf),net_pnl=float(net),return_on_buy_cash=float(net/root['spent']),outcome='W' if net>0 else 'L' if net<0 else 'B',final_S=root['S'])
    root=None;exited=True
   elif root['pending']:
    root['pending']=False;fl=D(str(root['S']));px=D(str(z.raw_open))*(1+SLIP);prior=p.iloc[k-20:k]
    if z.raw_open*root['factor']<=root['S_native']:out.update(status='NO_BUY_OPEN_BELOW_S')
    elif len(prior)!=20 or not (prior.raw_volume.gt(0)&np.isfinite(prior.raw_volume)&prior.volume_eligible.eq(True)).all():out.update(status='UNKNOWN_ENTRY_CAPACITY')
    else:
     capacity=int(prior.raw_volume.mean()*.01)
     try:q,bf,risk,fs,par=size(sid,d,px,fl,INIT,NAV*D('.0025'),capacity);qr,_,_=getmeta(sid,d)
     except (RuleUnavailable,KeyError,ValueError) as ex:out.update(status='UNKNOWN_ENTRY_DATED_RULE',error=str(ex));q=None
     if q is not None:
      out.update(prior20_capacity=capacity,quantity=q,entry_fee=float(bf),planned_risk=float(risk),entry_price=float(px))
      if not q:out.update(status='NO_BUY_MINIMUM_LOT')
      else:
       assert qr.buy_floor(q)==q and q<=capacity and D(q)*px+bf<=INIT and risk<=NAV*D('.0025')
       root.update(q=q,spent=D(q)*px+bf,entry_k=k);out.update(status='OPEN',accepted=True,entry_day=d,buy_cash=float(root['spent']))
  if root is not None:
   out=root['out'];bad=valid_prices(p.iloc[k:k+1])
   if bad:out.update(status='UNKNOWN_CLOSE_'+bad,unknown_day=d);coverage_row['stopped_unknown']=True;break
   old=root['S'];old_native=root['S_native'];failed=z.close<=old_native
   lift=None;err=None
   if failed:
    out.update(failure_close=d,failure_close_price=float(z.raw_close),failure_S=old,failure_S_native=old_native)
    if root['q']:root['exit_pending']=True
    else:root=None
   else:
    lift,err=e0_floor(f,p,d)
    if err:out.update(status='UNKNOWN_'+err,unknown_day=d);coverage_row['stopped_unknown']=True;break
    if lift is not None:
     root['S_native']=max(old_native,lift);root['S']=root['S_native']/root['factor']
   paths.append(dict(sid=sid,window=window,arm=arm,root_day=out['birth_day'],day=d,raw_close=float(z.raw_close),native_close=float(z.close),old_S_native=old_native,new_S_native=root['S_native'] if root is not None else None,old_S=old,new_S=root['S'] if root is not None else None,failed=bool(failed),e0_lift=(lift/float(z.adjustment_factor) if lift is not None else None),e0_lift_native=lift,quantity=out.get('quantity',0)))
   if inside:
    ft=featuremap[k]
    if (ft['control'] or ft['local']) if arm=='UNION' else ft.get(arm.lower(),False):coverage_row['suppressed_signals']+=1
   continue # Never fail and rebirth on same close, even a no-buy root.
  if not inside:continue
  ft=featuremap[k];known=ft['price_known'] if arm=='CONTROL' else (ft['price_known'] and (ft['control'] or ft['local_known'])) if arm=='UNION' else ft['local_known']
  coverage_row['known_signal_days' if known else 'unknown_signal_days']+=1
  qualifies=(ft['control'] or ft['local']) if arm=='UNION' else ft.get(arm.lower(),False)
  if not known or not qualifies:continue
  origin='CONTROL' if arm=='CONTROL' or (arm=='UNION' and ft['control']) else 'LOCAL'
  floor=ft['control_floor'] if origin=='CONTROL' else ft['l1'];floor_native=ft['control_floor_native'] if origin=='CONTROL' else ft['l1_native']
  out=dict(sid=sid,window=window,arm=arm,origin=origin,birth_day=d,birth_S=floor,birth_S_native=floor_native,birth_C=float(z.raw_close),old20_U=ft['u0'] if ft['u0']>=ft['u1'] else ft['u1'],local_U=ft['u1'],incremental_early=bool(origin=='LOCAL' and ft['early']),accepted=False,status='PENDING',historical_fill_certainty='UNKNOWN',account=False)
  rounds.append(out);root=dict(out=out,S=floor,S_native=floor_native,identity=identity(z),factor=float(z.adjustment_factor),pending=True,exit_pending=False,q=0)
 if root is not None and root['out']['status']=='OPEN':root['out'].update(status='UNRESOLVED_END',last_day=min(END,cal[-1]))
 coverage.append(coverage_row)

def main():
 global cal
 started=time.monotonic();assert not (O/'RUN_ONCE.json').exists()
 save('RUN_ONCE.json',dict(protocol_sha256=sha(O/'PROTOCOL.json'),amendment_sha256=sha(O/'AMENDMENT_BEFORE_VALID_RESULTS.json'),numerical_correction_sha256=sha(O/'NUMERICAL_CORRECTION.json'),script_sha256=sha(__file__),started_utc=str(pd.Timestamp.now(tz='UTC'))))
 cases=read(P/'FIXED_CASES.json');sids=sorted({c['sid'] for c in cases});assert len(sids)==22
 manifest={x['symbol']:x for x in read(M)};cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);assert cal.is_unique and cal.is_monotonic_increasing
 fixedpaths=[M,H,P/'FIXED_CASES.json',P/'PROTOCOL.json',P/'FEATURE_SEAL.json',helper,B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']
 hashes={str(x):sha(x) for x in fixedpaths};source_rows=[];prefix=[];casepaths=[]
 case_events=pd.read_csv(P/'ALL_FIXED_WINDOW_CANDIDATE_FACTS.csv').drop_duplicates(['sid','day'])
 for sid in sids:
  m=manifest[sid];sp=Path(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')));fp=Path(m['refs']['facts']);assert sha(sp)==m['source_sha256'][str(sp)]
  hashes[str(sp)]=sha(sp);hashes[str(fp)]=sha(fp);raw=pd.read_parquet(sp);f=pd.read_parquet(fp);assert raw.index.is_unique and f.index.is_unique
  p=raw.reindex(cal);featuremap={}
  for win,start,finish in read(O/'PROTOCOL.json')['windows']:
   ks=np.flatnonzero((cal>=pd.Timestamp(start))&(cal<=pd.Timestamp(finish)))
   for k in ks:
    ft=features(p,k);featuremap[k]=ft;signals.append(dict(sid=sid,window=win,day=cal[k],**ft))
   for arm in ['CONTROL','LOCAL','UNION']:run_stock(sid,win,start,finish,arm,p,f,featuremap)
  for row in case_events[case_events.sid.eq(sid)].itertuples():
   k=cal.get_loc(pd.Timestamp(row.day));ft=features(p,k);assert ft['local'] and np.isclose(ft['l1'],row.L1) and np.isclose(ft['u1'],row.U1)
   prefixft=features(p.iloc[:k+1],k);assert ft==prefixft;prefix.append(dict(sid=sid,day=row.day,physical_prefix_equal=True))
   for j in range(k,min(k+21,len(cal))):
    zz=p.iloc[j];valid=valid_prices(p.iloc[k:j+1]) is None
    casepaths.append(dict(sid=sid,candidate_day=row.day,day=cal[j],sessions_after=j-k,signal_only=True,coherent=valid,raw_close=float(zz.raw_close) if valid else None,raw_open=float(zz.raw_open) if valid else None,frozen_local_S=ft['l1'],frozen_local_U=ft['u1'],frozen_old20_U=max(ft['u0'],ft['u1']),above_local_S=bool(zz.raw_close>ft['l1']) if valid else None,above_old20_U=bool(zz.raw_close>max(ft['u0'],ft['u1'])) if valid else None))
  source_rows.append(dict(sid=sid,signal_path=str(sp),facts_path=str(fp),first=str(raw.index.min()),last=str(raw.index.max())))
  print('DONE',sid,round(time.monotonic()-started,1),flush=True)
 z=pd.DataFrame(rounds);
 for col in ['net_pnl','return_on_buy_cash']:
  if col not in z:z[col]=np.nan
 z.to_csv(O/'ROUNDS.csv',index=False);pd.DataFrame(paths).to_csv(O/'DAILY_ROOT_PATHS.csv',index=False);pd.DataFrame(signals).to_csv(O/'DAILY_SIGNALS.csv',index=False);pd.DataFrame(coverage).to_csv(O/'COVERAGE.csv',index=False);pd.DataFrame(casepaths).to_csv(O/'SIX_CASE_SIGNAL_PATHS.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_QA.csv',index=False)
 sums=[];paired=[]
 for (win,arm),g in z.groupby(['window','arm']):
  done=g[g.status.eq('COMPLETE')];w=done[done.net_pnl.gt(0)];l=done[done.net_pnl.lt(0)];accepted=g[g.accepted]
  sums.append(dict(window=win,arm=arm,root_births=len(g),accepted_buys=len(accepted),W=len(w),L=len(l),B=int(done.net_pnl.eq(0).sum()),U=int(accepted.status.eq('UNRESOLVED_END').sum()),UNKNOWN=int(accepted.status.str.startswith('UNKNOWN').sum()),unknown_unaccepted=int((~g.accepted&g.status.str.startswith('UNKNOWN')).sum()),minimum_lot_failures=int(g.status.eq('NO_BUY_MINIMUM_LOT').sum()),completed_net_cny=float(done.net_pnl.sum()),avg_win_cny=float(w.net_pnl.mean()),avg_loss_cny=float(l.net_pnl.mean()),avg_win_loss=float(w.net_pnl.mean()/-l.net_pnl.mean()),early_births=int(g.incremental_early.sum()),status_counts=g.status.value_counts().to_dict()))
 for win in z.window.unique():
  for sid in sids:
   r=dict(window=win,sid=sid)
   for arm in ['CONTROL','LOCAL','UNION']:
    g=z[z.window.eq(win)&z.sid.eq(sid)&z.arm.eq(arm)];done=g[g.status.eq('COMPLETE')];a=g[g.accepted];r.update({arm+'_births':len(g),arm+'_buys':len(a),arm+'_completed_net':float(done.net_pnl.sum()),arm+'_unresolved':int((~a.status.eq('COMPLETE')).sum())})
   r['completed_net_diff']=r['LOCAL_completed_net']-r['CONTROL_completed_net'];r['total_comparable']=r['LOCAL_unresolved']==0 and r['CONTROL_unresolved']==0;r['total_net_diff']=r['completed_net_diff'] if r['total_comparable'] else None;r['UNION_completed_net_diff']=r['UNION_completed_net']-r['CONTROL_completed_net'];r['UNION_total_comparable']=r['UNION_unresolved']==0 and r['CONTROL_unresolved']==0;r['UNION_total_net_diff']=r['UNION_completed_net_diff'] if r['UNION_total_comparable'] else None;paired.append(r)
 pd.DataFrame(paired).to_csv(O/'PAIRED_STOCK_DIFFERENCES.csv',index=False)
 assert all(sha(p)==h for p,h in hashes.items())
 save('SUMMARY.json',sums);save('SOURCE_HASHES.json',hashes);save('SOURCE_PATHS.json',source_rows)
 save('QA.json',dict(inputs_unchanged=True,stocks=22,windows=2,arms=3,original_simulator_executed=False,exact_helpers=['fee','getmeta','size'],prefix_cases=len(prefix),sizing_and_T1_assertions=True,full_account_runs=0,parameter_sweeps=0,unknown_not_zero=True,seconds=time.monotonic()-started))
 save('OUTPUT_HASHES.json',{x.name:sha(x) for x in O.iterdir() if x.is_file()})
 print(json.dumps(sums,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
