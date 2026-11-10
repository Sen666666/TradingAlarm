"""Latest owner revision: provider-only confirmation, no account construction."""
from datetime import datetime
from pathlib import Path
import hashlib
import json
import sys
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'code'))
import current_pool_bridge as bridge
from current_fixed_pool import PoolLine
from history_runner import FrozenMarket, validate_calendar
from market_rules import RuleUnavailable
from sector_account import FXQuote, dec, FeeSchedule, FeeComponent
import pandas as pd

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files={n:ROOT/'code'/n for n in ['history_runner.py','sector_account.py','market_rules.py','current_pool_bridge.py']}
before={n:sha(p) for n,p in files.items()}
at=lambda d:datetime.fromisoformat(d).replace(tzinfo=bridge.TZ)
version=lambda **kwargs:dict({'from':'2013-01-01','to':None,'source_id':'isolated-review','basis':'explicit_research_proxy','proxy_id':'review'},**kwargs)
m=object.__new__(FrozenMarket)
m.lines={sid:PoolLine(sid,'A',None,None,None,True) for sid in ['USHA600000','USZA000001','USTM920000']}
m.protocol={'approved_proxy_ids':['review']}
m.rules={'venue_versions':{s:[version(venue=v)] for s,v in zip(m.lines,['SSE_MAIN','SZSE_MAIN','BSE'])},'fee_versions':{v:[version(schedule={'schedule_id':v,'components':[{'name':'handling','rate':r,'basis':'fill'}]})] for v,r in [('SSE_MAIN','0.0000341'),('SZSE_MAIN','0.0000341'),('BSE','0.000125')]}}
fees={s:str(sum(m.fees(s,at('2026-10-22T09:30')).incremental('buy',dec(100000),{},{},1).values())) for s in m.lines}
assert dec(fees['USTM920000'])==dec('12.5') and dec(fees['USHA600000'])==dec('3.41')
sid='UHKMHK0001'
m.lines={sid:PoolLine(sid,'H',None,None,None,True,True)}
m.bundle=SimpleNamespace(series={sid:SimpleNamespace(record={'unavailable_from':'2015-05-27'})})
m.sessions={'H':[at('2015-05-27T09:30')]}
m.notices=[];m._notice_keys={}
assert m.window(sid,at('2015-05-27T09:30'),'sell',1) is None
try:
    m.latest_mark(sid,at('2015-05-27T17:00'))
    raise AssertionError('mark must reject known unavailable stock')
except RuleUnavailable as exc:
    source_rejection=str(exc)
m.sessions={'A':[at('2026-10-21T09:30'),at('2026-10-22T09:30')]}
lag_before_open=m.lag('A',at('2026-10-21T00:00'),1)
lag_at_open=m.lag('A',at('2026-10-21T09:30'),1)
assert lag_before_open==lag_at_open==at('2026-10-22T09:30')
try:
    validate_calendar([],{'A':[at('2026-10-21T09:30'),at('2026-10-21T13:00')]})
    raise AssertionError('duplicate local date must fail')
except ValueError as exc:
    calendar_rejection=str(exc)
try:
    FXQuote(dec('.9'),at('2026-10-22T17:00'),'probe').read(at('2026-10-22T09:30'))
    raise AssertionError('future FX must fail')
except ValueError as exc:
    future_fx_rejection=str(exc)
fee=FeeSchedule('read-only-known-terms',(FeeComponent('stamp',dec('.001'),basis='fill',rounding_unit=dec(1),rounding_mode='ceil'),FeeComponent('old_settlement',dec('.00002'),minimum_local=dec(2),maximum_local=dec(100),basis='fill')))
assert fee.incremental('buy',dec('1000.01'),{},{},1)=={'stamp':dec(2),'old_settlement':dec(2)}
assert fee.incremental('buy',dec('10000000'),{},{},1)['old_settlement']==dec(100)
after={n:sha(p) for n,p in files.items()};assert before==after
result=dict(status='pass',account_runs=0,synthetic_account_runs=0,algorithm_runs=0,network_requests=0,code_sha256=after,
    fee_100k_by_actual_pilot_identity=fees,source_unavailable_mark_rejection=source_rejection,
    before_open_lag1=str(lag_before_open),at_open_lag1=str(lag_at_open),calendar_rejection=calendar_rejection,future_fx_rejection=future_fx_rejection,
    fee_rounding_minimum_maximum='pass',real_sample_receipt='findings.json',
    scope='Provider and pure arithmetic only; not historical account or complete ledger certification.')
with (OUT/'final-check.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'status':'pass','account_runs':0,'runner_sha256':after['history_runner.py']}))
