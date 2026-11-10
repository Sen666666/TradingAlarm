"""Descriptive, causal-feature decomposition of sealed one-arm results. No economic rerun."""
from pathlib import Path
import pandas as pd, numpy as np, json, hashlib, time
O=Path(__file__).resolve().parent;R=O.parent;F=R/'fast_entry_equity_2022_v1';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
S={}
def src(p):
 p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def js(p):return json.loads(src(p).read_text())
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<='2026-06-30'];di={d:i for i,d in enumerate(cal)}
a=pd.read_parquet(src(F/'ALL_MARKET_INPUTS_2022.parquet'));startup=pd.read_parquet(src(F/'STARTUP_MARKET_INPUTS.parquet'));targets=pd.concat([a[['sid','day']],startup[['sid','day']]]).drop_duplicates();sm=js(U/'STOCK_MANIFEST.json');im=js(U/'INDUSTRY_MANIFEST.json');rows=[]
def fullfields(f,lineage):
 f=f.reindex(cal).copy();
 for col in ["i_target","i_floor","i_buy","g_grade","g_fresh_up","g_acute_down"]:
  if col not in f:f[col]=np.nan
 for col in f:f[col]=pd.to_numeric(f[col],errors="coerce").astype(float)
 lin=lineage.reindex(cal);adj=f.segment_id.notna()&f.segment_id.eq(f.segment_id.shift())
 for c in ['source_kind','source_path','segment_id']:adj &=lin[c].notna()&lin[c].shift().notna()&lin[c].eq(lin[c].shift())
 o=f.copy();o['adjacent']=adj
 for nm,field in [('I','i_target'),('E0','e0_target')]:
  known=f[field].isin([0,1])&f.segment_id.notna();birth=f[field].eq(1)&f[field].shift().eq(0)&adj&known&known.shift(fill_value=False)
  roots=[];root=None;prevpeak=None;peak=None
  lastroot=[];previous_peak=[]
  for i,(on,k,ad,bo,cl) in enumerate(zip(f[field],known,adj,birth,f.close)):
   if not k or not ad:root=None;peak=None;prevpeak=None
   if bo:root=i;peak=cl
   if k and on==0:
    if peak is not None:prevpeak=peak
    root=None;peak=None
   elif k and on==1 and root is not None:peak=max(peak,cl)
   roots.append(root);previous_peak.append(prevpeak)
  ri=pd.Series(roots,index=cal,dtype=float);o[nm+'_birth']=birth;o[nm+'_root_idx']=ri;o[nm+'_age']=np.arange(len(f))-ri;o[nm+'_previous_phase_peak']=np.array(previous_peak,dtype=float)
  o[nm+'_root_day']=[str(cal[int(v)].date()) if pd.notna(v) else None for v in ri]
  if nm=='I':
   o['i_buy_ordinal']=f.i_buy.eq(True).groupby(ri).cumsum().where(ri.notna())
 o['I_birth_ordinal_in_E0']=o.I_birth.groupby(o.E0_root_idx).cumsum().where(o.E0_root_idx.notna())
 o['previous_G']=f.g_grade.shift();o['G_delta']=(f.g_grade-f.g_grade.shift()).where(adj);o['G_direction']=np.where(o.G_delta>0,'UP',np.where(o.G_delta<0,'DOWN',np.where(o.G_delta==0,'SAME','UNKNOWN')))
 o['distance_I_log']=np.log(pd.to_numeric(f.close/f.i_floor,errors="coerce").astype(float));o['distance_E0_log']=np.log(pd.to_numeric(f.close/f.e0_floor,errors="coerce").astype(float))
 o['close_above_previous_I_peak']=np.where(o.I_previous_phase_peak.isna(), 'UNKNOWN',np.where(f.close>o.I_previous_phase_peak,'ABOVE','NOT_ABOVE'))
 return o
for j,m in enumerate(sm):
 sid=m['symbol'];dates=targets.loc[targets.sid.eq(sid),'day'];fp=src(m['refs']['facts']);sp=src(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')))
 assert S[str(fp)]==m['output_sha256'][str(fp)] and S[str(sp)]==m['source_sha256'][str(sp)]
 f=fullfields(pd.read_parquet(fp),pd.read_parquet(sp,columns=['source_kind','source_path','segment_id']));x=f.reindex(dates).copy();x['day']=dates.to_numpy();x['sid']=sid;rows.append(x.reset_index(drop=True))
 if (j+1)%300==0:print('STOCK',j+1,flush=True)
features=pd.concat(rows,ignore_index=True);features.to_parquet(O/'STOCK_FEATURES.parquet',index=False)
sectors=[]
for m in im:
 sid=m['series'];fp=src(next(p for p in m['source_sha256'] if '/industry-facts/' in p));sp=src(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));f=pd.read_parquet(fp)
 if 'raw_close' not in f:f['raw_close']=np.nan
 ff=fullfields(f,pd.read_parquet(sp,columns=['source_kind','source_path','segment_id']));x=ff.reindex(targets.day.unique()).copy();x['day']=x.index;x['sector']=sid;sectors.append(x.reset_index(drop=True))
sf=pd.concat(sectors,ignore_index=True);sf=sf.rename(columns={c:'sector_'+c for c in sf if c not in ['day','sector']});sf.to_parquet(O/'SECTOR_FEATURES.parquet',index=False)
z=pd.read_csv(src(F/'report/INITIAL_AND_FULL_ROUNDS.csv'),low_memory=False,parse_dates=['signal_day']);n=z[z.arm.eq('AB_FAST_SMALL')].copy();b=z[z.arm.eq('A_UNION_B')].copy();n['day']=n.signal_day
xcols=[c for c in features if c not in n or c in ['sid','day']];n=n.merge(features[xcols],on=['sid','day'],how='left',validate='many_to_one').merge(sf,on=['sector','day'],how='left',validate='many_to_one')
acols=[c for c in a if c not in n or c in ['sid','day']];n=n.merge(a[acols],on=['sid','day'],how='left',validate='one_to_one')
n=n.sort_values(['sid','day']);n['permit_ordinal_2022']=n.groupby('sid').cumcount()+1;n['permit_clock']=np.where(n.permit_ordinal_2022.eq(1),'FIRST_2022','REENTRY_2022');n['prior_round_id']=n.groupby('sid').round_id.shift();n['prior_status']=n.groupby('sid').status.shift();n['prior_exit_day']=n.groupby('sid').exit_day.shift();n['prior_initial_net']=n.groupby('sid').initial_net.shift();n['prior_initial_usable']=n.groupby('sid').initial_evidence_usable.shift()
n['prior_realized_outcome']=np.where(n.permit_ordinal_2022.eq(1),'FIRST_2022',np.where(n.prior_status.str.contains('NOFILL',na=False),'AFTER_NOFILL',np.where(n.prior_initial_usable.eq(True)&pd.to_datetime(n.prior_exit_day).le(n.day),np.where(n.prior_initial_net>0,'AFTER_KNOWN_WIN','AFTER_KNOWN_LOSS'),'PRIOR_FINANCIAL_UNKNOWN')))
n['quarter']=n.day.dt.to_period('Q').astype(str);n['has_AB']=n.AB_event_id.notna();n['new_vs_baseline_event']=~n.event_id.isin(b.event_id);n['I_clock']=np.where(n.I_root_day.isna(),'UNKNOWN_ROOT',np.where(n.I_birth,'I_BIRTH',np.where(n.i_buy.eq(True),'LATER_I_BUY','NO_I_BUY')));n['I_episode_position']=np.where(n.I_root_day.isna(),'UNKNOWN_ROOT',np.where(~n.i_buy.eq(True),'NO_CURRENT_I_BUY',np.where(n.i_buy_ordinal.eq(1),'FIRST_I_BUY_IN_EPISODE','LATER_I_BUY_IN_EPISODE')));n['I_root_pre2022']=n.I_root_day.notna()&n.I_root_day.lt('2022-01-01');n['G_sign']=np.where(n.g_grade>0,'POSITIVE',np.where(n.g_grade<0,'NEGATIVE',np.where(n.g_grade==0,'ZERO','UNKNOWN')));n['E0_I_alignment']=np.where(n.e0_target.eq(1),'E0_ON','E0_OFF_OR_UNKNOWN');n['PVR_half']=np.where(n.PVR_score>50,'ABOVE_50',np.where(n.PVR_score<=50,'AT_OR_BELOW_50','UNKNOWN'))
d=pd.read_csv(src(F/'economic/DECISIONS.csv'),parse_dates=['day']);d['market_fast']=d.event_Q.eq(True);d['market_cp']=d.continuing_Q.eq(True)&d.cp_id.notna();daily=d.groupby(['day','sector']).agg(candidate_events=('sid','size'),fast_events=('market_fast','sum'),cp_events=('market_cp','sum'),flat_events=('stock_state_before',lambda x:x.eq('FLAT').sum()),feasible_events=('decision',lambda x:x.isin(['SELECTED_PENDING','PASS_NOT_TOP2']).sum()),selected_events=('selected','sum')).reset_index();n=n.merge(daily,on=['day','sector'],validate='many_to_one');n['queue_competition']=np.where(n.feasible_events<=2,'NO_REJECTED_FEASIBLE','MORE_THAN_TWO');n['role_group']=np.where(n.entry_role.eq('MOBILE_CP'),'EMPTY_CP',np.where(n.entry_role.eq('I_CORE')&n.has_AB,'I_WITH_AB',np.where(n.entry_role.eq('I_CORE'),'FAST_I_NO_AB','UNCONFIRMED')))
n.to_csv(O/'PERMIT_FEATURES.csv',index=False);daily.to_csv(O/'DAILY_SECTOR_EVENTS.csv',index=False)
# Diagnostic groups never alter events, fills, exits or outcomes.
def stat(g):
 c=g[g.initial_evidence_usable];ff=g[g.full_evidence_usable]
 return dict(permits=len(g),stocks=g.sid.nunique(),confirmed_fills=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),financial_unknown_closed=int((g.initial_closed&~g.initial_evidence_usable).sum()),usable=len(c),wins=int(c.initial_net.gt(0).sum()),win_rate=float(c.initial_net.gt(0).mean()) if len(c) else None,net=float(c.initial_net.sum()),mean_net=float(c.initial_net.mean()) if len(c) else None,mean_return=float(c.initial_return.mean()) if len(c) else None,tail30=int(c.initial_return.ge(.3).sum()),tail50=int(c.initial_return.ge(.5).sum()),full_usable=len(ff),full_win_rate=float(ff.net_pnl.gt(0).mean()) if len(ff) else None,full_net=float(ff.net_pnl.sum()))
strata=[]
for scope,nn in [('ALL',n),('Q1',n[n.quarter.eq('2022Q1')]),('Q1_NEW_EVENT',n[n.quarter.eq('2022Q1')&n.new_vs_baseline_event]),('Q1_NO_AB',n[n.quarter.eq('2022Q1')&~n.has_AB])]:
 strata.append(dict(scope=scope,feature='TOTAL',value='ALL',**stat(nn)))
 for field in ['role_group','permit_clock','prior_realized_outcome','I_clock','I_episode_position','I_root_pre2022','E0_I_alignment','G_sign','g_grade','G_direction','g_fresh_up','g_acute_down','PVR_half','queue_competition','I_birth_ordinal_in_E0','close_above_previous_I_peak']:
  for val,g in nn.groupby(field,dropna=False):strata.append(dict(scope=scope,feature=field,value=str(val),**stat(g)))
pd.DataFrame(strata).to_csv(O/'STRATA.csv',index=False)
cross=[]
for fields in [['quarter','role_group'],['quarter','permit_clock'],['quarter','I_clock'],['quarter','G_sign'],['quarter','queue_competition'],['quarter','role_group','permit_clock'],['quarter','E0_I_alignment','G_sign'],['quarter','close_above_previous_I_peak']]:
 for val,g in n.groupby(fields,dropna=False):cross.append(dict(features='|'.join(fields),values='|'.join(map(str,val)),**stat(g)))
pd.DataFrame(cross).to_csv(O/'CROSS_STRATA.csv',index=False)
counts=[]
for q,g in a.groupby(a.day.dt.to_period('Q').astype(str)):
 sel=n[n.quarter.eq(q)];cg=d[d.day.dt.to_period('Q').astype(str).eq(q)]
 counts.append(dict(quarter=q,days=g.day.nunique(),event_Q=int(g.event_Q.fillna(False).sum()),event_Q_stocks=g[g.event_Q.fillna(False)].sid.nunique(),qualified_CP=int((g.continuing_Q.fillna(False)&g.cp_fresh.fillna(False)).sum()),all_cp=int(g.cp_fresh.fillna(False).sum()),eligible_I_epochs=g[g.event_Q.fillna(False)][['sid','i_epoch']].drop_duplicates().shape[0],candidates=len(cg),feasible=int(cg.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2']).sum()),blocked_held=int(cg.decision.eq('BLOCKED_HELD').sum()),blocked_unknown=int(cg.decision.eq('BLOCKED_UNKNOWN').sum()),**stat(sel)))
pd.DataFrame(counts).to_csv(O/'QUARTER_EVENT_COUNTS.csv',index=False)
# Date-equal descriptions, no matching on future outcome and not a causal estimate.
de=[]
for scope,gg in [('ALL',n),('Q1',n[n.quarter.eq('2022Q1')])]:
 c=gg[gg.initial_evidence_usable]
 for field in ['permit_clock','I_clock','G_sign','E0_I_alignment','queue_competition','close_above_previous_I_peak']:
  for v in c[field].dropna().unique():
   for by in [['day'],['day','sector']]:
    aa=c[c[field].eq(v)].groupby(by).agg(n=('sid','size'),wr=('initial_net',lambda x:(x>0).mean()),net=('initial_net','mean'));bb=c[~c[field].eq(v)].groupby(by).agg(n=('sid','size'),wr=('initial_net',lambda x:(x>0).mean()),net=('initial_net','mean'));j=aa.join(bb,lsuffix='_a',rsuffix='_b',how='inner')
    de.append(dict(scope=scope,feature=field,value=v,cluster='|'.join(by),clusters=len(j),group_n=int(j.n_a.sum()),other_n=int(j.n_b.sum()),equal_win_diff=(j.wr_a-j.wr_b).mean(),equal_net_diff=(j.net_a-j.net_b).mean()))
pd.DataFrame(de).to_csv(O/'CLUSTER_EQUAL_DESCRIPTIVE.csv',index=False)
# Causal feature-only startup join, no lifecycle labels.
sc=startup.merge(features[[c for c in features if c not in startup or c in ['sid','day']]],on=['sid','day'],validate='one_to_one').merge(sf,on=['sector','day'],validate='many_to_one');sc.to_csv(O/'STARTUP_FEATURES.csv',index=False)
summary=dict(no_economic_run=True,total=stat(n),q1=stat(n[n.quarter.eq('2022Q1')]),source_files=len(S),feature_rows=len(features),sector_rows=len(sf));(O/'SUMMARY.json').write_text(json.dumps(summary,indent=2,default=str));src(Path(__file__));(O/'SOURCE_HASHES.json').write_text(json.dumps(S,indent=2));print(json.dumps(summary,indent=2),flush=True)
