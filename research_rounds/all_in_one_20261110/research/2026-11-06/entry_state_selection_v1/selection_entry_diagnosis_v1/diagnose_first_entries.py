"""Read-only source diagnosis of existing account first entries. No account replay."""
from pathlib import Path
import json,gzip,ast,hashlib,time
from collections import defaultdict
import numpy as np,pandas as pd,pyarrow.parquet as pq
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1')
R=O.parent/'account_comparison_continuous_v1'
CACHE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def read(p): return json.loads(Path(p).read_text())
def dump(name,x): (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def clean(x):
 if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
 if isinstance(x,list):return [clean(v)for v in x]
 if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 return x
start=time.monotonic()
h=np.load(HP,allow_pickle=False); dates=pd.DatetimeIndex(h['dates']); symbols=list(h['symbols']); ix={s:j for j,s in enumerate(symbols)}
cl=pd.DataFrame(h['close'],index=dates,columns=symbols); hs=pd.DataFrame(h['score'],index=dates,columns=symbols); hr=pd.DataFrame(h['raw'],index=dates,columns=symbols)
segment=pd.DataFrame(h['segment'],index=dates,columns=symbols)
cl=cl.where(np.isfinite(cl)&(cl>0)); same20=segment.eq(segment.shift(19)); ma=cl.rolling(20,min_periods=20).mean().where(same20)
known=cl.notna()&ma.notna(); above=cl.gt(ma)
ids=[s for s in symbols if not s.startswith('URFI')]
def breadth(columns):
 k=known[columns]; a=above[columns]
 paired=k&k.shift(5,fill_value=False)
 delta=((a.astype(int)-a.shift(5,fill_value=False).astype(int))*paired).sum(axis=1)/paired.sum(axis=1).replace(0,np.nan)
 b=(a&k).sum(axis=1)/k.sum(axis=1).replace(0,np.nan)
 return pd.DataFrame({'breadth20':b,'delta5':delta,'known_n':k.sum(axis=1)})
market=breadth(ids)
market['regime']=np.where(market.breadth20.isna()|market.delta5.isna(),'UNKNOWN',np.where(market.breadth20>=.5,'SUPPORT',np.where(market.delta5>0,'IMPROVING','WEAK')))
market.loc['2022-01-01':'2026-05-15'].to_csv(O/'MARKET_FIXED1709_WARM.csv')
broad=pd.read_csv(O.parent/'local_v2/MARKET_BREADTH.csv')
broad.loc[broad.breadth20.isna()|broad.paired_delta5.isna(),'regime']='UNKNOWN'
broad.to_csv(O/'MARKET_5517_EXISTING_WITH_UNKNOWN_FIXED.csv',index=False)
rlog=np.log(cl).diff(); sigma=rlog.shift().rolling(20,min_periods=20).std(ddof=0).where(same20).replace(0,np.nan)
res20=cl.shift().rolling(20,min_periods=20).max().where(segment.eq(segment.shift(20)))
ret5=cl/cl.shift(5)-1;ret20=cl/cl.shift(20)-1;ret63=cl/cl.shift(63)-1
z5=np.log(cl/cl.shift(5))/(sigma*np.sqrt(5))
above20=cl>res20
# Explicit original H1 contributions, matching 252-history stocks only.
recent=.4*ret63
old=.2*(cl.shift(63)/cl.shift(126)-1)+.2*(cl.shift(126)/cl.shift(189)-1)+.2*(cl.shift(189)/cl.shift(252)-1)
accounts={a:json.load(gzip.open(R/f'run_1200000/pair/{a}.json.gz','rt')) for a in ['PVR','E31']}
rounds=[]; caseframes=[]; firsts=[]
for a,x in accounts.items():
 buys={t['layer']:t for t in x['trades']if t['side']=='buy'}
 decisions={(d['at'][:10],i['sid'],i['kind']):i for d in x['decisions']for i in d['intents']}
 by=defaultdict(list)
 for l in x['layers']:by[l['sid']].append(l)
 for sid,ls in by.items():
  cur=[];right=None
  def emit(cur):
   if not cur:return
   ls2=sorted(cur,key=lambda x:(x['opened'],x['id']));f=ls2[0];t=buys[f['id']];di=decisions[(f['signal_at'][:10],sid,f['kind'])]
   closed=max(l['closed']for l in cur)if all(l['closed']is not None for l in cur)else None
   cost=sum(float(buys[l['id']]['gross_cny'])+float(buys[l['id']]['fees_cny'])for l in cur)
   pnl=sum(float(l['cash'])+float(l['dividend'])for l in cur)if closed else np.nan
   meta=x['metadata'][str(f['id'])]
   row=dict(account=a,sid=sid,first_layer=f['id'],signal_day=f['signal_at'][:10],entry_day=f['opened'][:10],closed_day=closed[:10]if closed else None,year=int(f['opened'][:4]),first_kind=f['kind'],first_reason=t['reason'],layers=len(cur),sector=meta['sector'],closed=closed is not None,round_pnl=pnl,round_cost=cost,round_return_on_cumulative_cost=pnl/cost if closed else np.nan,closed_in_entry_year=bool(closed and closed[:4]==f['opened'][:4]),first_raw_open=float(t['raw_open']),first_fill=float(t['price']),stock_H1_decision=di['score'],PVR_decision=di.get('PVR_score'),original_H1_rank=di.get('original_H1_rank'),priority_rank=di.get('priority_rank'),first_role_floor=float(di['floor']),signal_raw_price=float(di['signal_price'])if di.get('signal_price')else np.nan)
   rounds.append(row)
  for l in sorted(ls,key=lambda x:(x['opened'],x['id'])):
   if cur and right is not None and l['opened']>=right:emit(cur);cur=[];right=None
   cur.append(l)
   if l['closed']is None:right=None
   elif len(cur)==1:right=l['closed']
   elif right is not None:right=max(right,l['closed'])
  emit(cur)
rr=pd.DataFrame(rounds); selected_cases={(str(r.sid),str(r.entry_day))for r in rr[(rr.account=='PVR')&(rr.year==2022)&rr.closed_in_entry_year].sort_values('round_pnl').iloc[[0,1,2,-2,-1]].itertuples()}
for no,(sid,g)in enumerate(rr.groupby('sid')):
 f=pq.read_table(CACHE/(sid+'.parquet')).to_pandas().set_index('day');f.index=pd.DatetimeIndex(f.index)
 C=f.price__close; signal_e=f.pvr__e
 # Concentration/efficiency diagnostic uses original e, not recalculated PVR.
 net=signal_e.rolling(21,min_periods=21).sum();gross=signal_e.abs().rolling(21,min_periods=21).sum()
 eff=net/gross.replace(0,np.nan)
 ar=f.price__amount/f.pvr__amount_ref
 for r in g.to_dict('records'):
  d=pd.Timestamp(r['signal_day']);en=pd.Timestamp(r['entry_day']);q=f.loc[d];s=r['sector'];pos=f.index.get_indexer([en])[0]
  r.update(stock_H1=float(hs.at[d,sid]),industry_H1=float(hs.at[d,s]),stock_H1_raw=float(hr.at[d,sid]),industry_H1_raw=float(hr.at[d,s]),H1_recent63_contribution=float(recent.at[d,sid]),H1_old_contribution=float(old.at[d,sid]),PVR_cache=float(q.pvr__score),e0_ready=int(q.native__e0_ready),e0_target=int(q.native__e0_target),i_target=float(q.native__i_target),i_buy=bool(q.native__i_buy),i_entered=float(q.native__i_entered),g_grade=float(q.native__g_grade),amount=float(q.price__amount),amount_relative_to_prior21median=float(ar.at[d]),prior20_resistance=float(res20.at[d,sid]),signal_close=float(C.at[d]),distance_to_resistance=float(cl.at[d,sid]/res20.at[d,sid]-1),ret5=float(ret5.at[d,sid]),ret20=float(ret20.at[d,sid]),ret63=float(ret63.at[d,sid]),sigma20_prior=float(sigma.at[d,sid]),z5=float(z5.at[d,sid]),pvr_eff21=float(eff.at[d]),market_breadth20=float(market.at[d,'breadth20']),market_delta5=float(market.at[d,'delta5']),market_regime=market.at[d,'regime'],industry_above_MA20=bool(above.at[d,s]),industry_ret5=float(ret5.at[d,s]),industry_ret20=float(ret20.at[d,s]),industry_ret63=float(ret63.at[d,s]),industry_distance_to_resistance=float(cl.at[d,s]/res20.at[d,s]-1))
  r['H1_score_matches_decision']=abs(r['stock_H1']-r['stock_H1_decision'])<1e-8
  r['PVR_score_matches_decision']=abs(r['PVR_cache']-r['PVR_decision'])<1e-8 if r['PVR_decision']is not None else False
  r['warm_close_scale_ratio']=float(C.at[d]/cl.at[d,sid])
  r['actual_entry_is_next_common_day']=bool(f.index.get_loc(d)+1==pos)
  op=float(f.price__open.iloc[pos]);r['entry_adjusted_open']=op;r['entry_gap']=op/float(C.at[d])-1
  r['weak_market']=r['market_regime']=='WEAK'
  r['below_resistance']=r['distance_to_resistance']<=0
  r['rebound_under_resistance']=bool(r['ret20']<0 and r['ret5']>0 and r['below_resistance'])
  r['stretched_rebound_under_resistance']=bool(r['rebound_under_resistance']and r['z5']>=1.5)
  r['industry_not_diffusing']=bool(r['industry_ret20']<=0 and r['industry_ret5']<=0)
  r['old_H1_carries_positive']=bool(r['ret63']<=0 and r['stock_H1_raw']>0)
  r['above_resistance']=bool(r['distance_to_resistance']>0)
  for n in [1,3,5,10,20,60]:
   v=f.iloc[pos:pos+n];valid=len(v)==n and v.source_row_present.eq(True).all() and np.isfinite(v.price__close).all() and v.price__close.gt(0).all()
   r['complete'+str(n)]=bool(valid)
   r['ret'+str(n)+'_forward']=float(v.price__close.iloc[-1]/op-1)if valid else np.nan
   r['close_MFE'+str(n)]=max(0,float(v.price__close.max()/op-1))if valid else np.nan
   r['close_MAE'+str(n)]=min(0,float(v.price__close.min()/op-1))if valid else np.nan
   hl=valid and np.isfinite(v.price__high).all()and np.isfinite(v.price__low).all()
   r['high_MFE'+str(n)]=max(0,float(v.price__high.max()/op-1))if hl else np.nan
   r['low_MAE'+str(n)]=min(0,float(v.price__low.min()/op-1))if hl else np.nan
  r['big60_posthoc']=bool(r['complete60']and r['close_MFE60']>=.3 and r['ret60_forward']>=.2)
  firsts.append(r)
  if r['account']=='PVR'and(sid,r['entry_day'])in selected_cases:
   ix1=max(0,f.index.get_loc(d)-10);ix2=min(len(f),max(pos+21,f.index.searchsorted(pd.Timestamp(r['closed_day']))+1))
   cf=f.iloc[ix1:ix2][['price__open','price__high','price__low','price__close','price__amount','pvr__score','pvr__e','pvr__E','pvr__u','pvr__b','native__e0_target','native__i_target','native__i_buy','native__i_entered','native__i_exited','native__g_grade','cp__receipt','cp__candidate']].copy()
   cf['sid']=sid;cf['case_entry_day']=r['entry_day'];cf['signal_day']=r['signal_day'];cf['stock_H1']=hs[sid].reindex(cf.index);cf['industry_H1']=hs[s].reindex(cf.index);cf['market_breadth20']=market.breadth20.reindex(cf.index);cf['market_delta5']=market.delta5.reindex(cf.index);cf['prior20_resistance_H1_scale']=res20[sid].reindex(cf.index);cf['close_H1_scale']=cl[sid].reindex(cf.index);cf['ret5']=ret5[sid].reindex(cf.index);cf['ret20']=ret20[sid].reindex(cf.index);cf['z5']=z5[sid].reindex(cf.index);cf['amount_relative']=ar.reindex(cf.index);cf['first_entry_return']=cf.price__close/op-1
   caseframes.append(cf.reset_index())
 if(no+1)%200==0:print('STOCKS',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
out=pd.DataFrame(firsts);out.to_csv(O/'ALL_FIRST_ENTRIES.csv',index=False);pd.concat(caseframes).to_csv(O/'FIVE_CASES_DAILY.csv',index=False)
# Exact identity check against frozen 2022 completed rounds, not recalculated account.
prior=pd.read_csv(R/'analysis/2022_loss_attribution/STOCK_ROUNDS_2022.csv')
oldc=prior[prior.closed.notna()].copy();oldc['entry_day']=oldc.opened.str[:10]
j=out[(out.year==2022)&out.closed_in_entry_year].merge(oldc,on=['account','sid','entry_day'],suffixes=('','_old'),validate='one_to_one')
assert len(j)==len(oldc)==1400
assert np.max(np.abs(j.round_pnl-j.pnl))<1e-7
assert out.H1_score_matches_decision.all()
out['PVR_cache_minus_original']=out.PVR_cache-out.PVR_decision
out[~out.PVR_score_matches_decision].to_csv(O/'PVR_SOURCE_DIFFERENCES.csv',index=False)
def metric(g):
 c=g[g.closed_in_entry_year]if int(g.year.iloc[0])==2022 else g[g.closed]
 return dict(n=len(g),complete_rounds=len(c),round_winrate=float(c.round_pnl.gt(0).mean())if len(c)else None,round_pnl=float(c.round_pnl.sum()),mean_ret5=float(g.ret5_forward.mean()),positive_ret5=float(g.ret5_forward.gt(0)[g.complete5].mean()),mean_ret20=float(g.ret20_forward.mean()),positive_ret20=float(g.ret20_forward.gt(0)[g.complete20].mean()),mean_close_MFE20=float(g.close_MFE20.mean()),mean_close_MAE20=float(g.close_MAE20.mean()),big60=int(g.big60_posthoc.sum()),big60_eligible=int(g.complete60.sum()))
groups=[];diagnostics=[]
for(a,y),g in out.groupby(['account','year']):
 groups.append(dict(account=a,year=y,dimension='ALL',value='ALL',**metric(g)))
 for col in ['market_regime','first_kind','weak_market','below_resistance','rebound_under_resistance','stretched_rebound_under_resistance','industry_not_diffusing','old_H1_carries_positive','above_resistance']:
  for val,z in g.groupby(col):groups.append(dict(account=a,year=y,dimension=col,value=str(val),**metric(z)))
 for col in ['stock_H1','industry_H1','PVR_decision','z5','amount_relative_to_prior21median','pvr_eff21']:
  bins={'stock_H1':[-np.inf,50,75,90,np.inf],'industry_H1':[-np.inf,50,75,90,np.inf],'PVR_decision':[-np.inf,60,75,85,np.inf],'z5':[-np.inf,0,1.5,3,np.inf],'amount_relative_to_prior21median':[-np.inf,1,2,4,np.inf],'pvr_eff21':[-np.inf,0,.25,.5,np.inf]}[col]
  for val,z in g.groupby(pd.cut(g[col],bins),observed=True):groups.append(dict(account=a,year=y,dimension=col,value=str(val),**metric(z)))
 for regime,rg in g.groupby('market_regime'):
  for col in ['below_resistance','rebound_under_resistance','industry_not_diffusing','old_H1_carries_positive']:
   for val,z in rg.groupby(col):groups.append(dict(account=a,year=y,dimension=regime+'|'+col,value=str(val),**metric(z)))
 for rule,mask in [('exclude_weak_market',g.weak_market),('exclude_rebound_under_resistance',g.rebound_under_resistance),('exclude_old_H1_carry',g.old_H1_carries_positive),('require_above_prior20close',~g.above_resistance),('require_industry_above_MA20',~g.industry_above_MA20),('require_eff21_positive',g.pvr_eff21.le(0))]:
  for side,z in [('removed',g[mask]),('retained',g[~mask])]:
   if len(z):diagnostics.append(dict(account=a,year=y,rule=rule,side=side,**metric(z)))
pd.DataFrame(groups).to_csv(O/'GROUPED_OUTCOMES.csv',index=False);pd.DataFrame(diagnostics).to_csv(O/'SINGLE_RULE_PATH_DIAGNOSTICS.csv',index=False)
cases=out[(out.account=='PVR')&out.apply(lambda r:(r.sid,r.entry_day)in selected_cases,axis=1)]
cases.to_csv(O/'FIVE_CASES_ENTRY.csv',index=False)
summary=dict(status='FIRST_ENTRY_DESCRIPTIVE_DIAGNOSIS_NOT_NEW_ACCOUNT_OR_OOS',seconds=time.monotonic()-start,rows=len(out),closed_2022_identity_rows=len(j),max_2022_pnl_identity_error=float(np.max(np.abs(j.round_pnl-j.pnl))),all_H1_decision_exact=bool(out.H1_score_matches_decision.all()),all_PVR_decision_exact=bool(out.PVR_score_matches_decision.all()),PVR_source_nonmatch_including_NA=int((~out.PVR_score_matches_decision).sum()),PVR_source_max_absolute_difference=float((out.PVR_cache-out.PVR_decision).abs().max()),all_entry_next_common=bool(out.actual_entry_is_next_common_day.all()),max_scale_ratio_variation=float(out.warm_close_scale_ratio.max()-out.warm_close_scale_ratio.min()),account_runs=0,original_indicator_runs=0,limitations=['fixed future-selected 1709-stock universe and non-PIT industry assignment','5517 broad cache January rolling knowledge UNKNOWN, not WEAK','all new statistics are descriptive on consumed history; no refitted score or randomized comparison','2022 round win rates use original closed-by-2022 denominator; other years full subsequent completed round, separately tagged','forward path uses same cached adjusted next actual open including buy-day close; no fillability claim or barrier execution','excluded original path profit is not counterfactual account PnL; released capital and interactions not simulated','PVR grouping uses original account decision score; canonical full-pool numeric differences retained, original e decomposition is only canonical-source diagnostic','warm H1 close and canonical cache have different adjustment scale; only within-source normalized features and returns used'])
dump('SUMMARY.json',clean(summary));print(json.dumps(clean(summary)),flush=True)
print('PVR_2022_GROUPS');print(pd.DataFrame(groups).query("account=='PVR' and year==2022").to_string(index=False))
print('FIVE_CASES');print(cases[['sid','signal_day','entry_day','round_pnl','first_kind','stock_H1','industry_H1','PVR_cache','market_regime','market_breadth20','market_delta5','ret5','ret20','z5','distance_to_resistance','amount_relative_to_prior21median','ret1_forward','ret5_forward','ret20_forward','close_MFE20','close_MAE20']].to_string(index=False))
dump('SOURCE_SHA256.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [HP,R/'run_1200000/pair/PVR.json.gz',R/'run_1200000/pair/E31.json.gz',R/'analysis/2022_loss_attribution/STOCK_ROUNDS_2022.csv',Path(__file__)]})
