import warnings
warnings.filterwarnings('ignore',category=FutureWarning)
import json,hashlib,math,time
from pathlib import Path
import numpy as np,pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
Q=R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet'
LAB=Q.parent/'FIXED_NATIVE_PRICE_LABELS.parquet'
N=14
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
mp={x['symbol']:x for x in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates'])
cal=cal[(cal>='2013-01-01')&(cal<='2026-05-15')]
def rma(v,n=14):
 v=np.asarray(v,dtype=float);o=np.full(len(v),np.nan)
 if len(v)<n:return o
 z=v[n-1:].copy();z[0]=np.mean(v[:n])
 o[n-1:]=pd.Series(z).ewm(alpha=1/n,adjust=False).mean().to_numpy()
 return o
def calc(p,cal):
 p=p.reindex(cal);cols=['open','high','low','close']
 ok=np.isfinite(p[cols]).all(axis=1)&p[cols].gt(0).all(axis=1)&p.high.ge(p[cols].max(axis=1))&p.low.le(p[cols].min(axis=1))&p.segment_id.notna()
 for c in ['price_eligible','observed_bar','is_observed_bar']:ok &= p[c].fillna(False).astype(bool)
 for c in ['source_invalid','synthetic_event_bar']:ok &= ~p[c].fillna(True).astype(bool)
 block=((~ok)|(~ok.shift(fill_value=False))|p.segment_id.ne(p.segment_id.shift())).cumsum()
 names=['d','dclose','plus_di','minus_di','dx','adx','up_rma','dn_rma','gain_rma','loss_rma','age','raw_plus_dm','raw_minus_dm']
 out=pd.DataFrame(np.nan,index=cal,columns=names)
 for _,g in p.loc[ok].groupby(block[ok],sort=False):
  if len(g)<2:continue
  hh=g.high.to_numpy();ll=g.low.to_numpy();cc=g.close.to_numpy()
  up=np.diff(hh);dn=-np.diff(ll);dc=np.diff(cc)
  plus=np.where((up>dn)&(up>0),up,0);minus=np.where((dn>up)&(dn>0),dn,0)
  tr=np.maximum.reduce([hh[1:]-ll[1:],np.abs(hh[1:]-cc[:-1]),np.abs(ll[1:]-cc[:-1])])
  u,v,t=rma(plus),rma(minus),rma(tr);gu,gl=rma(np.maximum(dc,0)),rma(np.maximum(-dc,0))
  d=np.divide(u-v,u+v,out=np.zeros(len(u)),where=(u+v)>0);d[~np.isfinite(u+v)]=np.nan
  c=np.divide(gu-gl,gu+gl,out=np.zeros(len(gu)),where=(gu+gl)>0);c[~np.isfinite(gu+gl)]=np.nan
  dip=np.divide(100*u,t,out=np.zeros(len(t)),where=t>0);dim=np.divide(100*v,t,out=np.zeros(len(t)),where=t>0);dip[~np.isfinite(t)]=np.nan;dim[~np.isfinite(t)]=np.nan
  dx=100*np.abs(d);adx=np.full(len(d),np.nan)
  if len(d)>=N:adx[N-1:]=rma(dx[N-1:])
  out.loc[g.index[1:],:]=np.column_stack([d,c,dip,dim,dx,adx,u,v,gu,gl,np.arange(1,len(g)),plus,minus])
 return out
def source(sid):
 r=mp[sid];path=next(p for p in r['source_sha256'] if p.endswith('/signal.parquet'))
 assert sha(path)==r['source_sha256'][path]
 p=pd.read_parquet(path).loc[:'2026-05-15'];native=pd.read_parquet(r['refs']['facts'],columns=['close','factor']).reindex(p.index)
 assert (p.close-native.close).abs().max()<1e-7 and (p.adjustment_factor-native.factor).abs().max()<1e-10
 return p,path
def fuse(p,d):
 x=np.asarray(p,dtype=float);known=np.isfinite(x)&(x>0)&(x<100)&np.isfinite(d);out=np.full(len(x),np.nan)
 e=np.arctanh((x[known]-50)/50)/2
 out[known]=50+50*np.tanh(2*(e+.25*np.asarray(d)[known]*np.maximum(e,0)))
 return out
cases=[('000620.SZ','2022-01-11'),('002911.SZ','2022-07-25'),('000029.SZ','2022-12-01'),('600056.SH','2022-03-03'),('600056.SH','2022-03-30'),('002317.SZ','2022-10-14'),('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('600606.SH','2022-03-22'),('601607.SH','2022-03-24'),('300085.SZ','2024-09-12'),('300085.SZ','2024-09-19'),('300085.SZ','2024-09-24'),('300085.SZ','2024-10-09'),('300085.SZ','2024-10-10'),('300085.SZ','2024-10-11'),('002583.SZ','2024-09-19'),('002583.SZ','2024-10-15'),('688582.SH','2024-07-29'),('300666.SZ','2026-01-15'),('603061.SH','2026-01-15'),('301611.SZ','2026-01-15'),('300623.SZ','2026-01-09')]

def save_json(n,x):
 (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)))
def checks():
 rng=np.random.default_rng(14);v=rng.uniform(0,2,90);z=rma(v);ref=np.full(90,np.nan);ref[13]=sum(v[:14])/14
 for i in range(14,90):ref[i]=(13*ref[i-1]+v[i])/14
 assert np.nanmax(abs(z-ref))<1e-14
 def synthetic(c,h,l):
  x=pd.DataFrame({'open':c,'high':h,'low':l,'close':c,'segment_id':0,'price_eligible':True,'observed_bar':True,'is_observed_bar':True,'source_invalid':False,'synthetic_event_bar':False},index=pd.date_range('2020-01-01',periods=len(c)))
  return calc(x,x.index)
 cc=np.full(60,10.);s=np.linspace(-.4,.4,60)
 a=synthetic(cc,11+s,9+s);b=synthetic(cc,11-s,9-s)
 assert a.d.iloc[-1]==1 and b.d.iloc[-1]==-1 and a.dclose.iloc[-1]==b.dclose.iloc[-1]==0
 a0=synthetic(cc,cc,cc);assert a0.d.iloc[-1]==a0.dclose.iloc[-1]==0 and a0.adx.iloc[-1]==0
 c=np.arange(60)+10.;u=synthetic(c,c+.1,c-.1);v=synthetic(c[::-1],c[::-1]+.1,c[::-1]-.1)
 assert u.d.iloc[-1]==u.dclose.iloc[-1]==1 and v.d.iloc[-1]==v.dclose.iloc[-1]==-1
 # Outside ties lose both; inside bars lose both. This is NOT independent max(+H,0)/max(-L,0).
 assert np.where((np.array([2,-1])>np.array([2,-1]))&(np.array([2,-1])>0),np.array([2,-1]),0).sum()==0
 # RMA source-reset contract is a fresh seed, not an old state carried across.
 assert np.flatnonzero(np.isfinite(a.d))[0]==14 and np.flatnonzero(np.isfinite(a.adx))[0]==27
 return dict(rma_vs_scalar_max_error=float(np.nanmax(abs(z-ref))),same_close_same_TR_d_different=True,constant_zero=True,monotone=True,competitive_tie_and_inside=True,first_d_bar_zero_based=14,first_adx_bar_zero_based=27)
def run():
 assert not(O/'RANK_SEAL.json').exists()
 start=time.monotonic();q=pd.read_parquet(Q);q=q[q.account.eq('PVR')].reset_index(drop=True);assert len(q)==53121
 ih={str(p):sha(p) for p in [M,H,Q,Path(__file__),O/'PROTOCOL.json']};features=[];aud=[];fixed=[];qa=checks();prefix=0
 for no,(sid,g) in enumerate(q.groupby('sid',sort=True)):
  p,path=source(sid);ih[path]=sha(path);ih[mp[sid]['refs']['facts']]=sha(mp[sid]['refs']['facts'])
  z=calc(p,cal);idx=pd.DatetimeIndex(g.day);a=z.reindex(idx).reset_index(drop=True);a['sid']=sid;a['day']=g.day.to_numpy();features.append(a)
  aud.append(dict(sid=sid,source=path,hash=ih[path],rows=len(g),known=int(a.d.notna().sum()),min_age=float(a.age.min())))
  for ss,day in cases:
   if ss!=sid:continue
   cc=cal[cal<=day];zz=calc(p.loc[:day],cc);pd.testing.assert_frame_equal(zz,z.loc[cc],check_exact=True);prefix+=1
   row=z.loc[day].to_dict();row.update(sid=sid,day=day);fixed.append(row)
  if (no+1)%300==0:print('FEATURES',no+1,round(time.monotonic()-start,2),flush=True)
 # Also fixed names absent from the MOBILE universe, without adding their observations to that universe.
 absent=set(ss for ss,day in cases)-set(q.sid)
 for sid in absent:
  p,path=source(sid);z=calc(p,cal)
  for ss,day in cases:
   if ss==sid:
    cc=cal[cal<=day];pd.testing.assert_frame_equal(calc(p.loc[:day],cc),z.loc[cc],check_exact=True);prefix+=1
    row=z.loc[day].to_dict();row.update(sid=sid,day=day);fixed.append(row)
 c=q.merge(pd.concat(features,ignore_index=True),on=['sid','day'],validate='one_to_one');assert len(c)==53121
 c['row']=np.arange(len(c));c['calendar_t']=[cal.get_loc(pd.Timestamp(d)) for d in c.day]
 c['DMI']=fuse(c.original_PVR,c.d);c['CLOSE']=fuse(c.original_PVR,c.dclose)
 c['common_known']=c[['DMI','CLOSE','original_PVR']].notna().all(axis=1)
 assert c.loc[c.common_known,'original_PVR'].gt(0).all() and c.loc[c.common_known,'original_PVR'].lt(100).all()
 nonzero=(c.plus_di+c.minus_di)>0
 assert ((c.loc[nonzero,'plus_di']-c.loc[nonzero,'minus_di'])/(c.loc[nonzero,'plus_di']+c.loc[nonzero,'minus_di'])-c.loc[nonzero,'d']).abs().max()<1e-12
 picks=[];moves=[];queues=[];corr=[]
 for day,g in c.groupby('day',sort=True):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));ks=base.head(K).groupby('sector').size().to_dict();bi=set(base.head(K).index)
  for method in ['PVR','CLOSE','DMI']:
   chosen=[]
   for sector,gs in base.groupby('sector',sort=False):
    k=int(ks.get(sector,0));order=list(gs.index)
    if method!='PVR':
     good=gs.common_known;ranked=gs[good].assign(score12=gs.loc[good,method].round(12)).sort_values(['score12','original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ranked.index)
     order=[next(it) if good.loc[j] else j for j in gs.index]
     assert all(order[pos]==j for pos,j in enumerate(gs.index) if not good.loc[j])
     assert set(order)==set(gs.index)
    chosen+=order[:k];moves.extend(dict(row=int(j),method=method,sector_rank=rank+1,selected=rank<k) for rank,j in enumerate(order))
   assert len(chosen)==K and c.loc[chosen].groupby('sector').size().to_dict()==ks
   picks.extend(dict(row=int(j),day=day,method=method) for j in chosen);queues.append(dict(day=day,method=method,N=len(g),K=K,known=int(g.common_known.sum()),changed=len(set(chosen)-bi)))
  for sector,gs in g[g.common_known].groupby('sector'):
   if len(gs)>=3:corr.append(dict(day=day,sector=sector,N=len(gs),d_close=gs.d.rank().corr(gs.dclose.rank()),d_PVR=gs.d.rank().corr(gs.original_PVR.rank())))
 c.to_parquet(O/'FEATURES.parquet',index=False);pd.DataFrame(picks).to_parquet(O/'SEALED_PICKS.parquet',index=False);pd.DataFrame(moves).to_parquet(O/'RANK_MOVES.parquet',index=False)
 pd.DataFrame(queues).to_csv(O/'QUEUE_AUDIT.csv',index=False);pd.DataFrame(aud).to_csv(O/'SOURCE_AUDIT.csv',index=False);pd.DataFrame(corr).to_csv(O/'RANK_OVERLAP.csv',index=False)
 pd.DataFrame(fixed).to_csv(O/'FIXED_CASE_FEATURES.csv',index=False)
 qa.update(prefix_exact=prefix,original_PVR_unknown=int(c.original_PVR.isna().sum()),common_known=int(c.common_known.sum()),unknown_original_slots_preserved=True,DX_TR_cancellation=True)
 save_json('QA.json',qa);save_json('INPUT_HASHES.json',ih)
 seal={n:sha(O/n) for n in ['FEATURES.parquet','SEALED_PICKS.parquet','RANK_MOVES.parquet','experiment.py','PROTOCOL.json']}
 save_json('RANK_SEAL.json',dict(hashes=seal,future_labels_read=False,rows=len(c),common_known=int(c.common_known.sum()),slots=len(picks)//3,seconds=time.monotonic()-start))
 print('SEALED',json.dumps(qa),flush=True)
def periods():
 return [('ALL',None,None)]+[(str(y),f'{y}-01-01',f'{y}-12-31') for y in range(2022,2027)]+[('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31')]
def per(x,a,b):return x if a is None else x[x.day.between(a,b)]
def blockstat(v):
 pos={str(d.date()):i for i,d in enumerate(cal)};b=pd.DataFrame({'v':v,'block':[pos[str(d)]//60 for d in v.index]}).groupby('block').v.agg(['sum','count'])
 out=dict(days=len(v),blocks=len(b),delta=float(v.mean()),lo=None,hi=None,leave_best_day=float(v.drop(v.idxmax()).mean()) if len(v)>1 else None)
 if len(b)>=5:
  rng=np.random.default_rng(20261106);ix=rng.integers(0,len(b),(2000,len(b)));z=b['sum'].to_numpy()[ix].sum(1)/b['count'].to_numpy()[ix].sum(1);out.update(lo=float(np.quantile(z,.025)),hi=float(np.quantile(z,.975)))
 return out
def evaluate():
 seal=json.loads((O/'RANK_SEAL.json').read_text());assert all(sha(O/n)==h for n,h in seal['hashes'].items())
 c=pd.read_parquet(O/'FEATURES.parquet');sel=pd.read_parquet(O/'SEALED_PICKS.parquet');lab=pd.read_parquet(LAB)
 c=c.merge(lab,on=['sid','day'],validate='one_to_one');s=sel.merge(c,on=['row','day'],validate='many_to_one')
 results=[];deltas=[]
 for h in [5,20,60]:
  good=s.groupby('day')['complete'+str(h)].all();whole=s[s.day.isin(good[good].index)]
  for period,a,b in periods():
   sub=per(whole,a,b)
   if not len(sub):continue
   means=sub.groupby(['day','method'])['ret'+str(h)].mean().unstack('method')
   for method,g in sub.groupby('method'):
    results.append(dict(period=period,H=h,method=method,N=len(g),days=g.day.nunique(),mean_day=g.groupby('day')['ret'+str(h)].mean().mean(),mean_event=g['ret'+str(h)].mean(),mae_day=g.groupby('day')['mae'+str(h)].mean().mean(),mfe_day=g.groupby('day')['mfe'+str(h)].mean().mean(),positive_40bp=(g['ret'+str(h)]>.004).mean()))
   for x,y in [('DMI','PVR'),('CLOSE','PVR'),('DMI','CLOSE')]:deltas.append(dict(period=period,H=h,comparison=x+'-'+y,**blockstat(means[x]-means[y])))
 pd.DataFrame(results).to_csv(O/'SAME_DATE_SECTOR_K_RESULTS.csv',index=False);pd.DataFrame(deltas).to_csv(O/'PAIRED_60SESSION_BLOCKS.csv',index=False)
 mem={m:set(g.row) for m,g in sel.groupby('method')};roots=[]
 for (sid,epoch),g in c.groupby(['sid','epoch'],dropna=False):
  g=g.sort_values('calendar_t');b=g.iloc[0];early=set(g.loc[g.calendar_t.le(b.calendar_t+5),'row'])
  z=dict(sid=sid,epoch=str(epoch),epoch_known=str(epoch) not in ['None','nan','[None, None]'],day=b.day,complete60=bool(b.complete60),big60=bool(b.big60_posthoc))
  z.update({m:bool(early&mm) for m,mm in mem.items()});roots.append(z)
 roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_COVERAGE.csv',index=False);rs=[]
 for period,a,b in periods():
  g=per(roots,a,b);g=g[g.epoch_known];big=g[g.big60]
  for m in mem:rs.append(dict(period=period,method=m,roots=len(g),complete=int(g.complete60.sum()),big=len(big),caught=int(big[m].sum()),lost_vs_PVR=int((big.PVR&~big[m]).sum()),added_vs_PVR=int((~big.PVR&big[m]).sum())))
 pd.DataFrame(rs).to_csv(O/'ROOT_COVERAGE_SUMMARY.csv',index=False)
 named=pd.DataFrame(cases,columns=['sid','day']).merge(c,on=['sid','day'],how='left',validate='one_to_one');moves=pd.read_parquet(O/'RANK_MOVES.parquet')
 named=named.merge(moves,on='row',how='left');named.to_csv(O/'NAMED_CASES.csv',index=False)
 # A descriptive association only. A missing counterfactual round is not a loss or a zero.
 ac=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv');ac=ac[ac.account.eq('PVR')&ac.first_kind.eq('add')]
 ac=ac.merge(c[['sid','day','row']],left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one');ar=[]
 for m,ss in mem.items():
  for y,g in ac[ac.row.isin(ss)&ac.closed].groupby('year'):ar.append(dict(year=y,method=m,original_filled_closed=len(g),original_wins=int((g.round_pnl>0).sum()),NOT_COUNTERFACTUAL=True))
 pd.DataFrame(ar).to_csv(O/'ORIGINAL_MOBILE_CLOSED_ASSOCIATION.csv',index=False)
 ih=json.loads((O/'INPUT_HASHES.json').read_text());assert all(sha(p)==h for p,h in ih.items());assert all(sha(O/n)==h for n,h in seal['hashes'].items())
 save_json('COMPLETION.json',dict(status='one_frozen_same_date_sector_K_comparison_complete',accounts=0,parameter_searches=0,original_models_rerun=0,source_hashes_unchanged=True,rank_seal_unchanged=True,label_sha=sha(LAB),net_round_target_verified=False,not_PIT=True,not_untouched_OOS=True))
 print('RESULTS',pd.DataFrame(results).query('H in [20,60]').round(8).to_csv(index=False),flush=True)
 print('DELTAS',pd.DataFrame(deltas).query('H in [20,60]').round(8).to_csv(index=False),flush=True)
 print('ROOTS',pd.DataFrame(rs).to_csv(index=False),flush=True)
 print('NAMED',named[['sid','day','method','sector_rank','selected','original_PVR','d','dclose','ret20','ret60']].round(6).to_csv(index=False),flush=True)
if __name__=='__main__':
 import sys
 O=R/'dmi_boundary_migration_v1'
 if sys.argv[1]=='run':run()
 elif sys.argv[1]=='evaluate':evaluate()
