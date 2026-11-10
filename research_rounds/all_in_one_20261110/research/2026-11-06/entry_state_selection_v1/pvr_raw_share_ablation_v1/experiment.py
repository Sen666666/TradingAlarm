"""Single fixed raw-share PVR ablation. No accounts, model fitting or parameter search."""
from pathlib import Path
import sys,json,time,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
B=R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1'
Q=B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet';LAB=B/'FIXED_NATIVE_PRICE_LABELS.parquet'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')
D=R/'dual_frontier_cp_full_v1'
sys.path.insert(0,str(F.parent));from features import original_pvr,original_observation_clock
END='2026-05-15';METHODS=['PVR','SHARES'];W=.9**np.arange(20,-1,-1);W/=W.sum()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
 if isinstance(x,(Path,pd.Timestamp)):return str(x)
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
def calendar():
 z=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);return z[z<=END]
def calc(p):
 z=original_pvr(p);valid,block=original_observation_clock(p)
 cols=['raw_open','raw_high','raw_low','raw_close']
 geo=np.isfinite(p[cols]).all(axis=1)&p[cols].gt(0).all(axis=1)&p.raw_high.ge(p[cols].max(axis=1))&p.raw_low.le(p[cols].min(axis=1))
 good=valid&geo
 for col in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:good &= p[col].notna()&p[col].eq(True)
 for col in ['source_invalid','synthetic_event_bar']:good &= p[col].notna()&p[col].eq(False)
 good &= p.volume_unit.eq('shares')&p.amount_unit.eq('CNY')&np.isfinite(p.raw_volume)&p.raw_volume.gt(0)&np.isfinite(p.volume_factor)&p.volume_factor.gt(0)&np.isfinite(p.adjustment_factor)&p.adjustment_factor.gt(0)
 rawq=p.amount/p.raw_volume;tol=.5/p.raw_volume+1e-8
 good &= np.isfinite(rawq)&rawq.ge(p.raw_low-tol)&rawq.le(p.raw_high+tol)
 good &= (p.raw_close*p.adjustment_factor-p.close).abs().le(1e-10)
 out=z.rename(columns={'b':'b_amount','e':'e_amount','E':'E_amount','score':'native_PVR'}).copy()
 for n in ['volume_ref','b_shares','e_shares','E_shares','score_shares']:out[n]=np.nan
 out['source_and_unit42']=False;out['factor_stable42']=False;out['source85']=False
 out['quantity_valid_current']=good;out['volume_factor']=p.volume_factor;out['raw_volume']=p.raw_volume;out['amount']=p.amount
 for _,g in p[valid].groupby(block[valid],sort=False):
  ix=g.index;v=g.raw_volume;fac=g.volume_factor;kind=pd.Series(pd.factorize(g.source_kind)[0],index=ix)
  source22=kind.rolling(22).min().eq(kind.rolling(22).max())&g.source_kind.notna().rolling(22).sum().eq(22)
  source85=kind.rolling(85).min().eq(kind.rolling(85).max())&g.source_kind.notna().rolling(85).sum().eq(85)
  good22=good.loc[ix].rolling(22,min_periods=22).sum().eq(22)&source22
  factor22=fac.rolling(22).min().eq(fac.rolling(22).max())
  vref=v.shift().rolling(21,min_periods=21).median();bv=np.tanh(np.log(v/vref)).where(good22&factor22)
  e=z.loc[ix,'u']*(1+.5*z.loc[ix,'u'].abs()*bv)
  E=e.rolling(21,min_periods=21).apply(lambda x:np.dot(W,x),raw=True)
  unit42=good.loc[ix].rolling(42,min_periods=42).sum().eq(42)&kind.rolling(42).min().eq(kind.rolling(42).max())
  stable42=fac.rolling(42).min().eq(fac.rolling(42).max())
  score=(50+50*np.tanh(2*E)).where(source85)
  out.loc[ix,['volume_ref','b_shares','e_shares','E_shares','score_shares']]=pd.DataFrame(dict(volume_ref=vref,b_shares=bv,e_shares=e,E_shares=E,score_shares=score),index=ix)
  out.loc[ix,'source_and_unit42']=unit42;out.loc[ix,'factor_stable42']=stable42;out.loc[ix,'source85']=source85
  expected=z.loc[ix,'score'].notna()&unit42&stable42&source85
  assert score.notna().equals(expected)
 out['feature_known']=out.score_shares.notna()
 out['status']=np.select([out.native_PVR.isna(),~out.source85,~out.source_and_unit42,~out.factor_stable42],['ORIGINAL_PVR_WARMUP_OR_INVALID','SOURCE_85_NOT_CONSTANT','QUANTITY_UNIT_OR_GEOMETRY_42_INVALID','VOLUME_FACTOR_CHANGED_42'],default='KNOWN')
 return out
def run():
 assert not(O/'RANK_SEAL.json').exists()
 start=time.monotonic();q=pd.read_parquet(Q);q=q[q.account.eq('PVR')].reset_index(drop=True)
 assert len(q)==53121 and not q.duplicated(['sid','day']).any()
 mp={x['symbol']:x for x in json.loads(M.read_text())};cal=calendar()
 cases=json.loads((R/'lifecycle_ordered_damage_v1/FIXED_CASES_BEFORE_COMPUTE.json').read_text())
 wanted={}
 for c in cases:wanted.setdefault(c['sid'],set()).add(c['day'])
 sources={str(p):sha(p)for p in [M,H,Q,F,Path(__file__),O/'PROTOCOL.json',D/'I_ROOTS.parquet']}
 parts=[];caseparts=[];aud=[];prefix=[]
 for no,(sid,g)in enumerate(q.groupby('sid',sort=True)):
  m=mp[sid];p=next(p for p in m['source_sha256']if p.endswith('/signal.parquet'));hs=sha(p);assert hs==m['source_sha256'][p]
  f=pd.read_parquet(p).loc[:END];assert f.index.is_unique and f.index.is_monotonic_increasing
  native=pd.read_parquet(m['refs']['facts']).reindex(f.index)
  assert (f.close-native.close).abs().max()<1e-7
  assert (f.adjustment_factor-native.factor).abs().max()<1e-10
  z=calc(f);idx=pd.DatetimeIndex(g.day);a=z.reindex(idx).reset_index(drop=True);a['sid']=sid;a['day']=g.day.to_numpy()
  err=(a.native_PVR.to_numpy()-g.original_PVR.to_numpy());finite=np.isfinite(err)
  maxerr=float(abs(err[finite]).max()) if finite.any() else 0.;assert maxerr<1e-10,(sid,maxerr)
  # Original native I root, only past-derived state fields, no future price labels.
  stpath=D/'states'/(sid+'.parquet');st=pd.read_parquet(stpath,columns=['day','I_root','segment'])
  a=a.merge(st,on='day',how='left',validate='one_to_one');assert a.I_root.notna().all()
  parts.append(a)
  if sid in wanted:
   cc=z.reindex(pd.DatetimeIndex(sorted(wanted[sid]))).copy();cc['day']=cc.index.strftime('%Y-%m-%d');cc['sid']=sid;caseparts.append(cc)
  aud.append(dict(sid=sid,candidates=len(g),feature_known=int(a.feature_known.sum()),native_score_max_error=maxerr,original_PVR_unknown=int(g.original_PVR.isna().sum()),raw_volume_unit='shares',amount_unit='CNY'))
  sources[p]=hs;sources[m['refs']['facts']]=sha(m['refs']['facts']);sources[str(stpath)]=sha(stpath)
  if sid in ['000001.SZ','600056.SH','002181.SZ','688585.SH','300666.SZ','301611.SZ']:
   for cut in ['2022-03-03','2024-09-24','2026-01-15']:
    zz=calc(f.loc[:cut]);pd.testing.assert_frame_equal(zz,z.loc[:cut],check_exact=True);prefix.append(dict(sid=sid,cut=cut,passed=True))
  if(no+1)%300==0:print('FEATURES',no+1,round(time.monotonic()-start,1),flush=True)
 c=q.merge(pd.concat(parts,ignore_index=True),on=['sid','day'],validate='one_to_one')
 c['row']=np.arange(len(c));c['calendar_t']=[cal.get_loc(pd.Timestamp(d))for d in c.day]
 c['reorderable']=c.feature_known&c.original_PVR.notna()
 c.loc[c.original_PVR.isna(),'status']='ORIGINAL_QUEUE_PVR_UNKNOWN_KEEP_SLOT'
 picks=[];moves=[];queues=[]
 for day,g in c.groupby('day',sort=True):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));baseids=set(base.head(K).index);ks=base.head(K).groupby('sector').size().to_dict()
  for method in METHODS:
   chosen=[]
   for sector,gg in base.groupby('sector',sort=False):
    k=int(ks.get(sector,0));order=list(gg.index)
    if method=='SHARES':
     good=gg.reorderable;ranked=gg[good].sort_values(['score_shares','original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ranked.index)
     order=[next(it)if good.loc[j]else j for j in gg.index]
     assert set(order)==set(gg.index)
     assert all(order[pos]==j for pos,j in enumerate(gg.index)if not good.loc[j])
    chosen+=order[:k]
    moves.extend(dict(row=int(j),method=method,sector_rank=rank+1,selected=rank<k,sector_K=k)for rank,j in enumerate(order))
   assert len(chosen)==K and c.loc[chosen].groupby('sector').size().to_dict()==ks
   picks.extend(dict(row=int(j),day=day,method=method)for j in chosen)
   queues.append(dict(day=day,method=method,N=len(g),K=K,reorderable=int(g.reorderable.sum()),changed=len(set(chosen)-baseids)))
 c.to_parquet(O/'FEATURES.parquet',index=False);pd.DataFrame(picks).to_parquet(O/'SEALED_PICKS.parquet',index=False)
 pd.DataFrame(moves).to_parquet(O/'RANK_MOVES.parquet',index=False);pd.DataFrame(queues).to_csv(O/'QUEUE_AUDIT.csv',index=False)
 pd.DataFrame(aud).to_csv(O/'SOURCE_AUDIT.csv',index=False);pd.concat(caseparts,ignore_index=True).to_csv(O/'FIXED_CASE_SCORES.csv',index=False)
 save('PREFIX_QA.json',prefix);save('INPUT_HASHES.json',sources)
 hashes={n:sha(O/n)for n in ['FEATURES.parquet','SEALED_PICKS.parquet','RANK_MOVES.parquet','experiment.py','PROTOCOL.json']}
 save('RANK_SEAL.json',dict(status='FEATURES_AND_SAME_DATE_SECTOR_K_SEALED_BEFORE_NEW_EVALUATION',hashes=hashes,future_labels_read=False,rows=len(c),dates=c.day.nunique(),feature_known=int(c.feature_known.sum()),reorderable=int(c.reorderable.sum()),original_PVR_unknown=int(c.original_PVR.isna().sum()),picks_each=len(picks)//2,seconds=time.monotonic()-start))
 print('RANK_SEALED',json.dumps(json.loads((O/'RANK_SEAL.json').read_text()),ensure_ascii=False),flush=True)
def periods():
 return [('ALL',None,None)]+[(str(y),f'{y}-01-01',f'{y}-12-31')for y in range(2022,2027)]+[('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31')]
def period(g,a,b):return g if a is None else g[g.day.between(a,b)]
def blocks(v,cal):
 pos={str(d.date()):i for i,d in enumerate(cal)};b=pd.DataFrame({'v':v,'block':[pos[str(d)]//60 for d in v.index]}).groupby('block').v.agg(['sum','count'])
 out=dict(days=len(v),blocks=len(b),delta=float(v.mean()),lo=None,hi=None)
 if len(b)>=5:
  rng=np.random.default_rng(20261107);ix=rng.integers(0,len(b),(2000,len(b)));zz=b['sum'].to_numpy()[ix].sum(1)/b['count'].to_numpy()[ix].sum(1)
  out.update(lo=float(np.quantile(zz,.025)),hi=float(np.quantile(zz,.975)))
 return out
def evaluate():
 start=time.monotonic();seal=json.loads((O/'RANK_SEAL.json').read_text());assert all(sha(O/n)==h for n,h in seal['hashes'].items())
 inputeval=[LAB,D/'FIXED_I_ROOT_COMPARISON.parquet',R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv']
 before={str(p):sha(p)for p in inputeval};save('EVALUATION_INPUT_HASHES_BEFORE.json',before)
 c=pd.read_parquet(O/'FEATURES.parquet');pick=pd.read_parquet(O/'SEALED_PICKS.parquet');cal=calendar()
 lab=pd.read_parquet(LAB);assert not lab.duplicated(['sid','day']).any()
 c=c.merge(lab,on=['sid','day'],validate='one_to_one');assert len(c)==53121
 s=pick.merge(c,on=['row','day'],validate='many_to_one');results=[];deltas=[];coverage=[];membership=[]
 for h in [5,20,60]:
  co='complete'+str(h);ret='ret'+str(h)
  supports={'ALL_CANDIDATES_COMPLETE':c.groupby('day')[co].all(),'SELECTED_UNION_COMPLETE':s.groupby('day')[co].all()}
  for scope,ok in supports.items():
   gooddays=set(ok[ok].index);whole=s[s.day.isin(gooddays)]
   for per,a,b in periods():
    u=period(s,a,b);z=period(whole,a,b);coverage.append(dict(scope=scope,period=per,H=h,total_days=u.day.nunique(),complete_days=z.day.nunique(),picks_each=len(z)//2))
    if not len(z):continue
    means=z.groupby(['day','method'])[ret].mean().unstack('method')
    for method,g in z.groupby('method'):
     rr=g[ret];results.append(dict(scope=scope,period=per,H=h,method=method,N=len(g),days=g.day.nunique(),mean_day=float(g.groupby('day')[ret].mean().mean()),mean_event=float(rr.mean()),median=float(rr.median()),positive_price=float(rr.gt(0).mean()),mae=float(g['mae'+str(h)].mean()),mfe=float(g['mfe'+str(h)].mean())))
    deltas.append(dict(scope=scope,period=per,H=h,comparison='SHARES-PVR',**blocks(means.SHARES-means.PVR,cal)))
 mem={m:set(g.row)for m,g in pick.groupby('method')}
 c['selection_group']=np.select([c.row.isin(mem['PVR'])&c.row.isin(mem['SHARES']),c.row.isin(mem['PVR'])],['both','removed'],default='unselected')
 c.loc[c.row.isin(mem['SHARES'])&~c.row.isin(mem['PVR']),'selection_group']='added'
 for per,a,b in periods():
  for group,g in period(c,a,b).groupby('selection_group'):
   membership.append(dict(period=per,group=group,rows=len(g),stocks=g.sid.nunique(),dates=g.day.nunique(),feature_known=int(g.feature_known.sum())))
 pd.DataFrame(results).to_csv(O/'SAME_DATE_SECTOR_K_RESULTS.csv',index=False);pd.DataFrame(deltas).to_csv(O/'PAIRED_60SESSION_BLOCKS.csv',index=False)
 pd.DataFrame(coverage).to_csv(O/'EVALUATION_COVERAGE.csv',index=False);pd.DataFrame(membership).to_csv(O/'SELECTION_MEMBERSHIP.csv',index=False)
 # Fixed native-root label cohorts from prior audit, common birth anchor, not selected-event returns.
 roots=pd.read_parquet(D/'FIXED_I_ROOT_COMPARISON.parquet')
 roots=roots[~roots.unknown_birth&~roots.birth_before_2022].copy();roots['day']=roots.I_root
 key=['sid','I_root','segment'];candidate_keys=set(map(tuple,c[key].to_numpy()));roots['has_original_legal_candidate']=[tuple(x)in candidate_keys for x in roots[key].to_numpy()]
 for method in METHODS:
  selected=c[c.row.isin(mem[method])]
  first=selected.groupby(key).day.min().rename(method+'_first').reset_index()
  roots=roots.merge(first,on=key,how='left',validate='one_to_one')
  roots[method+'_lag']=[(cal.get_loc(pd.Timestamp(fd))-cal.get_loc(pd.Timestamp(rt)))if pd.notna(fd)else np.nan for fd,rt in zip(roots[method+'_first'],roots.I_root)]
 rootout=[]
 for per,a,b in periods():
  p=period(roots,a,b)
  for scope,z in [('ALL_KNOWN_NATIVE_ROOTS',p),('ROOTS_WITH_ORIGINAL_LEGAL_CANDIDATE',p[p.has_original_legal_candidate])]:
   for h in [5,20,60]:
    big=z[z.big60];aa=big.PVR_lag.between(0,h-1);bb=big.SHARES_lag.between(0,h-1)
    rootout.append(dict(period=per,scope=scope,H=h,roots=len(z),mature60=int(z.complete60.sum()),big60=len(big),PVR_captured=int(aa.sum()),SHARES_captured=int(bb.sum()),lost=int((aa&~bb).sum()),added=int((~aa&bb).sum())))
 roots.to_parquet(O/'NATIVE_ROOT_SELECTION_COVERAGE.parquet',index=False);pd.DataFrame(rootout).to_csv(O/'NATIVE_ROOT_COVERAGE_SUMMARY.csv',index=False)
 # Only original actual first MOBILE campaigns, uniformly closed at the fixed cutoff.
 ff=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv');ff=ff[ff.account.eq('PVR')&ff.first_kind.eq('add')].copy()
 ff=ff.merge(c[['sid','day','row','selection_group','score_shares','original_PVR','reorderable']],left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='one_to_one')
 assert len(ff)==1814 and ff.row.notna().all() and not(ff.closed&ff.closed_day.gt(END)).any()
 ff.to_csv(O/'ORIGINAL_FIRST_MOBILE_MEMBERSHIP.csv',index=False);rounds=[]
 for per,a,b in periods():
  z=period(ff.rename(columns={'day':'candidate_day','signal_day':'day'}),a,b)
  groups=[('ALL_ORIGINAL',z),('BASELINE_TOPK',z[z.row.isin(mem['PVR'])]),('SHARES_TOPK',z[z.row.isin(mem['SHARES'])])]+[(x,g)for x,g in z.groupby('selection_group')]
  for group,g in groups:
   cl=g[g.closed];wins=cl[cl.round_pnl.gt(0)];loss=cl[cl.round_pnl.lt(0)]
   rounds.append(dict(period=per,group=group,original_campaigns=len(g),closed=len(cl),positive=len(wins),zero=int(cl.round_pnl.eq(0).sum()),negative=len(loss),original_net_winrate=len(wins)/len(cl)if len(cl)else None,original_net_sum=float(cl.round_pnl.sum()),original_winner_profit=float(wins.round_pnl.sum()),original_payoff=float(wins.round_pnl.mean()/-loss.round_pnl.mean())if len(wins)and len(loss)else None,NOT_NEW_STRATEGY=True))
 pd.DataFrame(rounds).to_csv(O/'ORIGINAL_CAMPAIGN_ASSOCIATION.csv',index=False)
 s.to_parquet(O/'SELECTED_WITH_PRICE_LABELS.parquet',index=False);c.to_parquet(O/'ALL_CANDIDATES_WITH_LABELS.parquet',index=False)
 assert all(sha(p)==h for p,h in before.items())
 assert all(sha(O/n)==h for n,h in seal['hashes'].items())
 sources=json.loads((O/'INPUT_HASHES.json').read_text());assert all(sha(p)==h for p,h in sources.items())
 save('COMPLETION.json',dict(status='ONE_FROZEN_SHARE_COUNT_ABLATION_COMPLETE_NOT_STRATEGY',rows=len(c),picks_each=len(pick)//2,accounts=0,parameter_scan=0,source_inputs_unchanged=True,rank_seal_unchanged=True,no_claim_true_float_turnover=True,not_PIT=True,not_out_of_sample=True,seconds=time.monotonic()-start))
 print('PRIMARY',pd.DataFrame(results).query("scope=='ALL_CANDIDATES_COMPLETE' and period=='ALL'").to_string(index=False),flush=True)
 print('DELTAS',pd.DataFrame(deltas).query("scope=='ALL_CANDIDATES_COMPLETE'").to_string(index=False),flush=True)
 print('ROUNDS',pd.DataFrame(rounds).query("period=='ALL'").to_string(index=False),flush=True)
 print('ROOTS',pd.DataFrame(rootout).query("period=='ALL'").to_string(index=False),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='run':run()
 elif sys.argv[1]=='evaluate':evaluate()
