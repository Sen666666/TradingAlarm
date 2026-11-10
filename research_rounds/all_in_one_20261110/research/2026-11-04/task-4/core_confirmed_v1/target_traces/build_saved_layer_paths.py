"""Actual new H1 semi layers: native buy/hold/exit facts, no valuation engine."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import gzip,hashlib,json,time
O=Path(__file__).resolve().parent;ROOT=O.parent.parent;start=time.monotonic();SHA={}
def bind(p):
 p=Path(p);SHA[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return [json.loads(s)for s in f]if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
run=ROOT/'core_confirmed_v1/funding/runs/strong_ON';assert read(run/'DONE.json')['completed']is True
fixed=read(O/'FIXED_TARGETS.json');ids=set(fixed['semiconductor126']);b=gz(run/'pair/B.json.gz');ds=gz(run/'pair/daily.jsonl.gz',True);dec={r['at'][:10]:r for r in b['decisions']};layers={int(x['id']):x for x in b['layers']};by={str(k):v for k,v in b['metadata'].items()}
buys={int(j['layer']):j for j in b['journal']if j['kind']=='real_buy_fill'and j['sid']in ids and '2026-01-01'<=j['at'][:10]<='2026-06-30'};rows=[]
for lid,j in buys.items():
 l=layers[lid];sid=j['sid'];ep=l.get('epoch');day=j['signal_at'][:10];role=j['role'];intent=next(i for i in dec[day]['intents']if i['sid']==sid and i['role']==role)
 nativebuy=next(t for t in b['trades']if t['side']=='buy'and int(t['layer'])==lid)
 states=[dict(day=r['at'][:10],ACT_on=r['on'],pending_sell=sid in r['pending_sells'],layer_state=z,account_NAV=r['nav'])for r in ds for z in r['layers']if int(z['id'])==lid]
 exits=[a for a in b['audit']if a['kind']=='pilot_layer_exit'and lid in a['layers']]
 sells=[dict(whole_trade=t,own_layer_parts=[p for p in t['parts']if int(p['layer'])==lid])for t in b['trades']if t['side']=='sell'and any(int(p['layer'])==lid for p in t['parts'])]
 related=[t['target_id']for t in fixed['targets25']if t['sid']==sid and t['source_I_epoch']==ep]
 net=D(l['cash'])+D(l['dividend']);closed=int(l['qty'])==0
 rows.append(dict(new_native_layer_id_internal_only=lid,sid=sid,name=fixed['semiconductor126'][sid]['name'],role=role,entry_pool=j['pool'],signal_day=day,source_I_epoch=ep,entry_canonical_receipt=j.get('CP1_id'),native_buy_fill=j,native_buy_trade=nativebuy,new_frozen_intent=intent,
    actual_daily_layer_states=states,actual_exit_proposals=exits,actual_sell_fills=sells,native_end_layer=l,native_end_metadata=by[str(lid)],closed=closed,
    closed_native_cash_plus_dividend_net=str(net)if closed else None,open_cash_plus_dividend_balance_not_profit=None if closed else str(net),
    original_target_keys_same_stock_source_I=related,scope='New account own layer facts; no old layer ID join. Closed net includes native accrued dividend entitlement, not all free cash. Open valuation/PnL deferred to root native-price finance reader. CORE stored floor is not a direct stop; last_core_line mirrors I, ACT/I exits remain original.'))
assert len(rows)==18
save('NEW_H1_SEMICONDUCTOR_LAYER_PATHS.json',rows)
save('NEW_LAYER_PATH_SUMMARY.json',dict(layers=len(rows),stocks=len({r['sid']for r in rows}),roles=dict(Counter(r['role']for r in rows)),closed_layers=sum(r['closed']for r in rows),open_layers=sum(not r['closed']for r in rows),cross_account_layer_ID_matching=False,seconds=time.monotonic()-start,new_Account=0,new_Market=0,new_RiskBook=0,new_marks=0))
bind(__file__);save('LAYER_PATH_SOURCE_SHA256.json',SHA);print(json.dumps(read(O/'NEW_LAYER_PATH_SUMMARY.json'),ensure_ascii=False))
