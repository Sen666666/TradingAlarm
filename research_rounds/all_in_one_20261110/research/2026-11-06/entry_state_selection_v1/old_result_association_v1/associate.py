from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');D=R/'old_result_association_v1';G=R/'price_entry_generation_gate_preflight_v1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def js(name,x): (D/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def records(df): return json.loads(df.to_json(orient='records',force_ascii=False))
def truth(x):return x.astype(str).str.lower().eq('true')
f=pd.read_csv(R/'price_entry_mechanism_comparison_v1/ENTRY_FACTS.csv',low_memory=False);g=pd.read_csv(G/'REGISTERED_ENTRY_GATE_FACTS.csv',dtype={'window':str});receipt=pd.read_parquet(G/'RECEIPT_GATE_FACTS.parquet');receipt['window']=receipt.window.astype(str)
for c in ['day','root_day','generation_birth']: receipt[c]=pd.to_datetime(receipt[c],format='mixed').dt.strftime('%Y-%m-%d')
assert g.round_id.is_unique and f.round_id.is_unique
cols=['round_id','sid','day','signal_day','window','name','entry_day','exit_day','status','full_closed','closed_total_pnl','fees','net80_income','remaining_known_cost','identifiable_realized_plus_income','all_strategy_buy_number','price_buy_number','prior_all_exit_day','prior_all_owner','prior_price_round_id']
x=g.merge(f[cols],on='round_id',validate='one_to_one',suffixes=('','_fact'),indicator=True);assert x._merge.eq('both').all();assert x.sid.eq(x.sid_fact).all() and pd.to_datetime(x.day).eq(pd.to_datetime(x.day_fact,format='mixed')).all() and x.day.eq(x.signal_day).all();assert x.window.eq(x.window_fact.astype(str)).all()
x['gate_group']=np.where(x.gate_status.eq('ALLOW'),'ALLOW',np.where(x.gate_status.str.startswith('DENY'),'DENY','UNKNOWN'))
x['actual_buy']=truth(x.actual_buy);x['common']=truth(x.common);x['known_old_full']=x.actual_buy & truth(x.full_closed) & x.closed_total_pnl.notna();x['old_FULL_net']=x.closed_total_pnl.where(x.known_old_full)
x['root_before_flat_start']=x.root_day.lt(x.window.map({'2022':'2022-01-01','2024_924':'2024-09-01','2024':'2024-09-01'}));x['first_all_lane_buy']=x.actual_buy & x.all_strategy_buy_number.eq(1)
allround=[];allactions=[]
for y in [2022,2024]:
 p=R/f'independent_channel_joint_economic_v1/economic_{y}/joint'; rr=pd.read_csv(p/'ROUNDS.csv',low_memory=False);aa=pd.read_csv(p/'ACTIONS.csv',low_memory=False);aa=aa.merge(rr[['round_id','owner_lane']],on='round_id',validate='many_to_one');allround.append(rr);allactions.append(aa)
rr=pd.concat(allround,ignore_index=True); aa=pd.concat(allactions,ignore_index=True)
for col in ['prior_PRICE_buy_count','prior_PRICE_sell_count','prior_any_buy_count','prior_any_sell_count','later_PRICE_buy_count','later_any_buy_count']:x[col]=0
for i,r in x.iterrows():
 a=aa[(aa.sid==r.sid)&(aa.window.astype(str)==r.window)]; before=a[a.day<=r.day];later=a[a.day>str(r.entry_day)] if r.actual_buy else a[a.day>r.day]
 for lane,label in [('PRICE','PRICE'),(None,'any')]:
  b=before if lane is None else before[before.owner_lane.eq(lane)];l=later if lane is None else later[later.owner_lane.eq(lane)]
  x.at[i,f'prior_{label}_buy_count']=int(b.side.eq('buy_core').sum());x.at[i,f'prior_{label}_sell_count']=int(b.side.str.startswith('sell').sum());x.at[i,f'later_{label}_buy_count']=int(l.side.eq('buy_core').sum())
 # Exact original FULL reconciliation, only closed rows.
 if r.known_old_full:
  orig=rr[rr.round_id.eq(r.round_id)].iloc[0];assert abs(orig.net_pnl-r.old_FULL_net)<1e-7
x['prior_PRICE_buy']=x.prior_PRICE_buy_count.gt(0);x['prior_PRICE_sell']=x.prior_PRICE_sell_count.gt(0)
def summary(t):
 k=t[t.known_old_full];v=k.old_FULL_net
 return dict(original_registered_rounds=len(t),actual_proxy_buy=int(t.actual_buy.sum()),known_full_buy=len(k),unknown_full_buy=int((t.actual_buy&~t.known_old_full).sum()),no_buy=int((~t.actual_buy).sum()),no_buy_unknown_status=int((~t.actual_buy&t.status.str.contains('UNKNOWN',case=False)).sum()),old_FULL_net=float(v.sum()) if len(k) else None,winners=int(v.gt(0).sum()),losers=int(v.lt(0).sum()),zero=int(v.eq(0).sum()),gross_winning_net_sum=float(v[v>0].sum()) if len(k) else None,gross_losing_net_sum=float(v[v<0].sum()) if len(k) else None,included_fees_known_full=float(k.fees.sum()) if len(k) else None,known_paid_fees_unknown_buy=float(t.loc[t.actual_buy&~t.known_old_full,'fees'].sum()),stocks=int(t.sid.nunique()))
s=[];stock=[];bounds=[]
for w,t in x.groupby('window'):
 for scope,u in [('ALL',t),('COMMON',t[t.common])]:
  for gate,v in [('TOTAL',u)]+list(u.groupby('gate_group')):
   s.append(dict(window=w,scope=scope,gate=gate,**summary(v)))
   for sid,z in v.groupby('sid'):stock.append(dict(window=w,scope=scope,gate=gate,sid=sid,name=z.name.iloc[0],**summary(z)))
  dn=u[u.actual_buy&u.gate_group.eq('DENY')]
  for label in ['root_before_flat_start','first_all_lane_buy','prior_PRICE_buy','prior_PRICE_sell']:
   bounds.append(dict(window=w,scope=scope,attribute=label,denominator=len(dn),count=int(dn[label].sum()),fraction=float(dn[label].mean()) if len(dn) else None))
assert len(x[x.common&x.actual_buy&x.gate_group.eq('DENY')])==167
assert list(x[x.common&x.actual_buy&x.gate_group.eq('DENY')].groupby('window').size())==[117,50]
x.to_csv(D/'ALL_ASSOCIATED_ROUNDS.csv',index=False);deny=x[x.gate_group.eq('DENY')];deny.to_csv(D/'ALL_DENY_ROUNDS.csv',index=False);deny[deny.common&deny.actual_buy].to_csv(D/'COMMON_167_DENY_BUYS.csv',index=False)
pd.DataFrame(s).to_csv(D/'SUMMARY.csv',index=False);js('SUMMARY.json',s);pd.DataFrame(stock).to_csv(D/'PER_STOCK_OLD_RESULTS.csv',index=False);pd.DataFrame(bounds).to_csv(D/'LEFT_BOUNDARY_STRATA.csv',index=False)
# Preserve all original joint rounds for every DENY stock, not just outcome-selected cases.
ids=set(deny.sid);related=rr[rr.sid.isin(ids)].merge(x[['round_id','gate_status','generation','generation_birth','root_day','common']],on='round_id',how='left',validate='one_to_one');related.to_csv(D/'DENY_STOCK_ALL_ORIGINAL_ROUNDS.csv',index=False)
rc=receipt[receipt.sid.isin(ids)];rc.to_csv(D/'DENY_STOCK_ALL_RECEIPT_GENERATIONS.csv',index=False)
cases=[];overlap=[]
for scope,w,t in [(scope,w,t) for scope,sub in [('COMMON',deny[deny.common&deny.known_old_full]),('ALL',deny[deny.known_old_full])] for w,t in sub.groupby('window')]:
 for sign,v in [('positive',t[t.old_FULL_net>0].nlargest(3,'old_FULL_net')),('negative',t[t.old_FULL_net<0].nsmallest(3,'old_FULL_net'))]:
  for r in v.itertuples():
   q=related[(related.sid==r.sid)&(related.window.astype(str)==w)].sort_values('signal_day'); rec=rc[(rc.sid==r.sid)&(rc.window==w)]
   original=x[(x.sid==r.sid)&(x.window==w)]
   item=dict(scope=scope,window=w,post_hoc_sign=sign,round_id=r.round_id,sid=r.sid,name=r.name,signal_day=r.day,old_FULL_net=r.old_FULL_net,root_day=r.root_day,generation=r.generation,generation_birth=r.generation_birth,first_all_lane_buy=r.first_all_lane_buy,root_before_flat_start=r.root_before_flat_start,all_original_stock_rounds=records(q))
   for relation,sel in [('earlier',rec[rec.day<r.day]),('same_day',rec[rec.day==r.day]),('later',rec[rec.day>r.day])]:
    for (root,gen,status),z in sel.groupby(['root_day','generation','gate_status'],dropna=False):
     overlap.append(dict(scope=scope,case_round_id=r.round_id,sid=r.sid,window=w,temporal_relation=relation,root_day=root,generation=gen,gate_status=status,receipt_count=len(z),first_receipt=z.day.min(),last_receipt=z.day.max(),same_original_root=bool(root==r.root_day),same_entry_generation=bool(root==r.root_day and gen==r.generation),original_registered_round_ids=';'.join(original[(original.root_day==root)&(original.generation==gen)].round_id)))
   cases.append(item)
assert all(z['same_original_root'] and z['same_entry_generation'] for z in overlap if z['temporal_relation']=='same_day')
js('TOP_CASES.json',cases);pd.DataFrame([{k:v for k,v in c.items() if k!='all_original_stock_rounds'} for c in cases]).to_csv(D/'TOP_CASES.csv',index=False);pd.DataFrame(overlap).to_csv(D/'TOP_CASE_RECEIPT_OVERLAP.csv',index=False)
# CORE_SUMMARY_RECOVERED is aggregate joint/common summary, not independent per-round initial-layer dated-fee result. No exact independent CORE file exists in frozen original joint directories.
core=dict(available=False,reason='Frozen original joint reports contain whole rounds and actions; CORE_SUMMARY_RECOVERED is aggregate common/joint summary. No exact independent per-round initial layer with independently recalculated dated fees is supplied. Allocated PROBE_realized is not independent CORE; no CORE association produced.',original_report_inventory=[str(p.relative_to(R)) for y in [2022,2024] for p in (R/f'independent_channel_joint_economic_v1/economic_{y}').rglob('*') if p.is_file()]);js('CORE_AVAILABILITY.json',core)
before=json.loads((D/'INPUT_HASHES_BEFORE.json').read_text());after={p:sha(Path(p)) for p in before};assert before==after;js('INPUT_HASHES_AFTER.json',after)
qa=dict(all_sources_unchanged=True,exact_round_join=True,original_closed_FULL_reconciled=True,all_common_deny_retained=167,economic_runs=0,parameters_changed=0,CORE_available=False,gate_key_sha256=sha(D/'FROZEN_GATE_KEYS.json'),original_registered_rounds=len(x),real_ACK_fill='UNKNOWN_NOT_PROVIDED',gross_sums_definition='sum of positive/negative net FULL outcomes, not pre-fee PnL',unknown_not_zero=True);js('QA.json',qa)
lines=['# Frozen gate: association with original historical FULL results','', 'Protocol and input hashes were saved before loading PnL columns. Prior semantic READOUT reports (including known aggregates) were already read. This is post hoc original-path association, NOT avoided losses, strategy gains, a new win rate, filtered performance or counterfactual equity.','', 'Static NON-PIT universe; conditional next-common OPEN full-fill proxy only. Real ACK/fill unknown. Original registered rounds mean old round/SELECTED_PENDING, NOT ExecutionBook target_registered. The 28 no-BUY rounds are not evidence of true zero-fill/partial orders. The proposed gate concerns only new initial parent creation; an existing parent and its fixed Q−F remainder do not reread it. Original root/Q/S/ADD/receipts/results are unchanged.','', '## Original denominators and FULL sums','Amounts CNY. Gross gains/losses below sum positive/negative net round outcomes; fees already included, never subtract again. UNKNOWN total result remains blank/null.']
for z in s:
 lines.append(f"- {z['window']} {z['scope']} {z['gate']}: registered {z['original_registered_rounds']}; proxy BUY {z['actual_proxy_buy']}; known {z['known_full_buy']}; UNKNOWN BUY {z['unknown_full_buy']}; no BUY {z['no_buy']}; old FULL net {z['old_FULL_net']}; W/L/Z {z['winners']}/{z['losers']}/{z['zero']}; positive/negative sums {z['gross_winning_net_sum']}/{z['gross_losing_net_sum']}; included known fees {z['included_fees_known_full']}.")
lines+=['','## Left boundary and previous participation','Independent FLAT boundaries are 2022-01-01 and 2024-09-01; these are not consecutive windows of one account. Prior actual BUY/SELL counts come from original joint ACTIONS at dates ≤ signal CLOSE; later BUY counts are after original first entry date. Root-before-window and first BUY are descriptive, not age/time gates.']
for z in bounds:lines.append(f"- {z['window']} {z['scope']} DENY {z['attribute']}: {z['count']}/{z['denominator']} ({z['fraction']:.2%}).")
lines+=['','## Post hoc cases (COMMON and ALL DENY separately)','Complete ALL and COMMON DENY tables remain saved. Case ranks cannot change the gate or create exemptions. TOP_CASES.json lists every original joint round of each case stock; TOP_CASE_RECEIPT_OVERLAP.csv lists earlier/same-day/later saved receipt generations and whether root/generation overlap. All receipts for all DENY stocks are also preserved.']
for c in cases:lines.append(f"- {c['window']} {c['scope']} {c['post_hoc_sign']}: {c['sid']} {c['name']} {c['signal_day']}, old FULL {c['old_FULL_net']:.2f}; original stock rounds {len(c['all_original_stock_rounds'])}.")
lines+=['','## CORE unavailable',core['reason'],'','## Evidence','ALL_ASSOCIATED_ROUNDS.csv; ALL_DENY_ROUNDS.csv; COMMON_167_DENY_BUYS.csv; SUMMARY.csv/JSON; PER_STOCK_OLD_RESULTS.csv (known partial sums plus UNKNOWN counts, never an unknown stock total); LEFT_BOUNDARY_STRATA.csv; DENY_STOCK_ALL_ORIGINAL_ROUNDS.csv; DENY_STOCK_ALL_RECEIPT_GENERATIONS.csv; TOP_CASES.csv/JSON; TOP_CASE_RECEIPT_OVERLAP.csv; CORE_AVAILABILITY.json; QA.json; PROTOCOL.md; FREEZE.json; INPUT_HASHES_BEFORE/AFTER.json; FROZEN_GATE_KEYS.json; associate.py; OUTPUT_HASHES.json.','Source hashes unchanged. No economic engine imported or executed. No causal attribution or continuous-system conclusion follows from these two independently FLAT samples.']
(D/'READOUT.md').write_text('\n'.join(lines)+'\n');js('OUTPUT_HASHES.json',{p.name:sha(p) for p in D.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(pd.DataFrame(s).to_string(index=False));print(pd.DataFrame(bounds).to_string(index=False));print(pd.DataFrame([{k:v for k,v in c.items() if k!='all_original_stock_rounds'} for c in cases]).to_string(index=False))
