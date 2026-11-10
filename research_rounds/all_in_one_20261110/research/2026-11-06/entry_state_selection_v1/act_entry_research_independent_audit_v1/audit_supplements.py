import json,gzip,pathlib,collections
import pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'act_entry_research_independent_audit_v1';S=R/'act_only_ablation_continuous_v1';F=R/'act_candidate_funnel_v1';N=R/'act_entry_loss_attribution_v1'
result={};df=pd.read_parquet(F/'ROLE_CANDIDATE_TRACE.parquet');periods=json.loads((F/'CONTRACT.json').read_text())['periods'];days=[]
for line in gzip.open(S/'run/pair/daily.jsonl.gz','rt'):
 d=json.loads(line)
 if d['account']=='PVR':days.append(d['at'][:10])
prev={d:days[i-1] for i,d in enumerate(days) if i};fund=collections.defaultdict(list)
for line in gzip.open(S/'run/pair/funding.jsonl.gz','rt'):
 t=json.loads(line)
 if t['at'][11:16]!='15:10':fund[t['account'],prev[t['at'][:10]],t['sid'],t['role']].append(t['result'])
for t in df.itertuples():assert t.open_result==';'.join(fund.get((t.account,t.signal_day,t.sid,t.role),[]))
previews={'missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract'};budget={'cash_or_original_reserve','pool_capital','probe_risk','sector_capital','sector_risk','stock_capital','minimum_unit_not_funded'}
rows=[]
for t in df.itertuples():
 vals=fund.get((t.account,t.signal_day,t.sid,t.role),[]);reasons=set(x for v in vals for x in v.split(','));rows.append((bool(vals),bool(vals) and not bool(set(vals)&previews),'industry_invalidated' in vals,bool(reasons&budget),'reserved' in vals))
df[['logged','route','invalid','budget','reserve']]=rows;df['right']=df.original_pending & df.signal_day.eq(days[-1]) & ~df.logged
published=pd.read_csv(F/'EXACT_ROUTE_AND_ORDER_COUNTS.csv')
for p in published.itertuples():
 g=df[df.account.eq(p.account)&df.signal_day.between(*periods[p.period])&df.role.eq(p.role)&df.held_at_signal.eq(p.held_at_signal)]
 if p.scope=='LEGAL_ACTIVE_RANKED':g=g[g.legal_ranked]
 expected={'role_rows':len(g),'native_pending':int(g.original_pending.sum()),'logged_open_attempts':int(g.logged.sum()),'entered_original_route':int(g.route.sum()),'industry_invalidated':int(g.invalid.sum()),'budget_rejected':int(g.budget.sum()),'positive_reserve':int(g.reserve.sum()),'actual_buy_orders':int(g.actual_buy.sum()),'actual_first_entry_orders':int(g.actual_first_entry.sum()),'same_stock_other_role_reserved':int(g.exclusive_role_stage.eq('SAME_STOCK_OTHER_ROLE_RESERVED').sum()),'right_censored':int(g.right.sum())}
 for k,v in expected.items():assert getattr(p,k)==v,(p.account,p.period,p.role,p.scope,k,v,getattr(p,k))
 assert p.native_pending==p.logged_open_attempts+p.same_stock_other_role_reserved+p.right_censored
 assert p.entered_original_route==p.industry_invalidated+p.budget_rejected+p.positive_reserve
old=pd.read_parquet(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');old=old[old.account.eq('PVR')].set_index(['day','sid']);new=df[df.account.eq('PVR')&df.role.eq('mobile')&~df.held_at_signal&df.legal_ranked].set_index(['signal_day','sid']);assert set(old.index)==set(new.index) and len(old)==53121
new.index.names=old.index.names;joined=old.join(new,lsuffix='_old',rsuffix='_new');assert (joined.CP1_id_old==joined.CP1_id_new).all() and (joined.original_priority_rank==joined.priority_rank).all();assert abs(joined.original_PVR-joined.PVR_score).max()==0
result['funnel_supplement']={'status':'PASS','open_funding_trace_rows_verified':len(df),'route_summary_rows_verified':len(published),'original_empty_mobile_queue_exact':len(old),'no_transfer_of_old_7871_rate':True}
# First-entry prefeatures, all original signal times and immutable trade floors.
freeze=json.loads((N/'FREEZE.json').read_text());rounds=pd.read_csv(N/'ALL_ROUND_ATTRIBUTION.csv').set_index(['account','round_id']);feat=pd.read_csv(N/'PREENTRY_FEATURES_ALL.csv');term=pd.read_csv(N/'TERMINAL_PRICE_GIVEBACK.csv').set_index(['account','round_id']);paths=pd.read_csv(N/'DAILY_HELD_PATH.csv');pmap={k:g for k,g in paths.groupby(['account','round_id'])};buys={};lastsales={};splits=collections.defaultdict(list)
for arm in ['PVR','NOACT']:
 a=json.load(gzip.open(S/f'run/pair/{arm}.json.gz','rt'))
 for t in a['trades']:
  if t['side']=='buy':buys[arm,int(t['layer'])]=t
  else:
   for p in t['parts']:lastsales[arm,int(p['layer'])]=t
 for t in a['journal']:
  if t['kind']=='actual_split':splits[arm,t['sid']].append(t)
origround=pd.read_csv(S/'analysis/STOCK_ROUNDS.csv').set_index(['account','round_id']);cal=pd.read_parquet(freeze['price_source_by_sid']['000001.SZ']).index;cal=cal[cal<='2026-05-15'];assert list(cal[cal>='2022-01-01'].strftime('%Y-%m-%d'))==days
maxerror=0.;verified=0
for sid,g in feat.groupby('sid'):
 source=pd.read_parquet(freeze['price_source_by_sid'][sid]).reindex(cal)
 good=source.price_eligible.eq(True)&source.observed_bar.eq(True)&source.source_invalid.eq(False)&source.synthetic_event_bar.eq(False)&np.isfinite(source.close)&source.close.gt(0)
 def valid_window(ids):
  z=source.iloc[ids];return bool(len(z) and good.iloc[ids].all() and all(z[c].notna().all() and z[c].nunique()==1 for c in ['source_kind','source_path','segment_id']))
 for t in g.itertuples():
  key=(t.account,t.round_id);rr=rounds.loc[key];buy=buys[t.account,int(rr.initial_layer)];assert t.signal_at==buy['signal_at'] and t.opened==buy['at'] and t.signal_at<t.opened;assert abs(t.signal_floor-float(buy['floor']))<1e-10
  i=cal.get_loc(pd.Timestamp(t.signal_at[:10]));values={}
  for n in [1,5,21]:
   ix=np.arange(i-n,i+1);values['log_return_'+str(n)]=float(np.log(source.close.iloc[i]/source.close.iloc[i-n])) if i>=n and valid_window(ix) else np.nan
  ix=np.arange(i-21,i+1);amount=source.amount.iloc[ix];values['amount_ratio_prev21']=float(amount.iloc[-1]/np.median(amount.iloc[:-1])) if i>=21 and valid_window(ix) and np.isfinite(amount).all() and amount.gt(0).all() else np.nan
  values['log_distance_signal_floor']=float(np.log(source.close.iloc[i]/float(buy['floor']))) if valid_window([i]) and np.isfinite(float(buy['floor'])) and float(buy['floor'])>0 else np.nan
  for k,v in values.items():
   actual=getattr(t,k);assert np.isfinite(v)==(getattr(t,k+'_status')=='KNOWN') and (pd.isna(v)==pd.isna(actual))
   if np.isfinite(v):maxerror=max(maxerror,abs(v-actual));assert abs(v-actual)<1e-11
  expected='OPEN_RETAINED' if rr.round_status=='OPEN' else ('STALLED20_FINAL_LOSS' if rr.round_pnl<0 and rr.round_progress20=='STALLED20' else ('BIG_WINNER30' if rr.round_return>=.3 else 'OTHER_CLOSED_RETAINED'));assert t.group==expected
  tp=term.loc[key];pp=pmap[key]
  for pref in ['initial','round']:
   p=pp[pp.initial_layer_live] if pref=='initial' else pp;values=p.close_price_return.dropna();peak=values.max()
   if rr[pref+'_status']=='CLOSED':
    lids=[int(rr.initial_layer)] if pref=='initial' else json.loads(origround.loc[key,'layer_ids']);sale=max((lastsales[t.account,k] for k in lids),key=lambda x:x['at']);factor=np.prod([float(x['ratio']) for x in splits[t.account,sid] if buy['at']<x['at']<=sale['at']]);v=float(sale['price'])*factor/float(buy['price'])-1;assert tp[pref+'_terminal_basis']=='ACTUAL_LAST_SELL_FILL'
   else:v=float(p.iloc[-1].close_price_return);assert tp[pref+'_terminal_basis']=='OBSERVED_LAST_HELD_CLOSE_OR_UNKNOWN'
   assert abs(v-tp[pref+'_terminal_price_return'])<1e-11 or pd.isna(v) and pd.isna(tp[pref+'_terminal_price_return'])
   assert abs(peak-v-tp[pref+'_observed_peak_minus_terminal_pp'])<1e-11 or pd.isna(v)
  verified+=1
slow=pd.read_csv(N/'STALLED20_LATE_WINNERS.csv');allr=rounds.reset_index()
for t in slow.itertuples():
 z=allr[allr.account.eq(t.account)&allr.round_progress20.eq('STALLED20')]
 if str(t.entry_year)!='ALL':z=z[z.entry_year.eq(int(t.entry_year))]
 assert len(z)==t.stalled_total
 winners=z[z.round_status.eq('CLOSED') & (z.round_pnl.gt(0) if t.threshold==0 else z.round_return.ge(t.threshold))];assert len(winners)==t.closed_winners_n and abs(winners.round_pnl.sum()-t.round_net)<1e-7
result['loss_supplement']={'status':'PASS','preentry_feature_rows':verified,'terminal_price_rows':len(term),'max_preentry_value_difference':maxerror,'slowwinner_rows':len(slow),'limits':['Pre-entry adjusted prices remain NON-PIT. These are descriptive overlapping groups, not fit or predictive gates.','Terminal last-fill versus observed held-close peak is a price drawdown descriptor, not captured executable peak profit.','Report rendering and newly added FAST_LOSS group need final separate file verification.']}
(O/'SUPPLEMENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
