"""Frozen natural-strata audit of original A/B entries. No new economics."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,sys,math,time,itertools
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
C=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code')
sys.path.insert(0,str(C))
from numeric import log_ratio,compare
from data_utils import eligible_prices
S={};t0=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);S[str(p)]=sha(p)
 if expected:assert S[str(p)]==expected,str(p)
 return p
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
def ageband(a):
 if a<0 or pd.isna(a):return 'UNKNOWN_ROOT'
 if a==0:return 'BIRTH_DAY_0'
 if a<=2:return 'AGE_1_2'
 if a<=20:return 'AGE_3_20'
 return 'AGE_GE21'
def ages(s):
 result=np.full(len(s),-1,dtype=int);start=-1
 for i,v in enumerate(s):
  if v!=1:start=-1;continue
  if i>0 and s[i-1]==0:start=i
  elif not(i>0 and s[i-1]==1 and start>=0):start=-1
  if start>=0:result[i]=i-start
 return result
def sign(v):return 'UNKNOWN' if not np.isfinite(v) else 'POSITIVE' if v>0 else 'NEGATIVE' if v<0 else 'ZERO'
def periods(z):
 yield '2022_ALL',z[z.window.eq('2022')]
 yield '2022_Q1',z[z.window.eq('2022')&z.signal_day.dt.quarter.eq(1)]
 yield '2022_REST',z[z.window.eq('2022')&z.signal_day.dt.quarter.ge(2)]
 for q in [2,3,4]:yield '2022_Q'+str(q),z[z.window.eq('2022')&z.signal_day.dt.quarter.eq(q)]
 yield '2024_924',z[z.window.eq('2024_924')]
with (O/'RUN_ONCE.lock').open('x') as h:h.write(pd.Timestamp.now(tz='UTC').isoformat())
for p in [O/'PROTOCOL.json',Path(__file__),C/'numeric.py',C/'data_utils.py']:src(p)
labpaths=[R/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv',R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv']
ident=['round_id','event_id','window','arm','event_type','sid','name','sector','industry','signal_day']
m=pd.concat([pd.read_csv(src(p),usecols=ident,parse_dates=['signal_day'],dtype={'window':str}) for p in labpaths],ignore_index=True)
m=m[m.arm.eq('A_UNION_B')].copy();assert len(m)==4086 and m.event_id.is_unique
root=pd.read_csv(src(R/'first_evidence_race_preflight_v1/ALL_PERMIT_RACE_FEATURES_PRELABEL.csv'),usecols=['round_id','root_known','root_day'],parse_dates=['root_day'])
m=m.merge(root,on='round_id',validate='one_to_one',how='left');assert m.root_known.notna().all()
D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
p=pd.read_parquet(src(D/'COMMON_K_COMPARISON.parquet')).sort_values(['sector','day'])
secs={}
for sec,g in p.groupby('sector'):
 s=g.M3_candidate.to_numpy();ag=ages(s);secs[sec]=pd.Series(ag,index=pd.DatetimeIndex(g.day))
rr=pd.concat([pd.read_parquet(src(D/'WARM_PREFIX_M_R.parquet')),pd.read_parquet(src(D/'RIGHT3.parquet'))]).sort_index()
kk=pd.concat([pd.read_parquet(src(D/'WARM_PREFIX_M_K.parquet')),pd.read_parquet(src(D/'KNOWN3.parquet'))]).sort_index()
assert rr.index.equals(kk.index) and not rr.index.duplicated().any()
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(src(H),allow_pickle=False) as hh:cal=pd.DatetimeIndex(hh['dates'])
cal=cal[cal<='2026-06-30'];di={d:i for i,d in enumerate(cal)}
mm={z['symbol']:z for z in json.loads(src(U/'STOCK_MANIFEST.json').read_text())}
stockage_cache={}
for sid in sorted(m.sid.unique()):
 states=rr[sid].astype(int).where(kk[sid],-1).to_numpy()
 stockage_cache[sid]=pd.Series(ages(states),index=rr.index)
# Every quarter's alphabetically first sid, earliest original selected signal; deterministic prelabel.
samples=set()
for _,g in m.groupby([m.window,m.signal_day.dt.quarter]):
 z=g.sort_values(['sid','signal_day']).iloc[0];samples.add((z.sid,z.signal_day))
old=pd.read_csv(src(R/'m3_native_leg_entry_preflight_v1/SIGNAL_TIME_FEATURES.csv'),usecols=['sid','signal_day'],parse_dates=['signal_day'])
actualkeys=set(zip(m.sid,m.signal_day))
samples|={(z.sid,z.signal_day) for z in old.itertuples() if (z.sid,z.signal_day) in actualkeys}
for _,g in m.groupby([m.window,m.signal_day.dt.quarter]):
 sortedg=g.sort_values(['sid','signal_day'])
 for condition in ['root_unknown','stock_M3_left_unknown','sector_M3_left_unknown']:
  for q in sortedg.itertuples():
   flag=(not bool(q.root_known)) if condition=='root_unknown' else (stockage_cache[q.sid].get(q.signal_day,-1)<0) if condition=='stock_M3_left_unknown' else (secs[q.sector].get(q.signal_day,-1)<0)
   if flag:samples.add((q.sid,q.signal_day));break
save('PREFIX_SAMPLE_FROZEN.json',[dict(sid=s,signal_day=d) for s,d in sorted(samples)])
axes=['entry_type','sector_M3_age','stock_M3_age','I_root_age','CP_root_context','i_buy_today','ret21_sign','I_birth_return_sign','prior21_high_position','I_floor_distance_unit','vol5_vs_prior63','amount_vs_prior21','price_amount_quadrant']
agecats=['BIRTH_DAY_0','AGE_1_2','AGE_3_20','AGE_GE21','UNKNOWN_ROOT']
cats={'entry_type':['A','B'],'sector_M3_age':agecats,'stock_M3_age':agecats,'I_root_age':agecats,
'CP_root_context':['FRESH_TODAY','PRIOR_RECEIPT_IN_ROOT','NONE_IN_ROOT','UNKNOWN_ROOT_OR_CP'],
'i_buy_today':['TRUE','FALSE','UNKNOWN'],'ret21_sign':['NEGATIVE','ZERO','POSITIVE','UNKNOWN'],
'I_birth_return_sign':['NEGATIVE','ZERO','POSITIVE','UNKNOWN'],'prior21_high_position':['AT_OR_ABOVE','BELOW','UNKNOWN'],
'I_floor_distance_unit':['LE1','GT1','UNKNOWN'],'vol5_vs_prior63':['LE1','GT1','UNKNOWN'],
'amount_vs_prior21':['LE1','GT1','UNKNOWN'],'price_amount_quadrant':[a+'_'+b for a in ['UP','DOWN','FLAT'] for b in ['GT1','LE1']]+['UNKNOWN']}
save('AXES_FROZEN.json',dict(axes=axes,categories=cats,interactions=[['entry_type','I_root_age'],['CP_root_context','vol5_vs_prior63']],empty_categories_retained=True))
def prep(b,f,cp,inp):
 idx=eligible_prices(b).index;b=b.reindex(cal);f=f.reindex(cal);cp=cp.reindex(cal);inp=inp.reindex(cal)
 valid=pd.Series(cal.isin(idx),index=cal)&np.isfinite(b.close)&b.close.gt(0)&f.segment_id.eq(b.segment_id)&b.source_kind.notna()&b.source_path.notna()
 # Source lineage is an observation fact; factor changes do not define a hidden gate.
 lineage=b[['source_kind','source_path','segment_id']]
 return b,f,cp,inp,valid,lineage
def point(r,data,stockage):
 b,f,cp,inp,valid,lin=data;d=r.signal_day;t=di[d]
 out={k:getattr(r,k) for k in ident if k!='arm'}
 out['entry_type']='A' if r.event_type=='A_SECTOR_BIRTH' else 'B'
 a=int(secs[r.sector].get(d,-1));out['sector_M3_age_n']=a;out['sector_M3_age']=ageband(a)
 a=int(stockage.get(d,-1));out['stock_M3_age_n']=a;out['stock_M3_age']=ageband(a)
 def ok(a,bx,amount=False):
  if a<0:return False
  v=valid.iloc[a:bx+1]
  if len(v)!=bx-a+1 or not bool(v.all()):return False
  ll=lin.iloc[a:bx+1]
  if not(ll.nunique(dropna=False)==1).all():return False
  if amount:
   aa=inp.amount.iloc[a:bx+1]
   if not(np.isfinite(aa).all() and aa.gt(0).all()):return False
  return True
 rootday=r.root_day;rootidx=di.get(rootday,-1);rootok=False
 if bool(r.root_known) and rootidx>0 and rootidx<=t and ok(rootidx-1,t):
  rootok=(f.i_target.iloc[rootidx-1]==0 and f.i_target.iloc[rootidx:t+1].eq(1).all())
 out['root_known_original']=bool(r.root_known);out['root_independently_verified']=bool(rootok);out['root_day']=rootday if rootok else None
 out['I_root_age_n']=t-rootidx if rootok else -1;out['I_root_age']=ageband(out['I_root_age_n'])
 out['e0_target']=f.at[d,'e0_target'];out['i_target']=f.at[d,'i_target'];out['g_grade']=f.at[d,'g_grade']
 ib=f.at[d,'i_buy'];out['i_buy_today']='UNKNOWN' if pd.isna(ib) else 'TRUE' if ib else 'FALSE'
 currentcp=pd.notna(cp.at[d,'ready']) and bool(cp.at[d,'ready']) and pd.notna(cp.at[d,'receipt'])
 if currentcp and bool(cp.at[d,'receipt']):context='FRESH_TODAY'
 elif rootok and cp.ready.iloc[rootidx:t+1].notna().all() and cp.ready.iloc[rootidx:t+1].eq(True).all() and cp.receipt.iloc[rootidx:t+1].notna().all():
  context='PRIOR_RECEIPT_IN_ROOT' if cp.receipt.iloc[rootidx:t].eq(True).any() else 'NONE_IN_ROOT'
 else:context='UNKNOWN_ROOT_OR_CP'
 out['CP_root_context']=context
 for k in ['ret21','I_birth_return','distance_I_log','sigma_prior63','risk_units','rms5','vol_ratio','amount_ratio','current_log_return']:out[k]=np.nan
 if ok(t-21,t):
  prices=b.close.iloc[t-21:t+1].to_numpy(float)
  out['ret21']=log_ratio(prices[-1],prices[0]);out['prior21_high_position']='AT_OR_ABOVE' if compare(prices[-1],float(max(prices[:-1])))>=0 else 'BELOW'
 else:out['prior21_high_position']='UNKNOWN'
 if rootok:out['I_birth_return']=log_ratio(float(b.close.iloc[t]),float(b.close.iloc[rootidx]))
 if ok(t-64,t):
  prices=b.close.iloc[t-64:t+1].to_numpy(float);returns=[log_ratio(float(prices[i]),float(prices[i-1])) for i in range(1,len(prices))]
  sig=max(math.sqrt(math.fsum(x*x for x in returns[:-1])/63),1e-8);rms5=math.sqrt(math.fsum(x*x for x in returns[-5:])/5)
  out.update(sigma_prior63=sig,rms5=rms5,vol_ratio=rms5/sig)
  floor=f.i_floor.iloc[t]
  if pd.notna(floor) and np.isfinite(floor) and floor>0 and compare(float(b.close.iloc[t]),float(floor))>0:
   out['distance_I_log']=log_ratio(float(b.close.iloc[t]),float(floor));out['risk_units']=out['distance_I_log']/(math.sqrt(5)*sig)
 if ok(t-21,t,amount=True):
  aa=inp.amount.iloc[t-21:t+1].to_numpy(float);out['amount_ratio']=aa[-1]/float(np.median(aa[:-1]))
 if ok(t-1,t):out['current_log_return']=log_ratio(float(b.close.iloc[t]),float(b.close.iloc[t-1]))
 out['ret21_sign']=sign(out['ret21']);out['I_birth_return_sign']=sign(out['I_birth_return'])
 for key,vv in [('I_floor_distance_unit','risk_units'),('vol5_vs_prior63','vol_ratio'),('amount_vs_prior21','amount_ratio')]:
  value=out[vv];out[key]='UNKNOWN' if not np.isfinite(value) else 'GT1' if compare(value,1.)>0 else 'LE1'
 rs=sign(out['current_log_return']);am=out['amount_vs_prior21']
 out['price_amount_quadrant']='UNKNOWN' if rs=='UNKNOWN' or am=='UNKNOWN' else dict(POSITIVE='UP',NEGATIVE='DOWN',ZERO='FLAT')[rs]+'_'+am
 return out
rows=[];checks=[];rootissues=[];identity=[];windowchecks=[]
for n,(sid,g) in enumerate(m.groupby('sid',sort=True),1):
 meta=mm[sid];path=next(q for q in meta['source_sha256'] if q.endswith('/signal.parquet'))
 b=pd.read_parquet(src(path,meta['source_sha256'][path])).loc[:g.signal_day.max()]
 f=pd.read_parquet(src(meta['refs']['facts'],meta['output_sha256'][meta['refs']['facts']])).loc[:g.signal_day.max()]
 cp=pd.read_parquet(src(meta['refs']['CP1'],meta['output_sha256'][meta['refs']['CP1']])).loc[:g.signal_day.max()]
 inp=pd.read_parquet(src(meta['refs']['CP1_input'],meta['output_sha256'][meta['refs']['CP1_input']])).loc[:g.signal_day.max()]
 states=rr[sid].astype(int).where(kk[sid],-1).to_numpy();stockage=stockage_cache[sid]
 data=prep(b,f,cp,inp)
 if n==1:
  # First lexicographic stock; first consecutive source-comparable65commonprices,
  # and its immediate predecessor: technical no-order window64/65 boundary.
  valid,lin=data[4],data[5];endidx=None
  for j in range(64,len(cal)):
   if valid.iloc[j-64:j+1].all() and (lin.iloc[j-64:j+1].nunique(dropna=False)==1).all():endidx=j;break
  assert endidx is not None
  save('WINDOW_BOUNDARY_ENDPOINTS_FROZEN.json',dict(sid=sid,dates=[cal[endidx-1],cal[endidx]],selection='firstlexicographicsid,firstsourcevalid65commonpricewindowandpredecessor;nooutcomes'))
  base=next(g.itertuples())
  for j in [endidx-1,endidx]:
   d=cal[j];technical=base._replace(signal_day=d,root_known=False,root_day=pd.NaT,event_id='TECH_WINDOW_'+str(j))
   out=point(technical,data,stockage);short=point(technical,prep(b.loc[:d],f.loc[:d],cp.loc[:d],inp.loc[:d]),stockage)
   eq=all((pd.isna(v) and pd.isna(short[k])) or v==short[k] for k,v in out.items())
   expected_unknown=j==endidx-1
   assert (not np.isfinite(out['vol_ratio']))==expected_unknown
   windowchecks.append(dict(sid=sid,day=d,technical_no_order=True,expected_vol_unknown=expected_unknown,actual_vol_unknown=not np.isfinite(out['vol_ratio']),prefix_exact=bool(eq)))
 for r in g.itertuples():
  out=point(r,data,stockage);rows.append(out)
  if out['root_known_original'] and not out['root_independently_verified']:rootissues.append(dict(event_id=r.event_id,sid=sid,signal_day=r.signal_day,original_root=r.root_day))
  # Exact native close coordinate equality at signal, not raw-price substitution.
  identity.append(dict(event_id=r.event_id,signal_close_exact=bool(b.at[r.signal_day,'close']==f.at[r.signal_day,'close']==inp.at[r.signal_day,'close'])))
  if (sid,r.signal_day) in samples:
   d=r.signal_day;dd=prep(b.loc[:d],f.loc[:d],cp.loc[:d],inp.loc[:d])
   prefix_state=states[:rr.index.get_loc(d)+1];shortage=pd.Series(ages(prefix_state),index=rr.index[:len(prefix_state)])
   again=point(r,dd,shortage)
   equal=all((pd.isna(v) and pd.isna(again[k])) or v==again[k] for k,v in out.items())
   checks.append(dict(sid=sid,signal_day=d,prepared_source_physically_truncated=True,features_exact=bool(equal)))
 if n%200==0:print('STOCKS',n,'/',m.sid.nunique(),'seconds',round(time.monotonic()-t0,2),flush=True)
features=pd.DataFrame(rows).sort_values(['window','signal_day','sid'])
assert len(features)==4086 and features.event_id.is_unique
features.to_csv(O/'ENTRY_FEATURES_PRELABEL.csv',index=False)
pd.DataFrame(checks).to_csv(O/'PHYSICAL_PREFIX_CHECKS.csv',index=False)
pd.DataFrame(identity).to_csv(O/'PRICE_COORDINATE_IDENTITY.csv',index=False)
pd.DataFrame(windowchecks).to_csv(O/'TECHNICAL_WINDOW_BOUNDARY.csv',index=False)
save('ROOT_RECHECK_ISSUES.json',rootissues)
save('FEATURE_SEAL.json',dict(created_utc=pd.Timestamp.now(tz='UTC'),rows=len(features),sha256=sha(O/'ENTRY_FEATURES_PRELABEL.csv'),code_sha256=sha(__file__),protocol_sha256=sha(O/'PROTOCOL.json'),new_features_all_signal_time=True))
labels=pd.concat([pd.read_csv(p,parse_dates=['signal_day'],dtype={'window':str}) for p in labpaths],ignore_index=True);labels=labels[labels.arm.eq('A_UNION_B')]
cols=['event_id','status','entry_status','entry_day','exit_day','core_net','core_return','net_pnl','net_return_on_buy_cash','financial_coverage_status','evidence_usable_closed']
z=features.merge(labels[cols],on='event_id',how='left',validate='one_to_one');assert z.status.notna().all()
z.to_csv(O/'ENTRY_FEATURES_WITH_OLD_LABELS.csv',index=False)
def stats(p,axis,value,g,layer):
 known=g[g.evidence_usable_closed.eq(True)];col,ret=('core_net','core_return') if layer=='CORE' else ('net_pnl','net_return_on_buy_cash')
 pos=known[col]>0;neg=known[col]<0
 return dict(period=p,axis=axis,value=value,layer=layer,permits=len(g),stocks=g.sid.nunique(),dates=g.signal_day.nunique(),industries=g.sector.nunique(),conditional_fills=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),usable_closed=len(known),wins=int(pos.sum()),losses=int(neg.sum()),zeros=int(known[col].eq(0).sum()),winrate=float(pos.mean()) if len(known) else None,net=float(known[col].sum()),mean_net=float(known[col].mean()),mean_win=float(known.loc[pos,col].mean()),mean_loss=float(known.loc[neg,col].mean()),payoff=float(known.loc[pos,col].mean()/-known.loc[neg,col].mean()) if pos.any() and neg.any() else None,mean_return=float(known[ret].mean()),gross_profit=float(known.loc[pos,col].sum()),gross_loss=float(known.loc[neg,col].sum()),final_net_ge30=int(known[ret].ge(.3).sum()),final_net_ge50=int(known[ret].ge(.5).sum()),financial_unusable_closed=int((g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&~g.evidence_usable_closed).sum()),execution_unknown=int(g.status.str.contains('UNKNOWN',na=False).sum()),nofill=int(g.status.str.contains('NOFILL',na=False).sum()),censored=int(g.status.str.contains('CENSORED',na=False).sum()))
summary=[];continuous=[];counts=[]
interactions=[('entry_type','I_root_age'),('CP_root_context','vol5_vs_prior63')]
for period,g in periods(z):
 for layer in ['CORE','FULL']:summary.append(stats(period,'ALL','ALL',g,layer))
 for axis in axes:
  assert g[axis].notna().all()
  assert set(g[axis])<=set(cats[axis])
  for value in cats[axis]:
   gg=g[g[axis].eq(value)]
   for layer in ['CORE','FULL']:summary.append(stats(period,axis,value,gg,layer))
  counts.append(dict(period=period,axis=axis,rows=len(g),sum_rows=sum(len(gg) for _,gg in g.groupby(axis,dropna=False)),unknown_rows=int(g[axis].str.contains('UNKNOWN').sum())))
 for one,two in interactions:
  for key in itertools.product(cats[one],cats[two]):
   gg=g[g[one].eq(key[0])&g[two].eq(key[1])]
   for layer in ['CORE','FULL']:summary.append(stats(period,one+'__X__'+two,'|'.join(key),gg,layer))
 lab=np.where(g.evidence_usable_closed.eq(True),np.where(g.core_net>0,'OLD_CORE_WIN','OLD_CORE_LOSS_OR_ZERO'),'ECONOMIC_UNKNOWN_OR_NOFILL')
 for label,gg in g.assign(oldlabel=lab).groupby('oldlabel'):
  for col in ['ret21','I_birth_return','risk_units','vol_ratio','amount_ratio']:
   a=gg[col].dropna()
   continuous.append(dict(period=period,old_core_group=label,feature=col,total=len(gg),known=len(a),unknown=len(gg)-len(a),q25=float(a.quantile(.25)),median=float(a.median()),q75=float(a.quantile(.75))))
pd.DataFrame(summary).to_csv(O/'ALL_PREDEFINED_STRATA.csv',index=False)
pd.DataFrame(continuous).to_csv(O/'CONTINUOUS_DISTRIBUTIONS.csv',index=False)
pd.DataFrame(counts).to_csv(O/'STRATA_COVERAGE_QA.csv',index=False)
assert all(q['rows']==q['sum_rows'] for q in counts)
save('SOURCE_HASHES.json',S);after={p:sha(p) for p in S};save('SOURCE_HASHES_AFTER.json',after);assert S==after
qa=dict(rows=len(features),stocks=features.sid.nunique(),all_event_identity_unique=True,all_label_joined=True,physical_prefix_samples=len(checks),all_prefix_exact=all(q['features_exact'] for q in checks),all_signal_price_coordinates_exact=all(q['signal_close_exact'] for q in identity),root_recheck_issues=len(rootissues),predefined_axes=len(axes),predefined_interactions=2,all_strata_denominators_exact=True,source_count=len(S),sources_unchanged=True,seconds=time.monotonic()-t0,no_new_economics=True,technical_window_boundary_checks=windowchecks)
save('QA.json',qa);save('DONE.json',qa);print(json.dumps(qa,indent=2),flush=True)
ss=pd.DataFrame(summary);print(ss[ss.axis.eq('ALL')].to_string(index=False),flush=True)
