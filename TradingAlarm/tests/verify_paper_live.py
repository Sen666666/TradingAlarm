"""Verify the local paper feature only; never calls actual-trade write routes."""
import argparse
import json
import time
import urllib.request
from decimal import Decimal as D
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='http://127.0.0.1:8765')
parser.add_argument('--output',required=True)
args=parser.parse_args()

def call(path,payload=None,token=None):
    headers={}
    if token:headers['X-TradingAlarm-Token']=token
    if payload is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(args.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)

config=call('/api/config');before=call('/api/desk/trades')['audit_events']
call('/api/paper/start',{},config['csrf'])
for _ in range(60):
    view=call('/api/paper')
    if view['job']['state'] not in ('queued','running'):break
    time.sleep(.25)
assert view['account']['initial_cash']=='1000000'
assert view['contract']['slippage_bps']==0
assert view['contract']['price']=='next_session_unadjusted_open'
assert len(view['events'])==4,view.get('waiting') or view.get('job')
expected={'002439.SZ':('15.04',9900),'603171.SH':('48.97',3000),'301269.SZ':('111.76',1300),'300017.SZ':('15.15',9900)}
for e in view['events']:
    p=e['payload'];price,shares=expected[p['symbol']]
    assert D(p['price'])==D(price) and p['shares']==shares
    assert e['at']=='2026-10-27T09:30:00+08:00' and p['guide_day']=='2026-10-26'
    assert D(p['fee'])>0
gross=sum(D(e['payload']['price'])*e['payload']['shares'] for e in view['events'])
fees=sum(D(e['payload']['fee']) for e in view['events'])
assert D(view['cash'])==D(1000000)-gross-fees
assert D(view['market_value'])==gross
assert D(view['nav'])==D(1000000)-fees
assert len(view['holdings'])==4
assert len(view['days'])==1 and view['days'][0]['day']=='2026-10-26'
assert view['curve'][-1]['basis']=='开盘，待收盘'
original=view['events']
for _ in range(2):
    call('/api/paper/sync',{},config['csrf'])
    for _ in range(60):
        next_view=call('/api/paper')
        if next_view['job']['state'] not in ('queued','running'):break
        time.sleep(.1)
    assert next_view['events']==original
assert call('/api/desk/trades')['audit_events']==before
result=dict(passed=True,account_initial_cash='1000000',start_decision='2026-10-26',execution_day='2026-10-27',fills=[dict(symbol=e['payload']['symbol'],shares=e['payload']['shares'],price=e['payload']['price'],fee=e['payload']['fee']) for e in original],gross=str(gross),fees=str(fees),cash=view['cash'],nav=view['nav'],holdings=len(view['holdings']),repeated_sync_events_unchanged=True,actual_account_events_unchanged=True,actual_events=len(before),price_basis='raw next-session open; zero slippage',source='retained THS 9602 responses',rest_request_paths=['/api/config','/api/desk/trades','/api/paper/start','/api/paper','/api/paper/sync'])
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
