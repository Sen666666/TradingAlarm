"""Posterior valuations on original saved inventory. No strategy/economic replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from functools import lru_cache
import json,hashlib,sys,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;T=time.time();H={};QA={};ROWS=[];DAILY=[]
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
S=D('.0005')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):H[str(p)]=sha(p);return json.loads(Path(p).read_text())
def csv(p):H[str(p)]=sha(p);return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,(pd.Timestamp,)):return str(v.date())
 return v

def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2)+'\n')
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
for p in [B/'code/market_rules.py',B/'code/sector_account.py',B/'code/sector_stock_admission.py',O/'PROTOCOL.json']:H[str(p)]=sha(p)
@lru_cache(None)
def getmeta(sid,ds):
 ident=market_identity_on(rules,sid,ds,proxies);v=version_on(rules['fee_versions'][ident['venue']],ds,proxies)['schedule'];qr=QuantityRule(**version_on(rules['quantity_versions'][sid],ds,proxies)['rule'])
 return qr,FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(rules['security_metadata'][sid]['par_value']))
def fee(sid,q,px,d):
 _,fs,par=getmeta(sid,str(d.date()));return sum(fs.incremental('sell',D(q)*px,{}, {},1,shares=q,par_value=par).values(),D(0))
def mark(sid,q,rawp,d,cash):
 px=D(str(rawp))*(1-S);return float(cash+D(q)*px-fee(sid,q,px,d))
mp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in read(mp)}
cp=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet';H[str(cp)]=sha(cp);cal=pd.DatetimeIndex(sorted(pd.read_parquet(cp,columns=['day']).day.unique()));cal=cal[cal<=pd.Timestamp('2026-06-30')];ix={d:i for i,d in enumerate(cal)}
r=csv(O/'ROUND_CLOSE_ATTRIBUTION.csv');r['window_label']=r.window_label.astype(str)
for col in ['entry_day','exit_day','signal_day','add_day']:r[col]=pd.to_datetime(r[col])
A={};C={};G={};BR={};expected={};qcover={}
for w in ['2022','2024']:
 E=R/f'independent_channel_joint_economic_v1/economic_{w}';source=read(E/'joint/SOURCE_HASHES.json');expected.update(source)
 a=csv(E/'joint/ACTIONS.csv');a['day']=pd.to_datetime(a.day);A[w]={k:g.sort_values('day') for k,g in a.groupby('round_id')}
 claims=read(E/'joint/CLAIMS.json');C[w]=defaultdict(list)
 for x in claims:
  if x['recognized']:C[w][x['owner_round_id']].append((pd.Timestamp(x['ex_date']),D(x['amount']),pd.Timestamp(x['pay_date'])))
 gates=csv(E/'joint/PROFIT_GATES.csv');gates=gates[gates.caller.eq('price_held_close')];gates['day']=pd.to_datetime(gates.day);G[w]={k:g.set_index('day') for k,g in gates.groupby('round_id')}
 bridges=read(E/'joint/BRIDGES.json');BR[w]=defaultdict(dict)
 for x in bridges:BR[w][x['round_id']][pd.Timestamp(x['day'])]=x
 QA[w]=dict(calendar_missing_rounds=0,price_unknown_rounds=0,net_unknown_rounds=0,max_saved_close_net_error=0.,max_exit_quote_final_error=0.,source_coordinate_unknown=0,quantity_action_rounds=0,claims_rounds=0,factor_changed_rounds=0,verified_rounds=0,verified_daily_marks=0)
# Validate only source paths consumed here against original sealed engine hashes when available.
for p,h in H.items():
 if p in expected:assert expected[p]==h,(p,'original source drift')
for i,(sid,grp) in enumerate(r.groupby('sid',sort=True)):
 m=manifest[sid];sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));h=sha(sp);assert h==m['source_sha256'][str(sp)];H[str(sp)]=h
 if str(sp) in expected:assert h==expected[str(sp)]
 bars=pd.read_parquet(sp).reindex(cal)
 for z in grp.itertuples():
  w=z.window_label;rid=z.round_id;rr=dict(round_id=rid,window_label=w,sid=sid);e=ix[z.entry_day];x=ix[z.exit_day];dates=cal[e:x];part=bars.iloc[e:x+1];held=part.iloc[:-1];g=G[w][rid];aa=A[w][rid];buys=aa[aa.side.str.startswith('buy')];sells=aa[aa.side.str.startswith('sell')];claims=C[w][rid]
  assert list(g.index)==list(dates),(rid,'missing gates');assert len(dates)==z.close_days;assert len(sells)==1 and sells.iloc[0].side=='sell_all' and sells.iloc[0].day==z.exit_day
  assert buys.q.sum()==sells.q.sum() and len(buys)==1+int(z.added);assert abs(float(sum(c[1] for c in claims))-z.net80_income)<1e-7
  valid=part.price_eligible.fillna(False).all() and part.observed_bar.fillna(False).all() and not part.source_invalid.fillna(True).any() and not part.synthetic_event_bar.fillna(True).any()
  valid=valid and np.isfinite(part[['raw_open','raw_high','raw_low','raw_close','adjustment_factor']].to_numpy()).all()
  lineage=part[['source_kind','source_path','segment_id']].nunique(dropna=False).le(1).all();coordinate=True
  fac=part.adjustment_factor.to_numpy();change=np.flatnonzero(~np.isclose(fac[1:],fac[:-1],rtol=1e-11,atol=0))+1
  for j in change:
   b=BR[w][rid].get(part.index[j]);coordinate=coordinate and b is not None and abs(float(b['old_factor'])/fac[j-1]-1)<1e-11 and abs(float(b['new_factor'])/fac[j]-1)<1e-11
  rr.update(price_path_status='KNOWN' if valid and lineage and coordinate else 'UNKNOWN',factor_changed=bool(len(change)),admitted_cash_claims=len(claims),held_close_days=len(dates))
  QA[w]['claims_rounds']+=int(bool(claims));QA[w]['factor_changed_rounds']+=int(bool(len(change)))
  if not (valid and lineage and coordinate):
   QA[w]['price_unknown_rounds']+=1;QA[w]['net_unknown_rounds']+=1;rr['net_path_status']='UNKNOWN';ROWS.append(rr);continue
  assert np.allclose(part[['open','high','low','close']].to_numpy(),part[['raw_open','raw_high','raw_low','raw_close']].to_numpy()*fac[:,None],rtol=1e-11,atol=1e-10)
  basis=z.entry_price*fac[0];close=held.close.to_numpy()/basis-1;hi=held.high.to_numpy()/basis-1;lo=held.low.to_numpy()/basis-1;op=part.open.iloc[1:].to_numpy()/basis-1
  rr.update(price_fixed_basis=basis,price_close_mfe=close.max(),price_close_mae=close.min(),price_high_mfe_including_unsettled_entry=hi.max(),price_low_mae=lo.min(),price_t1_high_mfe=hi[1:].max() if len(hi)>1 else np.nan,price_nextopen_mfe=op.max(),price_nextopen_mae=op.min(),price_exit_open_return=op[-1],price_observed_mfe_including_entry_high=max(hi.max(),op[-1]),price_observed_mae=min(lo.min(),op[-1]),price_raw_fixed_mfe=held.raw_high.max()/z.entry_price-1 if not len(change) else np.nan,price_raw_fixed_mae=held.raw_low.min()/z.entry_price-1 if not len(change) else np.nan)
  steps=[];cash=D(0);q=0;prevq=0
  for k,d in enumerate(dates):
   ba=buys[buys.day.eq(d)];todayq=0
   for a in ba.itertuples():q+=int(a.q);todayq+=int(a.q);cash-=D(str(a.q))*D(str(a.price))+D(str(a.fee))
   income=sum((v for ed,v,pd_ in claims if ed<=d),D(0));econ_cash=cash+income
   p=bars.loc[d];nd=cal[ix[d]+1];pn=bars.loc[nd];ninc=sum((v for ed,v,pd_ in claims if ed<=nd),D(0));ncash=cash+ninc
   nc=mark(sid,q,p.raw_close,d,econ_cash);nh=mark(sid,q,p.raw_high,d,econ_cash);nl=mark(sid,q,p.raw_low,d,econ_cash);no=mark(sid,q,pn.raw_open,nd,ncash)
   diff=abs(nc-float(g.loc[d,'net_equity']));assert diff<1e-7,(rid,d,'saved close mismatch',nc,g.loc[d,'net_equity']);QA[w]['max_saved_close_net_error']=max(QA[w]['max_saved_close_net_error'],diff)
   qr,_,_=getmeta(sid,str(nd.date()));assert qr.sell_floor(q,q)==q
   conflict=bool((buys.day==nd).any());stage='PRE_ADD' if pd.isna(z.add_day) or d<z.add_day else 'POST_ADD';settled=q-todayq
   step=dict(round_id=rid,window_label=w,sid=sid,day=d,next_open_day=nd,original_qty=q,new_bought_qty=todayq,t1_settled_qty=settled,original_buy_cash_to_date=float(-cash),recognized_net80=float(income),saved_net_close=float(g.loc[d,'net_equity']),reconstructed_net_close=nc,net_high_upperbound=nh,net_low_lowerbound=nl,next_open_prior_inventory_quote=no,next_open_original_ADD_conflict=conflict,stage=stage,all_qty_t1_settled_today=todayq==0,price_close_return=close[k],price_high_return=hi[k],price_low_return=lo[k],price_nextopen_return=op[k])
   steps.append(step);DAILY.append(step)
  s=pd.DataFrame(steps);terminal=no;err=abs(terminal-z.net_pnl);assert err<1e-7,(rid,'exit quote mismatch',terminal,z.net_pnl);QA[w]['max_exit_quote_final_error']=max(QA[w]['max_exit_quote_final_error'],err)
  rr.update(net_path_status='KNOWN',net_high_max_upperbound=s.net_high_upperbound.max(),net_low_min_lowerbound=s.net_low_lowerbound.min(),next_open_max_all_static=s.next_open_prior_inventory_quote.max(),next_open_min_all_static=s.next_open_prior_inventory_quote.min(),next_open_max_no_ADD_conflict=s.loc[~s.next_open_original_ADD_conflict,'next_open_prior_inventory_quote'].max(),next_open_min_no_ADD_conflict=s.loc[~s.next_open_original_ADD_conflict,'next_open_prior_inventory_quote'].min(),next_open_ADD_conflict_days=int(s.next_open_original_ADD_conflict.sum()),next_open_max_day=s.loc[s.next_open_prior_inventory_quote.idxmax(),'next_open_day'],close_reconstruction_max_error=float(max(abs(s.reconstructed_net_close-s.saved_net_close))),net_high_peak_day=s.loc[s.net_high_upperbound.idxmax(),'day'],net_high_peak_all_qty_t1_settled=bool(s.loc[s.net_high_upperbound.idxmax(),'all_qty_t1_settled_today']))
  for stage in ['PRE_ADD','POST_ADD']:
   sub=s[s.stage==stage];pre=stage.lower();rr[pre+'_next_open_max_no_conflict']=sub.loc[~sub.next_open_original_ADD_conflict,'next_open_prior_inventory_quote'].max();rr[pre+'_net_high_max_upperbound']=sub.net_high_upperbound.max();rr[pre+'_close_max_R']=sub.reconstructed_net_close.max()/z.entry_risk
  if z.added:
   a=buys[buys.side.eq('buy_add')].iloc[0];rr['pre_ADD_open_original_prior_net']=float(a.prior_round_net);rr['pre_ADD_open_original_prior_net_R']=float(a.prior_round_net)/z.entry_risk
  ROWS.append(rr);QA[w]['verified_rounds']+=1;QA[w]['verified_daily_marks']+=len(s)
 if (i+1)%100==0:print('STOCKS',i+1,'ROUNDS',len(ROWS),'SECONDS',round(time.time()-T,1),flush=True)
p=pd.DataFrame(ROWS);out=r.merge(p,on=['round_id','window_label','sid'],validate='one_to_one')
def bucket_price(v):
 if not np.isfinite(v):return 'UNKNOWN'
 return 'LE_0' if v<=0 else 'GT0_LT5PCT' if v<.05 else 'GE5_LT10PCT' if v<.10 else 'GE10PCT'
def bucket_net(v):
 if not np.isfinite(v):return 'UNKNOWN'
 return 'LE_0' if v<=0 else 'GT0_LT1R' if v<1 else 'GE1R'
for col in ['price_close_mfe','price_observed_mfe_including_entry_high','price_t1_high_mfe','price_nextopen_mfe']:out[col+'_bucket']=out[col].map(bucket_price)
out['price_observed_mae_bucket']=pd.cut(out.price_observed_mae,[-np.inf,-.1,-.05,0,np.inf],labels=['LE_MINUS10PCT','MINUS10_TO_MINUS5PCT','MINUS5_TO_0','GT0'],right=True).astype(str)
for col in ['next_open_max_no_ADD_conflict','net_high_max_upperbound']:
 out[col+'_R']=out[col]/out.entry_risk;out[col+'_R_bucket']=out[col+'_R'].map(bucket_net)
out['pre_add_close_R_bucket']=out.pre_add_close_max_R.map(bucket_net);out['post_add_close_R_bucket']=out.post_add_close_max_R.map(bucket_net);out.loc[~out.added,'post_add_close_R_bucket']='NOT_APPLICABLE_NO_ADD'
out['one_step_net_outcome']=np.where(out.net_path_status.ne('KNOWN'),'UNKNOWN',np.where(out.next_open_max_no_ADD_conflict.le(0),'NO_POSITIVE_NEXT_OPEN_QUOTE',np.where(out.net_pnl.lt(0),'POSITIVE_NEXT_OPEN_FINAL_LOSS','POSITIVE_NEXT_OPEN_FINAL_PROFIT')))
out['no_measured_high_profit']=out.net_high_max_upperbound.le(0)&out.next_open_max_all_static.le(0)
out.to_csv(O/'PRICE_ROUND_PATH_ATTRIBUTION.csv',index=False);pd.DataFrame(DAILY).to_csv(O/'ORIGINAL_INVENTORY_DAILY_PATH.csv',index=False)
def summ(x):
 p=x.net_pnl;return dict(n=len(x),stocks=x.sid.nunique(),wins=int((p>0).sum()),losses=int((p<0).sum()),net=p.sum(),profit_amount=p[p>0].sum(),loss_amount=-p[p<0].sum(),probe_trade=x.probe_trade.sum(),add_trade=x.add_trade.sum(),net80_income=x.net80_income.sum(),holding_inclusive_median=x.holding_sessions.median(),price_close_MFE_median=x.price_close_mfe.median(),price_MAE_median=x.price_observed_mae.median(),close_max_R_median=x.close_max_R.median())
tables={};groups=[['price_path_status'],['net_path_status'],['price_close_mfe_bucket'],['price_observed_mfe_including_entry_high_bucket'],['price_t1_high_mfe_bucket'],['price_nextopen_mfe_bucket'],['price_observed_mae_bucket'],['price_close_mfe_bucket','final_outcome'],['next_open_max_no_ADD_conflict_R_bucket','final_outcome'],['net_high_max_upperbound_R_bucket','final_outcome'],['one_step_net_outcome'],['no_measured_high_profit'],['added','pre_add_close_R_bucket'],['added','post_add_close_R_bucket'],['pre_add_close_R_bucket','close_R_bucket','final_outcome']]
for w,g in out.groupby('window_label'):
 for fields in groups:
  rows=[]
  for key,x in g.groupby(fields,dropna=False,observed=True):
   key=key if isinstance(key,tuple) else (key,);rows.append(dict(zip(fields,key),**summ(x)))
  assert abs(sum(x['net'] for x in rows)-g.net_pnl.sum())<1e-7
  tables[w+'__'+'__'.join(fields)]=rows
 QA[w]['all_metrics_partition_net']=g.net_pnl.sum();QA[w]['no_measured_high_profit_n']=int(g.no_measured_high_profit.sum());QA[w]['no_measured_high_profit_net']=g.loc[g.no_measured_high_profit,'net_pnl'].sum();QA[w]['nextopen_conflict_days']=int(g.next_open_ADD_conflict_days.sum())
 QA[w]['nextopen_conflict_changes_positive_n']=int((g.next_open_max_all_static.gt(0)&g.next_open_max_no_ADD_conflict.le(0)).sum())
 QA[w]['net_path_unknown_net']=g.loc[g.net_path_status.ne('KNOWN'),'net_pnl'].sum();QA[w]['price_path_unknown_net']=g.loc[g.price_path_status.ne('KNOWN'),'net_pnl'].sum()
print('QA',json.dumps(clean(QA),ensure_ascii=False),flush=True)
save('PATH_TABLES.json',tables);save('PATH_QA.json',QA);save('SOURCE_HASHES_STAGE2.json',H)
assert all(sha(p)==h for p,h in H.items())
print('ALL_USED_SOURCE_HASHES_UNCHANGED',len(H),'SECONDS',time.time()-T,flush=True)
