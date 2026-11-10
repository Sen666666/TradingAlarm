from pathlib import Path
from decimal import Decimal
import json,gzip,hashlib,collections,sys
import pandas as pd,numpy as np
sys.dont_write_bytecode=True
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent
C=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';T=R/'first_day_20220105_signal_trace_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');U=W/'universe-cp1-inputs-20261031';M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');A=R/'act_only_ablation_continuous_v1/run/pair';hs={}
def h(p):p=Path(p);hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def js(p):return json.loads(h(p).read_text())
def pq(p,**kw):return pd.read_parquet(h(p),**kw)
def csv(p,**kw):return pd.read_csv(h(p),**kw)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path,Decimal)):return str(x)
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
protocol=dict(signal_close='2022-01-04',actual_fill_open='2022-01-05',scope='Exactly original 52 fills and their 25 industries; no selection by future return',old_formula='n>=3 AND ((3*n>=N AND known paired t versus t-3 diffusion positive) OR 2*n>=N). Original research formula, NOT a user-prescribed meaning of many.',denominator='Display own-known and common-known, fixed N and UNKNOWN bounds, never impute unknown as false',historical_dates=['2021-11-30','2021-12-17','2021-12-31','2022-01-04'],future_fixed_endpoints=['2022-01-28','2022-03-31','2022-06-30'],future_window='All common industry days 2022-01-04 through 2022-06-30 inclusive; future max/min and chronological maximum drawdown are descriptive only',account_replays=0,parameter_searches=0,previous_cohort_and_results_seen=True)
save('PROTOCOL.json',protocol);save('FREEZE.json',dict(protocol_sha=hashlib.sha256((O/'PROTOCOL.json').read_bytes()).hexdigest(),code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
trace=csv(T/'FIRST_DAY_52_SIGNAL_EVIDENCE.csv');roster=csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid');sectors=sorted(trace.sector.unique());ids=roster[roster.sector_id.isin(sectors)].index.tolist();sm={x['symbol']:x for x in js(U/'STOCK_MANIFEST.json')};im={x['series']:x for x in js(U/'INDUSTRY_MANIFEST.json')}
# Read original actual journal, not inferred from a day-end pool snapshot.
a=json.load(gzip.open(h(A/'PVR.json.gz'),'rt'));fills=[x for x in a['journal'] if x.get('kind')=='real_buy_fill' and x['at'].startswith('2022-01-05')];assert len(fills)==len({x['sid'] for x in fills})==52
assert set(x['sid'] for x in fills)==set(trace.sid)
for x in fills:
 t=trace.set_index('sid').loc[x['sid']];assert x['role']==t.actual_role and x['pool']==t.actual_fill_pool and x['signal_at']==t.signal_at
fund=[]
with gzip.open(h(A/'funding.jsonl.gz'),'rt') as f:
 for line in f:
  x=json.loads(line)
  if str(x.get('at',x.get('day','')))[:10]>'2022-01-05':break
  if x.get('account')=='PVR' and str(x.get('at','')).startswith('2022-01-05') and x.get('sid') in set(trace.sid):fund.append(x)
mobile=[x for x in fills if x['role']=='mobile'];failed=[]
for x in mobile:
 attempts=[y for y in fund if y.get('sid')==x['sid'] and y.get('role')=='core' and y.get('result')!='reserved']
 failed.append(dict(sid=x['sid'],mobile_pool=x['pool'],core_attempted=bool(attempts),core_reasons='|'.join(y['result'] for y in attempts),CP1_id=x['CP1_id']))
assert len(mobile)==49 and sum(x['core_attempted'] for x in failed)==48 and all('probe_risk' in x['core_reasons'] for x in failed if x['core_attempted'])
save('ORIGINAL_FILL_AND_FUNDING_AUDIT.json',dict(fills=fills,mobile_core_attempts=failed))
# Independently reconstruct member state from original published G sign + raw flags and original PVR formula.
industry_inputs={s:pq(im[s]['refs']['CP1_input']) for s in sectors};calendar=pd.DatetimeIndex(sorted(set().union(*(set(z.index) for z in industry_inputs.values()))));calendar=calendar[calendar<=pd.Timestamp('2022-01-04')];six=calendar[-6:];assert list(six.strftime('%Y-%m-%d'))==['2021-12-27','2021-12-28','2021-12-29','2021-12-30','2021-12-31','2022-01-04']
env=dict(pd=pd,np=np);formula=h(W/'pvr-current-v3-information-capital-20261101/original_score_function.py');exec(compile(formula.read_text(),str(formula),'exec'),env)
MK={};MR={};PS={};rows=[];maxerr=0.
savedmk=pd.concat([pq(C/'WARM_PREFIX_M_K.parquet'),pq(C/'KNOWN3.parquet')]);savedmr=pd.concat([pq(C/'WARM_PREFIX_M_R.parquet'),pq(C/'RIGHT3.parquet')]);savedp=pq(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet');savedps=pd.concat([pq(C/'WARM_PREFIX_P_STATE.parquet'),savedp.pivot(index='day',columns='sid',values='state')]);pvals=savedp.set_index(['sid','day'])
for sid in ids:
 sp=next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet'));raw=pq(sp).loc[:'2022-01-04'];g=pq(M/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet').loc[:'2022-01-04'];q=raw.reindex(calendar);gg=g.reindex(calendar);ident=q.segment_id.astype('string')+'|'+q.source_kind.astype('string')+'|'+q.source_path.astype('string');same=ident.eq(ident.shift(1)).fillna(False)&ident.eq(ident.shift(2)).fillna(False)
 valid=gg.valid_strength_observation.eq(True)&q.observed_bar.eq(True)&q.price_eligible.eq(True)&q.volume_eligible.eq(True)&~q.source_invalid.eq(True)&q.close.gt(0)&q.volume.gt(0)&np.isfinite(gg.z5)
 known=valid&valid.shift(1,fill_value=False)&valid.shift(2,fill_value=False)&same;right=known&gg.z5.gt(0)&gg.z5.shift(1).gt(0)&gg.z5.shift(2).gt(0)
 p=env['score'](raw).score.reindex(calendar);ok=q.close.gt(0)&np.isfinite(q.close)&q.amount.gt(0)&np.isfinite(q.amount)&p.notna()&q.raw_volume.gt(0)
 for col in ['price_eligible','observed_bar','is_observed_bar']:ok &=q[col].eq(True)
 for col in ['source_invalid','synthetic_event_bar']:ok &=q[col].eq(False)
 pk=ok&ok.shift(1,fill_value=False)&ok.shift(2,fill_value=False)&same;ps=pd.Series(np.where(pk,p.rolling(3,min_periods=3).min().ge(60).astype(int),-1),index=calendar)
 for day in calendar[-4:]:
  assert known.at[day]==savedmk.at[day,sid] and right.at[day]==savedmr.at[day,sid] and ps.at[day]==savedps.at[day,sid],(sid,day)
 val=pvals.loc[(sid,pd.Timestamp('2022-01-04')),'score'];re=p.iloc[-1]
 assert (pd.isna(val) and pd.isna(re)) or abs(val-re)<1e-10,(sid,val,re)
 if np.isfinite(val):maxerr=max(maxerr,abs(val-re))
 MK[sid]=known;MR[sid]=right;PS[sid]=ps
 for d in six:rows.append(dict(sid=sid,sector=roster.loc[sid,'sector_id'],day=d,raw_present=d in raw.index,M3_known=bool(known.at[d]),M3_right=bool(right.at[d]),PVR_score=p.at[d],PVR3_state=int(ps.at[d]),G_z5=gg.at[d,'z5'],same_source_3days=bool(same.at[d])))
pd.DataFrame(rows).to_csv(O/'MEMBER_SIX_SESSION_REBUILD.csv',index=False)
mk=pd.DataFrame(MK);mr=pd.DataFrame(MR);ps=pd.DataFrame(PS);both=mk&ps.ge(0);pr=ps.eq(1)
def aggregate(sec,d,k,r):
 cols=roster[roster.sector_id.eq(sec)].index;idx=k.index.get_loc(d);before=k.index[idx-3];kv=k.loc[d,cols];rv=r.loc[d,cols];pair=kv&k.loc[before,cols];N=len(cols);K=int(kv.sum());n=int((rv&kv).sum());U=N-K;J=int(pair.sum());ent=int((pair&rv&~r.loc[before,cols]).sum());left=int((pair&~rv&r.loc[before,cols]).sum());delta=ent-left
 def gate(nn,den,up):return nn>=3 and ((3*nn>=den and up) or 2*nn>=den)
 lower=gate(n,N,J>0 and delta>0);upper=gate(n+U,N,delta>0 or J==0);st=1 if lower else 0 if not upper else -1
 return dict(N=N,K=K,U=U,n=n,known_share=n/K if K else np.nan,lower=n/N,upper=(n+U)/N,paired_K=J,entered3=ent,left3=left,delta3=delta/J if J else np.nan,candidate=st,observed_candidate=gate(n,K,J>0 and delta>0) if K else None)
old=pq(C/'COMMON_K_COMPARISON.parquet').set_index(['sector','day']);out=[]
for sec in sectors:
 for day in pd.to_datetime(['2021-12-31','2022-01-04']):
  z=dict(sector=sec,industry=roster[roster.sector_id.eq(sec)].industry.iloc[0],day=day,actual_fills=int(trace.sector.eq(sec).sum()))
  for label,k,r in [('M3_own',mk,mr),('PVR3_own',ps.ge(0),pr),('M3_common',both,mr&both),('PVR3_common',both,pr&both)]:
   v=aggregate(sec,day,k,r);z.update({label+'_'+k:x for k,x in v.items()})
   if day==pd.Timestamp('2022-01-04') and label.endswith('common'):
    o=old.loc[(sec,day)];pre=label.split('_')[0]
    assert (v['N'],v['K'],v['U'],v['n'],v['candidate'],v['entered3'],v['left3'])==(o.N,o.K,o.U,o[pre+'_n'],o[pre+'_candidate'],o[pre+'_entered3'],o[pre+'_left3'])
  out.append(z)
breadth=pd.DataFrame(out);breadth.to_csv(O/'SECTOR_BREADTH_REBUILT.csv',index=False)
signal=breadth[breadth.day.eq('2022-01-04')].copy();pd.DataFrame(dict(sid=x['sid'],role=x['role'],pool=x['pool'],sector=trace.set_index('sid').loc[x['sid'],'sector']) for x in fills).merge(signal,on='sector').to_csv(O/'ORIGINAL_52_WITH_BREADTH_PRE_OUTCOMES.csv',index=False)
save('FEATURE_SEAL.json',dict(breadth=hashlib.sha256((O/'SECTOR_BREADTH_REBUILT.csv').read_bytes()).hexdigest(),members=hashlib.sha256((O/'MEMBER_SIX_SESSION_REBUILD.csv').read_bytes()).hexdigest(),known_history=True))
# Fixed index path, posthoc descriptive. No new account or hindsight signal edits.
paths=[];daily=[]
for sec in sectors:
 z=industry_inputs[sec];fx=pq(next(p for p in im[sec]['source_sha256'] if '/industry-facts/' in p));raw=pq(next(p for p in im[sec]['source_sha256'] if p.endswith('/signal.parquet')));close=z.close;window=close.loc['2022-01-04':'2022-06-30'];common=pd.DatetimeIndex(sorted(set().union(*(set(v.loc['2022-01-04':'2022-06-30'].index) for v in industry_inputs.values()))));ww=z.reindex(common);rr=raw.reindex(common)
 valid=ww.close.notna().all() and ww.close.gt(0).all() and ww.segment_id.notna().all() and ww.segment_id.nunique()==1 and rr.observed_bar.eq(True).all() and rr.price_eligible.eq(True).all() and rr.source_invalid.eq(False).all()
 ident=rr.source_kind.astype('string')+'|'+rr.source_path.astype('string')+'|'+rr.segment_id.astype('string');valid=bool(valid and ident.nunique()==1)
 p=dict(sector=sec,industry=signal.set_index('sector').loc[sec,'industry'],actual_fills=int(trace.sector.eq(sec).sum()),complete_same_source_H1=valid,sessions=len(common),day0=close.loc['2022-01-04'],factor_min=fx.loc['2021-11-30':'2022-06-30','factor'].min(),factor_max=fx.loc['2021-11-30':'2022-06-30','factor'].max())
 for d in protocol['historical_dates']+protocol['future_fixed_endpoints']:p['close_'+d]=close.get(pd.Timestamp(d),np.nan)
 for name,b,e in [('pre_December','2021-11-30','2021-12-31'),('pre_last_half_December','2021-12-17','2021-12-31'),('signal_Jan4','2021-12-31','2022-01-04'),('post_January','2022-01-04','2022-01-28'),('post_Q1','2022-01-04','2022-03-31'),('post_Q2','2022-03-31','2022-06-30'),('post_H1','2022-01-04','2022-06-30')]:p[name]=close.loc[e]/close.loc[b]-1
 if valid:
  rel=window/window.iloc[0]-1;dd=window/window.cummax()-1;trough=dd.idxmin();peak=window.loc[:trough].idxmax();p.update(post_H1_max=rel.max(),post_H1_max_day=rel.idxmax(),post_H1_min=rel.min(),post_H1_min_day=rel.idxmin(),post_H1_MDD=dd.min(),post_H1_MDD_peak_day=peak,post_H1_MDD_trough_day=trough,post_H1_rebound_after_min=window.iloc[-1]/window.min()-1)
 for d,v in close.loc['2021-11-30':'2022-06-30'].items():daily.append(dict(sector=sec,industry=p['industry'],day=d,close=v,asof_signal=d<=pd.Timestamp('2022-01-04'),relative_to_signal=v/p['day0']-1))
 paths.append(p)
paths=pd.DataFrame(paths);paths.to_csv(O/'INDUSTRY_FIXED_PATHS.csv',index=False);pd.DataFrame(daily).to_csv(O/'INDUSTRY_DAILY_PATHS.csv',index=False)
# Existing actual labels attached after feature seal. Not a filtered-strategy performance estimate.
rounds=csv(R/'act_only_ablation_continuous_v1/analysis/STOCK_ROUNDS.csv');cohort=rounds[rounds.account.eq('PVR')&rounds.opened.str.startswith('2022-01-05')].copy();assert len(cohort)==52 and set(cohort.sid)==set(trace.sid) and cohort.closed.notna().all();z=trace[['sid','sector','actual_role','actual_fill_pool','core_pre_attempt_rejection']].merge(cohort,on='sid',validate='one_to_one').merge(signal,on='sector');z.to_csv(O/'ORIGINAL_52_EXISTING_OUTCOMES.csv',index=False)
group=[]
for label in ['M3_common','PVR3_common']:
 for st,g in z.groupby(label+'_candidate'):
  group.append(dict(model=label,state=int(st),n=len(g),closed_positive=int(g.pnl.gt(0).sum()),closed_negative=int(g.pnl.lt(0).sum()),old_core_positive=int(g.initial_layer_pnl.gt(0).sum()),old_full_net=g.pnl.sum(),old_first_layer_net=g.initial_layer_pnl.sum(),warning='Original fixed account cohort partition only, NOT alternative strategy return, savings, or achievable filled subset'))
pd.DataFrame(group).to_csv(O/'ORIGINAL_OUTCOME_PARTITIONS.csv',index=False)
# Verify fee-paid entry total directly from actual source trades.
trade=[x for x in a['trades'] if x['side']=='buy' and x['at'].startswith('2022-01-05')];cost=sum((Decimal(x['gross_cny'])+Decimal(x['fees_cny']) for x in trade),Decimal(0));assert len(trade)==52
for p in [W/'case-stage-ledger-20261031/v3/joint_v3.py',W/'account-risk-ablation-20261031/route_without_account_check.py',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py'),M/'rs-h1-execution-20261025/code/sector_stock_admission.py']:h(p)
summary=dict(members=len(ids),sectors=len(sectors),actual_fills=52,fill_roles=dict(collections.Counter(x['role'] for x in fills)),fill_pools=dict(collections.Counter(x['pool'] for x in fills)),mobile_prior_core_rejected=sum(x['core_attempted'] for x in failed),all_48_include_probe_risk=True,mobile_only=[x['sid'] for x in failed if not x['core_attempted']],actual_entry_cost=cost,member_four_endpoint_state_cells=len(ids)*4*3,member_all_states_match_original=True,score_max_abs_diff=maxerr,industry_common_formula_exact=True,M3_industry_counts=signal.M3_common_candidate.value_counts().to_dict(),PVR3_industry_counts=signal.PVR3_common_candidate.value_counts().to_dict(),M3_fill_counts=z.M3_common_candidate.value_counts().to_dict(),PVR3_fill_counts=z.PVR3_common_candidate.value_counts().to_dict(),all25_H1_complete_same_source=bool(paths.complete_same_source_H1.all()),original_52_positive=int(z.pnl.gt(0).sum()),original_52_negative=int(z.pnl.lt(0).sum()),new_account_runs=0,parameter_searches=0,original_sources_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hs.items()))
save('SOURCE_HASHES.json',hs);save('QA.json',summary);print(json.dumps(clean(summary),ensure_ascii=False,indent=2));print(paths[['industry','actual_fills','pre_December','signal_Jan4','post_January','post_Q1','post_Q2','post_H1','post_H1_MDD','post_H1_rebound_after_min']].to_string(index=False))
