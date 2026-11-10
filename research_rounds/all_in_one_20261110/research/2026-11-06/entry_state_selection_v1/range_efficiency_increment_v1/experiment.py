"""Frozen H/L range-efficiency increment. No native model, account, quantity or order."""
from pathlib import Path
import json,sys,time,hashlib,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
B=R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1'
Q=B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet';LAB=B/'FIXED_NATIVE_PRICE_LABELS.parquet'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
METHODS=['PVR','Qclose','Qrange'];N=14;END='2026-05-15'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item()if isinstance(v,np.generic)else str(v)))
def calendar():
 d=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);return d[(d>='2013-01-01')&(d<=END)]
def calc(p,cal):
 p=p.reindex(cal); cols=['open','high','low','close']
 ok=np.isfinite(p[cols]).all(axis=1)&p[cols].gt(0).all(axis=1)
 ok &= p.high.ge(p[cols].max(axis=1))&p.low.le(p[cols].min(axis=1))
 for c in ['price_eligible','observed_bar','is_observed_bar']:ok &= p[c].fillna(False).astype(bool)
 for c in ['source_invalid','synthetic_event_bar']:ok &= ~p[c].fillna(True).astype(bool)
 seg=p.segment_id
 warm=ok.rolling(N+1,min_periods=N+1).sum().eq(N+1)&seg.notna().rolling(N+1).sum().eq(N+1)&seg.rolling(N+1).min().eq(seg.rolling(N+1).max())
 C=p.close;diff=C.diff()
 tr=pd.concat([p.high-p.low,(p.high-C.shift()).abs(),(p.low-C.shift()).abs()],axis=1).max(axis=1)
 dc=C-C.shift(N);vc=diff.abs().rolling(N,min_periods=N).sum();vt=tr.rolling(N,min_periods=N).sum()
 warm &= vc.gt(0)&vt.gt(0)
 z=pd.DataFrame({'D':dc,'Vclose':vc,'Vrange':vt,'Qclose':dc/vc,'Qrange':dc/vt,'F':vc/vt,'logpret14':np.log(C/C.shift(N))},index=cal).where(warm)
 z['common_known']=warm
 assert ((z.F.dropna()>=-1e-12)&(z.F.dropna()<=1+1e-12)).all()
 assert (z.Qrange-z.Qclose*z.F).abs().max()<1e-12 or z.Qrange.notna().sum()==0
 return z
def run():
 assert not(O/'SEALED_PICKS.parquet').exists()
 start=time.monotonic();cal=calendar();q=pd.read_parquet(Q);q=q[q.account.eq('PVR')].reset_index(drop=True);assert len(q)==53121
 mp={x['symbol']:x for x in json.loads(M.read_text())}
 sources={str(p):sha(p)for p in [M,H,Q,Path(__file__),O/'PROTOCOL.json']}
 allf=[];aud=[];prefix=[]
 for no,(sid,g)in enumerate(q.groupby('sid',sort=True)):
  r=mp[sid];path=next(p for p in r['source_sha256']if p.endswith('/signal.parquet'));hs=sha(path);assert hs==r['source_sha256'][path]
  p=pd.read_parquet(path).loc[:END];assert p.index.is_unique and p.index.is_monotonic_increasing
  native=pd.read_parquet(r['refs']['facts'],columns=['close','factor']).reindex(p.index)
  err=float((p.close-native.close).abs().max());ferr=float((p.adjustment_factor-native.factor).abs().max());assert err<1e-7 and ferr<1e-10
  sources[path]=hs;sources[r['refs']['facts']]=sha(r['refs']['facts'])
  z=calc(p,cal);idx=pd.DatetimeIndex(g.day);a=z.reindex(idx).reset_index(drop=True);a['sid']=sid;a['day']=g.day.to_numpy();allf.append(a)
  aud.append(dict(sid=sid,source=path,source_hash=hs,candidates=len(g),known=int(a.common_known.sum()),close_error=err,factor_error=ferr))
  if sid in ['000001.SZ','300085.SZ','300666.SZ','688603.SH','301611.SZ']:
   for cut in ['2022-01-04','2024-09-24','2026-01-15']:
    cc=cal[cal<=cut];zz=calc(p.loc[:cut],cc);pd.testing.assert_frame_equal(zz,z.loc[cc],check_exact=True);prefix.append(dict(sid=sid,cut=cut,exact=True))
  if (no+1)%300==0:print('FEATURES',no+1,round(time.monotonic()-start,2),flush=True)
 c=q.merge(pd.concat(allf,ignore_index=True),on=['sid','day'],validate='one_to_one')
 assert not c.duplicated(['sid','day']).any()
 c['row']=np.arange(len(c));c['calendar_t']=[cal.get_loc(pd.Timestamp(d))for d in c.day]
 picks=[];queues=[];moves=[]
 for day,g in c.groupby('day',sort=True):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));bi=set(base.head(K).index);ks=base.head(K).groupby('sector').size().to_dict()
  for method in METHODS:
   chosen=[]
   for sector,gs in base.groupby('sector',sort=False):
    k=int(ks.get(sector,0));order=list(gs.index)
    if method!='PVR':
     good=gs.common_known;ranked=gs[good].sort_values([method,'original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ranked.index)
     order=[next(it)if good.loc[j]else j for j in gs.index]
     assert all(order[pos]==j for pos,j in enumerate(gs.index)if not good.loc[j])and set(order)==set(gs.index)
    chosen+=order[:k]
    moves.extend(dict(row=int(j),method=method,sector_rank=rank+1,selected=rank<k)for rank,j in enumerate(order))
   assert len(chosen)==K and c.loc[chosen].groupby('sector').size().to_dict()==ks
   picks.extend(dict(row=int(j),day=day,method=method)for j in chosen)
   queues.append(dict(day=day,method=method,N=len(g),K=K,known=int(g.common_known.sum()),changed=len(set(chosen)-bi)))
 # Strictly feature-only matching. No future labels, original closed labels or outcomes.
 pairs=[]
 for(day,sector),g in c[c.common_known&c.logpret14.gt(0)].groupby(['day','sector'],sort=True):
  a=g.sort_values(['logpret14','sid']);ids=list(a.index);edges=[]
  for j,i in enumerate(ids):
   for k in ids[j+1:]:
    dp=abs(float(c.at[i,'logpret14']-c.at[k,'logpret14']))
    if dp>.02+1e-12:continue
    de=abs(float(c.at[i,'Qclose']-c.at[k,'Qclose']))
    if de>.05+1e-12:continue
    edges.append((dp/.02+de/.05,c.at[i,'sid'],c.at[k,'sid'],i,k,dp,de))
  used=set()
  for distance,si,sk,i,k,dp,de in sorted(edges):
   if i in used or k in used:continue
   used|={i,k}
   if abs(float(c.at[i,'F']-c.at[k,'F']))<1e-12:continue
   if c.at[i,'F']<c.at[k,'F']:i,k=k,i
   pairs.append(dict(day=day,sector=sector,hi=int(i),lo=int(k),logpret_gap=dp,Qclose_gap=de,F_delta=float(c.at[i,'F']-c.at[k,'F']),Qrange_delta=float(c.at[i,'Qrange']-c.at[k,'Qrange']),PVR_delta=float(c.at[i,'original_PVR']-c.at[k,'original_PVR'])))
 c.to_parquet(O/'FEATURES.parquet',index=False);pd.DataFrame(picks).to_parquet(O/'SEALED_PICKS.parquet',index=False);pd.DataFrame(moves).to_parquet(O/'RANK_MOVES.parquet',index=False)
 pd.DataFrame(pairs).to_csv(O/'SEALED_MATCHED_PAIRS.csv',index=False);pd.DataFrame(queues).to_csv(O/'QUEUE_AUDIT.csv',index=False);pd.DataFrame(aud).to_csv(O/'SOURCE_AUDIT.csv',index=False)
 dump('PREFIX_QA.json',prefix);dump('INPUT_HASHES.json',sources)
 seal={n:sha(O/n)for n in ['FEATURES.parquet','SEALED_PICKS.parquet','RANK_MOVES.parquet','SEALED_MATCHED_PAIRS.csv','experiment.py','PROTOCOL.json']}
 dump('RANK_SEAL.json',dict(hashes=seal,future_labels_read=False,opportunities=len(c),known=int(c.common_known.sum()),matches=len(pairs),seconds=time.monotonic()-start))
 print('SEALED',json.loads((O/'RANK_SEAL.json').read_text()),flush=True)
def periods():
 return [('ALL',None,None)]+[(str(y),f'{y}-01-01',f'{y}-12-31')for y in range(2022,2027)]+[('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31')]
def period(df,start,end):return df if start is None else df[df.day.between(start,end)]
def blockstat(v,cal):
 pos={str(d.date()):i for i,d in enumerate(cal)};b=pd.DataFrame({'v':v,'block':[pos[str(d)]//60 for d in v.index]}).groupby('block').v.agg(['sum','count'])
 out=dict(days=len(v),blocks=len(b),delta=float(v.mean()),lo=None,hi=None,leave_best_day=float(v.drop(v.idxmax()).mean())if len(v)>1 else None)
 if len(b)>=5:
  rng=np.random.default_rng(20261106);ix=rng.integers(0,len(b),(2000,len(b)));z=b['sum'].to_numpy()[ix].sum(1)/b['count'].to_numpy()[ix].sum(1);out.update(lo=float(np.quantile(z,.025)),hi=float(np.quantile(z,.975)))
 return out
def evaluate():
 seal=json.loads((O/'RANK_SEAL.json').read_text());assert all(sha(O/n)==h for n,h in seal['hashes'].items())
 c=pd.read_parquet(O/'FEATURES.parquet');sel=pd.read_parquet(O/'SEALED_PICKS.parquet');cal=calendar();lab=pd.read_parquet(LAB);assert not lab.duplicated(['sid','day']).any()
 c=c.merge(lab,on=['sid','day'],validate='one_to_one');assert len(c)==53121
 s=sel.merge(c,on=['row','day'],validate='many_to_one')
 results=[];deltas=[];coverage=[]
 for h in [5,20,60]:
  co='complete'+str(h);ret='ret'+str(h);good=s.groupby('day')[co].all();gooddays=set(good[good].index);whole=s[s.day.isin(gooddays)].copy()
  for per,start,end in periods():
   u=period(s,start,end);sub=period(whole,start,end)
   coverage.append(dict(period=per,H=h,candidate_dates=period(c,start,end).day.nunique(),selection_dates=u.day.nunique(),complete_all_methods_dates=sub.day.nunique(),rows_per_method=len(sub)//3))
   if len(sub)==0:continue
   means=sub.groupby(['day','method'])[ret].mean().unstack('method')
   for method,g in sub.groupby('method'):
    results.append(dict(period=per,H=h,method=method,N=len(g),days=g.day.nunique(),mean_day=float(g.groupby('day')[ret].mean().mean()),mean_event=float(g[ret].mean()),median=float(g[ret].median()),positive_price=float(g[ret].gt(0).mean()),positive_40bp=float(g[ret].gt(.004).mean()),mae=float(g['mae'+str(h)].mean()),mfe=float(g['mfe'+str(h)].mean())))
   for a,b in [('Qrange','PVR'),('Qclose','PVR'),('Qrange','Qclose')]:
    deltas.append(dict(period=per,H=h,comparison=a+'-'+b,**blockstat(means[a]-means[b],cal)))
 pd.DataFrame(results).to_csv(O/'SAME_DATE_SECTOR_K_RESULTS.csv',index=False);pd.DataFrame(deltas).to_csv(O/'PAIRED_60SESSION_BLOCKS.csv',index=False);pd.DataFrame(coverage).to_csv(O/'EVALUATION_COVERAGE.csv',index=False)
 mem={m:set(g.row)for m,g in sel.groupby('method')};roots=[]
 for(sid,epoch),g in c.groupby(['sid','epoch'],dropna=False):
  g=g.sort_values('calendar_t');b=g.iloc[0];early=set(g.loc[g.calendar_t.le(b.calendar_t+5),'row']);validroot=str(epoch)not in ['None','nan','[None, None]']
  z=dict(sid=sid,epoch=str(epoch),epoch_known=validroot,day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc))
  z.update({m:bool(early&mm)for m,mm in mem.items()});roots.append(z)
 roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_COVERAGE.csv',index=False);rs=[]
 for per,start,end in periods():
  g=period(roots,start,end)
  for scope in ['ALL_ROOTS','KNOWN_EPOCH']:
   z=g if scope=='ALL_ROOTS'else g[g.epoch_known];big=z[z.big60]
   for method in METHODS:rs.append(dict(period=per,scope=scope,method=method,roots=len(z),complete=int(z.complete60.sum()),big=len(big),caught=int(big[method].sum()),lost_vs_PVR=int((big.PVR&~big[method]).sum()),added_vs_PVR=int((~big.PVR&big[method]).sum())))
 pd.DataFrame(rs).to_csv(O/'ROOT_COVERAGE_SUMMARY.csv',index=False)
 p=pd.read_csv(O/'SEALED_MATCHED_PAIRS.csv');p=p.merge(c.add_prefix('hi_'),left_on='hi',right_on='hi_row',validate='many_to_one').merge(c.add_prefix('lo_'),left_on='lo',right_on='lo_row',validate='many_to_one')
 p['year']=p.day.str[:4];p['range_order_agrees']=p.Qrange_delta.gt(0);matches=[];firstroot=set(c.sort_values('calendar_t').drop_duplicates(['sid','epoch']).row)
 p['both_root_first']=p.hi.isin(firstroot)&p.lo.isin(firstroot)
 for per,start,end in periods():
  g=period(p,start,end)
  for scope in ['ALL_PAIRS','BOTH_FIRST_ROOT_OPPORTUNITY']:
   z=g if scope=='ALL_PAIRS'else g[g.both_root_first]
   for h in [5,20,60]:
    z0=z[z['hi_complete'+str(h)]&z['lo_complete'+str(h)]]
    if not len(z0):continue
    delta=z0['hi_ret'+str(h)]-z0['lo_ret'+str(h)];byday=delta.groupby(z0.day).mean()
    matches.append(dict(period=per,scope=scope,H=h,pairs=len(z0),dates=z0.day.nunique(),stocks=len(set(z0.hi_sid)|set(z0.lo_sid)),mean_event_delta=float(delta.mean()),mean_logpret_gap=float(z0.logpret_gap.mean()),mean_Qclose_gap=float(z0.Qclose_gap.mean()),mean_PVR_delta=float(z0.PVR_delta.mean()),mean_F_delta=float(z0.F_delta.mean()),range_order_agrees=float(z0.range_order_agrees.mean()),**blockstat(byday,cal)))
 p.to_csv(O/'MATCHED_PAIRS_WITH_LABELS.csv',index=False);pd.DataFrame(matches).to_csv(O/'MATCHED_CONTROL_RESULTS.csv',index=False)
 # Named examples fixed by parent/prior diagnosis, not picked using new outcomes.
 named=[('000620.SZ','2022-01-11'),('002911.SZ','2022-07-25'),('000029.SZ','2022-12-01'),('600056.SH','2022-03-03'),('002317.SZ','2022-10-14'),('300085.SZ','2024-09-19'),('300085.SZ','2024-09-24'),('300085.SZ','2024-10-09'),('002583.SZ','2024-10-15'),('300666.SZ','2026-01-15'),('688603.SH','2026-01-15'),('301611.SZ','2026-01-15')]
 moves=pd.read_parquet(O/'RANK_MOVES.parquet');names=[]
 for sid,day in named:
  g=c[c.sid.eq(sid)&c.day.eq(day)]
  if not len(g):names.append(dict(sid=sid,day=day,legal_queue=False));continue
  r=g.iloc[0]
  for mm in moves[moves.row.eq(r.row)].to_dict('records'):names.append(dict(sid=sid,day=day,legal_queue=True,**mm,common_known=bool(r.common_known),Qclose=r.Qclose,Qrange=r.Qrange,F=r.F,logpret14=r.logpret14,PVR=r.original_PVR,ret20=r.ret20,ret60=r.ret60))
 pd.DataFrame(names).to_csv(O/'NAMED_CASES.csv',index=False)
 # Only old filled-round association: not a counterfactual strategy.
 ac=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv');ac=ac[ac.account.eq('PVR')];ac=ac.merge(c[['sid','day','row','common_known','Qclose','Qrange','F']],left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one');ar=[]
 for method in METHODS:
  for y,g in ac[ac.row.isin(mem[method])&ac.closed].groupby('year'):
   ar.append(dict(year=y,method=method,original_filled_closed_association=len(g),wins=int(g.round_pnl.gt(0).sum()),original_win_fraction=float(g.round_pnl.gt(0).mean()),NOT_NEW_STRATEGY=True))
 pd.DataFrame(ar).to_csv(O/'ORIGINAL_CLOSED_ASSOCIATION.csv',index=False)
 cor=[]
 for(day,sector),g in c[c.common_known].groupby(['day','sector']):
  if len(g)<3:continue
  cor.append(dict(day=day,sector=sector,N=len(g),range_close=g.Qrange.rank().corr(g.Qclose.rank()),range_PVR=g.Qrange.rank().corr(g.original_PVR.rank()),F_PVR=g.F.rank().corr(g.original_PVR.rank())))
 pd.DataFrame(cor).to_csv(O/'RANK_OVERLAP.csv',index=False)
 s.to_parquet(O/'SELECTED_WITH_LABELS.parquet',index=False)
 sources=json.loads((O/'INPUT_HASHES.json').read_text());unchanged=all(sha(p)==h for p,h in sources.items());assert unchanged
 assert all(sha(O/n)==h for n,h in seal['hashes'].items())
 dump('COMPLETION.json',dict(status='ONE_FROZEN_HL_INCREMENT_DIAGNOSTIC_COMPLETE',opportunities=len(c),common_known=int(c.common_known.sum()),total_slots=int(len(sel)//3),matches=len(p),accounts=0,original_models_rerun=0,parameter_searches=0,original_sources_unchanged=unchanged,selection_seal_unchanged=True,label_sha256=sha(LAB),not_PIT=True,not_untouched_OOS=True))
 dump('OUTPUT_HASHES.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_HASHES.json'})
 print('TOPK',pd.DataFrame(results).query('H in [20,60]').to_string(index=False),flush=True)
 print('MATCHES',pd.DataFrame(matches).query('scope==\"ALL_PAIRS\" and H in [20,60]').to_string(index=False),flush=True)
 print('ROOTS',pd.DataFrame(rs).query('scope==\"KNOWN_EPOCH\"').to_string(index=False),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='run':run()
 elif sys.argv[1]=='evaluate':evaluate()
