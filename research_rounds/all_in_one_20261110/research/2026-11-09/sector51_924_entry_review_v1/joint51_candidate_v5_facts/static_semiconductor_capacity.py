"""Single OPEN capital-dimension check. No return path or parameter selection."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,sys
import pandas as pd
sys.dont_write_bytecode=True
from engine import Data,Engine,B,U,SLIP,sha,save
O=Path(__file__).resolve().parent;R=O/'full_20241031_once';read=lambda p:json.loads(p.read_text());dt=pd.Timestamp('2024-09-27');ledger=read(R/'DAY_LEDGER.json');prev=next(x for x in ledger if x['day']=='2024-09-26');hold=[h for h in read(R/'HOLDINGS.json') if h['day']=='2024-09-26'];orders=read(R/'ORDERS.json');assert not [x for x in orders if x['day']=='2024-09-27'];ro=pd.read_csv(O/'CLASSIFICATION_ALL1709.csv');sm=ro.set_index('symbol').sector51.to_dict();names=ro.set_index('symbol').name.to_dict();pending=[x for x in read(O/'replay_20240926/PENDING_AT_END.json') if sm[x['sid']]=='半导体'];assert len(pending)==81 and not [h for h in hold if sm[h['sid']]=='半导体'];manifest={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')};raw={};sources={}
for s in {h['sid'] for h in hold}|{p['sid'] for p in pending}:
 p=Path(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet')));sources[str(p)]=sha(p);assert sources[str(p)]==manifest[s]['source_sha256'][str(p)];raw[s]=pd.read_parquet(p).loc[dt]
receivable=D(prev['receivable'])+sum((D(x['receivable_delta']) for x in read(R/'EQUITY_EVENTS.json') if x['day']=='2024-09-27' and x['event']=='ACCRUE_NET80'),D(0));pre_nav=D(prev['cash'])+receivable+sum((h['qty']*D(str(raw[h['sid']].raw_open)) for h in hold),D(0))
data=Data.__new__(Data);data.rules=read(B/'inputs-v2/market-rules.json');data.proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];data.meta={};data.names=names;data.sid_sector=sm;data.z=lambda s,d:raw[s]
minimum=[]
for r in pending:
 for k in ['budget','ifloor','factor','nav0']:r[k]=D(r[k])
 r['origin']=tuple(r['origin']);s=r['sid'];q=data.getmeta(s,dt)[0].buy_minimum;p=D(str(raw[s].raw_open))*(1+SLIP);fee=data.fee(s,dt,q,p,'buy');minimum.append(dict(sid=s,name=names[s],dated_minimum_qty=q,raw_OPEN=str(raw[s].raw_open),proxy_buy_price=str(p),fee=str(fee),minimum_all_in_cash=str(q*p+fee),frozen_attempt_budget=str(r['budget'])))
# Reuse the frozen allocator itself. Only cash availability is neutralized;
# actual OPEN NAV is held fixed, and there is no pre-existing semiconductor position.
engine=Engine(data);engine.cash=D('1000000000');engine.nav=lambda d,field:pre_nav;engine.alloc_open(dt,pending)
mm={x['sid']:x for x in minimum};rows=[dict(mm[c['sid']],**c) for c in engine.candidates];pd.DataFrame(rows).to_csv(O/'SEP27_SEMICONDUCTOR_STATIC_CASH_RELAXED.csv',index=False)
spent=sum((D(x['all_in_cost']) for x in engine.orders),D(0));needed=sum((D(x['minimum_all_in_cash']) for x in minimum),D(0));cap=D('.10')*pre_nav
summary=dict(scope='SINGLE_OPEN_STATIC_CAPITAL_DIMENSION_NOT_A_RETURN_PATH',date='2024-09-27',planned_SEEDs=81,actual_OPEN_NAV_after_exits=str(pre_nav),actual_cash_after_exits=prev['cash'],actual_cash_reserve_buy_budget=str(max(D(0),D(prev['cash'])-D('.10')*pre_nav)),all81_minimum_all_in_cash=str(needed),all81_as_pct_actual_OPEN_NAV=str(100*needed/pre_nav),semiconductor_existing_exposure='0',industry_10pct_slot=str(cap),all81_cash_to_industry_slot_ratio=str(needed/cap),cash_only_relaxation=dict(OPEN_NAV_unchanged=True,industry_cap_unchanged=True,attempt_budget_unchanged=True,stock_cap_unchanged=True,legal_lot_capacity_and_protection_unchanged=True,frozen_order_unchanged=True,filled_SEED_count=len(engine.orders),actual_all_in_cash=str(spent),industry_slot_remaining=str(cap-spent),decisions=dict(Counter(x['decision'] for x in engine.candidates)),filled_symbols=[x['sid'] for x in engine.orders],maximum_cardinality_or_best_stock_selection_not_claimed=True),no_future_prices_or_returns=True,no_new_strategy_run=True)
save(O/'SEP27_SEMICONDUCTOR_STATIC_CAPACITY.json',summary);save(O/'STATIC_CAPACITY_SOURCE_HASHES.json',{**sources,str(O/'engine.py'):sha(O/'engine.py'),str(Path(__file__)):sha(Path(__file__))});print(json.dumps(summary,ensure_ascii=False))
