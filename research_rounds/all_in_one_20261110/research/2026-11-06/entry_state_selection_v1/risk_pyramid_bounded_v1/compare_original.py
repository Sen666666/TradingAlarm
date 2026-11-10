from pathlib import Path
import pandas as pd,json,gzip
O=Path(__file__).resolve().parent
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE/2022_2024/pair')
a=json.load(gzip.open(B/'B.json.gz','rt'))
cases=[('300085.SZ','2024-09-18','2024-10-11'),('002583.SZ','2024-09-18','2024-11-27'),('600675.SH','2022-04-07','2022-04-21'),('601298.SH','2023-04-25','2023-05-31')]
rows=[];out=[]
for sid,start,end in cases:
 raw=pd.read_parquet(P/'bars'/f'{sid}.parquet').set_index('trade_date');raw.index=pd.to_datetime(raw.index)
 trades=[t for t in a['trades'] if t['security_id']==sid and start<=t['at'][:10]<=end]
 q=0;cf=0.;fees=0.
 for day,r in raw.loc[start:end].iterrows():
  d=str(day.date());tt=[t for t in trades if t['at'][:10]==d]
  for t in tt:
   sign=1 if t['side']=='buy' else -1;q+=sign*t['shares'];fees+=float(t['fees_cny']);cf-=sign*float(t['gross_cny'])+float(t['fees_cny'])
  rows.append(dict(sid=sid,day=d,raw_close=r.close,shares=q,nominal=q*r.close,window_cashflow=cf,window_marked_pnl=cf+q*r.close,fees=fees,original_initial_capital=1000000,not_1200000_scaled=True))
 out.append(dict(sid=sid,start=start,end=end,window_cashflow=cf,ending_shares=q,window_marked_pnl=cf+q*r.close,fees=fees))
pd.DataFrame(rows).to_csv(O/'ORIGINAL_DAILY_PATHS.csv',index=False)
(O/'ORIGINAL_WINDOW_SUMMARIES.json').write_text(json.dumps(out,indent=2))
# Exact named refusal; same old marks at next OPEN, no sell/corporate action before first candidate.
d=next(json.loads(x) for x in gzip.open(B/'daily.jsonl.gz','rt') if '2024-09-24 15:10' in x)
f=pd.read_parquet(P/'facts/300085.SZ.parquet');fac=float(f.loc['2024-09-25','factor']);intents=json.load(open(O.parent/'account_integration_audit_v1/2024-09-24_FROZEN_NATIVE_INTENTS.json'))
nav=float(d['nav']);used=d['pool_probe'][1];p=18.98*1.0005;buyfee=5+100*p*.0000641
refusal=dict(signal='2024-09-24',open='2024-09-25',nav=nav,probe_fraction=.005,cap_before_buyfee=.005*nav,existing_risk=used,available_risk=.005*nav-used,minimum_buyfee=buyfee,available_risk_after_fee_adjusted_nav=.005*(nav-buyfee)-used,roles=[])
for i in intents:
 if i['sid']=='300085.SZ':
  floor=float(i['floor'])/fac;refusal['roles'].append(dict(role=i['role'],raw_stop=floor,min_shares=100,min_risk=100*(p-floor),shortfall=100*(p-floor)-(.005*(nav-buyfee)-used)))
(O/'SILVER_PROBE_REFUSAL.json').write_text(json.dumps(refusal,indent=2))
print(json.dumps(out,indent=2));print(json.dumps(refusal,indent=2))
