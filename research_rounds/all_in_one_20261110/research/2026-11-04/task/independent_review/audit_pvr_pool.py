"""Independent read-only audit; Arrow rows, original ledgers and explicit arithmetic.

No native engine imports, market refresh, projection, account events or price labels.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json, gzip, hashlib
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
NOW=HERE.parent/'participation/PVR_SEMICONDUCTOR_CHAIN'
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PVR=OLD/'pvr-slot1-native-readiness-20261101'
RULE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
SHA={}
def read(p,lines=False):
    p=Path(p);raw=p.read_bytes();SHA[str(p)]=hashlib.sha256(raw).hexdigest()
    raw=gzip.decompress(raw) if p.suffix=='.gz' else raw
    return [json.loads(z) for z in raw.splitlines()] if lines else json.loads(raw)
def version(rows,day):
    vv=[r for r in rows if r['from']<=day and (r['to'] is None or day<r['to'])]
    assert len(vv)==1,(day,vv)
    return vv[0]
def serial(z):return json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n'

funnel=read(PVR/'semiconductor-2026H1-readonly/SEMICONDUCTOR_OPPORTUNITY_FUNNEL.json')['all_receipts']
book=read(PVR/'runs/2025_26/pair/B.json.gz')
days={r['at'][:10]:r for r in read(PVR/'runs/2025_26/pair/daily.jsonl.gz',True)}
sector={r['day']:r for r in read(PVR/'semiconductor-2026H1-readonly/DAILY_ALIGNED_CAPITAL.json') if r['sector']=='URFI881121'}
intents={(r['at'][:10],i['sid'],i['role']):i for r in book['decisions'] for i in r['intents']}
manifest={r['symbol']:r for r in read(OLD/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
rules=read(RULE);frames={}
def facts(sid,day):
    if sid not in frames:
        p=Path(manifest[sid]['refs']['facts']);raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
        SHA[str(p)]=h;assert h==manifest[sid]['output_sha256'][str(p)]
        frames[sid]={r['date'].date().isoformat():(D(str(r['raw_close'])),D(str(r['factor']))) for r in pq.read_table(p,columns=['date','raw_close','factor']).to_pylist()}
    return frames[sid][day]

rejected=[r for r in funnel if r['category']=='opening_rejected_raw_merged_constraints']
assert len(rejected)==537
records=read(NOW/'MINIMUM_SCREEN_ALL537.json')
saved={(r['signal_day'],r['sid']):r for r in records}
assert len(saved)==len(records)==537
failcounts=Counter();nonnumeric=Counter();exclusive=set();passed=set();checked=0
for r in rejected:
    d,sid=r['signal_day'],r['sid'];s=days[d];sec=sector[d];i=intents[d,sid,'mobile'];raw,factor=facts(sid,d)
    assert D(s['order_reserved'])==0
    nav=D(s['nav']);qty=D(version(rules['quantity_versions'][sid],d)['rule']['buy_minimum'])
    price=raw*D('1.0005');floor=D(i['floor'])/factor;gross=qty*price
    venue=version(rules['venue_versions'][sid],d)['venue'];schedule=version(rules['fee_versions'][venue],d)['schedule']
    fee=sum((max((qty if c.get('amount_basis')=='par_value' else gross)*D(c['rate']),D(c.get('minimum_local',0))) for c in schedule['components'] if c.get('side','buy')!='sell'),D(0))
    postnav=nav-fee;newrisk=qty*max(D(0),price-floor)
    margins={
        'open_at_or_below_protection_at_close_proxy':raw-floor,
        'frozen_contract_minimum':min(D(i['cap'])-qty,D(i['budget'])-gross),
        'cash_original_reserve':D(s['available'])-nav*D('.1')-gross-fee,
        'confirmed60':D('.6')*postnav-D(str(s['pool_confirmed'][0]))-gross,
        'sector_stage_capital':({'confirmed':D('.1'),'expanded':D('.2')}[sec['industry_stage']])*postnav-D(sec['industry_capital'])-gross,
        'sector_risk1':D('.01')*postnav-D(sec['industry_nominal_risk'])-newrisk,
        'stock10':nav*D('.1')-D(s['positions'].get(sid,0))*raw-gross,
    }
    failed=[k for k,v in margins.items() if v<0 or (k=='open_at_or_below_protection_at_close_proxy' and v==0)]
    z=saved[d,sid];assert failed==z['numeric_confirmed_route_failures'],(d,sid,failed,z)
    for k,v in [('minimum_quantity',qty),('proxy_price',price),('actual_intent_floor_raw',floor),('minimum_gross',gross),('buy_fee',fee),('new_nominal_risk',newrisk),('NAV',nav)]:assert D(z[k])==v,(k,z[k],v)
    others=[k for k in failed if k!='confirmed60'];assert others==z['other_numeric_failures_after_omit_confirmed60']
    failcounts[','.join(failed) or 'none']+=1
    nonnumeric[','.join(others) or 'none']+=1
    if not others:passed.add((d,sid))
    if failed==['confirmed60']:exclusive.add((d,sid))
    checked+=len(margins)
assert sum(failcounts.values())==537 and len(passed)==536 and len(exclusive)==513

# Original no_nominal_gap logs: independent dated minimum and actual close holdings.
small=[r for r in funnel if r['category']=='not_planned_original_target_or_sizing']
assert len(small)==257
for r in small:
    d,sid=r['signal_day'],r['sid'];raw,_=facts(sid,d);nav=D(days[d]['nav'])
    budget=min(nav*D('.02'),max(D(0),nav*D('.1')-D(days[d]['positions'].get(sid,0))*raw))
    minimum=D(version(rules['quantity_versions'][sid],d)['rule']['buy_minimum'])*raw
    assert 0<budget<minimum,(d,sid,budget,minimum)

out=dict(status='PASS_WITH_SCOPE',all537_numeric_checks=checked,
    original_confirmed_route_close_fail_combinations=dict(failcounts),
    after_omit60=dict(nonnumeric),minimum537_complete=True,
    other_numeric_passes=len(passed),only_confirmed60_close_fail=len(exclusive),
    distinct_stocks_pass=len({s for _,s in passed}),
    original257_all_positive_budget_below_dated_minimum=True,
    no_actual_open_or_serial_projection=True,no_executable_unlock_count=True,
    routing='probe always; successful whole-current-attempt migration admits confirmed as an additional route; max legal quantity, probe wins tie; raw failure tag union is not exclusive cause',
    three_same_contract_enforcers=['route.allowed confirmed60','budget.request confirmed60','budget.migrate confirmed60'],
    account_events=0,source_sha256=SHA)
(HERE/'PVR_POOL_LOGIC_AUDIT.json').write_text(serial(out))
print(serial({k:v for k,v in out.items() if k!='source_sha256'}))
