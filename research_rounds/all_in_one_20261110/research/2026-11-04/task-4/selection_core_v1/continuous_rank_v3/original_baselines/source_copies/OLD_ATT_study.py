from pathlib import Path
import json,time,sys,signal,hashlib,collections,traceback
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');R=ROOT/'research_rounds';P=ROOT/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared';START='2025-07-01';END='2026-06-30'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def attention(a,groups,ng):
 # Complete-window membership, fixed over both non-overlapping samples.
 valid=np.isfinite(a).all(axis=0)&(a>=0).all(axis=0);den=a[:,valid].sum(axis=1);rat=np.full(a.shape[1],np.nan);out=np.full(ng,np.nan);n=np.zeros(ng,int)
 if valid.any() and np.all(den>0):
  shares=a[:,valid]/den[:,None];prior=np.median(shares[:21],axis=0);recent=np.median(shares[21:],axis=0);good=prior>0;ids=np.flatnonzero(valid);rat[ids[good]]=recent[good]/prior[good]
  for g in range(ng):
   z=rat[groups==g];z=z[np.isfinite(z)];n[g]=len(z)
   if len(z):out[g]=np.median(z)
 return out,n,rat,int(valid.sum()),int((np.isfinite(a).sum(axis=0)>0).sum())
def price_mask(r):
 mean=np.mean(r,axis=-1,keepdims=True);return (r>0)&((r-mean)>0)
def synth():
 tests=[]
 def add(name,actual,expected):assert actual==expected,(name,actual,expected);tests.append(dict(name=name,actual=actual,expected=expected))
 g=np.array([0,0,1,1]);base=np.tile([10.,10,10,10],(26,1));down=base.copy();down[-5:,:2]*=3;v=attention(down,g,2)[0];add('down_volume_cannot_override_price',bool(price_mask(np.array([-.2,-.3]))[0] and v[0]>1),False)
 whole=base.copy();whole[-5:]*=3;add('market_wide_equal_volume_no_share_gain',bool(np.allclose(attention(whole,g,2)[0],1)),True)
 lead=np.tile([10.,10,10,10,10,10],(26,1));lead[-5:,0]*=4;v=attention(lead,np.array([0,0,0,1,1,1]),2)[0];add('single_leader_can_fail_median_attention',bool(v[0]<=1),True)
 add('two_sectors_parallel',int(price_mask(np.array([.2,.15,-.1,-.2])).sum()),2)
 missing=base.copy();missing[-5:,2:]=np.nan;v=attention(missing,g,2)[0];add('missing_denominator_no_false_attention',bool(np.isclose(v[0],1) and np.isnan(v[1])),True)
 future=np.vstack([base,np.ones((5,4))*999]);add('feature_prefix_unchanged',bool(np.allclose(attention(future[:26],g,2)[0],attention(base,g,2)[0],equal_nan=True)),True)
 save(O/'SYNTHETIC.json',dict(passed=True,tests=tests,no_ledger_or_orders=True))
def fwd(c,seg,ix,h):
 base=c[ix];mx=np.full(base.shape,-np.inf);count=np.zeros(base.shape,np.int16);same=np.isfinite(base)&(base>0)
 for k in range(1,h+1):
  q=c[ix+k];ok=np.isfinite(q)&(q>0)&(seg[ix+k]==seg[ix]);count+=ok;mx=np.maximum(mx,np.where(ok,q/base-1,-np.inf))
 valid=same&(count==h);end=np.where(valid,c[ix+h]/base-1,np.nan);mfe=np.where(valid,mx,np.nan);return end,mfe,valid
def stats(y,mask):
 v=y[mask&np.isfinite(y)];return dict(n=len(v),mean=float(v.mean()) if len(v) else None,median=float(np.median(v)) if len(v) else None,positive_fraction=float((v>0).mean()) if len(v) else None)
def main():
 global RUN_START
 start=RUN_START=time.monotonic();prior=read(O/'FAILED_ATTEMPT_TIMING.json')['wall_seconds'] if (O/'FAILED_ATTEMPT_TIMING.json').exists() else 0;signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('120s measurement budget incl failed attempt')));signal.setitimer(signal.ITIMER_REAL,120-prior);synth()
 z=np.load(P/'h1.npz');dates=pd.DatetimeIndex(z['dates']);symbols=[str(s) for s in z['symbols']];stock=np.array([not s.startswith('URFI') for s in symbols]);sc=np.flatnonzero(stock);gc=np.flatnonzero(~stock);sids=[symbols[j] for j in sc];gids=[symbols[j] for j in gc];assert len(sids)==1709 and len(gids)==90;meta=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json');groups=np.array([gids.index(meta[s]['sector_id']) for s in sids]);counts=np.bincount(groups,minlength=90)
 ix=np.flatnonzero((dates>=START)&(dates<=END));T=len(ix);b=np.load(R/'selection-rotation-abcd-20261025/prepared/dual-board.npz');bd=pd.DatetimeIndex(b['dates']);bi=bd.get_indexer(dates[ix]);bc={str(s):j for j,s in enumerate(b['symbols'])};gcol=[bc[s] for s in gids];r21=b['r21'][bi][:,gcol];r5=b['r5'][bi][:,gcol];r63=b['r63'][bi][:,gcol];B21=b['breadth21'][bi][:,gcol];B63=b['breadth63'][bi][:,gcol];N21=b['n21'][bi][:,gcol];N63=b['n63'][bi][:,gcol];h1=z['score'][ix][:,gc]
 absok=r21>0;benchmark=r21.mean(axis=1);rel=r21-benchmark[:,None];qual=absok&(rel>0);rank=pd.DataFrame(r21).rank(axis=1,ascending=False,method='first').to_numpy();price=z['close'];segment=z['segment'];warmix=np.arange(ix[0]-25,ix[-1]+1);wd=dates[warmix];amount=np.full((len(warmix),1709),np.nan);first=[];last=[];quality=[];records={r['series_id']:r for r in read(P/'manifest.json')['series']};io=time.monotonic()
 for j,sid in enumerate(sids):
  f=pd.read_parquet(records[sid]['raw']['path']);f=f.set_index('trade_date');f.index=pd.to_datetime(f.index);first.append(f.index.min());last.append(f.index.max());q=f.reindex(wd);units=set(f.amount_unit.dropna());assert units=={'CNY'},(sid,units)
  good=q.observed_bar.fillna(False).astype(bool)&q.price_eligible.fillna(False).astype(bool)&~q.synthetic_event_bar.fillna(True).astype(bool)&np.isfinite(q.amount)&q.amount.ge(0);amount[good,j]=q.loc[good,'amount'];quality.append(int(q.observed_bar.eq(True).sum()))
  if j==63:
   elapsed=time.monotonic()-io;estimate=elapsed/64*1709;save(O/'THROUGHPUT.json',dict(first64_seconds=elapsed,estimated_all_amount_read_seconds=estimate,budget=120));print('IO64',elapsed,'estimated1709',estimate,flush=True)
  if (j+1)%400==0:print('IO',j+1,round(time.monotonic()-start,2),flush=True)
 np.savez_compressed(O/'AMOUNT_INPUT.npz',dates=wd.to_numpy(),symbols=np.array(sids),amount=amount)
 ratios=np.full((T,90),np.nan);att_n=np.zeros((T,90),int);rawshare=np.full((T,90),np.nan);top3=np.full((T,90),np.nan);leader3=np.full((T,90),np.nan);complete_n=[];denomdrift=[];raw_n=[];stockR21=np.where(segment[ix][:,sc]==segment[ix-21][:,sc],price[ix][:,sc]/price[ix-21][:,sc]-1,np.nan)
 for t in range(T):
  a=amount[t:t+26];ratios[t],att_n[t],_,n,_=attention(a,groups,90);complete_n.append(n);valid=np.isfinite(a);denomdrift.append(int(np.any(valid!=valid[-1],axis=0).sum()));raw_n.append(int(valid[-1].sum()));current=a[-1];den=np.nansum(current)
  for g in range(90):
   q=current[groups==g];q=q[np.isfinite(q)];total=q.sum();rawshare[t,g]=total/den if den>0 and len(q) else np.nan;top3[t,g]=np.sort(q)[-3:].sum()/total if total>0 else np.nan;p=stockR21[t,groups==g];p=p[np.isfinite(p)&(p>0)];leader3[t,g]=np.sort(p)[-3:].sum()/p.sum() if len(p) else np.nan
 known=np.isfinite(ratios);attentionok=known&(ratios>1);both=qual&attentionok;rejected=qual&known&~attentionok;unknown=qual&~known
 # Prefix check on actual amount windows: feature function cannot see labels.
 for t in [0,T//2,T-1]:
  a=amount[:t+26];aa=attention(a[-26:],groups,90)[0];assert np.allclose(aa,ratios[t],equal_nan=True)
 quarters=[str(pd.Period(d,'Q')) for d in dates[ix]];frames=[]
 for t,day in enumerate(dates[ix]):frames.append(pd.DataFrame(dict(day=str(day.date()),quarter=quarters[t],sector=gids,member_count=counts,R5=r5[t],R21=r21[t],R63=r63[t],equal90_R21=benchmark[t],relative_R21=rel[t],absolute_positive=absok[t],relative_positive=rel[t]>0,price_qualified=qual[t],R21_rank=rank[t],H1_original=h1[t],attention_ratio=ratios[t],attention_members=att_n[t],attention_accept=attentionok[t],attention_known=known[t],price_and_attention=both[t],B21=B21[t],B63=B63[t],B21_members=N21[t],B63_members=N63[t],snapshot_amount_share=rawshare[t],amount_top3=top3[t],positive_R21_top3=leader3[t],denominator_complete_window_members=complete_n[t],denominator_members_changed=denomdrift[t],raw_amount_members=raw_n[t])))
 matrix=pd.concat(frames,ignore_index=True);matrix.to_parquet(O/'FEATURE_MATRIX_90.parquet',index=False);save(O/'FEATURE_FREEZE.json',dict(before_future_labels=True,sha256=sha(O/'FEATURE_MATRIX_90.parquet'),days=T,industry_rows=len(matrix),scope=[START,END],labels_not_used_in_features=True,attention_condition='industry median complete-window share ratio >1',index_amount_unit_unverified=True,amount_universe='fixed1709 snapshot; same26-window intersection denominator',sources={str(P/'h1.npz'):sha(P/'h1.npz'),str(R/'selection-rotation-abcd-20261025/prepared/dual-board.npz'):sha(R/'selection-rotation-abcd-20261025/prepared/dual-board.npz')}));print('FEATURES_FROZEN',round(time.monotonic()-start,2),flush=True)
 e21,m21,v21=fwd(price[:,gc],segment[:,gc],ix,21);e63,m63,v63=fwd(price[:,gc],segment[:,gc],ix,63);matrix['future21_return']=e21.ravel();matrix['future63_return']=e63.ravel();matrix['future63_closeMFE']=m63.ravel();matrix['future63_complete']=v63.ravel();matrix.to_parquet(O/'MATRIX_WITH_LABELS.parquet',index=False)
 se63,sm63,sv=fwd(price[:,sc],segment[:,sc],ix,63);se21,sm21,sv21=fwd(price[:,sc],segment[:,sc],ix,21);tail=sv&(sm63>=.3);Pstock=qual[:,groups];PAstock=both[:,groups];sectorsample=[];opportunities=[]
 # Left-boundary diagnostic: previous63 anchors (same future label), never
 # used in contemporaneous features or acceptance decisions.
 priorix=np.arange(ix[0]-63,ix[0]);_,pm,pv=fwd(price[:,sc],segment[:,sc],priorix,63);prior_last=np.max(np.where(pv&(pm>=.3),priorix[:,None],-100000),axis=0)
 np.savez_compressed(O/'STOCK_PRICE_LABELS.npz',dates=dates[ix].to_numpy(),symbols=np.array(sids),sector=np.array([gids[g] for g in groups]),MFE63=sm63,end63=se63,complete63=sv,MFE21=sm21,end21=se21,price_selected=Pstock,attention_selected=PAstock,main_tail=tail,prior_last_qualifying_anchor_index=prior_last)
 for j,sid in enumerate(sids):
  ts=np.flatnonzero(tail[:,j]);runs=[]
  for t in ts:
   if runs and ix[t]-ix[runs[-1][-1]]<=63 and segment[ix[t],sc[j]]==segment[ix[runs[-1][-1]],sc[j]]:runs[-1].append(int(t))
   else:runs.append([int(t)])
  for n,run in enumerate(runs):
   pp=[t for t in run if Pstock[t,j]];aa=[t for t in run if PAstock[t,j]];firstt=run[0];opportunities.append(dict(id=f'{sid}:{n}',stock=sid,sector=gids[groups[j]],quarter=quarters[firstt],first_anchor=str(dates[ix[firstt]].date()),last_anchor=str(dates[ix[run[-1]]].date()),qualifying_anchors=len(run),bridged_nonqualifying_days=run[-1]-run[0]+1-len(run),left_boundary_censored=bool(n==0 and ix[firstt]-prior_last[j]<=63),price_first_anchor=bool(Pstock[firstt,j]),attention_first_anchor=bool(PAstock[firstt,j]),price_any_qualified_anchor=bool(pp),attention_any_qualified_anchor=bool(aa),price_delay_observations=pp[0]-firstt if pp else None,attention_delay_observations=aa[0]-firstt if aa else None,price_first_date=str(dates[ix[pp[0]]].date()) if pp else None,attention_first_date=str(dates[ix[aa[0]]].date()) if aa else None))
 opp=pd.DataFrame(opportunities);opp.to_csv(O/'OPPORTUNITIES.csv',index=False);allstats=[];stocksummary=[];movement=[]
 for period in ['ALL']+list(dict.fromkeys(quarters)):
  tm=np.ones(T,bool) if period=='ALL' else np.array(quarters)==period;ss=opp if period=='ALL' else opp[opp.quarter.eq(period)];valid_now=np.isfinite(price[ix][:,sc])&(price[ix][:,sc]>0);den=int(valid_now[tm].sum());pa=int((Pstock[tm]&valid_now[tm]).sum());paa=int((PAstock[tm]&valid_now[tm]).sum());s=dict(period=period,days=int(tm.sum()),stock_day_universe=den,price_stock_days=pa,attention_stock_days=paa,price_retention=pa/den,attention_retention=paa/den,attention_incremental_retention=paa/pa if pa else None,tail_label_stock_days=int(tail[tm].sum()),future63_unknown_stock_days=int((valid_now[tm]&~sv[tm]).sum()),unique_tail_stocks=int(np.any(tail[tm],axis=0).sum()),unique_price_covered_stocks=int(np.any(tail[tm]&Pstock[tm],axis=0).sum()),unique_attention_covered_stocks=int(np.any(tail[tm]&PAstock[tm],axis=0).sum()),opportunity_segments=len(ss),left_boundary_segments=int(ss.left_boundary_censored.sum()),price_first=int(ss.price_first_anchor.sum()),attention_first=int(ss.attention_first_anchor.sum()),price_any=int(ss.price_any_qualified_anchor.sum()),attention_any=int(ss.attention_any_qualified_anchor.sum()),price_delay_median=float(ss.price_delay_observations.median()) if ss.price_delay_observations.notna().any() else None,attention_delay_median=float(ss.attention_delay_observations.median()) if ss.attention_delay_observations.notna().any() else None,price_parallel_mean=float(qual[tm].sum(axis=1).mean()),price_parallel_min=int(qual[tm].sum(axis=1).min()),price_parallel_max=int(qual[tm].sum(axis=1).max()),price_empty_days=int((qual[tm].sum(axis=1)==0).sum()),attention_empty_days=int((both[tm].sum(axis=1)==0).sum()),attention_unknown_industry_days=int(unknown[tm].sum()))
  stocksummary.append(s)
  for name,mask in [('price_yes',qual),('price_no',~qual),('price_attention_yes',both),('price_attention_no',rejected),('price_attention_unknown',unknown)]:
   mm=mask&tm[:,None];r=dict(period=period,group=name,industry_days=int(mm.sum()))
   for label,y in [('f21',e21),('f63',e63),('MFE63',m63)]:
    r.update({label+'_'+k:v for k,v in stats(y,mm).items()})
   allstats.append(r)
  # Observable price-state transitions only; no future low or I entry.
  active=qual[tm];att=both[tm];movement.append(dict(period=period,price_entries=int((active[1:]&~active[:-1]).sum()),price_exits=int((~active[1:]&active[:-1]).sum()),attention_entries=int((att[1:]&~att[:-1]).sum()),attention_exits=int((~att[1:]&att[:-1]).sum())))
 pd.DataFrame(stocksummary).to_csv(O/'COVERAGE.csv',index=False);pd.DataFrame(allstats).to_csv(O/'FUTURE_PRICE_GROUPS.csv',index=False);pd.DataFrame(movement).to_csv(O/'STATE_CHANGES.csv',index=False)
 # Price baseline onset versus absolute21 onset; A delay within each P run.
 delays=[]
 for g in range(90):
  on=False;startp=None
  for t in range(T):
   if qual[t,g] and not on:startp=t;on=True
   if on and (not qual[t,g] or t==T-1):
    end=t if qual[t,g] else t-1;accepted=np.flatnonzero(both[startp:end+1,g]);delays.append(dict(sector=gids[g],first=str(dates[ix[startp]].date()),last=str(dates[ix[end]].date()),left_censored=startp==0,attention_delay=int(accepted[0]) if len(accepted) else None,never_attention=not len(accepted)));on=False
 pd.DataFrame(delays).to_csv(O/'PRICE_STATE_SEGMENTS.csv',index=False)
 dataquality=dict(cohort=1709,industries=90,amount_units='CNY',index_amount_unit='source_index_amount_units_unverified',raw_member_count_range=[min(raw_n),max(raw_n)],complete26_member_count_range=[min(complete_n),max(complete_n)],denominator_drift_stock_counts_range=[min(denomdrift),max(denomdrift)],pre_first_observation_cells=int(sum((wd<f).sum() for f in first)),after_last_observation_cells=int(sum((wd>f).sum() for f in last)),inside_history_missing_amount_cells=int(sum((~np.isfinite(amount[:,j])&(wd>=first[j])&(wd<=last[j])).sum() for j in range(1709))),actual_suspension_flag_available=False,current_member_and_cap_snapshot_bias=True,full_native_I_coverage_not_tested=True,future63_last_date=str(dates[ix[-1]+63].date()),industry_future63_unknown=int((~v63).sum()),stock_future63_unknown=int((~sv).sum()),all_statistics_descriptive_no_independence_claim=True)
 save(O/'DATA_QUALITY.json',dataquality);save(O/'SUMMARY.json',dict(coverage=stocksummary,elapsed_seconds=time.monotonic()-start,new_economic_paths=0,features_sha_unchanged=sha(O/'FEATURE_MATRIX_90.parquet')==read(O/'FEATURE_FREEZE.json')['sha256'],opportunity_main_label='future63 maximum close >=30%; opportunity segment one vote; price proxy',quarters=list(dict.fromkeys(quarters))));print('COMPLETE',round(time.monotonic()-start,3),'opps',len(opp),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  if 'RUN_START' in globals():save(O/'ATTEMPT_TIMING.json',dict(seconds=time.monotonic()-RUN_START))
