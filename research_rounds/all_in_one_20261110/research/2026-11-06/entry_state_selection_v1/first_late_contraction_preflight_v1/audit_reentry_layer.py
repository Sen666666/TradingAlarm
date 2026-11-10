"""Independent reentry lifecycle layer from saved facts only. Prior BUY is descriptive, not a gate."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'first_late_contraction_preflight_v1';H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def csv(p,**kw):return pd.read_csv(src(p),**kw)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(a) for k,a in v.items()}
 if isinstance(v,(list,tuple)):return [clean(a) for a in v]
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
x=csv(R/'price_entry_right_breadth_diagnosis_v1/ALL_PRICE_ENTRY_FACTS.csv',low_memory=False)
base=csv(R/'late_frontier_entry_preflight_v1/REGISTERED_ENTRY_BASE_FACTS.csv',low_memory=False).set_index('round_id')
m=csv(R/'late_frontier_entry_preflight_v1/MARKET_RECEIPT_BASE_FACTS.csv',low_memory=False)
mi=m.set_index(['year','sid','day'])
z=x[x.actual_buy&x.ticket.eq('CONTINUING_FRONTIER')&x.participation.isin(['REPEAT_PRICE','FIRST_PRICE_AFTER_AB'])].copy()
audit=[]
for y,g in z.groupby('year'):
 a=csv(R/f'independent_channel_joint_economic_v1/economic_{y}/joint/ACTIONS.csv')
 rr=csv(R/f'independent_channel_joint_economic_v1/economic_{y}/joint/ROUNDS.csv')
 for q in g.itertuples():
  b=mi.loc[(y,q.sid,q.root_day)];prior=a[a.round_id.eq(q.prior_all_round_id)&a.side.eq('sell_all')&a.q.gt(0)]
  prior_day=prior.day.str[:10].max() if len(prior) else None
  birthreg=rr[rr.sid.eq(q.sid)&rr.owner_lane.eq('PRICE')&rr.signal_day.eq(q.root_day)]
  same_root_regs=rr[rr.sid.eq(q.sid)&rr.price_root.eq(q.price_root)&rr.signal_day.lt(q.signal_day)]
  row=dict(year=y,round_id=q.round_id,sid=q.sid,name=q.name,root_day=q.root_day,signal_day=q.signal_day,participation=q.participation,entry_root_relation=q.entry_root_relation,prior_all_round_id=q.prior_all_round_id,prior_all_owner=q.prior_all_owner,prior_sell_all_count=len(prior),prior_sell_all_day=prior_day,previous_sell_all_strictly_before_new_birth=bool(prior_day and prior_day<q.root_day),birth_receipt_confirmed=bool(b.born and b.receipt and b.new_frontier),birth_proxy_parent_state=b.proxy_parent_before_signal,current_proxy_parent_state=base.at[q.round_id,'proxy_parent_before_signal'],birth_selected_lane=b.selected_lane,birth_selected_status=b.selected_status,birth_had_actual_buy=b.had_actual_buy,birth_all_offer_results=b.all_offer_results,birth_price_registered_round_count=len(birthreg),prior_same_root_registration_count=len(same_root_regs),prior_same_root_registration_statuses='|'.join(same_root_regs.status.astype(str)),real_zero_partial_parent='UNKNOWN_NOT_PROVIDED')
  audit.append(row)
au=pd.DataFrame(audit)
assert au.previous_sell_all_strictly_before_new_birth.all()
assert au.birth_receipt_confirmed.all()
assert au.birth_proxy_parent_state.eq('NO_PROXY_PROBE_PARENT').all()
assert au.current_proxy_parent_state.eq('NO_PROXY_PROBE_PARENT').all()
assert (~au.birth_had_actual_buy).all()
au.to_csv(O/'REENTRY_ROOT_IDENTITY_AUDIT.csv',index=False)
z=z.merge(au[['round_id','birth_price_registered_round_count','prior_same_root_registration_count']],on='round_id',validate='one_to_one')
def agg(h):
 o=dict(actual_n=len(h),independent_stocks=h.sid.nunique(),economic_unknown=int(h.economic_partition.eq('ECONOMIC_UNKNOWN').sum()),known_financial_uncovered=int(h.economic_partition.eq('KNOWN_BUT_FINANCIAL_UNCOVERED').sum()),covered_open=int(h.economic_partition.eq('COVERED_OPEN_CENSORED').sum()),covered_closed=int(h.economic_partition.eq('COVERED_CLOSED').sum()),birth_price_registration_n=int(h.birth_price_registered_round_count.gt(0).sum()),prior_same_root_registration_n=int(h.prior_same_root_registration_count.gt(0).sum()))
 for role,col in [('CORE','probe_closed_net'),('FULL','full_closed_net')]:
  v=h.loc[h[role+'_financial_closed'],col];o.update({role+'_n':len(v),role+'_wins':int(v.gt(0).sum()),role+'_win_rate':v.gt(0).mean(),role+'_mean':v.mean(),role+'_sum':v.sum() if len(v) else None})
 return o
stats=[]
for y,g0 in z.groupby('year'):
 for scope,g1 in [('ALL',g0),('ORIGINAL_COMMON',g0[g0.common])]:
  for part,g in [('ALL_PRIOR_BUY_NEW_ROOT',g1),('FIRST_PRICE_AFTER_AB',g1[g1.participation.eq('FIRST_PRICE_AFTER_AB')]),('REPEAT_PRICE',g1[g1.participation.eq('REPEAT_PRICE')])]:
   for direction in ['TOTAL','POSITIVE','NEGATIVE','FLAT','UNKNOWN']:
    h=g if direction=='TOTAL' else g[g.peer_delta1_robust.eq(direction)]
    stats.append(dict(year=y,scope=scope,participation_layer=part,robust_direction=direction,**agg(h)))
ss=pd.DataFrame(stats);ss.to_csv(O/'REENTRY_ROOT_GROUPS.csv',index=False)
# Correct obsolete preliminary exemption naming without touching any prior source or old research directory.
old=O/'EXEMPT_ACTUAL_REENTRY_COUNTS.csv'
if old.exists():old.rename(O/'PRIOR_BUY_NEW_ROOT_COUNTS.csv')
fixed=pd.read_csv(O/'FIXED_EARLY_CASES.csv')
fixed.loc[fixed.narrow_scope_note.eq('EXEMPT_PRIOR_WINDOW_BUY'),'narrow_scope_note']='PRIOR_BUY_NEW_ROOT_SEPARATE_LAYER_NOT_PERMANENT_EXEMPTION'
fixed.to_csv(O/'FIXED_EARLY_CASES.csv',index=False)
dump('REENTRY_SOURCE_HASHES.json',H)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in H.items())
dump('REENTRY_QA.json',dict(source_unchanged=True,late_new_root_after_verified_sell_all=len(z),birth_receipt_no_parent=True,current_receipt_no_parent=True,birth_price_registration_rows=int(au.birth_price_registered_round_count.gt(0).sum()),prior_same_root_registration_rows=int(au.prior_same_root_registration_count.gt(0).sum()),same_day_exit_birth_rows=int(au.prior_sell_all_day.eq(au.root_day).sum()),economic_runs=0,filtered_returns=0,permanent_has_prior_buy_gate=False))
print(ss[ss.participation_layer.eq('ALL_PRIOR_BUY_NEW_ROOT')].to_string(index=False,float_format=lambda x:f'{x:.4f}'))
print('BIRTH_REGISTERED',au[au.birth_price_registered_round_count.gt(0)].to_string(index=False))
