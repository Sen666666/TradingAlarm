"""Frozen v4: minimal warm breadth, separated momentum and causal state table."""
from pathlib import Path
from fractions import Fraction
from collections import deque
import hashlib,importlib.util,json,time,sys
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent;S=ROOT.parent
B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
OLD=S/'industry_selection/channels_v2';V3=S/'continuous_rank_v3/ranking'
EXPECTED='29af69f156ea9c14ea62ab5eea3fc1a7ee56dcdebdd33a3fc01d5e493e30e495';HASH={}
STATES=('I0','I1','A0','A1','A2');SNAP=['2022-01-24','2024-09-24','2026-01-15']
def bind(p,h=None):
 p=Path(p).resolve();z=hashlib.sha256(p.read_bytes()).hexdigest()
 if h is not None:assert z==h,(str(p),'source changed')
 HASH[str(p)]=z;return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple,set)):return [clean(x)for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and not np.isfinite(v):return None
 return v
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def module(name,p):
 p=bind(p);sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def pq(p,h=None,columns=None):
 f=pd.read_parquet(bind(p,h),columns=columns)
 if isinstance(f.index,pd.DatetimeIndex):f.index=f.index.as_unit('ns')
 return f
def advance(s,r):
 if r is None:return 'A0'if s[0]=='A'else'I0'
 if r<=5:return 'I1'if s=='I0'else'A0'
 if r<=10:return 'A0'if s[0]=='A'else'I0'
 return {'I0':'I0','I1':'I0','A0':'A1','A1':'A2','A2':'I0'}[s]
def maturity(states):
 x={s[0]=='A'for s in states};return next(iter(x))if len(x)==1 else None
def state_json(states):return json.dumps([s for s in STATES if s in states])
def exact_above20(close,valid):
 # Exact comparison on source binary floats, avoiding rolling-sum history drift.
 # Every finite binary64 is an integer multiple of 2**-1074.
 denominator=1<<1074;queue=deque();total=0;count=0;out=[]
 for value,ok in zip(close,valid):
  known=bool(ok)and pd.notna(value)and np.isfinite(value)
  if known:
   num,den=float(value).as_integer_ratio();integer=num*(denominator//den)
  else:integer=0
  queue.append((integer,known));total+=integer;count+=int(known)
  if len(queue)>20:
   old,oldknown=queue.popleft();total-=old;count-=int(oldknown)
  out.append(len(queue)==20 and count==20 and 20*integer>total)
 return pd.Series(out,index=close.index,dtype=bool)
def main():
 begun=time.monotonic();bind(__file__);bind(ROOT/'FROZEN_DESIGN.txt',EXPECTED)
 old=module('v4_unchanged_stock_state',OLD/'compute_opportunities.py');ranker=module('v4_exact_rank_helper',V3/'rank_daily.py')
 sm=read(B/'STOCK_MANIFEST.json');im=read(B/'INDUSTRY_MANIFEST.json');meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 cp=read(M/'checkpoints/USHI1B0300.json');market=pd.read_csv(bind(M/'canonical/USHI1B0300.csv',cp['canonical_sha256']),parse_dates=['date']).set_index('date');market.index=market.index.as_unit('ns')
 warm=market.index[(market.index>='2021-01-01')&(market.index<='2021-12-31')];dates=market.index[(market.index>='2021-01-01')&(market.index<='2026-06-30')]
 a=market.index.get_loc(warm[0]);warmcal=market.index[a-29:market.index.get_loc(warm[-1])+1];rpcal=market.index[a-60:market.index.get_loc(dates[-1])+1]
 sectors=sorted(r['series']for r in im);si={s:i for i,s in enumerate(sectors)};n=len(warmcal)
 agg={k:np.zeros((90,n))for k in ['N_U_t','N25valid','Nobserved','N_above20_t','N_above20_tminus5']}
 if '--reuse-warm' in sys.argv:
  reuse=read(O/'WARM_REUSE_BINDING.json')
  for p,h in reuse.items():bind(p,h)
  wb=pq(O/'WARMUP_BREADTH_2021.parquet',reuse[str(O/'WARMUP_BREADTH_2021.parquet')]);assert len(wb)==243*90
  for r in sm:
   p=next(p for p in r['source_sha256']if '/prepared'in p and p.endswith('/signal.parquet'));bind(p,r['source_sha256'][p])
  bind(O/'FIRST_ATTEMPT_run_v4.py');bind(O/'FIRST_ATTEMPT_run_v4.log')
  print(json.dumps({'reused_completed_warm_rows':len(wb),'stock_sources_hash_verified':len(sm)}),flush=True)
 else:
  prefix_checks=[];prefix_sids={sorted(r['symbol']for r in sm)[0],'000988.SZ','300085.SZ'}
  for j,r in enumerate(sm):
   sid=r['symbol'];k=si[meta[sid]['sector_id']];p=next(p for p in r['source_sha256']if '/prepared'in p and p.endswith('/signal.parquet'))
   signal=pq(p,r['source_sha256'][p],old.COLS).loc[:'2021-12-31'];x=old.stock_state(signal,warmcal);u=x['U']
   close=pd.to_numeric(signal.reindex(warmcal).close,errors='coerce');above=exact_above20(close,x['observed_price']);above5=above.shift(5,fill_value=False)
   if sid in prefix_sids:
    for end in [warm[0],warm[len(warm)//2],warm[-1]]:
     check=exact_above20(close.loc[:end],x['observed_price'].loc[:end]);assert check.equals(above.loc[:end])
     prefix_checks.append({'sid':sid,'end':str(end.date()),'exact_binary_prefix_identical':True})
   for name,v in [('N_U_t',u),('N25valid',x['N25valid']),('Nobserved',x['observed_price']),('N_above20_t',u&above),('N_above20_tminus5',u&above5)]:agg[name][k]+=v.to_numpy(float)
   if(j+1)%400==0:print(json.dumps({'warm_stock_sources':j+1,'required':len(sm),'seconds':time.monotonic()-begun}),flush=True)
  frames=[]
  for sec,k in si.items():
   f=pd.DataFrame(index=warmcal);f['sector_id_static']=sec;f['industry_static']=next(meta[r['symbol']]['industry']for r in sm if meta[r['symbol']]['sector_id']==sec)
   for col in agg:f[col]=agg[col][k].astype(int)
   q=f.N_U_t.gt(0);f['B_now']=(f.N_above20_t/f.N_U_t).where(q);f['B_lag5_pairedU']=(f.N_above20_tminus5/f.N_U_t).where(q)
   f['dB5_paired']=((f.N_above20_t-f.N_above20_tminus5)/f.N_U_t).where(q)
   frames.append(f.loc[warm].reset_index(names='date'))
  wb=pd.concat(frames,ignore_index=True);wb['date']=wb.date.dt.strftime('%Y-%m-%d');wb.to_parquet(O/'WARMUP_BREADTH_2021.parquet',index=False)
  save('EXACT_ABOVE20_PREFIX_CHECKS.json',prefix_checks)
  save('WARM_REUSE_BINDING.json',{str((O/n).resolve()):hashlib.sha256((O/n).read_bytes()).hexdigest()for n in ['WARMUP_BREADTH_2021.parquet','EXACT_ABOVE20_PREFIX_CHECKS.json']})
 cols=['date','sector_id_static','industry_static','rs_ind5','B_now','B_lag5_pairedU','dB5_paired','N_U_t','N25valid','Nobserved','N_above20_t','N_above20_tminus5','B_lag5_ownU','N_U_previous5']
 prior=pq(OLD/'INDUSTRY_OPPORTUNITIES_DAILY.parquet',columns=cols);assert len(prior)==97650
 # Boundary proof uses old shifted own-U diagnostics; no2022 stock recompute.
 boundary=[];wlookup=wb.set_index(['date','sector_id_static']);indexer={str(d.date()):i for i,d in enumerate(market.index)}
 for r in prior[prior.date.isin(sorted(prior.date.unique())[:5])].itertuples():
  lag=str(market.index[indexer[r.date]-5].date());w=wlookup.loc[(lag,r.sector_id_static)]
  nmatch=int(w.N_U_t)==int(r.N_U_previous5)
  bmatch=(pd.isna(w.B_now)and pd.isna(r.B_lag5_ownU))or float(w.B_now)==float(r.B_lag5_ownU)
  boundary.append({'old_date':r.date,'warm_date':lag,'sector_id_static':r.sector_id_static,'N_U_exact':nmatch,'B_exact':bmatch,'warm_binary_B':w.B_now,'old_saved_B':r.B_lag5_ownU})
 assert all(x['N_U_exact']for x in boundary),'Non-floating cohort boundary mismatch'
 save('WARM_BOUNDARY_REUSE_CHECK.json',{'old2022_not_recomputed':True,'warm2021_end_vs_old_ownU_shift5_checks':boundary,'all_B_exact':all(x['B_exact']for x in boundary),'B_mismatches':sum(not x['B_exact']for x in boundary),'2021_comparison':'exact source-binary20-window','2022_comparison':'original saved pandas rolling; unchanged'})
 inputs=pd.concat([wb,prior],ignore_index=True);inputs=inputs.drop(columns=['rs_ind5'],errors='ignore')
 price=[]
 for r in im:
  f=pq(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']],['close','segment_id']).reindex(rpcal);I=f.close;Mkt=market.close.reindex(rpcal);seg=f.segment_id
  v=I.gt(0)&np.isfinite(I)&seg.notna()&Mkt.gt(0)&np.isfinite(Mkt)
  complete56=v.shift(5).rolling(56,min_periods=56).sum().eq(56)&seg.shift(5).rolling(56,min_periods=56).max().eq(seg.shift(5).rolling(56,min_periods=56).min())
  Rp=(np.log(I.shift(5)/I.shift(60))-np.log(Mkt.shift(5)/Mkt.shift(60))).where(complete56)
  six=v.rolling(6,min_periods=6).sum().eq(6)&seg.rolling(6,min_periods=6).max().eq(seg.rolling(6,min_periods=6).min())
  R5=(np.log(I/I.shift(5))-np.log(Mkt/Mkt.shift(5))).where(six)
  z=pd.DataFrame({'Rp':Rp.reindex(dates),'rs_ind5':R5.reindex(dates)},index=dates).reset_index(names='date');z['date']=z.date.dt.strftime('%Y-%m-%d');z['sector_id_static']=r['series'];price.append(z)
 inputs=inputs.merge(pd.concat(price,ignore_index=True),on=['date','sector_id_static'],validate='one_to_one');assert len(inputs)==119520
 # Keep T's old rawR5 bit-for-bit, and assert the newly read price projection agrees.
 chk=inputs[inputs.date.ge('2022-01-01')].merge(prior[['date','sector_id_static','rs_ind5']],on=['date','sector_id_static'],suffixes=('_new','_old'))
 assert np.allclose(chk.rs_ind5_new,chk.rs_ind5_old,equal_nan=True,rtol=0,atol=1e-14)
 raw5=prior.set_index(['date','sector_id_static']).rs_ind5
 for i in inputs.index[inputs.date.ge('2022-01-01')]:inputs.at[i,'rs_ind5']=raw5.loc[(inputs.at[i,'date'],inputs.at[i,'sector_id_static'])]
 vcols=['date','sector_id_static','A_known','E_known','D_known','H1_known','E_score','E_score_exact','native_E_selected','native_UNION_selected','N_native_union','common_H1_selected','D_score','D_score_exact','H1_cache_same_date_score','native_D_order','native_H1_order']
 v3=pq(V3/'DAILY_RANKINGS.parquet',columns=vcols);v3=v3.rename(columns={c:'v3_'+c for c in vcols if c not in ['date','sector_id_static']})
 inputs=inputs.merge(v3,on=['date','sector_id_static'],how='left',validate='one_to_one')
 possible={s:set(STATES)for s in sectors};previous={s:None for s in sectors};rows=[];daily=[]
 for day,g in inputs.groupby('date',sort=True):
  g=g.copy().reset_index(drop=True);ps={}
  for raw,pcol in [('Rp','p_Rp'),('B_now','p_B'),('rs_ind5','p_R5'),('dB5_paired','p_dB5')]:
   known=g[raw].notna();N=int(known.sum());vals={i:None for i in g.index};g[pcol]=np.nan;g[pcol+'_referenceN']=N
   if N:
    units=2*g.loc[known,raw].rank(method='average')-1
    for i,u in units.items():vals[i]=Fraction(int(u),2*N);g.at[i,pcol]=float(vals[i])
   ps[pcol]=vals
  P={i:(3*ps['p_Rp'][i]+2*ps['p_B'][i])/5 if ps['p_Rp'][i]is not None and ps['p_B'][i]is not None else None for i in g.index}
  T={i:(ps['p_R5'][i]+ps['p_dB5'][i])/2 if ps['p_R5'][i]is not None and ps['p_dB5'][i]is not None else None for i in g.index}
  for name,z in [('P',P),('T',T)]:g[name+'_score']=[float(z[i])if z[i]is not None else np.nan for i in g.index];g[name+'_score_exact']=[str(z[i])if z[i]is not None else None for i in g.index];g[name+'_known']=[z[i]is not None for i in g.index]
  ranker.assign_exact_queue(g,'P',P,None);ranker.assign_exact_queue(g,'T',T,3)
  before=[];after=[];public=[];prev=[];events=[];new=[];removed=[];resup=[];resdown=[];cntI=[];cntA=[]
  for i,r in g.iterrows():
   sec=r.sector_id_static;b=possible[sec];rank=int(r.P_order)if r.P_known else None;a={advance(s,rank)for s in b};bm=maturity(b);am=maturity(a);prev.append(previous[sec])
   out=am if rank is not None else None
   isnew=rank is not None and bm is False and am is True;isexit=rank is not None and bm is True and am is False
   if rank is None:event='INPUT_MISSING'
   elif isnew:event='NEW_MATURE'
   elif isexit:event='REMOVED'
   elif bm is None and am is True:event='RESOLVED_ACTIVE'
   elif bm is None and am is False:event='RESOLVED_INACTIVE'
   elif previous[sec]is None and out is True:event='DATA_RESUME_ACTIVE'
   elif previous[sec]is None and out is False:event='DATA_RESUME_INACTIVE'
   else:event='AMBIGUOUS'if out is None else'RETAIN_ACTIVE'if out else'RETAIN_INACTIVE'
   before.append(state_json(b));after.append(state_json(a));public.append(out);events.append(event);new.append(isnew);removed.append(isexit)
   resup.append(previous[sec]is None and out is True and not isnew);resdown.append(previous[sec]is None and out is False and not isexit)
   cntI.append(json.dumps(sorted({int(s[1])for s in a if s[0]=='I'})));cntA.append(json.dumps(sorted({int(s[1])for s in a if s[0]=='A'})))
   possible[sec]=a;previous[sec]=out
  g['possible_states_before']=before;g['possible_states_after']=after;g['P_entry_counts_possible']=cntI;g['P_exit_counts_possible']=cntA
  g['P_mature']=pd.Series(public,dtype='boolean');g['P_prevpublic']=pd.Series(prev,dtype='boolean');g['P_state_event']=events
  g['P_known_new_maturity']=new;g['P_known_exit']=removed;g['P_unknown_to_true']=resup;g['P_unknown_to_false']=resdown;g['P_input_missing_counter_break']=~g.P_known
  g['UNION_selected']=g.P_mature|g.T_selected
  g['channel_label']=[('P_TRUE_T_UNKNOWN'if bool(p)else'P_FALSE_T_UNKNOWN')if pd.isna(t)and not pd.isna(p)else('P_UNKNOWN_T_TRUE'if bool(t)else'P_UNKNOWN_T_FALSE')if pd.isna(p)and not pd.isna(t)else'UNKNOWN'if pd.isna(p)or pd.isna(t)else'BOTH'if p and t else'P_ONLY'if p else'T_ONLY'if t else'NONE'for p,t in zip(g.P_mature,g.T_selected)]
  study=day>='2022-01-01';g['warmup']=not study;g['membership_PIT_verified']=False;g['formal_PIT_union']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  allknown=bool(study and g.P_known.all()and g.T_known.all()and g.P_mature.notna().all()and g[['v3_A_known','v3_E_known','v3_D_known','v3_H1_known']].eq(True).all().all())
  lower=int(g.UNION_selected.eq(True).sum());unknown=int(g.UNION_selected.isna().sum());actual=lower if allknown else None
  g['main_day90known']=allknown;g['N_union_actual']=pd.Series([actual]*len(g),dtype='Int64');g['N_union_true_lower_bound']=lower;g['N_union_unknown']=unknown
  g['main_H1_selected']=pd.Series(pd.NA,index=g.index,dtype='boolean');g['main_D_selected']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  if allknown:
   g['main_H1_selected']=g.v3_native_H1_order.le(actual).astype('boolean');g['main_D_selected']=g.v3_native_D_order.le(actual).astype('boolean')
   assert g.main_H1_selected.sum()==g.main_D_selected.sum()==actual
  if study:
   assert g.T_score_exact.eq(g.v3_E_score_exact).all(),(day,'T score changed from v3 E')
   assert g.T_selected.eq(g.v3_native_E_selected).all(),(day,'T queue changed from v3 E')
  rows.append(g);daily.append({'date':day,'warmup':not study,'P_true_lower_bound':int(g.P_mature.eq(True).sum()),'P_unknown':int(g.P_mature.isna().sum()),'T_true':int(g.T_selected.eq(True).sum()),'UNION_true_lower_bound':lower,'UNION_unknown':unknown,'main_day90known':allknown,'N_union_actual':actual})
  if day in ['2021-12-31',*SNAP]:
   save('EARLY_'+day+'.json',{'date':day,'daily':daily[-1],'mature':g.loc[g.P_mature.eq(True),'industry_static'].tolist(),'T3':g.loc[g.T_selected.eq(True),'industry_static'].tolist(),'focal':g.loc[g.industry_static.isin(['半导体','软件开发','通信设备','房地产']),['industry_static','Rp','P_score','P_order','possible_states_before','possible_states_after','P_mature','T_order','T_selected','UNION_selected']].to_dict('records')});print(json.dumps(clean({'date':day,**daily[-1]})),flush=True)
 table=pd.concat(rows,ignore_index=True).sort_values(['date','sector_id_static']);table.to_parquet(O/'STATES_ALL_2021_2026.parquet',index=False);table.to_csv(O/'STATES_ALL_2021_2026.csv',index=False)
 study=table[~table.warmup].copy();study.to_parquet(O/'STUDY_STATES_2022_2026.parquet',index=False);pd.DataFrame(daily).to_csv(O/'DAILY_COUNTS.csv',index=False)
 save('SUMMARY.json',{'complete':True,'all_rows':len(table),'study_rows':len(study),'warm_rows':len(wb),'study_sessions':study.date.nunique(),'warm_sessions':len(warm),'main_known_days':sum(x['main_day90known']for x in daily),'T_score_and_selection_exact_v3_all97650':True,'new_accounts':0,'new_future_labels':0,'seconds':time.monotonic()-begun})
 save('SOURCE_SHA256.json',HASH);save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name not in ['OUTPUT_SHA256.json','run_v4.log']})
 print(json.dumps({'complete':True,'rows':len(table),'seconds':time.monotonic()-begun}),flush=True)
if __name__=='__main__':main()
