"""Read-only saved-ledger description. Never imports strategy or consumer modules."""
from pathlib import Path
from collections import defaultdict,deque
import json,hashlib,math
import numpy as np,pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent;H={}
def source(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(np.bool_,)):return bool(x)
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
source(O/'FEATURE_CONTRACT.md')
ov=pd.read_parquet(source(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'));ov['signal_day']=ov.day.dt.strftime('%Y-%m-%d');assert not ov.duplicated(['sid','signal_day']).any()
bp=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet';b=pd.read_parquet(source(bp));b['signal_day']=b.day.dt.strftime('%Y-%m-%d');assert not b.duplicated(['sector','signal_day']).any()
with np.load(source('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'),allow_pickle=False) as z:cal=pd.DatetimeIndex(z['dates'])
manifest={x['symbol']:x for x in json.loads(source('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
daily=pd.read_parquet(source(R/'independent_channel_full1709_preflight_v1/DAILY_STATES.parquet'),columns=['sid','day','window','root_day','Q']).sort_values(['sid','day']);daily['previous_Q']=daily.groupby(['sid','window']).Q.shift();daily['previous_root_day']=daily.groupby(['sid','window']).root_day.shift();daily['signal_day']=daily.day.dt.strftime('%Y-%m-%d')
parts=[];reps={};case_rounds={}
for year,w in [(2022,'2022'),(2024,'2024_924')]:
 e=R/f'independent_channel_joint_economic_v1/economic_{year}';reps[year]=rep=json.loads(source(e/'COMPARISON_REPORT_RECOVERED.json').read_text());rounds=pd.read_csv(source(e/'joint/ROUNDS.csv'));actions=pd.read_csv(source(e/'joint/ACTIONS.csv'));common=set(rep['summary'][0]['common_covered_sids']);rr=rounds.set_index('round_id')
 if year==2022:
  r=pd.read_csv(source(R/'price_loss_attribution_2022_v1/PRICE_ROUND_ATTRIBUTION_FINAL.csv'),low_memory=False);assert len(r)==2411
 else:
  r=rounds[rounds.owner_lane.eq('PRICE')].merge(ov[ov.window.astype(str).eq(w)],on=['sid','signal_day'],how='left',suffixes=('','_m'),indicator=True,validate='many_to_one');assert r._merge.eq('both').all()
  r['common']=r.sid.isin(common);r['full_closed']=r.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND');r['closed_total_pnl']=r.net_pnl.where(r.full_closed)
  r['stock_gate']=np.where(~r.old_e0_ready,'E0_NOT_READY',np.where(~r.old_e0_target,'E0_OFF',np.where(~r.old_i_target,'E0_ON_I_OFF','E0_ON_I_ON')));r['ticket']=np.where(r.born,'ROOT_BIRTH','CONTINUING_FRONTIER');r['signal_quarter']=pd.to_datetime(r.signal_day).dt.to_period('Q').astype(str)
  r['root_age_sessions']=[int(((cal>pd.Timestamp(rd))&(cal<=pd.Timestamp(d))).sum()) for rd,d in zip(r.root_day,r.signal_day)]
  r['confirmation_age_sessions']=[int(((cal>pd.Timestamp(c))&(cal<=pd.Timestamp(d))).sum()) if pd.notna(c) else np.nan for c,d in zip(r.confirmed_at,r.signal_day)]
  r['signal_amount_over_frozen_B']=r.amount/r.B
  r=r.merge(daily[['sid','signal_day','previous_Q','previous_root_day']],on=['sid','signal_day'],how='left',validate='many_to_one');same=pd.to_datetime(r.root_day).eq(r.previous_root_day);r['current_day_credit_increment_from_saved_daily']=r.Q.sub(r.previous_Q).where(same);r['credit_increment_known']=same&r.Q.notna()&r.previous_Q.notna()
  cur=[]
  for sid,g in r.groupby('sid',sort=False):
   m=manifest[sid];p=Path(next(k for k in m['source_sha256'] if k.endswith('/signal.parquet')));source(p);assert H[str(p)]==m['source_sha256'][str(p)]
   raw=pd.read_parquet(p,columns=['high','close','source_kind','source_path','segment_id','price_eligible','source_invalid']).reindex(cal);hi=raw.high.rolling(20,min_periods=20).max().shift(1)
   for z in g.itertuples():
    day=pd.Timestamp(z.signal_day);ix=cal.get_loc(day);q=raw.iloc[ix-20:ix+1];same=q[['source_kind','source_path','segment_id']].nunique(dropna=False).le(1).all();valid=q.price_eligible.fillna(False).all() and not q.source_invalid.fillna(True).any();hh=float(hi.loc[day]) if same and valid else np.nan;assert math.isclose(float(raw.loc[day,'close']),float(z.C),rel_tol=1e-11);cur.append(dict(round_id=z.round_id,contemporary_prior20_high=hh,contemporary_20high_break=None if not np.isfinite(hh) else bool(z.C>hh)))
  r=r.merge(pd.DataFrame(cur),on='round_id',validate='one_to_one');r['break20_fact']=r.contemporary_20high_break.map({True:'BREAKS_CURRENT_20HIGH',False:'DOES_NOT_BREAK_CURRENT_20HIGH'}).fillna('UNKNOWN')
  acc=defaultdict(lambda:defaultdict(float));lots=defaultdict(deque)
  for a in sorted(rep['normalized_actions'],key=lambda a:(str(a['known_day']),int(a['sequence']))):
   if a['arm']!='joint' or a['lane']!='PRICE':continue
   rid=a['round_id'];role=a['role'];q,p,f=float(a['q']),float(a['price']),float(a['fee']);acc[rid]['fees']+=f
   if a['side']=='BUY':lots[(rid,role)].append([q,q*p+f])
   else:
    rem=q;cost=0
    while rem>1e-8:
     lot=lots[(rid,role)][0];take=min(rem,lot[0]);c=lot[1]*take/lot[0];cost+=c;rem-=take;lot[0]-=take;lot[1]-=c
     if lot[0]<1e-8:lots[(rid,role)].popleft()
    acc[rid][role+'_realized']+=q*p-f-cost
  for (rid,role),ls in lots.items():acc[rid]['remaining_known_cost']+=sum(z[1] for z in ls)
  for c in rep['normalized_claims']:
   if c['arm']=='joint' and c['lane']=='PRICE' and c['legal_ex_confirmed'] is True:acc[c['round_id']]['net80_income']+=float(c['amount'])
  for c in ['fees','PROBE_realized','ADD_realized','remaining_known_cost','net80_income']:r[c]=r.round_id.map(lambda rid:acc[rid][c])
  assert np.allclose(r.loc[r.full_closed,'PROBE_realized']+r.loc[r.full_closed,'ADD_realized']+r.loc[r.full_closed,'net80_income'],r.loc[r.full_closed,'closed_total_pnl'],atol=1e-7)
 # Same saved-action ordinal and prior-round clocks in each independent window.
 buy=actions[actions.side.eq('buy_core')].sort_values(['day','sid','round_id']).copy();buy['all_strategy_buy_number']=buy.groupby('sid').cumcount()+1;buy['prior_all_round_id']=buy.groupby('sid').round_id.shift();buy['prior_all_exit_day']=buy.prior_all_round_id.map(rr.exit_day);buy['prior_all_owner']=buy.prior_all_round_id.map(rr.owner_lane);buy=buy.merge(rounds[['round_id','owner_lane']],on='round_id',validate='one_to_one');pb=buy[buy.owner_lane.eq('PRICE')].copy();pb['price_buy_number']=pb.groupby('sid').cumcount()+1;pb['prior_price_round_id']=pb.groupby('sid').round_id.shift()
 cols=['round_id','all_strategy_buy_number','price_buy_number','prior_all_round_id','prior_all_exit_day','prior_all_owner','prior_price_round_id'];r=r.drop(columns=[c for c in cols[1:] if c in r]).merge(pb[cols],on='round_id',how='left',validate='one_to_one');r['actual_buy']=r.price_buy_number.notna();r['participation']=np.where(~r.actual_buy,'NO_BUY',np.where(r.all_strategy_buy_number.eq(1),'FIRST_ALL_STRATEGY_BUY',np.where(r.price_buy_number.eq(1),'FIRST_PRICE_AFTER_AB','REPEAT_PRICE')))
 r['root_day']=pd.to_datetime(r.root_day);prior_exit=pd.to_datetime(r.prior_all_exit_day);sig=pd.to_datetime(r.signal_day);assert (prior_exit.dropna()<=sig[prior_exit.notna()]).all()
 r['entry_root_relation']=np.select([~r.actual_buy,r.all_strategy_buy_number.eq(1),prior_exit.isna(),r.root_day.gt(prior_exit),r.root_day.eq(prior_exit),r.root_day.lt(prior_exit)],['NO_BUY','FIRST_WINDOW_BUY','UNKNOWN_PRIOR_EXIT','ROOT_BORN_AFTER_PREVIOUS_EXIT','ROOT_BORN_ON_PREVIOUS_EXIT_DAY','ROOT_ALREADY_EXISTED_AT_PREVIOUS_EXIT'],default='UNKNOWN')
 # Replace existing partial breadth columns with the identical complete source.
 bc=[c for c in b if c not in ['day','signal_day','sector']];r=r.drop(columns=[c for c in bc if c in r]);r=r.merge(b.drop(columns=['day']),on=['sector','signal_day'],how='left',validate='many_to_one');assert r.N.notna().all();r['M3_entry']=r.M3_candidate.map({1:'ON',0:'OFF',-1:'UNKNOWN'});r['PVR3_entry']=r.PVR3_candidate.map({1:'ON',0:'OFF',-1:'UNKNOWN'})
 r['entry_cell']=r.participation+' | '+r.ticket+' | '+r.stock_gate+' | '+r.phase;r['Q_over_R']=r.Q/r.R;r['signal_month']=r.signal_day.str[:7];r['year']=year;r['fresh_confirmation_state']=np.where(r.phase.eq('CONFIRMED'),np.where(r.confirmed_now,'CONFIRMED_TODAY','CONFIRMED_EARLIER'),r.phase);r['retry_evidence']='UNKNOWN_NOT_PROVIDED_REAL_SUBMITTED_ZERO_OR_PARTIAL';r['protective_distance_fraction']=1-r.S_new/r.C
 ab=pd.DataFrame(json.loads(source(e/'AB_DECISION_AUDIT.json').read_text()));ab['signal_day']=ab.day.str[:10];r=r.drop(columns=['decision_before_joint'],errors='ignore').merge(ab[['sid','signal_day','decision_before_joint']],on=['sid','signal_day'],how='left',validate='many_to_one');r['actual_ab_close_diagnosis']=r.decision_before_joint.fillna('NO_ORIGINAL_AB_EVENT')
 parts.append(r);print('JOINED',year,len(r),flush=True)
x=pd.concat(parts,ignore_index=True);x.to_csv(O/'ENTRY_FACTS.csv',index=False)
def desc(s):
 s=pd.to_numeric(s,errors='coerce').replace([np.inf,-np.inf],np.nan);return dict(n_known=int(s.notna().sum()),n_missing=int(s.isna().sum()),minimum=s.min(),p10=s.quantile(.1),p25=s.quantile(.25),median=s.median(),p75=s.quantile(.75),p90=s.quantile(.9),maximum=s.max())
continuous=['root_age_sessions','confirmation_age_sessions','signal_amount_over_frozen_B','Q_over_R','current_day_credit_increment_from_saved_daily','old_sector_H1_score','M3_right_known','M3_right_fixed_lower','M3_right_fixed_upper','M3_delta3','PVR3_right_known','PVR3_right_fixed_lower','PVR3_right_fixed_upper','PVR3_delta3','N','K','U','protective_distance_fraction','entry_risk']
def agg(g):
 c=g[g.full_closed];u=g[g.status.str.contains('UNKNOWN')];return dict(n_registered=len(g),n_buy=int(g.actual_buy.sum()),n_stocks=int(g.sid.nunique()),n_closed=len(c),n_unknown=len(u),n_unknown_buy=int(u.actual_buy.sum()),n_no_buy=int((~g.actual_buy).sum()),n_q0=int(g.status.eq('PRECHECK_Q0_NO_SUBMIT').sum()),closed_net=c.closed_total_pnl.sum() if len(c) else None,closed_probe=c.PROBE_realized.sum() if len(c) else None,closed_add=c.ADD_realized.sum() if len(c) else None,closed_net80=c.net80_income.sum() if len(c) else None,profit_n=int(c.closed_total_pnl.gt(0).sum()),loss_n=int(c.closed_total_pnl.lt(0).sum()),unknown_known_cost=u.remaining_known_cost.sum())
features=['status','participation','ticket','stock_gate','phase','fresh_confirmation_state','M3_entry','PVR3_entry','entry_root_relation','break20_fact','actual_ab_close_diagnosis','signal_month','signal_quarter','entry_cell'];tables={};distributions={};coverage=[]
for year,g0 in x.groupby('year'):
 for scope,g in [('ALL',g0),('COMMON',g0[g0.common])]:
  prefix=f'{year}__{scope}';coverage.append(dict(year=year,scope=scope,**agg(g),feature_coverage={c:dict(known=int(g[c].notna().sum()),missing=int(g[c].isna().sum())) for c in continuous}));distributions[prefix]={c:desc(g[c]) for c in continuous}
  for fields in [[f] for f in features]+[['participation','ticket'],['ticket','break20_fact'],['M3_entry','stock_gate'],['entry_root_relation','participation']]:
   rows=[]
   for k,z in g.groupby(fields,dropna=False,observed=True):
    k=k if isinstance(k,tuple) else (k,);rows.append(dict(zip(fields,k),**agg(z),continuous={c:desc(z[c]) for c in continuous}))
   assert sum(t['n_registered'] for t in rows)==len(g);assert abs(sum(t['closed_net'] or 0 for t in rows)-g.loc[g.full_closed,'closed_total_pnl'].sum())<1e-6;tables[prefix+'__'+'__'.join(fields)]=rows
  # Outcome labels ONLY for explanatory continuous-distribution comparisons.
  distributions[prefix+'__CLOSED_OUTCOME_DESCRIPTIVE']={label:{c:desc(z[c]) for c in continuous} for label,z in [('PROFIT',g[g.full_closed&g.closed_total_pnl.gt(0)]),('LOSS',g[g.full_closed&g.closed_total_pnl.lt(0)])]}
dump('COVERAGE.json',coverage);dump('TABLES.json',tables);dump('DISTRIBUTIONS.json',distributions)
casecols=['year','sid','name','round_id','signal_day','entry_day','entry_price','entry_q','entry_floor_raw','entry_risk','root_day','ticket','root_age_sessions','confirmed_at','confirmation_age_sessions','phase','confirmed_now','signal_amount_over_frozen_B','Q','R','old_e0_target','old_i_target','old_i_buy','old_sector_H1_score','M3_entry','M3_right_known','M3_right_fixed_lower','M3_right_fixed_upper','M3_delta3','PVR3_entry','PVR3_right_known','PVR3_delta3','all_strategy_buy_number','price_buy_number','entry_root_relation','prior_all_exit_day','prior_all_owner','break20_fact','contemporary_prior20_high','C','S_new','protective_distance_fraction','exit_day','status','common','closed_total_pnl','PROBE_realized','ADD_realized','net80_income']
cases={}
for year,g in x[x.common&x.actual_buy].groupby('year'):
 for label,sub in [('old_root',g[g.ticket.eq('CONTINUING_FRONTIER')]),('new_root',g[g.ticket.eq('ROOT_BIRTH')]),('repeat_price',g[g.participation.eq('REPEAT_PRICE')]),('first_price_after_ab',g[g.participation.eq('FIRST_PRICE_AFTER_AB')])]:
  cases[f'{year}_{label}']={s:z[casecols].astype(object).where(z[casecols].notna(),None).to_dict('records') for s,z in [('profits',sub.nlargest(3,'closed_total_pnl')),('losses',sub.nsmallest(3,'closed_total_pnl'))]}
 cases[f'{year}_named']=g[g.sid.isin(['000977.SZ','605118.SH','605020.SH','002031.SZ','002174.SZ','002583.SZ','300085.SZ','300666.SZ'])][casecols].astype(object).where(g[casecols].notna(),None).to_dict('records')
# stringify timestamps in case artifact; CSV retains full source facts.
cases=json.loads(json.dumps(cases,default=str));dump('CASES.json',cases)
assert np.isclose(x[(x.year==2022)&x.common].closed_total_pnl.sum(),-1187457.6691341577,atol=1e-7);assert np.isclose(x[(x.year==2024)&x.common].closed_total_pnl.sum(),1616562.7357000383,atol=1e-7)
changed=[p for p,h in H.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h];assert not changed;dump('SOURCE_HASHES.json',H);dump('QA.json',dict(all_sources_unchanged=True,groups_count_and_closed_net_conserved=True,economic_reruns=0,filtered_counterfactual_pnl_runs=0,production_or_old_outputs_changed=False,real_zero_partial_retry_evidence='UNKNOWN_NOT_PROVIDED',source_files=len(H),rows=len(x)))
print('DONE',len(x),flush=True)
for k in ['2022__COMMON__entry_root_relation','2024__COMMON__participation','2024__COMMON__ticket','2024__COMMON__stock_gate','2024__COMMON__phase','2024__COMMON__M3_entry','2024__COMMON__entry_root_relation','2024__COMMON__ticket__break20_fact','2024__COMMON__entry_cell']:
 print(k);print(pd.DataFrame([{k:v for k,v in z.items() if k!='continuous'} for z in tables[k]]).to_string(index=False))
