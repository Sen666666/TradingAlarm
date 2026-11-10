from pathlib import Path
import json,gzip,hashlib,collections
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'act_pause_scope_diagnostic_v1'
P=R/'account_comparison_continuous_v1/run_1200000/pair';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');U=W/'universe-cp1-inputs-20261031'
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):
 p=Path(p);SRC[str(p)]=sha(p);return p
def read(p):return json.loads(bind(p).read_text())
def rows(p):
 with gzip.open(bind(p),'rt')as f:
  for l in f:yield json.loads(l)
def csv(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
def js(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
assert not (O/'SUMMARY.json').exists()
case_spec=[['688248.SH','2022-04-18','2022-06-24']]+[[s,'2024-09-02','2024-10-16']for s in ['002583.SZ','688660.SH','605488.SH','600396.SH','002241.SZ','601336.SH']]
js('PROTOCOL.json',dict(scope='Saved continuous PVR/E31 1200000 accounts only; no Account or Runner initialization or economic replay',window=['2022-01-04','2026-05-15'],fixed_pool=1709,case_windows=case_spec,pause_day='Post-transition CLOSE, includes trigger close and excludes resume close',only_ACT='saved roles nonempty, saved barriers exactly ACT_paused; before price/floor sizing, industry route and funding',industry_active='source same-day E0_valid and attempt_id nonnull and stage>=1; necessary, not sufficient',not_claimed=['counterfactual account','fill','missed profit','new final PVR queue during pause']))
daily={(x['account'],x['at'][:10]):x for x in rows(P/'daily.jsonl.gz')}
accounts={};risk={};events=[];annual=[]
for a in ['PVR','E31']:
 with gzip.open(bind(P/(a+'.json.gz')),'rt')as f:accounts[a]=json.load(f)
 rr=[x for x in accounts[a]['audit']if x['kind']=='risk_checkpoint']
 for x in rr:
  d=x['at'][:10];risk[(a,d)]=x;assert daily[(a,d)]['on']==x['on']
  if x['event']:events.append(dict(account=a,**x))
 for y in range(2022,2027):
  z=[x for x in rr if x['at'][:4]==str(y)]
  annual.append(dict(account=a,year=y,close_days=len(z),paused_close_days=sum(not x['on']for x in z),paused_with_inventory_days=sum(not x['on']and bool(daily[(a,x['at'][:10])]['positions'])for x in z),pause_events=sum(x['event']=='pause'for x in z),resume_events=sum(x['event']=='resume'for x in z)))
csv('RISK_EVENTS.csv',events);csv('RISK_DAILY.csv',[dict(account=a,**x)for(a,d),x in risk.items()])
sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};industries={}
for r in read(U/'INDUSTRY_MANIFEST.json'):
 z=pd.read_parquet(bind(r['refs']['state']))
 for row in z.loc[z.day.between('2022-01-04','2026-05-15')].to_dict('records'):industries[(r['series'],row['day'])]=row
case_ranges={s:(l,h)for s,l,h in case_spec};paused=[];cases=[];stats=collections.Counter();n=0
for x in rows(P/'opportunities.jsonl.gz'):
 n+=1;a=x['account'];d=x['day'];y=int(d[:4]);on=daily[(a,d)]['on'];roles=x['roles'];bar=x['barriers'];assert ('ACT_paused'in bar)==(not on)
 st=industries.get((x['sector'],d));active=bool(st is not None and st['E0_valid']and pd.notna(st['attempt_id'])and st['stage']>=1)
 extra=dict(industry_active=active,industry_stage=st['stage_name']if st else 'UNKNOWN',industry_E0=st['E0_valid']if st else None,industry_receipt=st['receipt']if st else None,industry_attempt=st['attempt_id']if st else None)
 if roles:stats[(a,y,'all_role_stock_days')]+=1
 if roles and not on:
  stats[(a,y,'paused_role_stock_days')]+=1
  if set(bar)=={'ACT_paused'}:
   paused.append(dict(x,**extra))
   for m,k in [('only_ACT_stock_days',1),('only_ACT_role_intents',len(roles)),('only_ACT_and_active_industry_stock_days',int(active))]:stats[(a,y,m)]+=k
 if x['sid']in case_ranges and case_ranges[x['sid']][0]<=d<=case_ranges[x['sid']][1]:cases.append(dict(x,**extra,ACT_on=on))
assert n==1054*1709*2
pf=pd.DataFrame(paused)
for r in annual:
 for k in ['all_role_stock_days','paused_role_stock_days','only_ACT_stock_days','only_ACT_role_intents','only_ACT_and_active_industry_stock_days']:r[k]=stats[(r['account'],r['year'],k)]
 sub=pf[(pf.account==r['account'])&(pf.day.str[:4]==str(r['year']))]
 r['only_ACT_unique_stocks']=int(sub.sid.nunique());r['only_ACT_active_unique_stocks']=int(sub.loc[sub.industry_active,'sid'].nunique())
 for role in ['core','mobile']:r['only_ACT_'+role+'_intents']=sum(role in z for z in sub.roles)
csv('ANNUAL_PAUSE_COVERAGE.csv',annual)
out=pf.copy()
for k in ['roles','barriers']:out[k]=out[k].map(json.dumps)
out.to_parquet(O/'ONLY_ACT_ROLE_STOCK_DAYS.parquet',index=False)
csv('PAUSE_DAILY_CANDIDATE_COUNTS.csv',[dict(account=a,day=d,role_stock_days=len(g),active_industry_stock_days=int(g.industry_active.sum()),core_intents=sum('core'in z for z in g.roles),mobile_intents=sum('mobile'in z for z in g.roles),held=int(g.held.sum()))for(a,d),g in pf.groupby(['account','day'])])
rec=pd.read_csv(bind(W/'mainline-absolute-Q4-20261031/recovery.csv'),index_col=0);cd={}
for sid in case_ranges:
 r=sm[sid];cd[sid]=(pd.read_parquet(bind(r['refs']['facts'])),pd.read_parquet(bind(r['refs']['CP1'])),pd.read_parquet(bind(next(p for p in r['source_sha256']if p.endswith('/signal.parquet')))))
cout=[];trades=[];pause_sells=[]
for a,j in accounts.items():
 for t in j['trades']:
  if t.get('reason')=='ACT_pause':pause_sells.append(dict(account=a,**t))
  if t.get('sid',t.get('security_id'))in case_ranges:trades.append(dict(account=a,**t))
for x in cases:
 a=x['account'];sid=x['sid'];d=x['day'];day=pd.Timestamp(d);f,c,raw=cd[sid];row=dict(x);rr=risk[(a,d)];dr=daily[(a,d)]
 for k in ['nav','episode_drawdown','flat','fast','breakout','event','peak','episode']:row['ACT_'+k]=rr[k]
 row.update(account_cash=dr['available'],account_inventory=dr['inventory'],account_stock_count=len(dr['positions']),actual_close_shares=dr['positions'].get(sid,0),pending_intents=dr['pending_intents'])
 if day in f.index:
  for k in ['close','raw_close','e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_ready','factor','segment_id']:row[k]=f.loc[day,k]
 if day in c.index:
  for k in ['ready','receipt','candidate','phase','credit','anchor']:row['CP_'+k]=c.loc[day,k]
 if day in raw.index:
  for k in ['raw_open','raw_close','raw_high','raw_low','adjustment_factor','price_eligible','observed_bar','synthetic_event_bar']:row['source_'+k]=raw.loc[day,k]
 if d in rec.index:
  for k in ['market','prior_high63','breadth','breakout','fast_on']:row['market_'+k]=rec.loc[d,k]
 for k in ['roles','barriers']:row[k]=json.dumps(row[k])
 dj=next(z for z in accounts[a]['decisions']if z['at'][:10]==d)
 row['actual_stock_pending']=json.dumps([z for z in dj['intents']if z['sid']==sid])
 row['actual_today_trades']=json.dumps([z for z in accounts[a]['trades']if z['at'][:10]==d and z.get('sid',z.get('security_id'))==sid])
 cout.append(row)
csv('FIXED_CASE_DAILY.csv',cout);csv('ALL_ACT_PAUSE_SELLS.csv',pause_sells);csv('FIXED_CASE_ALL_TRADES.csv',trades)
js('SUMMARY.json',dict(status='COMPLETE_READ_ONLY',opportunity_rows=n,close_rows=len(daily),annual=annual,only_ACT_rows=len(paused),fixed_case_rows=len(cout),ACT_pause_sell_rows=len(pause_sells),new_account_paths=0,new_signals=0,remaining_admission_unknowns=['price/floor sizing','minimum units','CP receipt industry attempt validity','counterfactual PVR pending rank','same-open competing cash/risk','real fill'],PIT=False))
bind(Path(__file__));js('SOURCE_HASHES.json',SRC);js('OUTPUT_HASHES.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(dict(annual=annual,case_rows=len(cout),paused_rows=len(paused),pause_sell_rows=len(pause_sells)),ensure_ascii=False))
