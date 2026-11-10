"""Saved-fact, source-hashed read-only preflight. No economic engine or consumer imports."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,ast,math
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'first_late_contraction_preflight_v1'
H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def csv(p,**kw):return pd.read_csv(src(p),**kw)
def js(p):return json.loads(src(p).read_text())
def clean(v):
 if isinstance(v,dict):return {str(k):clean(a) for k,a in v.items()}
 if isinstance(v,(list,tuple)):return [clean(a) for a in v]
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,pd.Timestamp):return v.strftime('%Y-%m-%d')
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write(n,d):d.to_csv(O/n,index=False)
start={2022:'2022-01-04',2024:'2024-09-02'}
x=csv(R/'price_entry_right_breadth_diagnosis_v1/ALL_PRICE_ENTRY_FACTS.csv',low_memory=False)
z=x[x.actual_buy&x.ticket.eq('CONTINUING_FRONTIER')&x.participation.eq('FIRST_ALL_STRATEGY_BUY')].copy()
z['prewindow_root_recomputed']=[d<start[y] for y,d in zip(z.year,z.root_day)]
assert z.all_strategy_buy_number.eq(1).all() and (~z.born).all() and z.receipt.all() and z.new_frontier.all()
assert z.root_day.lt(z.signal_day).all() and z.entry_root_relation.eq('FIRST_WINDOW_BUY').all()
base=csv(R/'late_frontier_entry_preflight_v1/REGISTERED_ENTRY_BASE_FACTS.csv',low_memory=False)
assert z.prewindow_root_recomputed.eq(z.round_id.map(base.set_index('round_id').prewindow_root_fact)).all()
m=csv(R/'late_frontier_entry_preflight_v1/MARKET_RECEIPT_BASE_FACTS.csv',low_memory=False)
assert not m.duplicated(['year','sid','day']).any()
m['root_tuple']=[(s,i,d) for s,i,d in zip(m.sid,m.identity,m.root_day)]
mroot={k:g.sort_values('day') for k,g in m.groupby(['year','root_tuple'])}
mi=m.set_index(['year','sid','day'])
z['root_tuple']=[(s,i,d) for s,i,d in zip(z.sid,z.identity,z.root_day)]
z['strict_window_birth']=~z.prewindow_root_recomputed
def agg(h):
 r=dict(actual_n=len(h),economic_unknown=int(h.economic_partition.eq('ECONOMIC_UNKNOWN').sum()),known_financial_uncovered=int(h.economic_partition.eq('KNOWN_BUT_FINANCIAL_UNCOVERED').sum()),covered_open_censored=int(h.economic_partition.eq('COVERED_OPEN_CENSORED').sum()),covered_closed=int(h.economic_partition.eq('COVERED_CLOSED').sum()),prewindow_roots=int(h.prewindow_root_recomputed.sum()))
 for role,c in [('CORE','probe_closed_net'),('FULL','full_closed_net')]:
  v=h.loc[h[role+'_financial_closed'],c];r.update({role+'_n':len(v),role+'_wins':int(v.gt(0).sum()),role+'_win_rate':v.gt(0).mean(),role+'_mean':v.mean(),role+'_sum':v.sum() if len(v) else None})
 return r
stats=[]
for y,g0 in z.groupby('year'):
 for scope,g1 in [('ALL',g0),('ORIGINAL_COMMON',g0[g0.common])]:
  for life,g in [('ALL_WINDOW_FIRST',g1),('PREWINDOW_ROOT',g1[g1.prewindow_root_recomputed]),('BORN_IN_WINDOW',g1[g1.strict_window_birth])]:
   for sign in ['TOTAL','POSITIVE','NEGATIVE','FLAT','UNKNOWN']:
    h=g if sign=='TOTAL' else g[g.peer_delta1_robust.eq(sign)]
    stats.append(dict(year=y,scope=scope,lifecycle=life,robust_direction=sign,**agg(h)))
write('TARGET_GROUPS.csv',pd.DataFrame(stats))
# Audit original actions, books and birth-day requests. All original initial order/ACK/fill is a conditional proxy.
audit=[];offermap={};abmap={};actionsmap={};roundsmap={};bookmap={};decmap={}
for y in [2022,2024]:
 e=R/f'independent_channel_joint_economic_v1/economic_{y}'
 a=csv(e/'joint/ACTIONS.csv');rr=csv(e/'joint/ROUNDS.csv');dec=csv(e/'joint/DECISIONS.csv')
 books=js(e/'EXECUTION_BOOKS.json');offers=pd.DataFrame(js(e/'OFFER_AUDIT.json'));offers['ds']=offers.day.str[:10]
 offermap[y]={k:g for k,g in offers.groupby(['sid','ds'])};actionsmap[y]=a;roundsmap[y]=rr;bookmap[y]=books;decmap[y]=dec
 buys=a[a.side.str.startswith('buy')].copy();groups={s:g for s,g in buys.groupby('sid')}
 probe_parents=[]
 for rid,b in books.items():
  for role,p in b.get('parents',{}).items():
   t=p['target'];probe_parents.append(dict(rid=rid,sid=t['root_id'][0],root_tuple=tuple(t['root_id']),role=role,day=t['registered_known_at']['day']))
 pp=pd.DataFrame(probe_parents)
 for q in z[z.year.eq(y)].itertuples():
  bs=groups.get(q.sid,pd.DataFrame(columns=buys.columns));prior=bs[bs.day.str[:10].le(q.signal_day)]
  rootprior=prior[prior.day.str[:10].ge(q.root_day)]
  cur=dec[dec.round_id.eq(q.round_id)]
  assert len(cur)==1 and cur.iloc[0].stock_state_before=='FLAT'
  priorparent=pp[pp.sid.eq(q.sid)&pp.day.le(q.signal_day)]
  sameparent=priorparent[priorparent.root_tuple.map(lambda rt:rt==q.root_tuple)]
  birth=mroot.get((y,q.root_tuple));birth=birth[birth.day.eq(q.root_day)] if birth is not None else pd.DataFrame()
  bo=offermap[y].get((q.sid,q.root_day),pd.DataFrame())
  priorregs=rr[rr.sid.eq(q.sid)&rr.signal_day.lt(q.signal_day)]
  sameregs=priorregs[priorregs.price_root.eq(q.price_root)]
  bbuy=a[a.sid.eq(q.sid)&a.side.str.startswith('buy')&a.signal_day.astype(str).str[:10].eq(q.root_day)]
  row=dict(year=y,round_id=q.round_id,sid=q.sid,name=q.name,root_day=q.root_day,signal_day=q.signal_day,prewindow_root=q.prewindow_root_recomputed,strict_window_birth=q.strict_window_birth,robust_direction=q.peer_delta1_robust,prior_window_any_buy_count=len(prior),root_birth_to_signal_buy_count=len(rootprior),prior_window_price_parent_count=len(priorparent),same_root_prior_price_parent_count=len(sameparent),current_stock_state_before=cur.iloc[0].stock_state_before,prior_registered_rounds=len(priorregs),prior_same_root_registered_rounds=len(sameregs),prior_same_root_statuses='|'.join(sameregs.status.astype(str)),birth_receipt_rows=len(birth),birth_receipt_confirmed=bool(len(birth)==1 and birth.iloc[0].born and birth.iloc[0].receipt and birth.iloc[0].new_frontier),birth_originating_buy_count=len(bbuy),birth_all_offer_results='|'.join(bo.result.astype(str)) if len(bo) else None,birth_price_offer_results='|'.join(bo.loc[bo.owner_lane.eq('PRICE'),'result'].astype(str)) if len(bo) else None,birth_AB_offer_results='|'.join(bo.loc[bo.owner_lane.eq('AB'),'result'].astype(str)) if len(bo) else None,real_parent_order_ACK_fill='UNKNOWN_NOT_PROVIDED')
  audit.append(row)
au=pd.DataFrame(audit)
assert au.prior_window_any_buy_count.eq(0).all() and au.prior_window_price_parent_count.eq(0).all()
assert au.loc[au.strict_window_birth,'birth_receipt_confirmed'].all()
assert au.loc[au.strict_window_birth,'birth_originating_buy_count'].eq(0).all()
write('TARGET_IDENTITY_AUDIT.csv',au)
strict=z[z.strict_window_birth].copy()
neg=strict[strict.peer_delta1_robust.eq('NEGATIVE')].copy()
assert len(neg)==54
write('STRICT_NEGATIVE_54.csv',neg.drop(columns='root_tuple'))
# Reuse frozen canonical M3 history to evaluate future saved fresh receipts, excluding target stock.
M=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
roster=csv(R/'momentum_persistence_breadth_v1/FIXED_ROSTER.csv').set_index('symbol')
k=pd.concat([pd.read_parquet(src(M/'WARM_PREFIX_M_K.parquet')),pd.read_parquet(src(M/'KNOWN3.parquet'))])
r=pd.concat([pd.read_parquet(src(M/'WARM_PREFIX_M_R.parquet')),pd.read_parquet(src(M/'RIGHT3.parquet'))])
assert k.index.equals(r.index) and k.columns.equals(r.columns)
sectors={s:list(g.index) for s,g in roster.groupby('sector_id')};cache={}
def robust(sid,day):
 key=(sid,day)
 if key in cache:return cache[key]
 peers=[s for s in sectors[roster.at[sid,'sector_id']] if s!=sid];t=pd.Timestamp(day);i=k.index.get_loc(t);prev=k.index[i-1]
 kt=k.loc[t,peers].to_numpy(bool);kp=k.loc[prev,peers].to_numpy(bool);rt=r.loc[t,peers].to_numpy(bool);rp=r.loc[prev,peers].to_numpy(bool)
 n=int((kt&rt).sum());np_=int((kp&rp).sum());u=int((~kt).sum());up=int((~kp).sum());L=n-np_-up;HH=n+u-np_
 sign='UNKNOWN' if not peers else 'POSITIVE' if L>0 else 'NEGATIVE' if HH<0 else 'FLAT' if L==HH==0 else 'UNKNOWN'
 v=dict(peer_N=len(peers),peer_delta1_L_count=L,peer_delta1_H_count=HH,peer_delta1_robust=sign,peer_previous_common_day=prev.strftime('%Y-%m-%d'));cache[key]=v;return v
for q in neg.itertuples():assert robust(q.sid,q.signal_day)['peer_delta1_robust']=='NEGATIVE'
ovcols=['sid','day','old_PVR_known','old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up','old_e0_target','old_i_target','old_i_buy','conditional_unstarted_target_feasible','conditional_unstarted_open_feasible','close_size_check','close_conditional_q','open_size_check','open_conditional_q','next_common_open_day','next_raw_open','next_daily_one_price_fact','volume_capacity_known_at','old_ab_I_PVR_qualified_permit','old_AB_event_id','old_AB_event_type']
ov=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'),columns=ovcols)
ov['day']=pd.to_datetime(ov.day).dt.strftime('%Y-%m-%d');oi=ov.set_index(['sid','day']);assert oi.index.is_unique
future=[];nextrows=[]
for q in neg.sort_values(['year','signal_day','sid']).itertuples():
 fut=mroot[(q.year,q.root_tuple)];fut=fut[fut.day.gt(q.signal_day)&fut.receipt&fut.new_frontier&~fut.born]
 selected=[]
 for a in fut.itertuples():
  rt=robust(q.sid,a.day);s=oi.loc[(q.sid,a.day)];four=all(s[c]==True for c in ['old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up'])
  fg=all(s[c]==True for c in ['old_e0_target','old_i_target','old_i_buy'])
  row=dict(year=q.year,round_id=q.round_id,sid=q.sid,name=q.name,root_day=q.root_day,original_signal_day=q.signal_day,future_signal_day=a.day,receipt_id=a.receipt_id,same_original_root=True,fresh_frontier=True,**rt,four_industry_known_true=four,original_stock_entry_flags_true=fg,old_PVR_known=s.old_PVR_known,old_AB_event_id=s.old_AB_event_id,old_AB_event_type=s.old_AB_event_type,same_stock_AB_market_permit=s.old_ab_I_PVR_qualified_permit,original_AB_valid_close=a.AB_valid_close,original_AB_result=a.AB_decision_before_joint,original_all_offer_results=a.all_offer_results,old_conditional_close_feasible=s.conditional_unstarted_target_feasible,old_close_size_check=s.close_size_check,old_close_q=s.close_conditional_q,old_conditional_open_feasible=s.conditional_unstarted_open_feasible,old_open_size_check=s.open_size_check,old_open_q=s.open_conditional_q,next_common_open_day=s.next_common_open_day,next_raw_open=s.next_raw_open,next_daily_one_price_fact=s.next_daily_one_price_fact,eligibility='SIGNAL_ONLY_NOT_A_NEW_SELECTED_TARGET_OR_FILL')
  row['nonnegative_gate']=rt['peer_delta1_robust']!='NEGATIVE'
  row['all_saved_market_and_size_flags']=row['nonnegative_gate'] and four and fg and s.old_PVR_known==True and s.conditional_unstarted_target_feasible==True and s.conditional_unstarted_open_feasible==True
  future.append(row);selected.append(row)
 nr=dict(year=q.year,round_id=q.round_id,sid=q.sid,name=q.name,root_day=q.root_day,original_signal_day=q.signal_day,same_root_future_fresh_receipt_count=len(selected))
 for lab,seq in [('first_fresh',selected),('first_not_robust_negative',[v for v in selected if v['nonnegative_gate']]),('first_market_size_visible',[v for v in selected if v['all_saved_market_and_size_flags']])]:
  a=seq[0] if seq else None
  nr[lab+'_day']=a['future_signal_day'] if a else None
  if a:
   for c in ['peer_delta1_robust','four_industry_known_true','original_stock_entry_flags_true','old_PVR_known','same_stock_AB_market_permit','original_AB_valid_close','old_conditional_close_feasible','old_conditional_open_feasible','next_common_open_day','next_daily_one_price_fact']:
    nr[lab+'_'+c]=a[c]
 nextrows.append(nr)
ff=pd.DataFrame(future);nn=pd.DataFrame(nextrows)
write('SAME_ROOT_FUTURE_FRESH_RECEIPTS.csv',ff);write('STRICT_NEGATIVE_NEXT_OPPORTUNITY.csv',nn)
# Fixed examples are predetermined saved facts, not PnL-selected.
fixed=csv(R/'price_entry_right_breadth_diagnosis_v1/FIXED_CASES.csv')
fixed['recomputed_prewindow_root']=[(str(rd)<start[int(str(ds)[:4])]) if int(str(ds)[:4]) in start and pd.notna(rd) else None for ds,rd in zip(fixed.signal_day,fixed.root_day)]
def fixed_scope(q):
 if q.born==True:return 'EXEMPT_BIRTH'
 if q.peer_delta1_robust in ['UNKNOWN','FLAT']:return 'NO_CONTRACTION_VETO'
 if getattr(q,'participation',None) in ['REPEAT_PRICE','FIRST_PRICE_AFTER_AB']:return 'EXEMPT_PRIOR_WINDOW_BUY'
 if q.recomputed_prewindow_root==True:return 'PREWINDOW_HISTORY_UNKNOWN_OUTSIDE_STRICT_SCOPE'
 if q.record_scope=='SIGNAL_ONLY_NO_2026_ECONOMICS':return 'SIGNAL_ONLY_WINDOW_PARTICIPATION_UNKNOWN'
 return 'REQUIRES_CURRENT_UNSTARTED_PARENT_AND_FIRST_WINDOW_BUY_CHECK'
fixed['narrow_scope_note']=[fixed_scope(q) for q in fixed.itertuples()]
write('FIXED_EARLY_CASES.csv',fixed)
summary=[]
for y,g in nn.groupby('year'):
 ids=set(g.round_id);aa=au[au.round_id.isin(ids)]
 summary.append(dict(year=y,strict_negative=len(g),birth_receipt_confirmed=int(aa.birth_receipt_confirmed.sum()),birth_zero_actual_proxy_buy=int(aa.birth_originating_buy_count.eq(0).sum()),no_prior_window_buy=int(aa.prior_window_any_buy_count.eq(0).sum()),no_prior_proxy_price_parent=int(aa.prior_window_price_parent_count.eq(0).sum()),prior_same_root_registered_rounds=int(aa.prior_same_root_registered_rounds.sum()),with_same_root_future_fresh=int(g.first_fresh_day.notna().sum()),with_same_root_not_robust_negative=int(g.first_not_robust_negative_day.notna().sum()),with_market_and_size_visible=int(g.first_market_size_visible_day.notna().sum()),first_nonnegative_directions=g.first_not_robust_negative_peer_delta1_robust.value_counts().to_dict(),first_nonnegative_four_true=int(g.first_not_robust_negative_four_industry_known_true.eq(True).sum()),first_nonnegative_close_feasible=int(g.first_not_robust_negative_old_conditional_close_feasible.eq(True).sum()),first_nonnegative_open_feasible=int(g.first_not_robust_negative_old_conditional_open_feasible.eq(True).sum()),first_nonnegative_AB_market_permit=int(g.first_not_robust_negative_same_stock_AB_market_permit.eq(True).sum())))
dump('NEXT_OPPORTUNITY_SUMMARY.json',summary)
qa=dict(rows=len(x),target_rows=len(z),strict_window_born_rows=len(strict),strict_negative_rows=len(neg),prewindow_field_warning='Original 2024 prewindow_root is missing, never treat missing as false. Recomputed against 2024-09-02 and cross-checked repaired base field.',no_prior_proxy_buy=True,no_prior_proxy_price_parent=True,birth_receipt_observed_for_all_window_born=True,birth_signal_no_originating_proxy_buy=True,source_files_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in H.items()),economic_runs=0,consumer_imports=0,raw_market_reloads=0,parameter_searches=0,filtered_returns=0,real_zero_partial_order_ACK_fill='UNKNOWN_NOT_PROVIDED',continuous_prewindow_history='UNKNOWN_NOT_PROVIDED')
assert qa['source_files_unchanged']
dump('QA.json',qa);dump('SOURCE_HASHES.json',H)
print('SUMMARY',json.dumps(clean(summary),ensure_ascii=False,indent=2));print('BIRTH OUTCOMES',au[au.round_id.isin(neg.round_id)].groupby(['year','birth_price_offer_results']).size().to_string());print('NEXT 54',nn.to_string(index=False));print('QA',json.dumps(qa,ensure_ascii=False))
