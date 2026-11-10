from pathlib import Path
import pandas as pd,numpy as np,json,sys,time,hashlib
from decimal import Decimal as D
R=Path.cwd(); E=R/'m3_stock_birth_during_sector_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import market_identity_on,version_on
from sector_account import FeeSchedule,FeeComponent
rules=json.loads((B/'inputs-v2/market-rules.json').read_text()); proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids']
manifest={v['symbol']:v for v in json.loads((U/'STOCK_MANIFEST.json').read_text())}
rr=pd.read_csv(E/'entry_quality_2022_v1/CORE_LAYER_RESULTS.csv',float_precision='round_trip',parse_dates=['signal_day','entry_day','exit_day','last_known_mark_day','status_day'])
rr=rr[rr.arm.eq('A_UNION_B')&rr.window.isin(['2022','2024_924'])].copy()
ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day']).set_index('event_id')
panel=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet')
cal=pd.DatetimeIndex(sorted(panel.day.unique())); cal=cal[cal<=pd.Timestamp('2026-06-30')]; di={d:j for j,d in enumerate(cal)}
market=pd.read_csv(R/'selection_entry_diagnosis_v1/MARKET_FIXED1709_WARM.csv',index_col=0,parse_dates=True)
meta={}
def fee(sid,d,q,px):
 key=(sid,str(d.date()))
 if key not in meta:
  ident=market_identity_on(rules,sid,key[1],proxies)
  v=version_on(rules['fee_versions'][ident['venue']],key[1],proxies)['schedule']
  meta[key]=(FeeSchedule(v['schedule_id'],tuple(FeeComponent(**z) for z in v['components'])),D(str(rules['security_metadata'][sid]['par_value'])))
 fs,par=meta[key]
 return sum(fs.incremental('sell',D(q)*px,{}, {},1,shares=q,par_value=par).values(),D(0))
rows=[]; start=time.time(); qamax=0; incomplete=[]; hashes={}
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
for j,(sid,sg) in enumerate(rr.groupby('sid')):
 m=manifest[sid]; sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 hashes[sp]=sha(sp); hashes[m['refs']['facts']]=sha(m['refs']['facts'])
 p=pd.read_parquet(sp).reindex(cal); f=pd.read_parquet(m['refs']['facts']).reindex(cal)
 for r in sg.itertuples(index=False):
  row=r._asdict(); e=ev.loc[r.event_id]; t=r.signal_day; k=di[t]
  for c in ['g_grade','g_fresh_up','i_buy','e0_target','sector_run_age','sector_M3_n','sector_N','sector_delta3','previous_stock_state']:
   row[c]=e[c]
  row['sector_share']=e.sector_M3_n/e.sector_N
  row['market_regime']=market.loc[t,'regime'] if t in market.index else 'UNKNOWN'
  row['quarter']=str(t.to_period('Q'))
  row['distance']=np.log(e.close/e.i_floor)
  for n in [5,21,63]:
   h=f.iloc[max(0,k-n):k+1]
   ok=len(h)==n+1 and h.close.gt(0).all() and h.close.notna().all() and h.segment_id.notna().all() and h.segment_id.nunique()==1
   row['ret'+str(n)]=np.log(h.close.iloc[-1]/h.close.iloc[0]) if ok else np.nan
  # Root age from immediately contiguous known I state; not treated as a new rule.
  prior=f.i_target.iloc[:k+1]
  nz=prior.index[prior.ne(1)]
  root=di[nz[-1]]+1 if len(nz) else 0
  row['I_root_age']=k-root if root>0 and prior.iloc[root-1]==0 else np.nan
  buy=f.i_buy.iloc[:k+1].fillna(False).astype(bool); hits=np.flatnonzero(buy)
  row['last_i_buy_age']=k-hits[-1] if len(hits) else np.nan
  row['closed']=r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND'; row['win']=row['closed'] and r.core_net>0
  row['tail30']=row['closed'] and r.core_return>=.3
  if pd.notna(r.entry_day) and pd.notna(r.last_known_mark_day):
   ia=di[r.entry_day]; ib=di[r.exit_day]-1 if row['closed'] else di[r.last_known_mark_day]
   z=p.iloc[ia:ib+1]
   assert len(z)==ib-ia+1 and z.raw_close.notna().all()
   assert z.observed_bar.all() and z.price_eligible.all() and z.volume_eligible.all() and (~z.synthetic_event_bar).all() and (~z.source_invalid).all()
   assert all(z[c].nunique(dropna=False)==1 for c in ['source_kind','source_path','segment_id'])
   assert np.isclose(z.adjustment_factor.to_numpy(),z.adjustment_factor.iloc[0],rtol=1e-11).all()
   q=int(r.entry_q); K=D(q)*D(str(r.entry_price))+D(str(r.entry_fee))
   ns=[]
   for d,cl in zip(z.index,z.raw_close):
    px=D(str(cl))*D('.9995'); ns.append(float(D(q)*px-fee(sid,d,q,px)-K))
   ns=np.array(ns); rts=ns/float(K)
   profitable=np.flatnonzero(ns>0)
   row['peak_after_entry_return']=float(rts[1:].max()) if len(rts)>1 else np.nan
   row['ever_after_entry_positive']=bool((ns[1:]>0).any()) if len(ns)>1 else None
   row['only_entry_positive']=bool(ns[0]>0 and not (ns[1:]>0).any())
   row.update(path_known=True,held_days=len(ns),R_fraction=r.entry_risk/float(K),peak_core_net=float(ns.max()),peak_core_return=float(rts.max()),min_core_return=float(rts.min()),ever_core_positive=bool(len(profitable)),first_core_positive_day=cal[ia+profitable[0]] if len(profitable) else None,first_positive_lag=int(profitable[0])+1 if len(profitable) else np.nan,positive_close_days=int((ns>0).sum()),first5_min=float(rts[:5].min()),first5_max=float(rts[:5].max()),first_close_return=float(rts[0]),last_core_mark=float(ns[-1]),core_never_prefix=not bool(len(profitable)))
   if row['closed']:
    px=D(str(r.exit_price)); net=float(D(q)*px-fee(sid,r.exit_day,q,px)-K); qamax=max(qamax,abs(net-r.core_net))
    row['exit_close_to_fill']=q*(float(z.raw_close.iloc[-1])-r.exit_price)
    row['over_R']=(-r.core_net)>r.entry_risk
    if ib>=ia:
     oldfloor=f.i_floor.iloc[ib-1]/p.adjustment_factor.iloc[ib-1]
     row['pretrigger_floor']=oldfloor
     row['entry_to_floor']=q*(r.entry_price-oldfloor)
     row['floor_to_triggerclose']=q*(oldfloor-float(z.raw_close.iloc[-1]))
     row['fees_core']=r.entry_fee+r.core_sell_fee
  else: row['path_known']=False
  rows.append(row)
 if (j+1)%300==0: print('LOADED',j+1,'STOCKS',round(time.time()-start,1),flush=True)
x=pd.DataFrame(rows)
x['loss']=x.closed&~x.win
x['profit_path']=np.where(~x.path_known.astype(bool),'NO_KNOWN_PATH',np.where(~x.ever_core_positive.fillna(False).astype(bool),'NEVER_POSITIVE',np.where(x.peak_core_return<.1,'POSITIVE_BELOW_10PCT',np.where(x.peak_core_return<.2,'PEAK_10_20PCT','PEAK_GE20PCT'))))
x['hold_bucket']=pd.cut(x.held_days,[0,5,20,63,np.inf],labels=['1_5','6_20','21_63','64_PLUS'])
x['PVR_band']=pd.cut(x.PVR_score,[-np.inf,60,75,85,np.inf],labels=['LE60','60_75','75_85','GT85'])
x['G_band']=pd.cut(x.g_grade,[-np.inf,0,2,np.inf],labels=['LE0','1_2','GE3'])
x['I_age_band']=pd.cut(x.I_root_age,[-1,5,20,63,np.inf],labels=['0_5','6_20','21_63','64_PLUS'])
x['R_band']=pd.cut(x.R_fraction,[0,.05,.1,.2,np.inf],labels=['LE5PCT','5_10PCT','10_20PCT','GT20PCT'])
def summary(g):
 c=g[g.closed]; loss=c[~c.win]; w=c[c.win]; u=g[~g.closed]
 return pd.Series(dict(selected=len(g),closed=len(c),wins=len(w),losses=len(loss),win_rate=100*c.win.mean(),gross_loss=-loss.core_net.sum(),gross_win=w.core_net.sum(),net=c.core_net.sum(),tail30=int(c.tail30.sum()),median_hold=c.held_days.median(),unknown=int(u.status.str.contains('UNKNOWN').sum()),unknown_prefix_positive=int(u.ever_core_positive.fillna(False).sum())))
O=Path(__file__).resolve().parent
x['diagnostic_group']=np.where(x.win,'WIN',np.where(x.loss & x.profit_path.eq('POSITIVE_BELOW_10PCT'),'SMALL_POS_FAIL',np.where(x.loss,'OTHER_LOSS','UNKNOWN')))
x['early_full_R_loss']=(x.first5_min/x.R_fraction<=-1)
x['t1_profit_path']=np.where(x.peak_after_entry_return.isna(),'NO_T1_CLOSE',np.where(x.peak_after_entry_return.le(0),'NEVER_POSITIVE',np.where(x.peak_after_entry_return<.1,'POSITIVE_BELOW_10PCT',np.where(x.peak_after_entry_return<.2,'PEAK_10_20PCT','PEAK_GE20PCT'))))
x.to_csv(O/'ALL_CORE_PATH_DIAGNOSTICS.csv',index=False)
x[x.loss].groupby(['window','t1_profit_path']).agg(n=('round_id','size'),loss=('core_net',lambda a:-a.sum())).to_csv(O/'T1_LOSS_PATH.csv')
x[x.closed].groupby('window').agg(only_entry_positive=('only_entry_positive','sum')).to_csv(O/'T1_ENTRY_ONLY.csv')
x.groupby('window').apply(summary).to_csv(O/'BASELINE.csv')
x[x.loss].groupby(['window','profit_path']).agg(n=('round_id','size'),loss=('core_net',lambda a:-a.sum()),median_hold=('held_days','median'),median_peak=('peak_core_return','median'),overR=('over_R','sum')).to_csv(O/'LOSS_PATH.csv')
x[x.loss].groupby(['window','profit_path','hold_bucket'],observed=True).agg(n=('round_id','size'),loss=('core_net',lambda a:-a.sum())).to_csv(O/'LOSS_HOLD.csv')
x[x.status.str.contains('UNKNOWN')].groupby(['window','profit_path']).agg(n=('round_id','size'),median_days=('held_days','median'),lastmark=('last_core_mark','sum')).to_csv(O/'UNKNOWN_PREFIX.csv')
allstrata=[]
for col in ['event_type','market_regime','G_band','i_buy','PVR_band','I_age_band','R_band','quarter']:
 s=x.groupby(['window',col],observed=True).apply(summary).reset_index().rename(columns={col:'state'});s['feature']=col;allstrata.append(s)
pd.concat(allstrata,ignore_index=True).to_csv(O/'PREENTRY_STRATA.csv',index=False)
# R_band is actual entry execution risk, not a t-close predictor; quarter is descriptive, not a future-known regime.
x.groupby(['quarter','i_buy'],observed=True).apply(summary).to_csv(O/'IBUY_BY_QUARTER.csv')
x.groupby(['quarter','G_band'],observed=True).apply(summary).to_csv(O/'G_BY_QUARTER.csv')
metrics=['PVR_score','distance','g_grade','I_root_age','last_i_buy_age','sector_run_age','sector_share','sector_delta3','ret5','ret21','ret63']
x.groupby(['window','diagnostic_group'])[metrics].median().to_csv(O/'FEATURE_MEDIANS.csv')
pm=[]
for (w,d,s),g in x[x.diagnostic_group.isin(['WIN','SMALL_POS_FAIL'])].groupby(['window','signal_day','sector']):
 if len(g)==2 and set(g.diagnostic_group)=={'WIN','SMALL_POS_FAIL'}:
  a=g[g.win].iloc[0]; b=g[~g.win].iloc[0]; z={'window':w,'day':d,'sector':s,'winner':a['name'],'loser':b['name'],'winner_round':a.round_id,'loser_round':b.round_id}
  for c in ['PVR_score','distance','g_grade','I_root_age','last_i_buy_age','ret5','ret21','ret63']:
   z[c]=a[c]-b[c]
  pm.append(z)
pair=pd.DataFrame(pm); pair.to_csv(O/'SAME_DAY_INDUSTRY_SMALL_POS_PAIRS.csv',index=False)
pc=['PVR_score','distance','g_grade','I_root_age','last_i_buy_age','ret5','ret21','ret63']
pair.groupby('window')[pc].median().to_csv(O/'PAIRED_MEDIAN_DIFF.csv')
pair.groupby('window')[pc].agg(lambda a:(a>0).sum()).to_csv(O/'PAIRED_WINNER_HIGHER.csv')
pair.groupby('window')[pc].agg(lambda a:(a==0).sum()).to_csv(O/'PAIRED_EQUAL.csv')
x[x.loss].groupby('window')[['core_net','entry_to_floor','floor_to_triggerclose','exit_close_to_fill','fees_core']].sum().to_csv(O/'EXIT_DECOMPOSITION.csv')
x[x.closed].groupby(['window','loss','early_full_R_loss']).agg(n=('round_id','size'),net=('core_net','sum'),median_hold=('held_days','median'),tail30=('tail30','sum')).to_csv(O/'EARLY_R.csv')
pd.concat([g.nsmallest(8,'core_net') for _,g in x[x.loss].groupby('window')]).to_csv(O/'TOP_LOSSES.csv',index=False)
pd.concat([g.nlargest(6,'core_net') for _,g in x[x.win].groupby('window')]).to_csv(O/'TOP_WINNERS.csv',index=False)
sources=[E/'entry_quality_2022_v1/CORE_LAYER_RESULTS.csv',E/'lifecycle_v1/ROUNDS.csv',E/'SEALED_ALL_BIRTH_EVENTS.csv',R/'selection_entry_diagnosis_v1/MARKET_FIXED1709_WARM.csv',R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet',U/'STOCK_MANIFEST.json',B/'code/market_rules.py',B/'code/sector_account.py',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json']
hashes.update({str(p):sha(p) for p in sources})
(O/'SOURCE_HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
qa=dict(selected=len(x),core_terminal_max_error=qamax,loss_decomposition_max_error=float((-x[x.loss].core_net-x[x.loss][['entry_to_floor','floor_to_triggerclose','exit_close_to_fill','fees_core']].sum(axis=1)).abs().max()),scope='A_UNION_B only, original dates, independent core fees, no new strategy or account',source_files=len(hashes),seconds=time.time()-start,classification_bool_dtype_explicit=True,output_reproduction_after_initial_interactive_analysis=True)
(O/'QA.json').write_text(json.dumps(qa,indent=2)+'\n')
print('QA',json.dumps(qa))
print('BASELINE\n',x.groupby('window').apply(summary).to_string())
print('LOSS_PATH\n',x[x.loss].groupby(['window','profit_path']).agg(n=('round_id','size'),loss=('core_net',lambda a:-a.sum()),median_hold=('held_days','median'),median_peak=('peak_core_return','median'),overR=('over_R','sum')).to_string())
print('LOSS_HOLD\n',x[x.loss].groupby(['window','profit_path','hold_bucket'],observed=True).agg(n=('round_id','size'),loss=('core_net',lambda a:-a.sum())).to_string())
print('UNKNOWN_PREFIX\n',x[x.status.str.contains('UNKNOWN')].groupby(['window','profit_path']).agg(n=('round_id','size'),median_days=('held_days','median'),lastmark=('last_core_mark','sum')).to_string())
print('READY_FOR_QUERIES',flush=True)
