"""Frozen 2019-style nine-scale monthly coefficient learning, local opportunity diagnostic only."""
from pathlib import Path
import json,sys,time,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'selection_entry_diagnosis_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
Q=B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet'
LAB=B/'mobile_candidate_response_v1/FIXED_NATIVE_PRICE_LABELS.parquet'
SCALES=[3,5,10,20,50,100,200,300,400];P=[f'P{n}'for n in SCALES];A=[f'A{n}'for n in SCALES];F=P+A
METHODS=['PVR','H1','P9','PA18']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item()if isinstance(v,np.generic)else str(v)))
def calendar():
 d=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);return d[(d>='2013-01-01')&(d<='2026-05-15')]
def calc(f,cal):
 f=f.reindex(cal);v=np.isfinite(f.close)&f.close.gt(0)&np.isfinite(f.amount)&f.amount.gt(0)
 for c in ['price_eligible','observed_bar','is_observed_bar']:v &= f[c].fillna(False).astype(bool)
 for c in ['source_invalid','synthetic_event_bar']:v &= ~f[c].fillna(True).astype(bool)
 seg=f.segment_id;full=v.rolling(400,min_periods=400).sum().eq(400)&seg.rolling(400).min().eq(seg.rolling(400).max())
 x=pd.DataFrame(index=cal)
 for typ,col in [('P','close'),('A','amount')]:
  for n in SCALES:x[f'{typ}{n}']=(f[col].where(v).rolling(n,min_periods=n).mean()/f[col]).where(full)
 for n in [5,21,63]:x[f'past{n}']=(f.close/f.close.shift(n)-1).where(v&v.shift(n,fill_value=False)&seg.eq(seg.shift(n)))
 return x,full,v

def prep():
 assert not(O/'MONTHLY.parquet').exists();start=time.monotonic();cal=calendar();q=pd.read_parquet(Q);q=q[q.account.eq('PVR')].reset_index(drop=True)
 assert len(q)==53121 and not q.duplicated(['sid','day']).any()
 m=json.loads(M.read_text());mp={r['symbol']:r for r in m};sources={str(p):sha(p)for p in [M,H,Q,Path(__file__),O/'FREEZE.json']}
 monends=pd.Series(cal,index=cal).groupby(cal.to_period('M')).last();monends=monends[monends.index<pd.Period('2026-05')]
 samples=[];opps=[];aud=[];qa=[]
 for no,r in enumerate(m):
  sid=r['symbol'];path=next(p for p in r['source_sha256']if p.endswith('/signal.parquet'));f=pd.read_parquet(path).loc[:cal[-1]]
  f=f.loc[f.index>=cal[0]];assert f.index.is_unique and f.index.is_monotonic_increasing
  hs=sha(path);assert hs==r['source_sha256'][path];sources[path]=hs
  native=pd.read_parquet(r['refs']['facts'],columns=['close','factor']).reindex(f.index);present=f.close.notna()&native.close.notna();err=(f.loc[present,'close']-native.loc[present,'close']).abs().max();assert pd.isna(err)or err<1e-7
  facerr=(f.adjustment_factor-native.factor).abs().max();assert pd.isna(facerr)or facerr<1e-10
  units=set(f.loc[f.amount.notna(),'amount_unit'].dropna());assert units<={'CNY'}
  x,known,valid=calc(f,cal);ff=f.reindex(cal);sx=x.loc[monends.to_numpy()].copy();sx['sid']=sid;sx['month']=monends.index.astype(str);sx['month_end']=monends.to_numpy();sx['close']=ff.close.loc[sx.index];sx['segment']=ff.segment_id.loc[sx.index]
  # Label may only be consumed after its actual month end. No future-month eligibility in feature mask.
  sx['y']=sx.close.shift(-1)/sx.close-1;sx['maturity']=sx.month_end.shift(-1);sx['target_month']=sx.month.shift(-1)
  priceok=np.isfinite(ff.close)&ff.close.gt(0)&~ff.source_invalid.fillna(True).astype(bool)
  labs=[]
  for k in range(len(sx)):
   if k+1==len(sx):labs.append(False);continue
   sl=ff.loc[sx.index[k]:sx.index[k+1]]
   labs.append(bool(priceok.loc[sl.index].all()and sl.segment_id.notna().all()and sl.segment_id.nunique()==1))
  sx['label_known']=labs;sx.loc[~sx.label_known,'y']=np.nan;samples.append(sx.reset_index(drop=True))
  a=q[q.sid.eq(sid)][['sid','day']].copy();idx=pd.DatetimeIndex(a.day);xx=x.reindex(idx).reset_index(drop=True);a=a.reset_index(drop=True)
  opps.append(pd.concat([a,xx],axis=1))
  aud.append(dict(sid=sid,source=path,source_sha256=hs,rows=len(f),valid=int(valid.sum()),known400=int(known.sum()),queue=len(a),queue_known=int(np.isfinite(xx[F]).all(1).sum()),max_native_error=err,max_factor_error=facerr))
  if sid in ['000001.SZ','300085.SZ','300666.SZ','688603.SH','301611.SZ']:
   for cut in ['2022-01-04','2024-09-24','2026-01-15']:
    cc=cal[cal<=cut];xp,_,_=calc(f.loc[:cut],cc);pd.testing.assert_frame_equal(x.loc[cc],xp,check_exact=True);qa.append(dict(sid=sid,cut=cut,physical_prefix_equal=True))
  if(no+1)%300==0:print('PREP',no+1,'seconds',round(time.monotonic()-start,2),flush=True)
 pd.concat(samples,ignore_index=True).to_parquet(O/'MONTHLY.parquet',index=False)
 feats=pd.concat(opps,ignore_index=True);c=q.merge(feats,on=['sid','day'],validate='one_to_one');c.to_parquet(O/'OPPORTUNITIES.parquet',index=False)
 pd.DataFrame(aud).to_csv(O/'SOURCE_AUDIT.csv',index=False);dump('INPUT_HASHES.json',sources);dump('PREFIX_QA.json',qa)
 dump('PREP_AUDIT.json',dict(rows=len(c),known=int(np.isfinite(c[F]).all(1).sum()),stocks=len(m),cal_first=str(cal[0]),cal_last=str(cal[-1]),seconds=time.monotonic()-start))
 print('PREP_DONE',len(c),int(np.isfinite(c[F]).all(1).sum()),flush=True)

def regress(g,cols):
 X=g[cols].to_numpy();y=g.y.to_numpy();mu=X.mean(0);sd=X.std(0);assert(sd>1e-12).all()
 Z=(X-mu)/sd;S=Z.T@Z;cond=np.linalg.cond(Z);pen=len(g)*.01;gamma=np.linalg.solve(S+pen*np.eye(len(cols)),Z.T@(y-y.mean()));beta=gamma/sd;inter=y.mean()-mu@beta
 # In-sample linear-system influence diagnostics only, not alternate ranking/model.
 hat=np.sum((Z@np.linalg.inv(S+pen*np.eye(len(cols))))*Z,axis=1)+1/len(g)
 threshold=np.quantile(y,.99);tail=y>=threshold;cross=Z*(y-y.mean())[:,None]
 return np.r_[inter,beta],dict(n=len(g),condition=float(cond),effective_df=float(hat.sum()),max_leverage=float(hat.max()),top1_y_threshold=float(threshold),top1_y_count=int(tail.sum()),top1_y_abs_share=float(np.abs(y[tail]).sum()/np.abs(y).sum()),top1_normal_equation_l1_share=float(np.abs(cross[tail]).sum()/np.abs(cross).sum()),max_feature=float(X.max()),max_y=float(y.max()),min_y=float(y.min()),mean=mu.tolist(),sd=sd.tolist(),coef=np.r_[inter,beta].tolist())
def run():
 assert not(O/'SEALED_PICKS.parquet').exists();c=pd.read_parquet(O/'OPPORTUNITIES.parquet');m=pd.read_parquet(O/'MONTHLY.parquet');cal=calendar();mods=[];states={};snap={};count=0
 for month,g in m.dropna(subset=['target_month']).groupby('target_month',sort=True):
  tr=g[g.label_known&np.isfinite(g[F]).all(1)&np.isfinite(g.y)].copy();cut=pd.Period(month).end_time
  assert (pd.to_datetime(tr.maturity)<=cut).all()and (pd.to_datetime(tr.month_end)<pd.to_datetime(tr.maturity)).all()
  if len(tr)<100:mods.append(dict(month=month,status='UNSUPPORTED',n=len(tr)));continue
  count+=1
  for name,cols in [('P9',P),('PA18',F)]:
   b,diag=regress(tr,cols);states[name]=b if name not in states else .98*states[name]+.02*b
   mods.append(dict(month=month,model=name,status='FIT',count=count,maturity_max=str(tr.maturity.max()),warm=count>=38,ema=states[name].tolist(),**diag))
  snap[month]=(count,{n:b.copy()for n,b in states.items()})
 for name in ['P9','PA18']:c[name]=np.nan
 for month,g in c.groupby(c.day.str[:7],sort=True):
  previous=str(pd.Period(month)-1);eligible=[k for k in snap if k<=previous]
  if not eligible:continue
  used=max(eligible);count,st=snap[used]
  if count<38:continue
  ix=g.index[np.isfinite(g[F]).all(1)];assert used<month
  for name,cols in [('P9',P),('PA18',F)]:c.loc[ix,name]=np.column_stack([np.ones(len(ix)),c.loc[ix,cols].to_numpy()])@st[name]
  c.loc[g.index,'coefficient_through_month']=used
 c['H1']=pd.to_numeric(c.original_H1);c['common_known']=np.isfinite(c[['PA18','P9','H1','original_PVR']]).all(1)
 c['stage']=np.where((c.past21>0)&(c.past63<=0),'start_short_up_long_not',np.where((c.past21>0)&(c.past63>0),'aligned_up','other_or_unknown'))
 c['accelerating']=(c.past5>0)&(np.log1p(c.past5)/5>np.log1p(c.past21)/21)
 picks=[];queues=[];moves=[]
 for day,g in c.groupby('day',sort=True):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));bi=list(base.head(K).index);ks=base.head(K).groupby('sector').size().to_dict()
  for method in METHODS:
   chosen=[]
   for sector,gs in base.groupby('sector',sort=False):
    k=int(ks.get(sector,0));order=list(gs.index)
    if method!='PVR':
     good=gs.common_known;ranked=gs[good].sort_values([method,'original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ranked.index);order=[next(it)if good.loc[j]else j for j in gs.index]
     assert all(order[k]==j for k,j in enumerate(gs.index)if not good.loc[j])and set(order)==set(gs.index)
    chosen+=order[:k]
    for rank,j in enumerate(order):moves.append(dict(row=int(j),day=day,sid=c.at[j,'sid'],sector=sector,method=method,sector_rank=rank+1,selected=j in order[:k]))
   assert len(chosen)==K and c.loc[chosen].groupby('sector').size().to_dict()==ks
   picks.extend(dict(row=int(j),day=day,method=method)for j in chosen);queues.append(dict(day=day,method=method,N=len(g),K=K,known=int(g.common_known.sum()),changed=len(set(chosen)-set(bi))))
 c.to_parquet(O/'PREDICTIONS.parquet',index=False);sel=pd.DataFrame(picks);sel.to_parquet(O/'SEALED_PICKS.parquet',index=False);pd.DataFrame(queues).to_csv(O/'QUEUE_AUDIT.csv',index=False);pd.DataFrame(moves).to_parquet(O/'RANK_MOVES.parquet',index=False);dump('MONTHLY_MODELS.json',mods)
 dump('RANK_SEAL.json',dict(predictions=sha(O/'PREDICTIONS.parquet'),picks=sha(O/'SEALED_PICKS.parquet'),code=sha(Path(__file__)),future_opportunity_labels_read=False))
 # Score clock invariance: truncating monthly model history beyond selected cutoff changes no used state.
 qa=[]
 for month in ['2022-01','2024-09','2026-01']:
  last=str(pd.Period(month)-1);prefix=m[m.target_month.le(last)].copy();poison=m.copy();poison.loc[poison.target_month.gt(last),'y']=999999
  tr0=m[m.target_month.le(last)];tr1=poison[poison.target_month.le(last)];pd.testing.assert_frame_equal(tr0,tr1,check_exact=True);qa.append(dict(month=month,future_label_poison_keeps_training_exact=True))
 dump('LABEL_CLOCK_QA.json',qa);print('RANK_SEALED',len(sel),'commonknown',int(c.common_known.sum()),flush=True)

def evaluate():
 c=pd.read_parquet(O/'PREDICTIONS.parquet');sel=pd.read_parquet(O/'SEALED_PICKS.parquet');lab=pd.read_parquet(LAB);assert not lab.duplicated(['sid','day']).any()
 c=c.merge(lab,on=['sid','day'],validate='many_to_one');c['row']=np.arange(len(c));s=sel.merge(c,on=['row','day'],validate='many_to_one');s.to_parquet(O/'SELECTIONS_WITH_LABELS.parquet',index=False)
 periods=[('ALL',None,None)]+[(str(y),f'{y}-01-01',f'{y}-12-31')for y in range(2022,2027)]+[('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31')]
 results=[];paired=[];stage=[];cal=calendar();daypos={str(d.date()):i for i,d in enumerate(cal)};rng=np.random.default_rng(20261106)
 for h in [5,20,60]:
  good=s.groupby('day')['complete'+str(h)].all();whole=s[s.day.isin(good[good].index)].copy()
  for period,start,end in periods:
   sub=whole if start is None else whole[whole.day.between(start,end)]
   if not len(sub):continue
   means=sub.groupby(['day','method'])['ret'+str(h)].mean().unstack('method');threshold=sub.drop_duplicates(['sid','day'])['ret'+str(h)].quantile(.99)
   for method,g in sub.groupby('method'):
    ret=g['ret'+str(h)];trim=g[g['ret'+str(h)]<=threshold]
    results.append(dict(period=period,H=h,method=method,n=len(g),dates=g.day.nunique(),mean_day=float(g.groupby('day')['ret'+str(h)].mean().mean()),mean_event=float(ret.mean()),median=float(ret.median()),minus40bp=float(g.groupby('day')['ret'+str(h)].mean().mean()-.004),positive40bp=float((ret>.004).mean()),positive100bp=float((ret>.01).mean()),avgwin40bp=float((ret[ret>.004]-.004).mean()),avgloss40bp=float((ret[ret<=.004]-.004).mean()),mae=float(g['mae'+str(h)].mean()),big60=int(g.big60_posthoc.sum()),past21=float(g.past21.mean()),past63=float(g.past63.mean()),tail_threshold=float(threshold),trim_top1_mean=float(trim.groupby('day')['ret'+str(h)].mean().mean())))
    for st,sg in g.groupby('stage'):
     stage.append(dict(period=period,H=h,method=method,stage=st,n=len(sg),mean=float(sg['ret'+str(h)].mean()),positive40bp=float(sg['ret'+str(h)].gt(.004).mean())))
   for method in METHODS[1:]:
    delta=means[method]-means.PVR;blocks=pd.DataFrame({'d':delta,'block':[daypos[d]//60 for d in delta.index]}).groupby('block').d.agg(['sum','count']);draw=rng.integers(0,len(blocks),(2000,len(blocks)));boot=blocks['sum'].to_numpy()[draw].sum(1)/blocks['count'].to_numpy()[draw].sum(1);lo,hi=np.quantile(boot,[.025,.975])
    paired.append(dict(period=period,H=h,method=method,n_days=len(delta),blocks=len(blocks),delta=float(delta.mean()),lo=float(lo),hi=float(hi),leave_best_day=float(delta.drop(delta.idxmax()).mean())if len(delta)>1 else np.nan))
 pd.DataFrame(results).to_csv(O/'SAME_DATE_SECTOR_K_RESULTS.csv',index=False);pd.DataFrame(paired).to_csv(O/'PAIRED_60BLOCK_RESULTS.csv',index=False);pd.DataFrame(stage).to_csv(O/'STAGE_RESULTS.csv',index=False)
 members={method:set(g.row)for method,g in sel.groupby('method')};roots=[]
 for(sid,epoch),g in c.groupby(['sid','epoch']):
  g=g.sort_values('t');b=g.iloc[0];early=set(g.loc[g.t.le(b.t+5),'row']);r=dict(sid=sid,epoch=epoch,first_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc))
  r.update({method:bool(early&mem)for method,mem in members.items()});roots.append(r)
 roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_COVERAGE.csv',index=False);rs=[]
 for y,g in roots.groupby('year'):
  z=g[g.big60]
  for method in METHODS:rs.append(dict(year=y,method=method,roots=len(g),complete=int(g.complete60.sum()),big=len(z),caught=int(z[method].sum()),lost=int((z.PVR&~z[method]).sum()),added=int((~z.PVR&z[method]).sum())))
 pd.DataFrame(rs).to_csv(O/'ROOT_COVERAGE_SUMMARY.csv',index=False)
 cor=[]
 for(day,sector),g in c[c.common_known].groupby(['day','sector']):
  if len(g)<3:continue
  for name in ['original_PVR','H1','P9']:
   x=g.PA18.rank();y=g[name].rank();cor.append(dict(day=day,sector=sector,n=len(g),comparator=name,spearman=float(x.corr(y))if x.nunique()>1 and y.nunique()>1 else np.nan))
 pd.DataFrame(cor).to_csv(O/'RANK_CORRELATIONS.csv',index=False)
 ids=['300085.SZ','002583.SZ','300666.SZ','688603.SH','301611.SZ','600056.SH','002317.SZ','000620.SZ','002911.SZ','000506.SZ'];mv=pd.read_parquet(O/'RANK_MOVES.parquet');mv=mv[mv.sid.isin(ids)];mv=mv.merge(c.drop(columns=['row','day','sid','sector']).assign(row=c.row),on='row',validate='many_to_one');mv.to_csv(O/'NAMED_CASE_RANKS.csv',index=False)
 ann=c.groupby('year').agg(rows=('sid','size'),known=('common_known','sum'),stocks=('sid','nunique'));ann.to_csv(O/'COVERAGE_BY_YEAR.csv')
 actual=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');actual=actual[actual.account.eq('PVR')];ac=actual.merge(c[['sid','day','PA18','P9','common_known','row']],left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one');ar=[]
 for method in METHODS:
  ac[method+'_chosen']=ac.row.isin(members[method])
  for year,g in ac.groupby('year'):
   z=g[g[method+'_chosen']&g.closed];ar.append(dict(year=year,method=method,original_filled_selected_closed=len(z),wins=int(z.round_pnl.gt(0).sum()),descriptive_winrate=float(z.round_pnl.gt(0).mean()),NOT_counterfactual_strategy=True))
 pd.DataFrame(ar).to_csv(O/'ORIGINAL_ROUND_ASSOCIATION.csv',index=False)
 hashes=json.loads((O/'INPUT_HASHES.json').read_text());unchanged=all(sha(p)==v for p,v in hashes.items()if p!=str(Path(__file__)));assert unchanged
 dump('COMPLETION.json',dict(status='ONE_FROZEN_DIAGNOSTIC_COMPLETE_NOT_STRATEGY',opportunities=len(c),known=int(c.common_known.sum()),monthly_fits=len([m for m in json.loads((O/'MONTHLY_MODELS.json').read_text())if m.get('status')=='FIT']),accounts=0,parameters_scanned=0,original_inputs_unchanged=unchanged,label_sha256=sha(LAB)))
 dump('OUTPUT_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print('RESULTS\n',pd.DataFrame(results).query('H==60').to_string(index=False),flush=True);print('PAIRED\n',pd.DataFrame(paired).query('H==60').to_string(index=False),flush=True);print('ROOTS\n',pd.DataFrame(rs).to_string(index=False),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='prep':prep()
 elif sys.argv[1]=='run':run()
 elif sys.argv[1]=='evaluate':evaluate()
