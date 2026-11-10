"""Frozen industry opportunity diagnostics and saved-price paths; no strategy/account."""
from pathlib import Path
import collections,hashlib,json,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;S=P.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
MP=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
sha={};begun=time.monotonic()
def bind(p,h=None):
 p=Path(p)
 if str(p) not in sha:sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 if h is not None:assert sha[str(p)]==h,('source changed',str(p))
 return p
def dump(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def ds(x):return pd.Timestamp(x).strftime('%Y-%m-%d')
def flags(f,k,v):return f[k].eq(v).fillna(False).to_numpy(dtype=bool)
def save(name,f,parquet=True):
 f.to_csv(O/(name+'.csv'),index=False)
 if parquet:f.to_parquet(O/(name+'.parquet'),index=False)
def window(date):return '2022_2023' if date[:4]<='2023' else '2024' if date[:4]=='2024' else '2025_2026H1'
bind(P/'FROZEN_CHANNELS_DESIGN.txt');bind(O/'EXECUTION_CONTRACT.txt')
d=pd.read_parquet(bind(S/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet')).sort_values(['date','sector_id_static']).reset_index(drop=True)
assert len(d)==97650 and not d.duplicated(['date','sector_id_static']).any()
d['study_window']=d.date.map(window);d['month']=d.date.str[:7]
m=pd.read_csv(bind(MP),parse_dates=['date']).set_index('date');cal=m.index;market=m.close.to_numpy(dtype=float)
assert d.date.nunique()==1085 and d.sector_id_static.nunique()==90
assert d.groupby('date').size().eq(90).all()
# Daily transition statistics consume saved state/prevsession, not recomputed thresholds.
daily=[];mat=[]
def mode(c,s):
 if pd.isna(c) or pd.isna(s):return 'UNKNOWN_PARTIAL'
 return 'BOTH' if c and s else 'CONT_ONLY' if c else 'START_ONLY' if s else 'NONE'
for date,g in d.groupby('date',sort=True):
 for ch in ['CONT','START','UNION']:
  c=g[ch].astype('boolean');p=g[ch+'_prevsession'].astype('boolean');known=c.notna()&p.notna()
  ct=c.fillna(False);pt=p.fillna(False);inter=int((known&ct&pt).sum());den=int((known&(ct|pt)).sum());prevact=int((known&pt).sum())
  daily.append({'date':date,'study_window':window(date),'month':date[:7],'channel':ch,'industries':len(g),'known_current':int(c.notna().sum()),'unknown_current':int(c.isna().sum()),
   'active':int(c.eq(True).sum()),'common_known_with_previous':int(known.sum()),'intersection':inter,'union_pair':den,
   'jaccard_known_pair':inter/den if den else np.nan,'previous_active_retention_known_pair':inter/prevact if prevact else np.nan,
   'known_entries':int((known&~pt&ct).sum()),'known_exits':int((known&pt&~ct).sum()),'true_to_unknown':int((p.eq(True)&c.isna()).sum()),'unknown_to_true':int((p.isna()&c.eq(True)).sum())})
 for _,r in g.iterrows():
  prev=mode(r.CONT_prevsession,r.START_prevsession);cur=mode(r.CONT,r.START)
  mat.append({'date':date,'study_window':window(date),'month':date[:7],'sector_id_static':r.sector_id_static,'previous_label':prev,'current_label':cur,
   'label_change_union_stays_true':bool(prev in ['BOTH','CONT_ONLY','START_ONLY'] and cur in ['BOTH','CONT_ONLY','START_ONLY'] and prev!=cur)})
dc=pd.DataFrame(daily);save('DAILY_COUNTS_TRANSITIONS_JACCARD',dc)
tm=pd.DataFrame(mat);save('GROUP_LABEL_TRANSITIONS',tm)
tm.groupby(['study_window','previous_label','current_label']).size().rename('industry_day_transitions').reset_index().to_csv(O/'GROUP_TRANSITION_MATRIX_BY_WINDOW.csv',index=False)
dc.groupby(['study_window','channel']).agg(days=('date','size'),mean_active=('active','mean'),median_active=('active','median'),min_active=('active','min'),max_active=('active','max'),
 known_entries=('known_entries','sum'),known_exits=('known_exits','sum'),unknown_current=('unknown_current','sum'),mean_jaccard=('jaccard_known_pair','mean')).reset_index().to_csv(O/'TRANSITIONS_BY_WINDOW.csv',index=False)
print('DAILY_STATE_COMPLETE',round(time.monotonic()-begun,2),flush=True)
# Original industry prepared prices, extended only through already-saved October22.
im={r['series']:r for r in json.loads(bind(U/'INDUSTRY_MANIFEST.json').read_text())};labels=[];source=[];rs_checks=[]
for k,(sector,g) in enumerate(d.groupby('sector_id_static',sort=True),1):
 rec=im[sector];sp=[p for p in rec['source_sha256'] if '/prepared' in p and p.endswith('/signal.parquet')];assert len(sp)==1
 sp=sp[0];f=pd.read_parquet(bind(sp,rec['source_sha256'][sp])).loc[:'2026-10-22'];assert f.index.is_unique and f.index.is_monotonic_increasing
 qpath=rec['refs']['CP1_input'];q=pd.read_parquet(bind(qpath,rec['output_sha256'][qpath]),columns=['close','segment_id'])
 ix=f.index.intersection(q.index);pd.testing.assert_frame_equal(f.loc[ix,['close','segment_id']],q.loc[ix,['close','segment_id']],check_dtype=False,check_exact=True,check_freq=False)
 fc=f.reindex(cal);c=pd.to_numeric(fc.close,errors='coerce').to_numpy(dtype=float);seg=pd.to_numeric(fc.segment_id,errors='coerce').to_numpy(dtype=float)
 priceok=np.isfinite(c)&(c>0)&flags(fc,'observed_bar',True)&flags(fc,'price_eligible',True)&flags(fc,'source_invalid',False)&flags(fc,'synthetic_event_bar',False)&np.isfinite(seg)
 pos=cal.get_indexer(pd.to_datetime(g.date));assert (pos>=20).all()
 rr=np.log(c[pos]/c[pos-20])-np.log(market[pos]/market[pos-20]);diff=rr-g.rs_ind20.to_numpy(dtype=float)
 good=np.isfinite(diff);assert not good.any() or float(np.abs(diff[good]).max())<1e-12
 rs_checks.append({'sector':sector,'known_comparisons':int(good.sum()),'max_abs_rs20_diff':float(np.abs(diff[good]).max()) if good.any() else None})
 out=pd.DataFrame({'date':g.date.to_numpy(),'sector_id_static':sector,'index_close_T':c[pos],'source_segment_T':seg[pos]})
 for h in [5,20]:
  rawix=pos[:,None]+np.arange(h+1)[None,:];inrange=(rawix[:,-1]<len(cal));ind=np.minimum(rawix,len(cal)-1)
  cp=c[ind];sg=seg[ind];mk=market[ind]
  validprices=priceok[ind].all(axis=1)&np.isfinite(mk).all(axis=1)&(mk>0).all(axis=1)
  same=np.isfinite(sg).all(axis=1)&(sg==sg[:,[0]]).all(axis=1)
  valid=inrange&validprices&same
  status=np.where(~inrange,'RIGHT_CENSORED_REFERENCE_SOURCE_END',np.where(~priceok[pos],'CURRENT_INDEX_SOURCE_INVALID',np.where(~validprices,'FUTURE_PRICE_OBSERVATION_MISSING_OR_INVALID',np.where(~same,'INDUSTRY_SOURCE_SEGMENT_BOUNDARY','COMPLETE'))))
  with np.errstate(invalid='ignore',divide='ignore'):
   qa=np.log(cp[:,1:]/cp[:,[0]]);qr=qa-np.log(mk[:,1:]/mk[:,[0]])
  out[f'label_valid{h}']=valid;out[f'label_status{h}']=status
  out[f'label_end{h}']=[ds(cal[p+h]) if p+h<len(cal) else None for p in pos]
  out[f'calendar_span_days{h}']=[int((cal[p+h]-cal[p]).days) if p+h<len(cal) else np.nan for p in pos]
  for tag,ar in [('abs',qa),('rel',qr)]:
   out[f'final{h}_{tag}_log']=np.where(valid,ar[:,-1],np.nan)
   out[f'mfe{h}_{tag}_log']=np.where(valid,np.maximum(0,np.max(ar,axis=1)),np.nan)
   out[f'mae{h}_{tag}_log']=np.where(valid,np.minimum(0,np.min(ar,axis=1)),np.nan)
  out[f'future_missing_or_invalid_index_sessions{h}']=(~priceok[ind[:,1:]]).sum(axis=1)
 labels.append(out);source.append({'sector':sector,'prepared_source':sp,'prepared_sha256':sha[sp],'source_first':ds(f.index.min()),'source_last':ds(f.index.max()),'CP_input_source':qpath,'exact_coordinate_rows':len(ix)})
 if k%30==0:print('PRICE_LABELS',k,round(time.monotonic()-begun,2),flush=True)
lp=pd.concat(labels,ignore_index=True);assert len(lp)==len(d)
save('INDUSTRY_PRICE_PATH_LABELS',lp)
dd=d.merge(lp,on=['date','sector_id_static'],validate='one_to_one');dd.to_parquet(O/'DAILY_STATES_WITH_PRICE_LABELS.parquet',index=False)
# Observed true-runs are clipped at frozen study boundaries; unknown stops are censored, not exits.
spells=[]
for (sector,win),g in dd.groupby(['sector_id_static','study_window'],sort=True):
 g=g.sort_values('date');dates=g.date.to_numpy();indices=g.index.to_numpy()
 for ch in ['CONT','START','UNION']:
  st=g[ch].astype('Float64').to_numpy(dtype=float,na_value=np.nan);start=None;left=None;start_reason=None
  def emit(end,exitdate,right,why):
   nonlocal_placeholder=None
   row={'spell_id':ch+'|'+sector+'|'+win+'|'+dates[start],'channel':ch,'sector_id_static':sector,'study_window':win,'start':dates[start],'end_last_true':dates[end],
    'exit_date_known_false':exitdate,'active_common_sessions':int(end-start+1),'left_censored':bool(left),'right_censored':bool(right),'start_reason':start_reason,'stop_reason':why,
    'known_new_entry':bool(not left),'complete_uncensored_spell':bool(not left and not right),'first_day_row_index':int(indices[start])}
   spells.append(row)
  for j,v in enumerate(st):
   if v==1:
    if start is None:
     start=j;left=j==0 or np.isnan(st[j-1]);start_reason='WINDOW_HEAD_ACTIVE' if j==0 else 'RECOVERED_AFTER_UNKNOWN' if np.isnan(st[j-1]) else 'KNOWN_FALSE_TO_TRUE'
   elif start is not None:
    if v==0:emit(j-1,dates[j],False,'KNOWN_TRUE_TO_FALSE')
    else:emit(j-1,None,True,'INPUT_UNKNOWN_NOT_ECONOMIC_EXIT')
    start=None
  if start is not None:emit(len(st)-1,None,True,'WINDOW_END_ACTIVE')
sp=pd.DataFrame(spells);labelcols=[c for c in lp.columns if c not in ['date','sector_id_static']]
first=sp.merge(dd[['date','sector_id_static']+labelcols].rename(columns={'date':'start'}),on=['start','sector_id_static'],validate='many_to_one')
save('SPELLS_AND_FIRST_DAY_PRICE_LABELS',first)
spellstat=[]
for (win,ch),g in first.groupby(['study_window','channel']):
 complete=g[g.complete_uncensored_spell]
 z={'study_window':win,'channel':ch,'observed_true_runs':len(g),'left_censored':int(g.left_censored.sum()),'right_censored':int(g.right_censored.sum()),'complete_uncensored_spells':len(complete),
  'median_complete_duration':float(complete.active_common_sessions.median()) if len(complete) else np.nan}
 for h in [1,3,5]:z[f'complete_duration_le{h}_count']=int(complete.active_common_sessions.le(h).sum());z[f'complete_duration_le{h}_rate']=float(complete.active_common_sessions.le(h).mean()) if len(complete) else np.nan
 spellstat.append(z)
save('SPELL_DURATION_AND_CENSORING_BY_WINDOW',pd.DataFrame(spellstat))
# All active days and observed run first days; no conditioning on future outcome.
samples=[]
for ch in ['CONT','START','UNION']:
 active=dd[dd[ch].eq(True)].copy();active['channel']=ch;active['sample']='ACTIVE_DAYS';active['left_censored_first_day']=False;samples.append(active)
 fs=first[first.channel.eq(ch)].copy().rename(columns={'start':'date'});fs['sample']='SPELL_FIRST_DAYS';fs['left_censored_first_day']=fs.left_censored;samples.append(fs)
sample=pd.concat(samples,ignore_index=True,sort=False)
outstats=[]
for dims in [['study_window','channel','sample'],['month','channel','sample']]:
 if dims[0]=='month':sample['month']=sample.date.str[:7]
 for keys,g in sample.groupby(dims):
  z=dict(zip(dims,keys));z['industry_observations']=len(g);z['distinct_industries']=g.sector_id_static.nunique();z['left_censored_first_days']=int(g.left_censored_first_day.eq(True).sum())
  for h in [5,20]:
   z[f'label_valid{h}']=int(g[f'label_valid{h}'].eq(True).sum())
   for col in [f'final{h}_abs_log',f'final{h}_rel_log',f'mfe{h}_abs_log',f'mae{h}_abs_log',f'mfe{h}_rel_log',f'mae{h}_rel_log']:
    v=g[col].dropna();z[col+'_mean']=float(v.mean()) if len(v) else np.nan;z[col+'_median']=float(v.median()) if len(v) else np.nan;z[col+'_p10']=float(v.quantile(.1)) if len(v) else np.nan;z[col+'_p90']=float(v.quantile(.9)) if len(v) else np.nan
   for tag in ['abs','rel']:
    v=g[f'final{h}_{tag}_log'].dropna();z[f'final{h}_{tag}_nonpositive_count']=int(v.le(0).sum());z[f'final{h}_{tag}_nonpositive_rate']=float(v.le(0).mean()) if len(v) else np.nan
  outstats.append(z)
stat=pd.DataFrame(outstats);save('ACTIVE_AND_FIRST_DAY_PATH_DISTRIBUTIONS',stat)
cross=[]
for (win,ch),g in first[first.complete_uncensored_spell].groupby(['study_window','channel']):
 for sh in [1,3,5]:
  for h in [5,20]:
   for tag in ['abs','rel']:
    gg=g[g[f'label_valid{h}'].eq(True)];short=gg.active_common_sessions.le(sh);nonpos=gg[f'final{h}_{tag}_log'].le(0)
    for a in [False,True]:
     for b in [False,True]:cross.append({'study_window':win,'channel':ch,'short_horizon':sh,'path_horizon':h,'path_type':tag,'short_license':a,'final_nonpositive':b,'count':int((short.eq(a)&nonpos.eq(b)).sum()),'complete_spell_price_valid_denominator':len(gg),'complete_spell_denominator_before_price_valid':len(g)})
save('SHORT_LICENSE_X_FUTURE_NONPOSITIVE',pd.DataFrame(cross))
# Pair-vs-ownU change direction uses source integer counts, not floating epsilon comparisons.
lookup={(r.sector_id_static,r.date):(int(r.N_above20_t),int(r.N_U_t)) for r in dd.itertuples()};pairs=[]
for r in dd.itertuples():
 pos=int(cal.get_loc(pd.Timestamp(r.date)));past=ds(cal[pos-5]);old=lookup.get((r.sector_id_static,past));known=old is not None and r.N_U_t>0 and old[1]>0
 pair_up=r.N_above20_t>r.N_above20_tminus5
 own_up=(int(r.N_above20_t)*old[1]>old[0]*int(r.N_U_t)) if known else None
 pairs.append({'date':r.date,'study_window':r.study_window,'sector_id_static':r.sector_id_static,'N_U_t':r.N_U_t,'U_joiners1':r.U_joiners1,'U_leavers1':r.U_leavers1,
  'U_joiners5':r.U_joiners5,'U_leavers5':r.U_leavers5,'B_now':r.B_now,'B_lag5_pairedU':r.B_lag5_pairedU,'B_lag5_ownU':r.B_lag5_ownU,
  'dB5_paired':r.dB5_paired,'dB5_ownU':r.dB5_ownU,'paired_change_positive_integer':bool(pair_up),'ownU_change_positive_exact':own_up,'ownU_exact_diagnostic_known':known,
  'paired_own_direction_disagree':bool(pair_up!=own_up) if known else None,'scope':'Coverage diagnostic only; no alternate START gate calculated.'})
pa=pd.DataFrame(pairs);save('PAIRED_BREADTH_VS_HISTORICAL_OWNU_DIAGNOSTIC',pa)
source_summary={'source':source,'rs20_source_checks':rs_checks};dump('PRICE_SOURCE_BINDINGS_AND_COORDINATE_CHECKS.json',source_summary)
summary={'daily_rows':len(dd),'sessions':dd.date.nunique(),'industries':dd.sector_id_static.nunique(),'unknown_UNION_rows':int(dd.UNION.isna().sum()),
 'future5_complete':int(dd.label_valid5.sum()),'future20_complete':int(dd.label_valid20.sum()),'future5_status':dd.label_status5.value_counts().to_dict(),'future20_status':dd.label_status20.value_counts().to_dict(),
 'observed_spells':len(first),'complete_uncensored_spells':int(first.complete_uncensored_spell.sum()),'left_censored_spells':int(first.left_censored.sum()),'right_censored_spells':int(first.right_censored.sum()),
 'label_changes_union_stays_true':int(tm.label_change_union_stays_true.sum()),'pair_own_direction_disagree':int(pa.paired_own_direction_disagree.eq(True).sum()),'pair_own_direction_unknown':int((~pa.ownU_exact_diagnostic_known).sum()),
 'no_new_thresholds_or_accounts_or_trade_returns':True,'seconds':time.monotonic()-begun}
bind(__file__);dump('SOURCE_SHA256.json',sha);dump('SUMMARY.json',summary)
print(json.dumps(summary,ensure_ascii=False),flush=True)
