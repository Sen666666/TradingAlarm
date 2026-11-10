"""Single frozen range-position conditional PVR fusion. Research only, no accounts."""
from pathlib import Path
import sys,json,hashlib,time,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
B=R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1'
MP=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')
sys.path.insert(0,str(F.parent));from features import original_pvr,original_observation_clock
W=.9**np.arange(20,-1,-1);W/=W.sum();END='2026-05-15'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
def calc(p,extra=False):
 z=original_pvr(p);valid,block=original_observation_clock(p)
 cols=['high','low','close'];ok=valid&np.isfinite(p[cols]).all(axis=1)&p[cols].gt(0).all(axis=1)&p.high.ge(p.close)&p.low.le(p.close)&p.high.ge(p.low)&p.source_kind.notna()
 bb=((~ok)|(~ok.shift(fill_value=False))|block.ne(block.shift())|p.source_kind.ne(p.source_kind.shift())).cumsum()
 for c in ['k','D','slowD','WR','CCI','eK','EK','scoreK','P','N','PK','NK','rangebias','record_bear','record_bull']:z[c]=np.nan
 for _,g in p[ok].groupby(bb[ok],sort=False):
  ix=g.index;lo=g.low.rolling(14,min_periods=14).min();hi=g.high.rolling(14,min_periods=14).max();width=(hi-lo).replace(0,np.nan)
  k=(g.close-lo)/width;e=z.loc[ix,'e'];ep=e.clip(lower=0);en=(-e).clip(lower=0);ek=k*ep-(1-k)*en
  emean=lambda x:x.rolling(21,min_periods=21).apply(lambda v:np.dot(W,v),raw=True)
  vals={'k':k,'D':k.rolling(3,min_periods=3).mean()*100,'WR':100*k-100,'eK':ek,'EK':emean(ek),'P':emean(ep),'N':emean(en),'PK':emean(k*ep),'NK':emean((1-k)*en),'rangebias':emean((k-.5)*e.abs())}
  vals['scoreK']=50+50*np.tanh(2*vals['EK']);vals['slowD']=vals['D'].rolling(3,min_periods=3).mean()
  if extra:
   tp=(g.high+g.low+g.close)/3;mean=tp.rolling(20,min_periods=20).mean();md=tp.rolling(20,min_periods=20).apply(lambda a:np.abs(a-a.mean()).mean(),raw=True).replace(0,np.nan);vals['CCI']=(tp-mean)/(.015*md)
   bear=pd.Series(np.nan,index=ix);bull=bear.copy()
   for j in range(14,len(g)):
    hh=g.close.iloc[j-14:j];jhi=hh.idxmax();jlo=hh.idxmin()
    if np.isfinite(k.iloc[j]) and np.isfinite(k.at[jhi]):bear.iloc[j]=float(g.close.iloc[j]>g.close.at[jhi] and k.iloc[j]<k.at[jhi])
    if np.isfinite(k.iloc[j]) and np.isfinite(k.at[jlo]):bull.iloc[j]=float(g.close.iloc[j]<g.close.at[jlo] and k.iloc[j]>k.at[jlo])
   vals['record_bear']=bear;vals['record_bull']=bull
  for key,v in vals.items():z.loc[ix,key]=v
 assert np.allclose(z.EK,.5*z.E+z.rangebias,equal_nan=True,atol=1e-12) if z.EK.notna().equals(z.E.notna()) else True
 return z

def synthetic():
 rows=[];daily=[]
 for name,c in {'flat':np.full(130,100.),'alternating':100+np.array([(-1.)**j for j in range(130)]),'smooth_up':100+np.arange(130),'gap_reversal':np.r_[np.full(90,100.),120.,np.arange(118.,79.,-2.)[:20],np.full(19,80.)]}.items():
  p=pd.DataFrame(dict(close=c,high=c+1,low=c-1,amount=np.full(len(c),1e8),segment_id=np.zeros(len(c)),source_kind='synthetic'),index=pd.date_range('2000-01-01',periods=len(c)))
  z=calc(p,True);good=z.EK.notna();assert np.allclose(z.loc[good,'EK'],.5*z.loc[good,'E']+z.loc[good,'rangebias'],atol=1e-12)
  pd.testing.assert_frame_equal(calc(p.iloc[:95],True),z.iloc[:95],check_exact=True)
  rows.append(dict(name=name,last=z.iloc[-1].to_dict(),mean_original_score=z.loc[good,'score'].mean(),mean_fused_score=z.loc[good,'scoreK'].mean(),mean_bias=z.loc[good,'rangebias'].mean()))
  zz=z.iloc[85:].copy();zz['name']=name;zz['close']=p.close;daily.append(zz)
 # Zero range is unknown; no synthetic certainty or arbitrary neutral replacement.
 p['close']=100.;p['high']=100.;p['low']=100.;zz=calc(p);assert zz.k.isna().all() and zz.scoreK.isna().all()
 save('SYNTHETIC_SUMMARY.json',rows);pd.concat(daily).to_csv(O/'SYNTHETIC_DAILY.csv')

def main():
 start=time.monotonic();freeze=sha(O/'FREEZE.json');source={str(p):sha(p) for p in [MP,F,O/'FREEZE.json',Path(__file__),B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet']}
 mp={x['symbol']:x for x in json.loads(MP.read_text())};q=pd.read_parquet(B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');q=q[q.account.eq('PVR')].reset_index(drop=True);assert len(q)==53121
 cases=json.loads((R/'lifecycle_ordered_damage_v1/FIXED_CASES_BEFORE_COMPUTE.json').read_text());keys={(x['sid'],x['day']) for x in cases}
 keys.update([('601607.SH','2022-03-24'),('300085.SZ','2024-09-24'),('002583.SZ','2024-09-24')]);keys.update((s,'2026-01-15') for s in ['300666.SZ','603061.SH','000681.SZ','603000.SH','002153.SZ','002716.SZ','002865.SZ'])
 synthetic();parts=[];fixed=[];audit=[];prefix=[]
 sids=sorted(set(q.sid)|{s for s,d in keys})
 for no,sid in enumerate(sids):
  m=mp[sid];path=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));h=sha(path);assert h==m['source_sha256'][path];source[path]=h
  p=pd.read_parquet(path).loc[:END];z=calc(p,extra=sid in {s for s,d in keys})
  g=q[q.sid.eq(sid)];a=z.reindex(pd.DatetimeIndex(g.day)).reset_index(drop=True);err=a.score.to_numpy()-g.original_PVR.to_numpy();finite=np.isfinite(err);mx=float(np.abs(err[finite]).max()) if finite.any() else 0.;assert mx<1e-10,(sid,mx)
  a['sid']=sid;a['day']=g.day.to_numpy();parts.append(a)
  audit.append(dict(sid=sid,rows=len(g),known=int(a.scoreK.notna().sum()),baseline_error=mx,original_unknown=int(g.original_PVR.isna().sum())))
  ck=sorted(d for s,d in keys if s==sid)
  if ck:
   facts=pd.read_parquet(m['refs']['facts']);cp=pd.read_parquet(m['refs']['CP1']);source[m['refs']['facts']]=sha(m['refs']['facts']);source[m['refs']['CP1']]=sha(m['refs']['CP1'])
   for day in ck:
    zz=calc(p.loc[:day],True);pd.testing.assert_frame_equal(zz,z.loc[:day],check_exact=True);prefix.append(dict(sid=sid,day=day,exact=True))
    row=z.loc[day].to_dict();row.update(sid=sid,day=day,raw_close=float(p.loc[day,'raw_close']),i_target=float(facts.loc[day,'i_target']),i_buy=bool(facts.loc[day,'i_buy']),cp_receipt=bool(cp.loc[day,'receipt']));fixed.append(row)
  if (no+1)%300==0:print('FEATURES',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
 c=q.merge(pd.concat(parts,ignore_index=True),on=['sid','day'],validate='one_to_one');c['known']=np.isfinite(c.scoreK)&np.isfinite(c.original_PVR)
 pd.DataFrame(fixed).to_csv(O/'FIXED_CASES.csv',index=False);pd.DataFrame(audit).to_csv(O/'BASELINE_AUDIT.csv',index=False);save('PREFIX_CHECKS.json',prefix)
 c.to_parquet(O/'CANDIDATE_FEATURES.parquet',index=False)
 picks=[];moves=[];counts=[]
 for day,g in c.groupby('day',sort=True):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));ks=base.head(K).groupby('sector').size().to_dict();bid=set(base.head(K).index);aid=set()
  for sector,gg in base.groupby('sector',sort=False):
   ids=list(gg.index);pos=[j for j,i in enumerate(ids) if c.at[i,'known']];knownids=[ids[j] for j in pos];new=sorted(knownids,key=lambda i:(-round(float(c.at[i,'scoreK']),12),float(c.at[i,'original_priority_rank']),c.at[i,'sid']));alt=ids.copy()
   for j,i in zip(pos,new):alt[j]=i
   assert all(ids[j]==alt[j] for j in range(len(ids)) if not c.at[ids[j],'known'])
   sk=ks.get(sector,0);aid.update(alt[:sk]);assert len(alt[:sk])==sk
   for method,chosen in [('PVR',ids[:sk]),('STOCH',alt[:sk])]:
    for rank,i in enumerate(chosen,1):picks.append(dict(row=i,day=day,sid=c.at[i,'sid'],sector=sector,year=int(c.at[i,'year']),epoch=c.at[i,'epoch'],method=method,sector_rank=rank,sectorK=sk))
  assert len(aid)==len(bid)==K
  for i in base.index:moves.append(dict(row=i,day=day,sid=c.at[i,'sid'],base_selected=i in bid,fused_selected=i in aid))
  counts.append(dict(day=day,year=int(g.year.iloc[0]),K=K,N=len(g),added=len(aid-bid),unknown=int((~g.known).sum())))
 sel=pd.DataFrame(picks);mv=pd.DataFrame(moves);cnt=pd.DataFrame(counts)
 old=pd.read_parquet(R/'selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/soft_cp1_quality_v1/candidate_test/SEALED_SELECTIONS_BEFORE_LABELS.parquet');old=old[old.account.eq('PVR')&old.strategy.eq('ORIGINAL_PVR')]
 assert set(zip(sel[sel.method.eq('PVR')].day,sel[sel.method.eq('PVR')].sid))==set(zip(old.day,old.sid))
 sel.to_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet',index=False);seal=sha(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet');save('RANK_SEAL.json',dict(hash=seal,freeze_hash=freeze,baseline_selections_exact=True,unknown_slots_preserved=True,same_sectorK=True,source_hashes=source))
 print('RANK_SEALED',len(c),len(sel),seal,'seconds',round(time.monotonic()-start,1),flush=True)
 # Only now load existing future labels, never available to calc/ranking.
 lp=B/'FIXED_NATIVE_PRICE_LABELS.parquet';source[str(lp)]=sha(lp);lab=pd.read_parquet(lp);s=sel.merge(lab,on=['sid','day'],validate='many_to_one');allc=c.merge(lab,on=['sid','day'],validate='many_to_one');pairs=[]
 for H in [5,20,60]:
  for day,g in s.groupby('day'):
   b=g[g.method.eq('PVR')];f=g[g.method.eq('STOCH')];assert len(b)==len(f)
   if b['complete'+str(H)].all() and f['complete'+str(H)].all():
    row=dict(day=day,year=int(b.year.iloc[0]),H=H,K=len(b))
    for col in ['ret','mae','mfe']:
     row['base_'+col]=b[col+str(H)].mean();row['fused_'+col]=f[col+str(H)].mean();row['delta_'+col]=row['fused_'+col]-row['base_'+col]
    row['base_positive40bp']=b['ret'+str(H)].gt(.004).mean();row['fused_positive40bp']=f['ret'+str(H)].gt(.004).mean();pairs.append(row)
 pair=pd.DataFrame(pairs);pair.to_csv(O/'PAIRED_DAILY.csv',index=False)
 agg=dict(days=('day','size'),events=('K','sum'),base_ret=('base_ret','mean'),fused_ret=('fused_ret','mean'),delta_ret=('delta_ret','mean'),delta_mae=('delta_mae','mean'),delta_mfe=('delta_mfe','mean'),base_positive40bp=('base_positive40bp','mean'),fused_positive40bp=('fused_positive40bp','mean'))
 annual=pair.groupby(['year','H']).agg(**agg).reset_index();annual.to_csv(O/'ANNUAL_PAIRED.csv',index=False)
 periods=[]
 for name,mask in [('ALL',pair.day.ne('')),('924',pair.day.between('2024-09-24','2024-10-31')),('2026Q1',pair.day.between('2026-01-01','2026-03-31'))]:
  t=pair[mask].groupby('H').agg(**agg).reset_index();t['period']=name;periods.append(t)
 pd.concat(periods).to_csv(O/'PERIOD_PAIRED.csv',index=False)
 # Unchanged existing opportunity roots and independent fixed60 labels.
 selected={m:set(zip(g.day,g.sid,g.epoch)) for m,g in sel.groupby('method')};roots=[]
 for (sid,ep),g in allc.groupby(['sid','epoch'],sort=True,dropna=False):
  g=g.sort_values('t');b=g.iloc[0];early=g[g.t.le(b.t+5)];row=dict(sid=sid,epoch=ep,birth_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc))
  for method,ss in selected.items():row[method]=any((r.day,sid,ep) in ss for r in early.itertuples())
  roots.append(row)
 rt=pd.DataFrame(roots);rt.to_csv(O/'ROOT_COVERAGE.csv',index=False);oldrt=pd.read_csv(B/'ROOT_EPISODE_COVERAGE.csv',keep_default_na=False);oldrt=oldrt[oldrt.account.eq('PVR')];rr=rt.merge(oldrt,on=['sid','epoch'],validate='one_to_one',suffixes=('','_old'));assert len(rr)==len(rt)==len(oldrt);assert rr.PVR.eq(rr.ORIGINAL_PVR_early_capture).all()
 rc=[]
 for y,g in rt.groupby('year'):
  bb=g[g.big60];rc.append(dict(year=int(y),roots=len(g),complete60=int(g.complete60.sum()),big=len(bb),base=int(bb.PVR.sum()),fused=int(bb.STOCH.sum()),lost=int((bb.PVR&~bb.STOCH).sum()),added=int((~bb.PVR&bb.STOCH).sum())))
 save('ROOT_SUMMARY.json',rc)
 # Contribution distribution, not PnL labels. High k does not imply economically superior quality.
 cs=c[c.known].copy();cs['score_change']=cs.scoreK-cs.original_PVR;cs['positive_discount']=cs.P-cs.PK;cs['negative_discount']=cs.N-cs.NK
 cs['identity_error']=cs.EK-(.5*cs.E+cs.rangebias);assert cs.identity_error.abs().max()<1e-12
 distribution=cs.groupby('year')[['k','E','EK','rangebias','P','N','PK','NK','positive_discount','negative_discount','score_change']].agg(['mean','median','min','max']);distribution.to_csv(O/'CONTRIBUTION_DISTRIBUTION.csv')
 save('DISTRIBUTION_SUMMARY.json',dict(known=len(cs),unknown=int((~c.known).sum()),positive_score_change=int(cs.score_change.gt(1e-12).sum()),negative_score_change=int(cs.score_change.lt(-1e-12).sum()),mean_score_change=cs.score_change.mean(),mean_range_bias=cs.rangebias.mean(),mean_positive_discount=cs.positive_discount.mean(),mean_negative_discount=cs.negative_discount.mean(),max_identity_error=cs.identity_error.abs().max()))
 mv.to_csv(O/'QUEUE_MOVES.csv',index=False);cnt.to_csv(O/'QUEUE_COUNTS.csv',index=False);cnt.groupby('year').agg(days=('day','size'),changed=('added',lambda x:int(x.gt(0).sum())),slots=('K','sum'),replaced=('added','sum'),unknown=('unknown','sum')).to_csv(O/'REPLACEMENTS.csv')
 c[['sid','day','original_PVR','scoreK','k']].merge(mv,on=['sid','day']).merge(pd.DataFrame(fixed)[['sid','day']],on=['sid','day']).to_csv(O/'FIXED_QUEUE_MOVES.csv',index=False)
 assert all(sha(k)==v for k,v in source.items());assert sha(O/'FREEZE.json')==freeze;assert sha(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet')==seal
 save('CHECKS.json',dict(baseline_score_maxerror=max(x['baseline_error'] for x in audit),baseline_selection_exact=True,prefix_checks=len(prefix),unknown_preserve=True,same_day_sectorK=True,source_hashes_unchanged=True,sources=source,candidates=len(c),stocks=len(sids),accounts=0,parameter_sweeps=0,seconds=time.monotonic()-start))
 print(annual.to_string(index=False),flush=True);print('ROOT_SUMMARY',json.dumps(rc),flush=True);print('COMPLETE',round(time.monotonic()-start,1),flush=True)
if __name__=='__main__':main()
