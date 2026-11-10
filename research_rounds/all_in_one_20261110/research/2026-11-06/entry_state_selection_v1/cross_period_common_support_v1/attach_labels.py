"""Attach saved old A+B labels only after the feature/match seal. No economic replay."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(v):
 if isinstance(v,dict):return {str(k):norm(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [norm(x) for x in v]
 if isinstance(v,np.generic):return norm(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def save(n,v):
 with (O/n).open('x') as f:json.dump(norm(v),f,ensure_ascii=False,indent=2,allow_nan=False)
seal=json.loads((O/'FEATURE_MATCH_SEAL.json').read_text())
for p,h in seal.items():assert sha(O/p)==h,(p,'match seal changed')
assert not (O/'LABEL_ATTACHMENT.json').exists()
if (O/'MATCHING_STOP.json').exists():raise RuntimeError('Scale support failed; do not attach outcomes')
members=pd.read_csv(O/'SELECTED_MEMBERS_PRELABEL.csv')
if members.empty:raise RuntimeError('No selected triplets. Do not consume outcome columns for empty common support.')
p=json.loads((O/'PROTOCOL_V1.json').read_text())
allf=pd.read_csv(O/'FEATURES_SCALED_PRELABEL.csv')
labcols=['round_id','arm','status','entry_status','execution_status','financial_coverage_status','coverage_reasons','evidence_usable_closed','entry_day','exit_day','core_net','core_return','net_pnl','net_return_on_buy_cash','all_fees','core_buy_fee','core_sell_fee','core_dividend_net80','dividend_net80_total','entry_q']
labs=[];sources={}
for path in p['outcomes']['sources']:
 path=R/path;sources[str(path)]=sha(path);v=pd.read_csv(path,usecols=labcols);labs.append(v[v.arm.eq('A_UNION_B')].drop(columns='arm'))
lab=pd.concat(labs);assert lab.round_id.is_unique
a=allf.merge(lab,on='round_id',how='left',validate='one_to_one');assert a.status.notna().all()
a['financial_known']=a.evidence_usable_closed.eq(True)&a.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&np.isfinite(a[['core_net','core_return','net_pnl','net_return_on_buy_cash']]).all(axis=1)
sel=members[['triplet_id','round_id']].merge(a,on='round_id',how='left',validate='one_to_one')
assert sel.groupby('triplet_id').size().eq(3).all()
good=sel.groupby('triplet_id').financial_known.all()
common=sel[sel.triplet_id.isin(good[good].index)].copy()
a.to_csv(O/'ALL_ORIGINAL_WITH_OLD_LABELS.csv',index=False);sel.to_csv(O/'SELECTED_WITH_OLD_LABELS.csv',index=False);common.to_csv(O/'COMMON_CLOSED_TRIPLETS.csv',index=False)
sets={'ORIGINAL_PERMITS':a,'FEATURE_COMPLETE':a[a.feature_known],'SELECTED_MEMBERS':sel,'COMMON_CLOSED_TRIPLETS':common}
status=[];summary=[]
def stats(g,net,ret):
 z=g[g.financial_known];v=z[net];r=z[ret];win=v>0;loss=v<0;rw=r>0;rl=r<0
 mw=float(v[win].mean()) if win.any() else np.nan;ml=float(v[loss].mean()) if loss.any() else np.nan
 mrw=float(r[rw].mean()) if rw.any() else np.nan;mrl=float(r[rl].mean()) if rl.any() else np.nan
 tail=r>=.30
 return dict(all_n=len(g),financial_known=len(z),financial_unknown=len(g)-len(z),wins=int(win.sum()),losses=int(loss.sum()),zeros=int(v.eq(0).sum()),win_rate=float(win.mean()) if len(z) else np.nan,mean_net=float(v.mean()) if len(z) else np.nan,net_sum=float(v.sum()) if len(z) else np.nan,mean_win=mw,mean_loss=ml,cash_payoff=mw/abs(ml) if np.isfinite(ml) and ml<0 else np.nan,mean_return=float(r.mean()) if len(z) else np.nan,mean_win_return=mrw,mean_loss_return=mrl,return_payoff=mrw/abs(mrl) if np.isfinite(mrl) and mrl<0 else np.nan,final_ge30_n=int(tail.sum()),final_ge30_net_sum=float(v[tail].sum()),signal_dates=z.signal_day.nunique(),industries=z.sector.nunique(),stocks=z.sid.nunique(),I_roots=z.root_id.nunique(),event_clusters=z.event_cluster.nunique())
for name,g in sets.items():
 for per,z in g.groupby('period'):
  for layer,net,ret in [('CORE','core_net','core_return'),('FULL','net_pnl','net_return_on_buy_cash')]:summary.append(dict(scope=name,period=per,layer=layer,**stats(z,net,ret)))
  for keys,c in z.groupby(['status','entry_status','financial_coverage_status','financial_known'],dropna=False):
   status.append(dict(scope=name,period=per,status=keys[0],entry_status=keys[1],financial_coverage_status=keys[2],financial_known=keys[3],n=len(c)))
pd.DataFrame(summary).to_csv(O/'ECONOMIC_DESCRIPTIVES.csv',index=False);pd.DataFrame(status).to_csv(O/'FINANCIAL_DENOMINATORS.csv',index=False)
clock=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
sources[str(clock)]=sha(clock)
cal=pd.DatetimeIndex(np.load(clock,allow_pickle=False)['dates'])
block20={str(d.date()):i//20 for i,d in enumerate(cal)}
comparisons=[('Q3','Q1'),('AUTUMN','Q1'),('AUTUMN','Q3')]
pairs=[];contrasts=[];cluster=[];loo=[]
for left,right in comparisons:
 ll=common[common.period.eq(left)].set_index('triplet_id');rr=common[common.period.eq(right)].set_index('triplet_id')
 assert ll.index.equals(rr.index)
 for layer,net,ret in [('CORE','core_net','core_return'),('FULL','net_pnl','net_return_on_buy_cash')]:
  z=pd.DataFrame(dict(triplet_id=ll.index,sector=ll.sector.to_numpy(),left_day=ll.signal_day.to_numpy(),right_day=rr.signal_day.to_numpy(),left_sid=ll.sid.to_numpy(),right_sid=rr.sid.to_numpy(),left_net=ll[net].to_numpy(),right_net=rr[net].to_numpy(),left_return=ll[ret].to_numpy(),right_return=rr[ret].to_numpy()))
  z['left_block20']=z.left_day.map(block20);z['right_block20']=z.right_day.map(block20)
  z['delta_net']=z.left_net-z.right_net;z['delta_return']=z.left_return-z.right_return
  z['delta_win']=(z.left_net>0).astype(int)-(z.right_net>0).astype(int);z['delta_tail']=(z.left_return>=.3).astype(int)-(z.right_return>=.3).astype(int)
  z['comparison']=left+'-'+right;z['layer']=layer;pairs+=z.to_dict('records')
  for var in ['delta_net','delta_return','delta_win','delta_tail']:
   for cl in ['sector','left_day','right_day','left_block20','right_block20']:
    q=z.groupby(cl)[var].mean()
    for key,value in q.items():cluster.append(dict(comparison=left+'-'+right,layer=layer,metric=var,cluster_type=cl,cluster=key,n=int(z[cl].eq(key).sum()),mean_delta=float(value)))
    if len(q)>1:
     for key in q.index:
      zz=z[z[cl].ne(key)];loo.append(dict(comparison=left+'-'+right,layer=layer,metric=var,excluded_cluster_type=cl,excluded_cluster=key,n=len(zz),mean_delta=float(zz[var].mean())))
  sec=z.groupby('sector').delta_net.mean()
  contrasts.append(dict(comparison=left+'-'+right,layer=layer,n=len(z),mean_net_delta=float(z.delta_net.mean()),mean_return_delta=float(z.delta_return.mean()),win_rate_delta=float(z.delta_win.mean()),tail_count_delta=int(z.delta_tail.sum()),higher_net=int(z.delta_net.gt(0).sum()),lower_net=int(z.delta_net.lt(0).sum()),both_win=int((z.left_net.gt(0)&z.right_net.gt(0)).sum()),both_nonwin=int((z.left_net.le(0)&z.right_net.le(0)).sum()),left_only_win=int((z.left_net.gt(0)&z.right_net.le(0)).sum()),right_only_win=int((z.left_net.le(0)&z.right_net.gt(0)).sum()),industries=len(sec),industry_equal_mean_net_delta=float(sec.mean()),positive_industries=int(sec.gt(0).sum()),negative_industries=int(sec.lt(0).sum()),left_dates=z.left_day.nunique(),right_dates=z.right_day.nunique(),same_sid=int(z.left_sid.eq(z.right_sid).sum()),p_value=None,significance='NOT_IDENTIFIED_BY_THIS_DESCRIPTIVE_DESIGN'))
pd.DataFrame(pairs).to_csv(O/'PAIRED_OUTCOME_DIFFERENCES.csv',index=False);pd.DataFrame(contrasts).to_csv(O/'PAIRED_CONTRASTS.csv',index=False);pd.DataFrame(cluster).to_csv(O/'CLUSTER_DIRECTION.csv',index=False);pd.DataFrame(loo).to_csv(O/'LEAVE_ONE_CLUSTER.csv',index=False)
quality=[]
for l,r in comparisons:
 ll=members[members.period.eq(l)].set_index('triplet_id');rr=members[members.period.eq(r)].set_index('triplet_id')
 for c in p['features']:
  delta=ll[c+'_z']-rr[c+'_z'];quality.append(dict(comparison=l+'-'+r,feature=c,n=len(delta),mean_standardized_difference=float(delta.mean()),mean_abs_difference=float(delta.abs().mean()),max_abs_difference=float(delta.abs().max())))
pd.DataFrame(quality).to_csv(O/'MATCH_QUALITY.csv',index=False)
for name,df in [('selected',sel),('common',common)]:
 df.groupby(['period','sid'],dropna=False).size().rename('n').reset_index().to_csv(O/(name.upper()+'_STOCK_REUSE.csv'),index=False)
 df.groupby(['period','root_id'],dropna=False).size().rename('n').reset_index().to_csv(O/(name.upper()+'_ROOT_REUSE.csv'),index=False)
for name,h in seal.items():assert sha(O/name)==h,(name,'changed after labels')
for path,h in sources.items():assert sha(path)==h
save('LABEL_ATTACHMENT.json',dict(status='DESCRIPTIVE_OLD_PATHS_ONLY',selected_triplets=int(sel.triplet_id.nunique()),common_financial_triplets=int(common.triplet_id.nunique()),unknown_triplets=int(sel.triplet_id.nunique()-common.triplet_id.nunique()),all_matches_unchanged=True,financial_source_hashes=sources,financial_contracts_not_identical_by_feature_matching=True,new_strategy=False,no_p_value=True))
print(json.dumps(norm({'selected_triplets':sel.triplet_id.nunique(),'common_financial_triplets':common.triplet_id.nunique(),'contrasts':contrasts}),ensure_ascii=False),flush=True)
