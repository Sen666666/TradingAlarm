"""Seal the single fixed queue before inspecting future or existing-round outcomes."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;B=O.parent/'selection_entry_diagnosis_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
sc=pd.read_parquet(O/'CANDIDATE_SCORES.parquet');sc['known']=sc.star_score.notna()&sc.original_PVR.notna()
sel=[];moves=[];counts=[]
for day,g in sc.groupby('day',sort=True):
 base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));ready=base.known
 ranked=base[ready].sort_values(['star_score','original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ranked.index)
 ix=[next(it) if ready.loc[i] else i for i in base.index];assert set(ix)==set(base.index)
 assert all(ix[k]==i for k,i in enumerate(base.index) if not ready.loc[i])
 alt=base.loc[ix];bp={i:k+1 for k,i in enumerate(base.index)};ap={i:k+1 for k,i in enumerate(ix)}
 for strategy,ii in [('PVR',list(base.index[:K])),('ATTR',ix[:K])]:sel.append(sc.loc[ii,['sid','day','year','sector','epoch','original_PVR','star_score','score_delta','known','common_t']].assign(strategy=strategy,selected_rank=range(1,K+1)))
 for i in base.index:moves.append(dict(sid=base.at[i,'sid'],day=day,sector=base.at[i,'sector'],old_rank=bp[i],new_rank=ap[i],rank_up=bp[i]-ap[i],known=bool(ready.loc[i]),score_delta=base.at[i,'score_delta']))
 counts.append(dict(day=day,year=int(day[:4]),N=len(g),K=K,known=int(ready.sum()),unknown=int((~ready).sum()),changed=len(set(ix[:K])-set(base.index[:K])),rank_changed=sum(bp[i]!=ap[i] for i in base.index),mean_abs_rank_change=np.mean([abs(bp[i]-ap[i]) for i in base.index])))
sel=pd.concat(sel,ignore_index=True);mv=pd.DataFrame(moves);qc=pd.DataFrame(counts)
sel.to_parquet(O/'SEALED_SELECTIONS.parquet',index=False);mv.to_csv(O/'RANK_MOVES.csv',index=False);qc.to_csv(O/'QUEUE_AUDIT.csv',index=False)
save('RANK_SEAL.json',dict(status='SEALED_BEFORE_THIS_SCRIPT_READS_OUTCOMES',selection_sha=sha(O/'SEALED_SELECTIONS.parquet'),scores_sha=sha(O/'CANDIDATE_SCORES.parquet'),formula_sha=sha(O/'PROTOCOL.json'),code_sha=sha(Path(__file__)),account_runs=0,parameter_searches=0,labels_used_for_order=[],tie='star_score descending then original priority then sid; unknown slot fixed'))
# Outcome reading starts after the sealed rank file.
lab=pd.read_parquet(B/'mobile_candidate_response_v1/FIXED_NATIVE_PRICE_LABELS.parquet')
sel=sel.merge(lab,on=['sid','day'],how='left',validate='many_to_one');allq=sc.merge(lab,on=['sid','day'],how='left',validate='one_to_one')
# Re-verify original block continuity for each complete selected horizon. Does not alter ranking.
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in json.loads(M.read_text())}
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);cal=cal[cal<='2026-05-15']
import sys
sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design');from features import original_observation_clock
continuity=[]
for sid,g in allq.groupby('sid'):
 m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));f=pd.read_parquet(p).loc[:'2026-05-15'];valid,block=original_observation_clock(f);vb=block.where(valid).reindex(cal);spos={str(d.date()):i for i,d in enumerate(cal)}
 for r in g.itertuples():
  t=spos[r.day];row=dict(sid=sid,day=r.day)
  for h in [5,20,60]:
   b=vb.iloc[t:t+h+1];row['continuous'+str(h)]=bool(len(b)==h+1 and b.notna().all() and b.nunique()==1)
  continuity.append(row)
cont=pd.DataFrame(continuity);cont.to_parquet(O/'LABEL_CONTINUITY.parquet',index=False)
allq=allq.merge(cont,on=['sid','day'],validate='one_to_one');sel=sel.merge(cont,on=['sid','day'],validate='many_to_one')
changes={}
for h in [5,20,60]:
 changes[h]=int((allq['complete'+str(h)]&~allq['continuous'+str(h)]).sum())
 # Preserve raw label fields, use strict source-consistent completion separately.
 allq['strict'+str(h)]=allq['complete'+str(h)]&allq['continuous'+str(h)]
 sel['strict'+str(h)]=sel['complete'+str(h)]&sel['continuous'+str(h)]
allq.to_parquet(O/'ALL_CANDIDATES_WITH_LABELS.parquet',index=False);sel.to_parquet(O/'SELECTIONS_WITH_LABELS.parquet',index=False)
def periods(g):
 yield 'ALL',g
 for y in [2022,2023,2024,2025,2026]:yield str(y),g[g.year.eq(y)]
 yield '2024_924',g[g.day.between('2024-09-24','2024-10-31')]
 yield '2026Q1',g[g.day.between('2026-01-01','2026-03-31')]
def met(g,h):
 r=g['ret'+str(h)];win=r>0;loss=r<0
 return dict(n=len(g),dates=g.day.nunique(),day_mean=r.groupby(g.day).mean().mean(),event_mean=r.mean(),price_winrate=win.mean(),avg_win=r[win].mean(),avg_loss=r[loss].mean(),mae=g['mae'+str(h)].mean(),mfe=g['mfe'+str(h)].mean(),q90=r.quantile(.9),net40bp=r.mean()-.004,net100bp=r.mean()-.01,winrate40bp=r.gt(.004).mean(),winrate100bp=r.gt(.01).mean())
res=[];blocks=[];daily=[];rng=np.random.default_rng(20261106)
for h in [5,20,60]:
 good=sel.groupby('day')['strict'+str(h)].all();p=sel[sel.day.isin(good[good].index)]
 d=p.groupby(['day','strategy'])['ret'+str(h)].mean().unstack('strategy');d['delta']=d.ATTR-d.PVR;d['year']=d.index.str[:4].astype(int);d=d.reset_index();d['H']=h;daily.append(d)
 for period,z in periods(p):
  for strategy,g in z.groupby('strategy'):res.append(dict(period=period,H=h,strategy=strategy,**met(g,h)))
 for period,z in periods(d):
  v=z.delta
  if len(z)==0:continue
  mm=z.assign(month=z.day.str[:7]).groupby('month').delta.agg(['sum','count']);dr=rng.integers(0,len(mm),(2000,len(mm)));boot=mm['sum'].to_numpy()[dr].sum(1)/mm['count'].to_numpy()[dr].sum(1)
  lo,hi=np.quantile(boot,[.025,.975]);bestmonth=z.assign(month=z.day.str[:7]).groupby('month').delta.mean().idxmax();exclude=z[~z.day.str.startswith(bestmonth)].delta.mean()
  blocks.append(dict(period=period,H=h,dates=len(z),delta=v.mean(),month_block_lo=lo,month_block_hi=hi,leave_best_date=v.drop(v.idxmax()).mean() if len(v)>1 else np.nan,leave_best_month=exclude,positive_dates=int(v.gt(0).sum()),negative_dates=int(v.lt(0).sum())))
pd.DataFrame(res).to_csv(O/'SAME_DATE_K_RESULTS.csv',index=False);pd.DataFrame(blocks).to_csv(O/'MONTH_BLOCK_DIAGNOSTIC.csv',index=False);pd.concat(daily).to_csv(O/'PAIRED_DAILY_RESULTS.csv',index=False)
members={m:set(zip(g.day,g.sid)) for m,g in sel.groupby('strategy')}
roots=[]
for (sid,epoch),g in allq.groupby(['sid','epoch']):
 g=g.sort_values('t');b=g.iloc[0];early=g[g.t<=b.t+5];rr=dict(sid=sid,epoch=epoch,first_day=b.day,year=b.year,sector=b.sector,complete60=b.strict60,big60=bool(b.big60_posthoc and b.strict60))
 for m,ss in members.items():rr[m]=any((r.day,sid) in ss for r in early.itertuples())
 roots.append(rr)
roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_COVERAGE.csv',index=False);rs=[]
for period,g in [('ALL',roots)]+[(str(y),roots[roots.year.eq(y)]) for y in [2022,2023,2024,2025,2026]]:
 b=g[g.big60];rs.append(dict(period=period,roots=len(g),complete60=int(g.complete60.sum()),big60=len(b),base=int(b.PVR.sum()),candidate=int(b.ATTR.sum()),retained=int((b.PVR&b.ATTR).sum()),lost=int((b.PVR&~b.ATTR).sum()),added=int((~b.PVR&b.ATTR).sum())))
pd.DataFrame(rs).to_csv(O/'ROOT_COVERAGE_SUMMARY.csv',index=False)
# All real baseline first rounds, original labels only, including cross-year exits.
first=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');first['row_id']=np.arange(len(first));first=first[first.account.eq('PVR')].copy()
fscore=pd.read_parquet(O/'SCORES.parquet')[['sid','day','score','star_score','score_delta','delta_E','delta','r','n','d','m','prev_m','k']]
f=first.merge(fscore,left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='many_to_one');f=f.merge(mv[['sid','day','old_rank','new_rank','rank_up']],on=['sid','day'],how='left',validate='many_to_one')
for m,ss in members.items():f[m+'_chosen']=[(r.signal_day,r.sid) in ss for r in f.itertuples()]
f.to_csv(O/'ACTUAL_ROUND_ASSOCIATION.csv',index=False);assoc=[]
def rm(z):
 c=z[z.closed];return dict(n=len(z),closed=len(c),wins=int(c.round_pnl.gt(0).sum()),net_winrate=c.round_pnl.gt(0).mean(),pnl=c.round_pnl.sum(),positive_pnl=c.loc[c.round_pnl.gt(0),'round_pnl'].sum(),mean_return=c.round_return_on_cumulative_cost.mean(),cross_year=int((c.closed_day.str[:4]!=c.entry_day.str[:4]).sum()))
for period,g in [('ALL',f)]+[(str(y),f[f.year.eq(y)]) for y in [2022,2023,2024,2025,2026]]:
 for group,z in [('all_original_firsts',g),('known',g[g.star_score.notna()]),('score_up',g[g.score_delta>0]),('score_down',g[g.score_delta<0]),('base_top20_mobile',g[g.PVR_chosen]),('retained_base_top20',g[g.PVR_chosen&g.ATTR_chosen]),('lost_base_top20',g[g.PVR_chosen&~g.ATTR_chosen])]:assoc.append(dict(period=period,group=group,**rm(z)))
pd.DataFrame(assoc).to_csv(O/'ROUND_ASSOCIATION_SUMMARY.csv',index=False)
# Reuse already fixed, close-H1/PVR matched winner/loser pairs. Never rematch on new score.
pairs=pd.read_csv('/Users/bytedance/Documents/Codex/2026-11-06/multiscale_entry_R_coverage_v1/MATCHED_PAIRS.csv');pairs=pairs[pairs.account.eq('PVR')&pairs.scope.eq('all_closed')].copy();lookup=f.set_index('row_id')
for col in ['score','star_score','score_delta']:
 pairs['winner_'+col]=pairs.winner_row.map(lookup[col]);pairs['loser_'+col]=pairs.loser_row.map(lookup[col]);pairs['difference_'+col]=pairs['winner_'+col]-pairs['loser_'+col]
pairs.to_csv(O/'EXISTING_MATCHED_PAIRS.csv',index=False);pairres=[]
for period,g in [('ALL',pairs)]+[(str(y),pairs[pairs.year.eq(y)]) for y in [2022,2023,2024,2025,2026]]:
 for col in ['score','star_score','score_delta']:
  z=g['difference_'+col].dropna();pairres.append(dict(period=period,metric=col,n=len(g),known=len(z),winner_higher=int(z.gt(0).sum()),loser_higher=int(z.lt(0).sum()),mean_difference=z.mean(),median_difference=z.median()))
pd.DataFrame(pairres).to_csv(O/'MATCHED_PAIR_SUMMARY.csv',index=False)
# Exact same-sector same-date candidate comparisons, all pairs, no new fitted rank.
peer=[]
for (day,sec),g in allq.groupby(['day','sector']):
 g=g[g.known].copy();n=len(g)
 if n<2:continue
 old=g.original_PVR.to_numpy();new=g.star_score.to_numpy();i,j=np.triu_indices(n,1);od=np.sign(old[i]-old[j]);nd=np.sign(new[i]-new[j]);row=dict(day=day,year=int(day[:4]),sector=sec,n=n,pairs=len(i),flips=int((od*nd<0).sum()))
 for h in [5,20,60]:
  ok=g['strict'+str(h)].to_numpy();rr=g['ret'+str(h)].to_numpy();v=ok[i]&ok[j];yd=np.sign(rr[i]-rr[j]);vv=v&(yd!=0)
  row.update({f'n{h}':int(vv.sum()),f'old_concord{h}':int(((od*yd>0)&vv).sum()),f'new_concord{h}':int(((nd*yd>0)&vv).sum()),f'flipped{h}':int(((od*nd<0)&vv).sum()),f'new_better_flips{h}':int(((od*nd<0)&(nd*yd>0)&vv).sum())})
 peer.append(row)
peer=pd.DataFrame(peer);peer.to_csv(O/'SAME_SECTOR_DATE_PAIR_COUNTS.csv',index=False)
pr=[]
for period,g in periods(peer):
 for h in [5,20,60]:
  n=g['n'+str(h)].sum();fl=g['flipped'+str(h)].sum();pr.append(dict(period=period,H=h,groups=len(g),pairs=int(g.pairs.sum()),flips=int(g.flips.sum()),complete_pairs=int(n),base_concordance=g['old_concord'+str(h)].sum()/n if n else np.nan,candidate_concordance=g['new_concord'+str(h)].sum()/n if n else np.nan,flips_complete=int(fl),candidate_wins_flips=int(g['new_better_flips'+str(h)].sum()),candidate_winrate_flips=g['new_better_flips'+str(h)].sum()/fl if fl else np.nan))
pd.DataFrame(pr).to_csv(O/'SAME_SECTOR_DATE_SUMMARY.csv',index=False)
# Unchanged, added, removed price paths and first-round association.
a=allq.merge(mv[['day','sid','old_rank','new_rank']],on=['day','sid'],validate='one_to_one');a['side']=np.where(a.old_rank.le(20)&a.new_rank.gt(20),'removed',np.where(a.old_rank.gt(20)&a.new_rank.le(20),'added','unchanged'));diff=a[a.side.ne('unchanged')];diff.to_csv(O/'ADDED_REMOVED.csv',index=False)
semi=set(sc.loc[sc.sid.isin(['300666.SZ','301611.SZ','688603.SH']),'sector']);a[a.day.between('2026-01-01','2026-03-31')&a.sector.isin(semi)].to_csv(O/'SEMICONDUCTOR_2026Q1_CANDIDATES.csv',index=False);a[a.day.between('2024-09-24','2024-10-31')].to_csv(O/'924_CANDIDATES.csv',index=False)
named=['600056.SH','002317.SZ','000620.SZ','002911.SZ','300085.SZ','002583.SZ','000506.SZ','300666.SZ','688603.SH','301611.SZ','002385.SZ','600606.SH','688582.SH','300182.SZ'];f[f.sid.isin(named)].to_csv(O/'NAMED_ACTUAL_FIRST_ROUNDS.csv',index=False)
summary=dict(status='SINGLE_FORMULA_DIAGNOSTIC_DONE_NOT_ACCOUNT',candidate_rows=len(sc),known=int(sc.known.sum()),unknown=int((~sc.known).sum()),dates=sc.day.nunique(),picks_per_arm=int(sel.strategy.eq('PVR').sum()),changed_picks=int(qc.changed.sum()),changed_dates=int(qc.changed.gt(0).sum()),changed_ranks=int(qc.rank_changed.sum()),max_abs_rank_move=int(mv.rank_up.abs().max()),source_path_continuity_corrections=changes,semiconductor_sector_ids=sorted(semi),original_rounds=len(f),original_closed=int(f.closed.sum()),original_winners=int((f.closed&f.round_pnl.gt(0)).sum()),account_runs=0,parameter_scans=0,fits=0)
save('EVALUATION_SUMMARY.json',summary);print(json.dumps(clean(summary),ensure_ascii=False,indent=2));print('RESULTS',pd.DataFrame(res).to_string(index=False));print('BLOCKS',pd.DataFrame(blocks).to_string(index=False));print('ROOTS',pd.DataFrame(rs).to_string(index=False));print('PEERS',pd.DataFrame(pr).to_string(index=False));print('PAIRS',pd.DataFrame(pairres).to_string(index=False))
