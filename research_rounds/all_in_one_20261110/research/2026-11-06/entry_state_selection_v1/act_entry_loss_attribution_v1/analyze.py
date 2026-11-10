"""Read-only completed-ledger attribution; no strategy/account imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import pandas as pd,numpy as np,json,gzip,hashlib,datetime,traceback,gc
O=Path(__file__).resolve().parent;F=json.loads((O/'FREEZE.json').read_text());S=Path(F['source_root']);Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readcsv(n):return pd.read_csv(S/'analysis'/n,keep_default_na=False,float_precision='round_trip')
def save(n,x):
 def clean(v):
  if isinstance(v,dict):return {str(k):clean(t) for k,t in v.items()}
  if isinstance(v,(list,tuple)):return [clean(t) for t in v]
  if isinstance(v,np.generic):return clean(v.item())
  if isinstance(v,float) and not np.isfinite(v):return None
  if isinstance(v,D):return str(v)
  return v
 (O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def export(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
def sign(x):return 'POSITIVE' if x>1e-8 else 'NEGATIVE' if x< -1e-8 else 'ZERO'
def quant(v,q=.5):
 v=np.asarray(v,dtype=float);v=v[np.isfinite(v)];return float(np.quantile(v,q)) if len(v) else np.nan
def main():
 assert sha(O/'DEFINITIONS.md')==F['definitions_sha256']
 rounds=readcsv('STOCK_ROUNDS.csv');layers=readcsv('LAYER_ATTRIBUTION.csv')
 for k in ['pnl','buy_cost','buy_gross','remaining_cost','ending_inventory','ending_quantity','initial_layer_pnl']:
  rounds[k]=pd.to_numeric(rounds[k])
 for k in ['pnl','buy_cost','buy_gross','buy_fees','remaining_cost','ending_inventory','qty']:
  layers[k]=pd.to_numeric(layers[k])
 days=[];by=defaultdict(dict)
 with gzip.open(S/'run/pair/daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);by[x['account']][x['at'][:10]]=x
 days=sorted(by['PVR']);assert len(days)==1054 and sorted(by['NOACT'])==days
 ix={d:i for i,d in enumerate(days)};cal=pd.DatetimeIndex(days);price={};valid={};stale={};qa={'account_runs':0,'common_sessions':len(days),'original_source_files':len(F['source_hashes'])}
 for sid,p in F['price_source_by_sid'].items():
  assert sha(p)==F['source_hashes'][p],p
  b=pd.read_parquet(p,columns=['raw_close','price_eligible','observed_bar','source_invalid','synthetic_event_bar'])
  v=b.price_eligible.fillna(False)&b.observed_bar.fillna(False)&~b.source_invalid.fillna(True)&~b.synthetic_event_bar.fillna(True)&np.isfinite(b.raw_close)&b.raw_close.gt(0)
  price[sid]=b.raw_close.reindex(cal).to_numpy(float)
  valid[sid]=v.reindex(cal,fill_value=False).to_numpy(bool)
  stale[sid]=b.raw_close.where(v).ffill().reindex(cal).to_numpy(float)
 rows=[];dailyrows=[];annualcap=[];qaby={}
 for arm in ['PVR','NOACT']:
  rr=rounds[rounds.account.eq(arm)].copy();ll=layers[layers.account.eq(arm)].copy();ld={int(x['id']):x for x in ll.to_dict('records')};rd={int(x['round_id']):x for x in rr.to_dict('records')};assign={k:int(x['round_id']) for k,x in ld.items()};initial={int(x['round_id']):int(x['initial_layer']) for x in rd.values()}
  with gzip.open(S/f'run/pair/{arm}.json.gz','rt') as f:a=json.load(f)
  trades=a['trades'];events=defaultdict(list);buy={};splits=defaultdict(list)
  for j,t in enumerate(a['journal']):
   if t['kind']=='actual_split':events[t['at'][:10]].append((t['at'],0,j,t));splits[t['sid']].append(t)
  for j,t in enumerate(trades):
   events[t['at'][:10]].append((t['at'],1,j,t))
   if t['side']=='buy':buy[int(t['layer'])]=t
  del a;gc.collect()
  q={};cost={};cash={};div={};paths=defaultdict(list);maxinv=0;maxcost=0;maxq=0;pool={};yearcap=defaultdict(lambda:defaultdict(float))
  for di,d in enumerate(days):
   for at,typ,j,t in sorted(events[d]):
    if typ==0:
     keys=[k for k,n in q.items() if n>0 and ld[k]['sid']==t['sid']]
     old=sum(q[k] for k in keys)
     if old:
      ratio=D(t['ratio']);target=int(D(old)*ratio);parts=[int(D(q[k])*ratio) for k in keys]
      for z in range(target-sum(parts)):parts[z%len(parts)]+=1
      for k,n in zip(keys,parts):
       q[k]=n
       if not n:cost[k]=Z
    elif t['side']=='buy':
     k=int(t['layer']);q[k]=int(t['shares']);cost[k]=D(t['gross_cny'])+D(t['fees_cny']);cash[k]=-cost[k];div[k]=Z
    else:
     for p in t['parts']:
      k=int(p['layer']);n=int(p['shares']);assert 0<n<=q[k]
      allocation=cost[k]*D(n)/D(q[k]);cost[k]-=allocation;q[k]-=n;cash[k]+=D(p['net_cash'])
   snap=by[arm][d];sq={int(x['id']):int(x['qty']) for x in snap['layers']}
   assert {k:n for k,n in q.items() if n}==sq,(arm,d,'daily layer quantities')
   for x in snap['layers']:
    k=int(x['id']);div[k]=D(x['dividend'])
    assert abs(cash[k]-D(x['cash']))<D('1e-7'),(arm,d,k,'cash')
    pool.setdefault(k,x.get('pool','UNKNOWN'))
   inv=sum(q[k]*stale[ld[k]['sid']][di] for k in sq)
   maxinv=max(maxinv,abs(inv-float(snap['inventory'])))
   live=defaultdict(list)
   for k in sq:live[assign[k]].append(k)
   for rid,keys in live.items():
    r=rd[rid];sid=r['sid'];k0=initial[rid];initq=q.get(k0,0);rc=float(sum((cost[k] for k in keys),Z));ic=float(cost.get(k0,Z)) if initq else 0.
    sr=1.
    for t in splits[sid]:
     if r['opened']<t['at'] and t['at'][:10]<=d:sr*=float(t['ratio'])
    obs=bool(valid[sid][di]);pr=float(price[sid][di])*sr/float(buy[k0]['price'])-1 if obs else np.nan
    ipnl=float(cash[k0]+div[k0])+initq*stale[sid][di] if initq else np.nan
    x=dict(account=arm,round_id=rid,sid=sid,day=d,entry_year=r['opened'][:4],held_close_ordinal=di-ix[r['opened'][:10]]+1,valid_fresh_close=obs,raw_close=float(price[sid][di]) if obs else np.nan,native_mark=float(stale[sid][di]),ledger_split_factor=sr,close_price_return=pr,round_quantity=sum(q[k] for k in keys),initial_quantity=initq,round_remaining_cost=rc,initial_remaining_cost=ic,initial_mark_pnl=ipnl,initial_layer_live=bool(initq))
    paths[rid].append(x);dailyrows.append(x);yearcap[d[:4]]['round_capital_days']+=rc;yearcap[d[:4]]['initial_capital_days']+=ic
   for k in sq:
    r=rd[assign[k]]
    assert r['opened'][:10]<=d and (not r['closed'] or d<r['closed'][:10]),(arm,d,k,'round window')
  assert maxinv<1e-6,(arm,'raw mark mismatch',maxinv)
  for k,x in ld.items():
   maxcost=max(maxcost,abs(float(cost[k])-x['remaining_cost']));assert q[k]==int(x['qty'])
  assert maxcost<1e-7,(arm,'cost final mismatch',maxcost)
  for rid,r in rd.items():
   k0=initial[rid];l=ld[k0];p=paths[rid];assert len(p)>0
   expected=ix[r['closed'][:10]]-ix[r['opened'][:10]] if r['closed'] else len(days)-ix[r['opened'][:10]]
   assert len(p)==expected,(arm,rid,'path daily count')
   p0=[x for x in p if x['initial_layer_live']]
   addids=[int(k) for k in json.loads(r['layer_ids']) if int(k)!=k0 and ld[int(k)]['kind']=='add']
   laterids=[int(k) for k in json.loads(r['layer_ids']) if int(k)!=k0]
   firstadd=min((ld[k]['opened'] for k in addids),default='')
   row=dict(account=arm,round_id=rid,sid=r['sid'],opened=r['opened'],closed=r['closed'],entry_year=r['opened'][:4],round_status='CLOSED' if r['closed'] else 'OPEN',initial_layer=k0,initial_kind=r['initial_kind'],initial_pool=pool.get(k0,'UNKNOWN'),initial_closed=l['closed'],initial_status='CLOSED' if l['closed'] else 'OPEN',round_pnl=r['pnl'],initial_pnl=l['pnl'],later_layer_pnl=r['pnl']-l['pnl'],round_buy_cost=r['buy_cost'],initial_buy_cost=l['buy_cost'],round_return=r['pnl']/r['buy_cost'],initial_return=l['pnl']/l['buy_cost'],round_sign=sign(r['pnl']),initial_sign=sign(l['pnl']),has_followup_buy=bool(laterids),has_followup_add=bool(addids),followup_add_count=len(addids),followup_buy_count=len(laterids),first_followup_add=firstadd,first_followup_add_session=(ix[firstadd[:10]]-ix[r['opened'][:10]]+1) if firstadd else np.nan,booked_dividend=r['booked_dividend_accrual'],initial_booked_dividend=l['dividend'],historical_real_tradability='UNKNOWN',external_dividend_payout='UNKNOWN',historical_terms_PIT='UNKNOWN')
   for pref,pp,status,pnl in [('round',p,row['round_status'],row['round_pnl']),('initial',p0,row['initial_status'],row['initial_pnl'])]:
    assert len(pp)>0
    arr=np.array([x['close_price_return'] for x in pp]);vv=np.isfinite(arr);good=arr[vv];complete=bool(vv.all());hits=np.flatnonzero(arr>=.05);hit=int(hits[0]) if len(hits) else None
    first20=arr[:20];h20=np.any(first20>=.05);known20=bool(np.isfinite(first20).all())
    stalled='PROMOTED_BY_20' if h20 else 'UNKNOWN' if not known20 else 'STALLED20' if len(pp)>=20 else 'EXIT_BEFORE20' if status=='CLOSED' else 'OPEN_CENSORED_BEFORE20'
    space='OBSERVED_GE5' if len(hits) else 'UNKNOWN' if not complete else 'CLOSE_NO_UPSIDE' if good.max()<=0 else 'CLOSE_UP_LT5'
    capital=sum(x[pref+'_remaining_cost'] for x in pp);before=sum(x[pref+'_remaining_cost'] for i,x in enumerate(pp) if hit is None or i<hit)
    row.update({pref+'_held_closes':len(pp),pref+'_calendar_days':(pd.Timestamp(row['closed'] if pref=='round' else row['initial_closed'])-pd.Timestamp(r['opened'])).total_seconds()/86400 if status=='CLOSED' else (pd.Timestamp(days[-1]+' 15:10:00+08:00')-pd.Timestamp(r['opened'])).total_seconds()/86400,pref+'_valid_closes':int(vv.sum()),pref+'_missing_closes':int((~vv).sum()),pref+'_path_status':'COMPLETE' if complete else 'UNKNOWN',pref+'_close_mfe':float(good.max()) if complete else np.nan,pref+'_close_mae':float(good.min()) if complete else np.nan,pref+'_observed_close_max':float(good.max()) if len(good) else np.nan,pref+'_observed_close_min':float(good.min()) if len(good) else np.nan,pref+'_space_bucket':space,pref+'_first5_day':pp[hit]['day'] if hit is not None else '',pref+'_first5_session':hit+1 if hit is not None else np.nan,pref+'_first5_time_known':bool(np.isfinite(arr[:hit+1]).all()) if hit is not None else complete,pref+'_progress20':stalled,pref+'_capital_days':capital,pref+'_capital_days_before_first5':before,pref+'_capital_days_from20':sum(x[pref+'_remaining_cost'] for x in pp[19:]),pref+'_space_then_loss':space=='OBSERVED_GE5' and status=='CLOSED' and pnl<0,pref+'_space_then_mark_loss':space=='OBSERVED_GE5' and status=='OPEN' and pnl<0})
   row['round_stalled20_no_add_by20']=row['round_progress20']=='STALLED20' and (not firstadd or row['first_followup_add_session']>20)
   row['round_stalled20_initial_capital_days']=sum(x['initial_remaining_cost'] for x in p) if row['round_progress20']=='STALLED20' else 0
   row['round_stalled20_initial_capital_days_from20']=sum(x['initial_remaining_cost'] for x in p[19:]) if row['round_progress20']=='STALLED20' else 0
   row['initial_mark_positive_close_count']=sum(x['initial_mark_pnl']>0 for x in p0)
   row['initial_mark_max']=max(x['initial_mark_pnl'] for x in p0)
   rows.append(row)
  qaby[arm]=dict(rounds=len(rr),closed=int(rr.closed.ne('').sum()),open=int(rr.closed.eq('').sum()),max_inventory_mark_gap=maxinv,max_remaining_cost_gap=maxcost,all_daily_layer_shares_match=True)
  for y,v in yearcap.items():annualcap.append(dict(account=arm,year=y,sessions=sum(d.startswith(y) for d in days),**v))
  del trades,events,paths;gc.collect()
 out=pd.DataFrame(rows);export('ALL_ROUND_ATTRIBUTION.csv',out);export('DAILY_HELD_PATH.csv',dailyrows);export('CALENDAR_YEAR_CAPITAL_DAYS.csv',annualcap)
 def metrics(g,pref):
  p=g[pref+'_pnl'];st=g[pref+'_status'];closed=st.eq('CLOSED');neg=p.lt(0);positive=p.gt(0)
  return dict(n=len(g),closed=int(closed.sum()),open=int((~closed).sum()),closed_wins=int((closed&positive).sum()),closed_losses=int((closed&neg).sum()),closed_gross_profit=float(p[closed&positive].sum()),closed_gross_loss=float(-p[closed&neg].sum()),closed_net=float(p[closed].sum()),open_mark_gross_profit=float(p[~closed&positive].sum()),open_mark_gross_loss=float(-p[~closed&neg].sum()),open_mark_net=float(p[~closed].sum()),all_net_including_open_mark=float(p.sum()),buy_cost=float(g[pref+'_buy_cost'].sum()),capital_days=float(g[pref+'_capital_days'].sum()),capital_days_from20=float(g[pref+'_capital_days_from20'].sum()),median_held_closes=quant(g[pref+'_held_closes']),p90_held_closes=quant(g[pref+'_held_closes'],.9),median_mfe=quant(g[pref+'_close_mfe']),median_mae=quant(g[pref+'_close_mae']),median_first5_session=quant(g[pref+'_first5_session']),with_followup_add=int(g.has_followup_add.sum()),price_unknown=int(g[pref+'_path_status'].eq('UNKNOWN').sum()))
 totals=[];spaces=[];prog=[];signs=[];loss=[];add=[];holds=[]
 for arm in ['PVR','NOACT']:
  for year in ['ALL']+sorted(out.entry_year.unique()):
   g=out[out.account.eq(arm)&(True if year=='ALL' else out.entry_year.eq(year))]
   for pref in ['initial','round']:
    base=dict(account=arm,entry_year=year,level=pref);m=metrics(g,pref);totals.append({**base,**m})
    for column,target in [(pref+'_space_bucket',spaces),(pref+'_progress20',prog)]:
     for category,z in g.groupby(column,dropna=False):
      zz=metrics(z,pref);zz['round_capital_days']=float(z.round_capital_days.sum());zz['initial_capital_days']=float(z.initial_capital_days.sum());zz['round_net']=float(z.round_pnl.sum());zz['initial_net']=float(z.initial_pnl.sum());zz['fraction_of_all_capital_days']=zz['capital_days']/m['capital_days'] if m['capital_days'] else np.nan;zz['fraction_of_all_closed_gross_loss']=zz['closed_gross_loss']/m['closed_gross_loss'] if m['closed_gross_loss'] else np.nan
      target.append({**base,'category':category,**zz})
    for (sp,ad),z in g.groupby([pref+'_progress20','has_followup_add'],dropna=False):add.append({**base,'progress20':sp,'has_followup_add':bool(ad),**metrics(z,pref)})
    h=pd.cut(g[pref+'_held_closes'],[0,5,20,60,np.inf],labels=['1_5','6_20','21_60','61_PLUS'])
    for cat in ['1_5','6_20','21_60','61_PLUS']:holds.append({**base,'holding_bucket':cat,**metrics(g[h.eq(cat)],pref)})
   for (s0,s1,i0,i1),z in g.groupby(['initial_sign','round_sign','initial_status','round_status']):signs.append(dict(account=arm,entry_year=year,initial_sign=s0,round_sign=s1,initial_status=i0,round_status=i1,n=len(z),initial_net=float(z.initial_pnl.sum()),round_net=float(z.round_pnl.sum()),later_layer_net=float(z.later_layer_pnl.sum()),initial_capital_days=float(z.initial_capital_days.sum()),round_capital_days=float(z.round_capital_days.sum())))
 for n,t in [('COHORT_TOTALS.csv',totals),('PRICE_SPACE_PARTITION.csv',spaces),('PROGRESS20_PARTITION.csv',prog),('PROGRESS20_BY_ADD.csv',add),('INITIAL_TO_ROUND_SIGN.csv',signs),('HOLDING_DURATION_PARTITION.csv',holds)]:export(n,t)
 cases=[]
 for arm in ['PVR','NOACT']:
  for year in ['2022','2024']:
   g=out[out.account.eq(arm)&out.entry_year.eq(year)].sort_values(['opened','sid','round_id'])
   conditions={'INITIAL_LOSS_NO_UPSIDE':g.initial_pnl.lt(0)&g.initial_space_bucket.eq('CLOSE_NO_UPSIDE'),'INITIAL_LOSS_GE5':g.initial_pnl.lt(0)&g.initial_space_bucket.eq('OBSERVED_GE5'),'STALLED20_ROUND_LOSS':g.round_pnl.lt(0)&g.round_progress20.eq('STALLED20')}
   for typ,c in conditions.items():
    if c.any():cases.append(dict(case_type=typ,**g[c].iloc[0].to_dict()))
  g=out[out.account.eq(arm)&out.round_status.eq('OPEN')].sort_values(['opened','sid','round_id'])
  if len(g):cases.append(dict(case_type='OPEN_RETAINED',**g.iloc[0].to_dict()))
 export('MECHANISM_CASES.csv',cases)
 casekeys={(r['account'],r['round_id']) for r in cases};export('MECHANISM_CASE_PATHS.csv',[x for x in dailyrows if (x['account'],x['round_id']) in casekeys])
 srcsum=json.loads((S/'analysis/SUMMARY.json').read_text())['summary']
 for arm in ['PVR','NOACT']:
  g=out[out.account.eq(arm)];gg=rounds[rounds.account.eq(arm)];l=layers[layers.account.eq(arm)]
  assert abs(g.round_pnl.sum()-gg.pnl.sum())<1e-7
  assert abs(g.initial_pnl.sum()-l[l.initial_layer.astype(str).str.lower().eq('true')].pnl.sum())<1e-7
  expected=float(srcsum[arm]['mean_remaining_buy_cost'])*len(days);err=abs(g.round_capital_days.sum()-expected);assert err<1e-5,(arm,'capital-days',err)
  qaby[arm]['round_capital_days']=float(g.round_capital_days.sum());qaby[arm]['initial_capital_days']=float(g.initial_capital_days.sum());qaby[arm]['capital_days_mean_cost_bridge_gap']=err
  qaby[arm]['price_unknown_rounds']=int(g.round_path_status.eq('UNKNOWN').sum());qaby[arm]['initial_price_unknown']=int(g.initial_path_status.eq('UNKNOWN').sum())
 for p,h in F['source_hashes'].items():assert sha(p)==h,('source changed',p)
 qa.update(accounts=qaby,source_hashes_unchanged=True,definitions_unchanged=sha(O/'DEFINITIONS.md')==F['definitions_sha256'],status='PASS',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 save('CHECKS.json',qa);save('TABLES.json',dict(totals=totals,space=spaces,progress20=prog,by_add=add,sign=signs,holding=holds));save('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(qa,indent=2));print(pd.DataFrame(totals).query("entry_year in ['ALL','2022','2024']").to_string(index=False))
if __name__=='__main__':
 try:main()
 except Exception as e:
  save('FAILURE.json',dict(error=repr(e),traceback=traceback.format_exc(),account_runs=0));raise
