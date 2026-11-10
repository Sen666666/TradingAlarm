"""Capacity-only shadow diagnosis on an immutable original account path."""
from common_m1 import *
import pandas as pd
import gzip,collections

CAPACITY={'total_slots_full','sector_slots_full','sector_issuer_slots_full'}
def select(ids,occupied,sector,rank,sector_rank,allowed=None):
 # Same S0 sector rounds and skip-within-sector behavior, no cash allocation.
 counts=collections.Counter(o['sector_id'] for o in occupied)
 used={o['security_id'] for o in occupied}
 groups={}
 for s in ids:
  if s not in used:groups.setdefault(sector[s],[]).append(s)
 def order(ids,scores):
  ids=sorted(ids)
  return ids if any(not np.isfinite(scores[s]) for s in ids) else sorted(ids,key=lambda s:(-scores[s],s))
 ordered=order(groups,sector_rank);queues={sec:order(groups[sec],rank) for sec in ordered};selected=[]
 while any(queues.values()):
  for sec in ordered:
   q=queues[sec]
   while q:
    sid=q.pop(0)
    if len(used)>=6 or counts[sec]>=2 or (sec not in counts and len(counts)>=3):continue
    if allowed is not None and not allowed[sid]:continue
    selected.append(sid);used.add(sid);counts[sec]+=1;break
 return selected

def test():
 sec={'a':'X','b':'X','c':'Y','d':'Z','e':'W'};rank={'a':90.,'b':80.,'c':95.,'d':70.,'e':100.};sr={'X':80.,'Y':90.,'Z':70.,'W':100.}
 assert select(sec,[],sec,rank,sr)==['e','c','a','b']
 assert select(sec,[],sec,rank,sr,{s:s!='e' for s in sec})==['c','a','d','b']
 occ=[dict(security_id='a',sector_id='X'),dict(security_id='b',sector_id='X'),dict(security_id='c',sector_id='Y'),dict(security_id='d',sector_id='Z')]
 assert select(['e'],occ,sec,rank,sr)==[]
 assert select(['e'],occ[:-1],sec,rank,sr)==['e']
 # Removing one of two positions in an industry does not free that industry.
 assert select(['e'],occ[1:],sec,rank,sr)==[]

def rows(path):
 with gzip.open(path,'rt') as f:
  for line in f:
   if '"account": "IX__S0_base"' in line:yield json.loads(line)

def main():
 verify();test();out=HERE/'handoff-v1';out.mkdir(exist_ok=False)
 obj=read(SRC/'accounts/IX__S0_base.json');completed=collections.defaultdict(set)
 for x in obj['completed_exits']:completed[x['completed_at'][:10]].add(x['security_id'])
 rules=read(OLD/'inputs-v2/market-rules.json');cal=sorted(set(x[:10] for x in rules['calendars']['A']));nxt=dict(zip(cal,cal[1:]));meta=read(OLD/'inputs-v2/metadata.json');sector={s:x['sector_id'] for s,x in meta.items()}
 z=np.load(OLD/'h1/matrix.npz');dates=pd.DatetimeIndex(z['dates']);cols={str(s):i for i,s in enumerate(z['symbols'])};score=z['score'];dp={str(d.date()):i for i,d in enumerate(dates)}
 manifest={r['series_id']:r for r in read(OLD/'inputs-v2/input-manifest.json')['series']};raw={};daily={x['at'][:10]:x for x in rows(SRC/'accounts/daily.jsonl.gz')}
 def minimum(sid,day):
  if sid not in raw:
   r=manifest[sid];p=Path(r['raw']['path']);p=p if p.is_absolute() else (OLD/'inputs-v2'/p).resolve();assert sha(p)==r['raw']['sha256'];f=pd.read_parquet(p);f.index=pd.DatetimeIndex(pd.to_datetime(f.trade_date if 'trade_date' in f else f.index));raw[sid]=f.close
  if pd.Timestamp(day) not in raw[sid].index:return np.nan
  v=[x for x in rules['quantity_versions'][sid] if x['from']<=day and (x['to'] is None or day<=x['to'])];assert len(v)==1
  return float(raw[sid].loc[day])*v[0]['rule']['buy_minimum']
 details=[];dayrows=[]
 for d in rows(SRC/'accounts/decisions.jsonl.gz'):
  day=d['at'][:10];nextday=nxt[day];occ=d['occupancy'];occupied_ids={o['security_id'] for o in occ};candidates=[s for s,r in d['first_rejected'] if r in CAPACITY and s not in occupied_ids and s not in d['accepted']]
  removed={o['security_id'] for o in occ if o['exit_latched'] and o['security_id'] in completed[nextday]}
  if not removed:
   dayrows.append(dict(date=day,capacity_rejected=len(candidates),removed=0,capacity_selected=0,lot_aware_selected=0));continue
  retained=[o for o in occ if o['security_id'] not in removed];i=dp[day]
  ranks={s:score[i,cols[s]] for s in candidates};sr={sector[s]:score[i,cols[sector[s]]] for s in candidates};minlot={s:minimum(s,day) for s in candidates};cap=float(daily[day]['nav'])*.15
  allowed={s:np.isfinite(minlot[s]) and minlot[s]<=cap for s in candidates}
  alone=select(candidates,retained,sector,ranks,sr);lot=select(candidates,retained,sector,ranks,sr,allowed)
  for s in candidates:
   single=select([s],retained,sector,ranks,sr)
   details.append(dict(date=day,next_market_day=nextday,symbol=s,name=meta[s]['name'],industry=meta[s]['industry'],sector_id=sector[s],original_reason=dict(d['first_rejected'])[s],removed='|'.join(sorted(removed)),removed_count=len(removed),individual_capacity_fit=bool(single),capacity_selected=s in alone,lot_aware_selected=s in lot,minimum_lot=minlot[s],cap15=cap,lot_within_cap=allowed[s],stock_rs=ranks[s],sector_rs=sr[sector[s]]))
  dayrows.append(dict(date=day,capacity_rejected=len(candidates),removed=len(removed),capacity_selected=len(alone),lot_aware_selected=len(lot)))
 df=pd.DataFrame(details);labels=pd.read_parquet(HERE/'analysis/all-event-multiscale.parquet');df=df.merge(labels[['symbol','date','year','profile','ret21','ret63']],on=['symbol','date'],how='left',validate='one_to_one');assert df.year.notna().all()
 assert df.minimum_lot.notna().all();df.to_parquet(out/'candidate-capacity-shadow.parquet',index=False);pd.DataFrame(dayrows).to_csv(out/'daily-capacity.csv',index=False)
 summary=[]
 for scope,start in [('full','2015-01-01'),('recent','2023-01-01')]:
  a=df.loc[df.date.ge(start)];days=pd.DataFrame(dayrows).query('date>=@start')
  for flag in ['individual_capacity_fit','capacity_selected','lot_aware_selected']:
   b=a.loc[a[flag]];vals=b.ret63.dropna();sy=b.dropna(subset=['ret63']).groupby(['symbol','year']).ret63.mean()
   summary.append(dict(scope=scope,kind=flag,all_capacity_rejected_events=int(days.capacity_rejected.sum()),days_with_true_next_exit=int(days.removed.gt(0).sum()),events=len(b),unique_stocks=b.symbol.nunique(),days=b.date.nunique(),complete_63_labels=len(vals),mean63=vals.mean(),median63=vals.median(),positive63=vals.gt(0).mean(),stock_year_mean63=sy.mean()))
 pd.DataFrame(summary).to_csv(out/'summary.csv',index=False);write(out/'summary.json',summary)
 focus=df.loc[df.symbol.isin(['688256.SH','300308.SZ','300502.SZ'])];focus.to_csv(out/'three-stock-shadow.csv',index=False)
 write(out/'receipt.json',dict(passed=True,original_account='IX__S0_base',all_dates=len(dayrows),shadow_candidate_rows=len(df),synthetic_tests=5,new_accounts=0,no_cash_or_fills_invented=True,actual_future_exit_used_only_in_retrospective_shadow=True,original_pending_buys_kept=True))
 print(pd.DataFrame(summary).to_string(index=False),flush=True)
if __name__=='__main__':main()
