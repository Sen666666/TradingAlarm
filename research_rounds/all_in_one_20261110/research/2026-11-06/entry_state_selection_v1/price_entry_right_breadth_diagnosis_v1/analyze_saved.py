"""Read only frozen source artifacts; never import/execute any economic consumer."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent; M=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'; H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,pd.Timestamp):return v.isoformat()
 return v
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
src(O/'FEATURE_CONTRACT.md');src(O/'HYPOTHESIS_AND_QA_ADDENDUM.md');src(__file__)
x=pd.read_csv(src(R/'price_entry_mechanism_comparison_v1/ENTRY_FACTS.csv'),low_memory=False)
assert len(x)==3621 and not x.round_id.duplicated().any()
original_columns=set(x.columns); ledger_qa=[]; parts=[]
for y in [2022,2024]:
 p=R/f'independent_channel_joint_economic_v1/economic_{y}'; rep=json.loads(src(p/'COMPARISON_REPORT_RECOVERED.json').read_text()); common=set(rep['summary'][0]['common_covered_sids'])
 orig=pd.read_csv(src(p/'joint/ROUNDS.csv'));acts=pd.read_csv(src(p/'joint/ACTIONS.csv')); buys=set(acts.loc[acts.side.eq('buy_core'),'round_id'])
 core=pd.DataFrame(rep['core_independent_dated_fee_diagnostics']);core=core[core.arm.eq('joint')&core.lane.eq('PRICE')]
 cov=pd.DataFrame(rep['round_coverage']);cov=cov[cov.arm.eq('joint')&cov.lane.eq('PRICE')]
 saved=pd.read_csv(src(R/f'price_entry_generation_dynamic_v1/report_{y}/ALL_ROUNDS.csv'));saved=saved[saved.arm.eq('baseline')&saved.owner_lane.eq('PRICE')].copy()
 z=x[x.year.eq(y)].copy();assert set(z.round_id)==set(saved.round_id)==set(orig.loc[orig.owner_lane.eq('PRICE'),'round_id'])
 assert z.common.eq(z.sid.isin(common)).all() and z.actual_buy.eq(z.round_id.isin(buys)).all()
 s=saved.merge(core[['round_id','closed_net','fee_basis']],on='round_id',validate='one_to_one').merge(cov[['round_id','financial_covered','reason']],on='round_id',validate='one_to_one',suffixes=('','_orig'))
 assert s.probe_closed_net.notna().eq(s.closed_net.notna()).all() and np.allclose(s.probe_closed_net,s.closed_net,equal_nan=True,atol=1e-8)
 assert s.financial_covered.eq(s.financial_covered_orig).all() and s.coverage_reason.eq(s.reason).all()
 assert s.independent_probe_fee_basis.fillna('MISSING').eq(s.fee_basis.fillna('MISSING')).all()
 keep=['round_id','full_closed_net','probe_closed_net','financial_covered','coverage_reason','unknown','book_derived_unresolved','open_censored','independent_probe_fee_basis','entered']
 z=z.merge(saved[keep].rename(columns={'unknown':'economic_unknown'}),on='round_id',validate='one_to_one')
 z=z.merge(core[['round_id','buy_cash']].rename(columns={'buy_cash':'initial_core_buy_cash'}),on='round_id',validate='one_to_one')
 assert z.actual_buy.eq(z.entered).all() and np.allclose(z.full_closed_net.where(z.actual_buy),z.closed_total_pnl.where(z.actual_buy),equal_nan=True,atol=1e-8)
 z['economic_partition']=np.select([~z.actual_buy,z.economic_unknown,~z.financial_covered,z.open_censored,z.full_closed_net.notna()&z.probe_closed_net.notna()],['NO_BUY','ECONOMIC_UNKNOWN','KNOWN_BUT_FINANCIAL_UNCOVERED','COVERED_OPEN_CENSORED','COVERED_CLOSED'],default='COVERED_OTHER_NOT_CLOSED')
 for role,col in [('FULL','full_closed_net'),('CORE','probe_closed_net')]:
  z[role+'_conditional_closed']=z.actual_buy&~z.economic_unknown&~z.open_censored&z[col].notna()
  z[role+'_financial_closed']=z[role+'_conditional_closed']&z.financial_covered
 ledger_qa.append(dict(year=y,registered=len(z),actual_buy=int(z.actual_buy.sum()),original_common_stock_count=len(common),common_registered=int(z.common.sum()),common_actual=int((z.common&z.actual_buy).sum()),economic_partition=z.economic_partition.value_counts().to_dict(),unknown_and_uncovered=int((z.actual_buy&z.economic_unknown&~z.financial_covered).sum()),all_financial_uncovered_actual=int((z.actual_buy&~z.financial_covered).sum()),all_economic_unknown_actual=int((z.actual_buy&z.economic_unknown).sum()),full_financial_n=int(z.FULL_financial_closed.sum()),core_financial_n=int(z.CORE_financial_closed.sum()),independent_core_source_equal=True,financial_source_equal=True))
 parts.append(z)
x=pd.concat(parts,ignore_index=True)
roster=pd.read_csv(src(R/'momentum_persistence_breadth_v1/FIXED_ROSTER.csv')).set_index('symbol')
k=pd.concat([pd.read_parquet(src(M/'WARM_PREFIX_M_K.parquet')),pd.read_parquet(src(M/'KNOWN3.parquet'))])
r=pd.concat([pd.read_parquet(src(M/'WARM_PREFIX_M_R.parquet')),pd.read_parquet(src(M/'RIGHT3.parquet'))])
assert k.index.equals(r.index) and k.columns.equals(r.columns) and k.index.is_unique and k.index.is_monotonic_increasing
assert not k.isna().any().any() and not r.isna().any().any() and not (r&~k).any().any()
assert set(k.columns)==set(roster.index)
b=pd.read_parquet(src(M/'SECTOR_DAILY.parquet')).set_index(['sector','day']); groups={sec:list(g.index) for sec,g in roster.groupby('sector_id')}
cache={}; member_cases=[]
def features(sid,ds,case=False):
 key=(sid,str(ds)[:10]);t=pd.Timestamp(ds);sec=roster.at[sid,'sector_id'];peers=[s for s in groups[sec] if s!=sid];N=len(peers)
 if key in cache and not case:return cache[key]
 assert sid in k and t in k.index and (sec,t) in b.index
 i=k.index.get_loc(t);assert i>0;prev=k.index[i-1]
 kt=k.loc[t,peers].to_numpy(bool);kp=k.loc[prev,peers].to_numpy(bool);rt=r.loc[t,peers].to_numpy(bool);rp=r.loc[prev,peers].to_numpy(bool)
 at=(kt&rt).astype(int);ap=(kp&rp).astype(int);bt=at+(~kt).astype(int);bp=ap+(~kp).astype(int)
 K=int(kt.sum());Kp=int(kp.sum());n=int(at.sum());np_=int(ap.sum());U=N-K;Up=N-Kp
 L=int((at-bp).sum());HH=int((bt-ap).sum());assert L==n-np_-Up and HH==n+U-np_
 assert HH-L==U+Up and -N<=L<=HH<=N
 pair=kt&kp;J=int(pair.sum());en=int((pair&rt&~rp).sum());left=int((pair&~rt&rp).sum());D=en-left
 half='UNKNOWN' if N==0 else ('AT_LEAST_HALF' if 2*n>=N else ('BELOW_HALF' if 2*(n+U)<N else 'UNKNOWN'))
 direction='UNKNOWN' if N==0 else ('POSITIVE' if L>0 else ('NEGATIVE' if HH<0 else ('FLAT' if L==HH==0 else 'UNKNOWN')))
 paired='UNKNOWN' if J==0 else ('POSITIVE' if D>0 else ('NEGATIVE' if D<0 else 'FLAT'))
 if K==Kp==N:
  assert L==HH==D and J==N
  if N:assert direction==paired
 sk=bool(k.at[t,sid]);sr=bool(r.at[t,sid]); stock='UNKNOWN' if not sk else ('ON' if sr else 'OFF');old=b.loc[(sec,t)]
 ids=groups[sec];assert int(k.loc[t,ids].sum())==int(old.K) and int((k.loc[t,ids]&r.loc[t,ids]).sum())==int(old.n) and len(ids)==int(old.N)
 res=dict(peer_N=N,peer_K=K,peer_n=n,peer_U=U,peer_prev_K=Kp,peer_prev_n=np_,peer_prev_U=Up,peer_known_share=n/K if K else np.nan,peer_fixed_lower=n/N if N else np.nan,peer_fixed_upper=(n+U)/N if N else np.nan,peer_half=half,peer_previous_common_day=prev.strftime('%Y-%m-%d'),peer_delta1_L_count=L if N else np.nan,peer_delta1_H_count=HH if N else np.nan,peer_delta1_lower=L/N if N else np.nan,peer_delta1_upper=HH/N if N else np.nan,peer_delta1_robust=direction,paired_J=J,paired_entered=en,paired_left=left,paired_D=D,paired_delta1=D/J if J else np.nan,paired_coverage=J/N if N else np.nan,paired_known_direction=paired,stock_M3=stock,independent_sector_M3_candidate={1:'ON',0:'OFF',-1:'UNKNOWN'}[int(old.candidate)],independent_sector_N=int(old.N),independent_sector_K=int(old.K),independent_sector_n=int(old.n),independent_sector_delta3=old.delta3,peer_source_status='NO_PEERS' if N==0 else 'COMPLETE_CACHE_CLOCK',independent_sector_E0=old.sector_E0_valid)
 cache[key]=res
 if case:
  for q,s in enumerate(peers):member_cases.append(dict(target=sid,signal_day=str(ds)[:10],previous_common_day=prev.strftime('%Y-%m-%d'),member=s,known_today=bool(kt[q]),right_today=bool(rt[q]),known_previous=bool(kp[q]),right_previous=bool(rp[q]),current_lower=int(at[q]),current_upper=int(bt[q]),previous_lower=int(ap[q]),previous_upper=int(bp[q]),delta_lower=int(at[q]-bp[q]),delta_upper=int(bt[q]-ap[q]),paired=bool(pair[q])))
 return res
f=pd.DataFrame([features(z.sid,z.signal_day) for z in x.itertuples()]);x=pd.concat([x.reset_index(drop=True),f],axis=1)
# Keep the old joint-known subset visibly distinct from the new independent evidence.
oldcols=[c for c in x if c.startswith(('M3_','PVR3_')) or c in ['N','K','U','common3_K','both_right','M3_only','PVR3_only']]
x=x.rename(columns={c:'OLD_COMMON_K_'+c for c in oldcols})
x['sector_E0_state']=x.independent_sector_E0.map({True:'ON',False:'OFF'}).fillna('UNKNOWN')
x['original_fast_market_state']=x.old_fast_core_market_prereq_ignoring_consumption.map({True:'ON',False:'OFF'}).fillna('UNKNOWN')
x['intended_hypothesis_cell']=np.select([x.peer_half.eq('AT_LEAST_HALF')&x.peer_delta1_robust.eq('POSITIVE'),x.peer_half.ne('UNKNOWN')&x.peer_delta1_robust.ne('UNKNOWN')],['HALF_AND_POSITIVE','OTHER_CLASSIFIABLE'],default='MECHANISM_UNCLASSIFIABLE')
primary=['peer_half','peer_delta1_robust','stock_M3','independent_sector_M3_candidate']
fields=[[q] for q in primary]+[['paired_known_direction'],['ticket'],['participation'],['entry_root_relation'],['sector_E0_state'],['original_fast_market_state'],['peer_half','peer_delta1_robust'],['peer_half','stock_M3']]
for q in ['peer_half','peer_delta1_robust']:
 for s in ['ticket','participation','signal_month']:fields.append([s,q])
fields.append(['intended_hypothesis_cell'])
for s in ['ticket','participation','stock_M3','signal_month']:fields.append([s,'intended_hypothesis_cell'])
def agg(g):
 actual=g[g.actual_buy];out=dict(registered=len(g),actual_buy=len(actual),no_buy=int((~g.actual_buy).sum()),stocks=int(g.sid.nunique()),half_unknown_actual=int(actual.peer_half.eq('UNKNOWN').sum()),robust_delta_unknown_actual=int(actual.peer_delta1_robust.eq('UNKNOWN').sum()),stock_m3_unknown_actual=int(actual.stock_M3.eq('UNKNOWN').sum()),paired_unknown_actual=int(actual.paired_known_direction.eq('UNKNOWN').sum()),economic_unknown_actual=int(actual.economic_unknown.sum()),financial_uncovered_flag_actual=int((~actual.financial_covered).sum()),unknown_and_uncovered_actual=int((actual.economic_unknown&~actual.financial_covered).sum()),economic_partition=g.economic_partition.value_counts().to_dict())
 for role,col in [('FULL','full_closed_net'),('CORE','probe_closed_net')]:
  for coverage in ['conditional','financial']:
   vals=g.loc[g[role+'_'+coverage+'_closed'],col];out[role+'_'+coverage]=dict(n=len(vals),total_net=vals.sum() if len(vals) else None,mean_net=vals.mean() if len(vals) else None,wins=int(vals.gt(0).sum()),win_rate=vals.gt(0).mean() if len(vals) else None)
 out['scale_CORE_financial']=dict(initial_core_buy_cash_n=int(g.loc[g.CORE_financial_closed,'initial_core_buy_cash'].notna().sum()),mean_initial_core_buy_cash=g.loc[g.CORE_financial_closed,'initial_core_buy_cash'].mean(),mean_entry_gross=g.loc[g.CORE_financial_closed,'entry_gross'].mean(),mean_entry_risk=g.loc[g.CORE_financial_closed,'entry_risk'].mean())
 return out
tables=[];coverage=[]
for y,g0 in x.groupby('year'):
 for scope,g in [('ALL',g0),('ORIGINAL_COMMON',g0[g0.common])]:
  baseline=agg(g);coverage.append(dict(year=int(y),scope=scope,**baseline))
  for fs in fields:
   entries=[]
   for keys,z in g.groupby(fs,dropna=False,observed=True):
    if not isinstance(keys,tuple):keys=(keys,)
    entries.append(dict(year=int(y),scope=scope,grouping='__'.join(fs),**dict(zip(fs,keys)),**agg(z)))
   assert sum(q['registered'] for q in entries)==len(g)
   for role in ['FULL','CORE']:
    for cv in ['conditional','financial']:
     key=role+'_'+cv;assert sum(q[key]['n'] for q in entries)==baseline[key]['n'];assert np.isclose(sum(q[key]['total_net'] or 0 for q in entries),baseline[key]['total_net'],atol=1e-6)
   tables+=entries
# Predetermined fixed cases, including no-registration facts and 2025/26 signal-only checks.
cases=[('000977.SZ','2022-01-05'),('600100.SH','2022-01-04'),('002174.SZ','2022-11-08'),('605020.SH','2022-07-15'),('002031.SZ','2022-06-13'),('688248.SH','2022-05-12'),('688256.SH','2022-03-04'),('002583.SZ','2024-09-20'),('002583.SZ','2024-09-23'),('002583.SZ','2024-09-24'),('002583.SZ','2024-09-25'),('688660.SH','2024-09-25'),('605488.SH','2024-09-30'),('002241.SZ','2024-09-30'),('600396.SH','2024-10-28'),('600126.SH','2024-12-11'),('605099.SH','2024-12-11'),('002126.SZ','2024-12-25'),('300666.SZ','2025-12-15'),('300666.SZ','2025-12-17'),('300666.SZ','2026-01-05'),('300666.SZ','2026-01-15')]
fixed=pd.read_csv(src(R/'independent_channel_probe_preflight_v1/FIXED_DAILY.csv'));over=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'));over['daystr']=over.day.dt.strftime('%Y-%m-%d')
case_rows=[]
casecols=['round_id','actual_buy','common','entry_day','exit_day','ticket','root_day','root_age_sessions','phase','born','receipt','confirmed_now','E0','I','old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up','old_fast_core_market_prereq_ignoring_consumption','Q','R','all_strategy_buy_number','price_buy_number','participation','entry_root_relation','prior_all_exit_day','full_closed_net','probe_closed_net','economic_partition','financial_covered','economic_unknown']
for sid,ds in cases:
 z=x[x.sid.eq(sid)&x.signal_day.eq(ds)];assert len(z)<=1
 row=dict(sid=sid,name=roster.at[sid,'name'],signal_day=ds,**features(sid,ds,case=True))
 if len(z):row.update({q:z.iloc[0][q] for q in casecols if q in z});row['record_scope']='ORIGINAL_REGISTERED_PRICE'
 else:
  ff=fixed[fixed.sid.eq(sid)&fixed.day.eq(ds)];ov=over[over.sid.eq(sid)&over.daystr.eq(ds)]
  assert len(ff)==1,(sid,ds,'FIXED_DAILY_NOT_UNIQUE')
  for q in casecols:
   if q in ff:row[q]=ff.iloc[0][q]
   if q in ov and len(ov)==1:row[q]=ov.iloc[0][q]
  row['record_scope']='SIGNAL_ONLY_NO_2026_ECONOMICS' if ds[:4] in ['2025','2026'] else 'ORIGINAL_NOT_REGISTERED_PRICE'
  row['actual_buy']=None if ds[:4] in ['2025','2026'] else False
  row['round_id']=None;row['full_closed_net']=None;row['probe_closed_net']=None
 case_rows.append(row)
# Report no same-root reuse across successive actual PRICE initial entries; no invented pre-window history.
reuse=[]
for (y,sid),g in x[x.actual_buy].groupby(['year','sid']):
 g=g.sort_values('signal_day');same=g.root_day.eq(g.root_day.shift())
 if same.any():reuse+=g.loc[same,['year','sid','round_id','root_day']].to_dict('records')
assert not reuse
qa=dict(contract_sha256=H[str(O/'FEATURE_CONTRACT.md')],ledger=ledger_qa,all_signal_keys_hit=True,independent_sector_source_totals_equal=True,paired_and_fixed_counts_integer_exact=True,endpoint_width_equals_total_unknown=True,all_known_robust_equals_paired=True,no_peer_rows=int(x.peer_N.eq(0).sum()),no_same_root_initial_reuse=True,economic_runs=0,fee_recalculations=0,parameter_searches=0,filtered_strategy_returns=0,original_common_scope_preserved=True,source_count=len(H),source_files_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in H.items()))
assert qa['source_files_unchanged']
x.to_csv(O/'ALL_PRICE_ENTRY_FACTS.csv',index=False);pd.DataFrame(case_rows).to_csv(O/'FIXED_CASES.csv',index=False);pd.DataFrame(member_cases).to_csv(O/'FIXED_PEER_COMPONENTS.csv',index=False)
dump('COVERAGE.json',coverage);dump('GROUPED_DESCRIPTIVE.json',tables);dump('QA.json',qa);dump('SOURCE_HASHES.json',H)
flat=[]
for t in tables:
 q={a:b for a,b in t.items() if not isinstance(b,dict)}
 for a,b in t.items():
  if a in ['FULL_financial','CORE_financial','FULL_conditional','CORE_conditional','scale_CORE_financial']:
   for c,d in b.items():q[a+'_'+c]=d
 flat.append(q)
pd.DataFrame(flat).to_csv(O/'GROUPED_DESCRIPTIVE.csv',index=False)
dump('OUTPUT_HASHES.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(clean(qa),ensure_ascii=False,indent=2));print('PRIMARY RESULTS')
cols=['year','scope','grouping']+primary+['paired_known_direction','actual_buy','economic_unknown_actual','FULL_financial_n','FULL_financial_mean_net','FULL_financial_total_net','FULL_financial_win_rate','CORE_financial_n','CORE_financial_mean_net','CORE_financial_total_net','CORE_financial_win_rate']
df=pd.DataFrame(flat);print(df[df.grouping.isin(primary+['paired_known_direction'])][cols].to_string(index=False));print('FIXED CASES');print(pd.DataFrame(case_rows)[['name','signal_day','peer_N','peer_K','peer_n','peer_half','peer_delta1_L_count','peer_delta1_H_count','peer_delta1_robust','paired_known_direction','stock_M3','full_closed_net','probe_closed_net']].to_string(index=False))
