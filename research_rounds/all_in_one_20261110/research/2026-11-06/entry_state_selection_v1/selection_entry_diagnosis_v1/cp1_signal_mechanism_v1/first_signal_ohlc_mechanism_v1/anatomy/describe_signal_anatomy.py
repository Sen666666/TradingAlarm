import os,json,math,hashlib,time
from pathlib import Path
import numpy as np
import pandas as pd
O=Path(__file__).parent
BASE=O.parents[2]
FIRST=BASE/'ALL_FIRST_ENTRIES.csv'
CPMAN=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
RAWMAN=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as fh:
  for x in iter(lambda:fh.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
src={str(p):sha(p) for p in [FIRST,CPMAN,RAWMAN,O/'DESCRIPTIVE_FREEZE.json']}
srcstats={}
a=pd.read_csv(FIRST)
assert len(a)==5373
a['row_id']=np.arange(len(a));a['signal_day']=pd.to_datetime(a.signal_day)
check=a[(a.account=='PVR')&(a.year==2022)&a.closed_in_entry_year]
assert len(check)==692 and check.round_pnl.gt(0).sum()==130
cm={x['symbol']:x for x in json.load(open(CPMAN))}
rm={x['series_id']:x for x in json.load(open(RAWMAN))['series']}
cpcols=['r','delta_frontier','displacement','credit','m','scale','anchor','frontier','receipt','reset_reason','phase','ready','s','z','B']
factscols=['close','factor','raw_close','segment_id']
rawcols=['trade_date','open','high','low','close','amount','price_eligible','source_invalid','observed_bar']
parts=[];missing=[];sourceaudit=[]
start=time.time()
for n,(sid,group) in enumerate(a.groupby('sid')):
 cpfile=Path(cm[sid]['refs']['CP1']);ffile=Path(cm[sid]['refs']['facts']);rawfile=Path(rm[sid]['raw']['path'])
 for p in [cpfile,ffile,rawfile]:
  if str(p) not in src:
   src[str(p)]=sha(p);st=p.stat();srcstats[str(p)]=(st.st_size,st.st_mtime_ns)
 cp=pd.read_parquet(cpfile,columns=cpcols);facts=pd.read_parquet(ffile,columns=factscols)
 raw=pd.read_parquet(rawfile,columns=rawcols).set_index('trade_date')
 assert cp.index.is_unique and facts.index.is_unique and raw.index.is_unique
 days=pd.DatetimeIndex(group.signal_day)
 cp_exists=days.isin(cp.index);facts_exists=days.isin(facts.index);raw_exists=days.isin(raw.index)
 c=cp.reindex(days).reset_index(drop=True);f=facts.reindex(days).reset_index(drop=True);r=raw.reindex(days).reset_index(drop=True)
 z=group[['row_id','account','sid','first_kind','first_reason','signal_day','entry_day','closed_day','year','quarter','market_regime','broad5517_regime','closed','closed_in_entry_year','round_pnl','round_return_on_cumulative_cost']].reset_index(drop=True)
 z['cp_source_present']=cp_exists;z['facts_source_present']=facts_exists;z['raw_source_present']=raw_exists
 for k in cpcols:z['cp_'+k]=c[k]
 for k in factscols:z['facts_'+k]=f[k]
 for k in rawcols[1:]:z['raw_'+k]=r[k]
 fr=np.log(facts.close).diff().where(facts.segment_id.eq(facts.segment_id.shift()))
 z['facts_r']=fr.reindex(days).to_numpy()
 z['raw_close_error']=(z.raw_close-z.facts_raw_close).abs()
 z['cp_r_error']=(z.cp_r-z.facts_r).abs()
 z['source_ohlc_valid']=(z[['raw_open','raw_high','raw_low','raw_close']].gt(0).all(axis=1)&z.raw_high.ge(z[['raw_open','raw_low','raw_close']].max(axis=1))&z.raw_low.le(z[['raw_open','raw_high','raw_close']].min(axis=1))&z.raw_price_eligible.eq(True)&z.raw_source_invalid.eq(False)&z.raw_observed_bar.eq(True)&z.raw_close_error.le(1e-8))
 z['b']=np.log(z.raw_close/z.raw_open).where(z.source_ohlc_valid)
 z['g']=(z.cp_r-z.b).where(z.source_ohlc_valid)
 z['w']=np.log(z.raw_high/z.raw_close).where(z.source_ohlc_valid)
 z['range']=np.log(z.raw_high/z.raw_low).where(z.source_ohlc_valid)
 z['close_position']=(np.log(z.raw_close/z.raw_low)/z['range']).where(z['range'].gt(0))
 z['fresh_cp']=z.cp_receipt.eq(True)
 z['fresh_frontier_share']=(z.cp_delta_frontier/z.cp_r).where(z.fresh_cp&z.cp_r.gt(0))
 z['cp_status']=np.select([z.fresh_cp,z.cp_source_present&z.first_kind.eq('core')],['fresh_CP','CORE_only_no_fresh_CP'],default='nonfresh_other_or_unknown')
 z['gap_body_class']=np.select([z.g.isna()|z.b.isna(),z.g.gt(0)&z.b.lt(0)],['unknown','gap_up_body_down'],default='other_valid')
 z['gap_body_net_class']=np.select([z.g.isna()|z.b.isna()|z.cp_r.isna(),z.g.gt(0)&z.b.lt(0)&z.cp_r.gt(0),z.g.gt(0)&z.b.lt(0)&z.cp_r.le(0)],['unknown','gap_up_body_down_net_positive','gap_up_body_down_net_nonpositive'],default='other_valid')
 z['close_half_class']=np.select([z.close_position.isna(),z.close_position.lt(.5)],['unknown_zero_or_invalid_range','lower_half'],default='upper_half')
 z['outcome']=np.select([~z.closed,z.round_pnl.gt(0),z.round_pnl.lt(0)],['open','win','loss'],default='zero')
 parts.append(z)
 if (n+1)%200==0:print('READ',n+1,'stocks',round(time.time()-start,1),'s',flush=True)
d=pd.concat(parts,ignore_index=True).sort_values('row_id')
assert len(d)==5373 and d.row_id.is_unique
d['signal_day']=d.signal_day.dt.strftime('%Y-%m-%d')
d['entry_quarter']=pd.to_datetime(d.entry_day).dt.to_period('Q').astype(str)
d.to_csv(O/'SIGNAL_DAY_ANATOMY.csv',index=False,float_format='%.17g')
groups=[];cont=[]
features=['g','b','w','range','close_position','fresh_frontier_share','cp_r','cp_delta_frontier','cp_displacement','cp_credit','cp_m','cp_scale']
def strata(df):
 yield 'all','ALL',df
 for cols in [['year'],['entry_quarter'],['market_regime'],['year','market_regime'],['entry_quarter','market_regime']]:
  for key,sub in df.groupby(cols,dropna=False):
   if not isinstance(key,tuple):key=(key,)
   yield ' x '.join(cols),'|'.join(map(str,key)),sub
for account,ad in d.groupby('account'):
 for scope,sdf in [('all_first_entries',ad),('2022_closed_in_entry_year',ad[(ad.year==2022)&ad.closed_in_entry_year])]:
  for stratum,key,s in strata(sdf):
   for cp_scope,ss in [('all',s),('fresh_CP',s[s.fresh_cp]),('CORE_only_no_fresh_CP',s[s.cp_status=='CORE_only_no_fresh_CP'])]:
    baseclosed=ss[ss.closed];bw=int(baseclosed.round_pnl.gt(0).sum());bl=int(baseclosed.round_pnl.lt(0).sum())
    for family,col in [('baseline',None),('cp_status','cp_status'),('gap_body','gap_body_class'),('gap_body_net','gap_body_net_class'),('close_half','close_half_class')]:
     pairs=[('ALL',ss)] if col is None else list(ss.groupby(col,dropna=False))
     for category,t in pairs:
      closed=t[t.closed];nw=int(closed.round_pnl.gt(0).sum());nl=int(closed.round_pnl.lt(0).sum());nz=int(closed.round_pnl.eq(0).sum())
      groups.append(dict(account=account,scope=scope,stratum=stratum,stratum_value=key,cp_scope=cp_scope,family=family,category=category,n=len(t),closed_n=len(closed),open_n=int((~t.closed).sum()),wins=nw,losses=nl,zeros=nz,win_rate=nw/len(closed) if len(closed) else np.nan,winner_coverage=nw/bw if bw else np.nan,loser_coverage=nl/bl if bl else np.nan,stratum_closed_n=len(baseclosed),stratum_wins=bw,stratum_losses=bl))
    if stratum in ['all','year','entry_quarter','market_regime','year x market_regime']:
     for outcome,t in [('closed_all',baseclosed),('win',baseclosed[baseclosed.round_pnl.gt(0)]),('loss',baseclosed[baseclosed.round_pnl.lt(0)])]:
      for f in features:
       v=t[f].replace([np.inf,-np.inf],np.nan).dropna()
       q=v.quantile([.25,.5,.75]) if len(v) else pd.Series([np.nan]*3,index=[.25,.5,.75])
       cont.append(dict(account=account,scope=scope,stratum=stratum,stratum_value=key,cp_scope=cp_scope,outcome=outcome,feature=f,closed_n=len(t),known_n=len(v),missing_n=len(t)-len(v),q25=q.loc[.25],median=q.loc[.5],q75=q.loc[.75],iqr=q.loc[.75]-q.loc[.25]))
g=pd.DataFrame(groups);c=pd.DataFrame(cont)
g.to_csv(O/'NATURAL_GROUPS.csv',index=False,float_format='%.17g')
c.to_csv(O/'CONTINUOUS_IQR.csv',index=False,float_format='%.17g')
quality=dict(actual_rows=len(d),unique_stock_signal_days=len(d[['sid','signal_day']].drop_duplicates()),stocks=d.sid.nunique(),all_source_rows_present=bool(d[['cp_source_present','facts_source_present','raw_source_present']].all().all()),ohlc_valid=int(d.source_ohlc_valid.sum()),raw_close_match_n=int(d.raw_close_error.le(1e-8).sum()),max_raw_close_error=float(d.raw_close_error.max()),cp_r_match_n=int(d.cp_r_error.le(1e-12).sum()),max_cp_r_error=float(d.cp_r_error.max()),zero_range_n=int(d['range'].eq(0).sum()),fresh_cp_n=int(d.fresh_cp.sum()),core_only_n=int(d.cp_status.eq('CORE_only_no_fresh_CP').sum()),nonfresh_other_n=int(d.cp_status.eq('nonfresh_other_or_unknown').sum()),fresh_r_nonpositive_n=int((d.fresh_cp&d.cp_r.le(0)).sum()),fresh_share_outside_01_n=int((d.fresh_frontier_share.lt(-1e-10)|d.fresh_frontier_share.gt(1+1e-10)).sum()),pvr_2022_sameyear_closed=692,pvr_2022_sameyear_wins=130,original_indicator_runs=0,account_runs=0,ranking_runs=0,parameter_scans=0,wall_seconds=time.time()-start)
changed=[]
for p,h in src.items():
 if sha(p)!=h:changed.append(p)
quality['source_sha256_unchanged']=not changed;quality['source_files_checked']=len(src);quality['source_files_changed']=changed
(O/'SOURCE_SHA256.json').write_text(json.dumps(src,ensure_ascii=False,indent=2))
(O/'QUALITY.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2))
print('QUALITY',json.dumps(quality,ensure_ascii=False),flush=True)
showcols=['category','n','closed_n','open_n','wins','losses','win_rate','winner_coverage','loser_coverage']
for account in ['PVR','E31']:
 print('\nACCOUNT',account)
 sel=g[(g.account==account)&(g.scope=='all_first_entries')&(g.stratum=='all')&(g.cp_scope=='all')]
 print(sel[['family']+showcols].to_string(index=False))
print('\nPVR YEAR x REGIME GAP BODY AND CLOSE HALF')
print(g[(g.account=='PVR')&(g.scope=='all_first_entries')&(g.stratum=='year x market_regime')&(g.cp_scope=='all')&g.family.isin(['gap_body','close_half'])][['stratum_value','family']+showcols].to_string(index=False))
print('\nPVR OVERALL CONTINUOUS')
print(c[(c.account=='PVR')&(c.scope=='all_first_entries')&(c.stratum=='all')&(c.cp_scope=='all')&c.outcome.isin(['win','loss'])].to_string(index=False))
