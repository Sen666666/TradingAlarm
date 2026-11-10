"""Relative directional change. Signal diagnostics only; no new return simulation."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def rdc(x,valid):
 x=np.asarray(x,float);valid=np.asarray(valid,bool)
 eps=np.r_[np.nan,np.diff(x)];eps[~valid]=np.nan
 sigma=pd.Series(eps).shift(1).rolling(63,min_periods=63).apply(lambda a:np.sqrt(np.mean(a*a)),raw=True).to_numpy()
 phase=0;lo=hi=None;loe=hie=None;ld=hd=None;lastup=-1;lastdown=-1
 state=[];event=[];lowat=[];highat=[];lastups=[];lastdowns=[];threshold=[]
 for j,v in enumerate(x):
  sig=sigma[j];evt=0
  if not valid[j] or not np.isfinite(v) or not np.isfinite(sig) or sig<=0:
   phase=0;lo=hi=None;loe=hie=None;ld=hd=None;lastup=lastdown=-1
   state.append(np.nan);event.append(0);lowat.append(-1);highat.append(-1);lastups.append(-1);lastdowns.append(-1);threshold.append(np.nan);continue
  delta=math.sqrt(5)*sig
  if lo is None:lo=hi=v;loe=hie=j;ld=hd=delta
  if phase==0:
   if v<lo:lo=v;loe=j;ld=delta
   if v>hi:hi=v;hie=j;hd=delta
   if v-lo>=ld:phase=1;evt=1;lastup=j;hi=v;hie=j;hd=delta
   elif hi-v>=hd:phase=-1;evt=-1;lastdown=j;lo=v;loe=j;ld=delta
  elif phase==1:
   if v>hi:hi=v;hie=j;hd=delta
   if hi-v>=hd:phase=-1;evt=-1;lastdown=j;lo=v;loe=j;ld=delta
  else:
   if v<lo:lo=v;loe=j;ld=delta
   if v-lo>=ld:phase=1;evt=1;lastup=j;hi=v;hie=j;hd=delta
  state.append(phase);event.append(evt);lowat.append(loe);highat.append(hie);lastups.append(lastup);lastdowns.append(lastdown);threshold.append(ld if phase<=0 else hd)
 return pd.DataFrame(dict(relative_phase=state,relative_event=event,relative_low_index=lowat,relative_high_index=highat,last_relative_up_index=lastups,last_relative_down_index=lastdowns,active_delta=threshold,sigma=sigma))
# Synthetic invariants before reading empirical clock labels.
base=np.r_[np.cumsum(np.tile([.01,-.01],40)),np.linspace(0,.10,25),np.linspace(.10,-.05,35),np.linspace(-.05,.08,30)]
valid=np.ones(len(base),bool);valid[0]=False
a=rdc(base,valid);b=rdc(base*7,valid);neg=rdc(-base,valid)
assert a.relative_event.equals(b.relative_event)
assert (a.relative_event.to_numpy()==-neg.relative_event.to_numpy()).all()
for n in [90,115,150]:pd.testing.assert_frame_equal(rdc(base[:n],valid[:n]),a.iloc[:n].reset_index(drop=True))
loops=np.r_[np.cumsum(np.tile([.01,-.01],40)),np.tile([.0001,0.],100)]
rl=rdc(loops,np.r_[False,np.ones(len(loops)-1,dtype=bool)])
assert not rl.relative_event.iloc[80:].eq(1).any(),'Small repeated loops cannot accumulate credit'
flat=rdc(np.zeros(200),np.r_[False,np.ones(199,bool)]);assert not flat.relative_event.ne(0).any()
save('RELATIVE_SYNTHETIC_TESTS.json',dict(scale_invariant=True,sign_symmetric=True,prefix_invariant=True,no_small_loop_credit=True,common_factor_flat_ratio_no_events=True))
protocol=O/'RELATIVE_CLOCK_PROTOCOL.json';save('RELATIVE_RUN_SEAL.json',dict(hashes={str(p):sha(p) for p in [protocol,Path(__file__),O/'SEALED_REPRESENTATIVE_CASES.csv',O/'ALL_2022_ENTRY_FEATURES.csv']},before_new_clock_outputs=True))
h=np.load(H,allow_pickle=False);cal=pd.DatetimeIndex(h['dates']);syms=pd.Index(h['symbols']);mask=cal<=pd.Timestamp('2022-12-31')
cal=cal[mask];C=pd.DataFrame(h['close'][mask],index=cal,columns=syms);G=pd.DataFrame(h['segment'][mask],index=cal,columns=syms)
di={d:j for j,d in enumerate(cal)}
old=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day']);old=old[old.window.eq('2022')&old.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
oldids=set(zip(old.sid,old.day))
selected=pd.read_csv(O/'ALL_2022_ENTRY_FEATURES.csv',parse_dates=['signal_day']);cases=pd.read_csv(O/'SEALED_REPRESENTATIVE_CASES.csv',parse_dates=['signal_day'])
sm=pd.read_parquet(M/'RIGHT3.parquet');sk=pd.read_parquet(M/'KNOWN3.parquet');panel=pd.read_parquet(M/'COMMON_K_COMPARISON.parquet').set_index(['sector','day'])
manifest={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())}
features=[];events=[];paths=[];prefixes=0;hashes={str(p):sha(p) for p in [H,M/'RIGHT3.parquet',M/'KNOWN3.parquet',M/'COMMON_K_COMPARISON.parquet',E/'SEALED_ALL_BIRTH_EVENTS.csv']}
for sid,sg in selected.groupby('sid'):
 sec=sg.sector.iloc[0];cc=C[sid];sc=C[sec]
 valid=cc.gt(0)&sc.gt(0)&np.isfinite(cc)&np.isfinite(sc)&G[sid].notna()&G[sec].notna()&G[sid].eq(G[sid].shift())&G[sec].eq(G[sec].shift())
 x=np.log(cc/sc);out=rdc(x.to_numpy(),valid.to_numpy());out.index=cal
 fp=manifest[sid]['refs']['facts'];f=pd.read_parquet(fp);hashes[fp]=sha(fp)
 for t,rr in out[out.relative_event.ne(0)&out.index.to_series().ge(pd.Timestamp('2022-01-01'))].iterrows():
  fr=f.loc[t] if t in f.index else None;ss=panel.loc[(sec,t)].M3_candidate if (sec,t) in panel.index else -1
  mk=t in sm.index and bool(sk.loc[t,sid]);m=bool(sm.loc[t,sid]) if mk else None
  iq=fr is not None and fr.e0_ready==1 and fr.g_ready==True and fr.i_target==1 and np.isfinite(fr.i_floor) and fr.i_floor>0
  invitation=rr.relative_event==1 and iq and ss==1 and m is True
  events.append(dict(sid=sid,sector=sec,day=t,relative_event=rr.relative_event,relative_phase=rr.relative_phase,originalIqualified=iq,stockM3=m,sectorS=ss,new_invitation=invitation,old_A_or_B_birth=(sid,t) in oldids,old_i_buy=bool(fr.i_buy) if fr is not None and pd.notna(fr.i_buy) else None,relative_low_day=cal[int(rr.relative_low_index)] if rr.relative_low_index>=0 else None,relative_high_day=cal[int(rr.relative_high_index)] if rr.relative_high_index>=0 else None))
 for r in sg.to_dict('records'):
  t=r['signal_day'];q=out.loc[t].to_dict();j=di[t]
  q['last_relative_up_age']=j-q['last_relative_up_index'] if q['last_relative_up_index']>=0 else np.nan
  q['last_relative_down_age']=j-q['last_relative_down_index'] if q['last_relative_down_index']>=0 else np.nan
  features.append(dict(r,**q))
  if r['round_id'] in set(cases.round_id):
   pd.testing.assert_frame_equal(rdc(x.iloc[:j+1].to_numpy(),valid.iloc[:j+1].to_numpy()),out.iloc[:j+1].reset_index(drop=True));prefixes+=1
   for k in range(j-10,j+1):
    t2=cal[k];v=out.iloc[k]
    paths.append(dict(round_id=r['round_id'],sid=sid,name=r['name'],signal_day=t,day=t2,relative_day=k-j,x=x.iloc[k],relative_phase=v.relative_phase,relative_event=v.relative_event,active_delta=v.active_delta,last_up_age=k-v.last_relative_up_index if v.last_relative_up_index>=0 else np.nan))
ee=pd.DataFrame(events);ff=pd.DataFrame(features);pp=pd.DataFrame(paths)
ee.to_csv(O/'RELATIVE_ALL_2022_EVENTS.csv',index=False);ff.to_csv(O/'RELATIVE_OLD_ENTRY_DESCRIPTORS.csv',index=False);pp.to_csv(O/'RELATIVE_REPRESENTATIVE_PREFIXES.csv',index=False)
ff[ff.round_id.isin(cases.round_id)].to_csv(O/'RELATIVE_REPRESENTATIVE_DESCRIPTORS.csv',index=False)
up=ee[ee.relative_event.eq(1)];inv=ee[ee.new_invitation]
summary=dict(scope_stocks=selected.sid.nunique(),relative_UP=len(up),new_qualified_invitations=len(inv),also_old_A_B=int(inv.old_A_or_B_birth.sum()),outside_old_A_B=int((~inv.old_A_or_B_birth).sum()),i_buy_false=int((~inv.old_i_buy.fillna(False)).sum()),relative_UP_rejected_I=int((~up.originalIqualified).sum()),relative_UP_rejected_M3=int((up.stockM3!=True).sum()),relative_UP_rejected_sector=int((up.sectorS!=1).sum()),prefix_cases_passed=prefixes,no_new_return_or_win_rate_estimated=True)
save('RELATIVE_SUMMARY.json',summary);assert all(sha(p)==v for p,v in hashes.items());save('RELATIVE_SOURCE_HASHES.json',hashes)
print(summary)
print(ff[ff.round_id.isin(cases.round_id)][['signal_day','name','industry','label','relative_phase','relative_event','last_relative_up_age','last_relative_down_age','relative_ret21','net_return_on_buy_cash']].to_string(index=False))
print('\nORIGINAL ENTRY STATES ONLY, NOT NEW STRATEGY')
print(ff.groupby(['label','relative_phase']).size().to_string())
