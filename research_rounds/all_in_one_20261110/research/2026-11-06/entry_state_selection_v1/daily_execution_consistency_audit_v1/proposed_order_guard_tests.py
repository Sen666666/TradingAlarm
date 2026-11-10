"""Isolated proposal/tests only. Never imported by, or connected to, the sealed engine.
No trading calls, no account replay, no day HIGH/LOW/CLOSE/volume inputs.
Opening price must already be officially observed; order starts after 09:30.
This is not a retrospective auction fill, nor historical execution certification.
"""
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR
from datetime import datetime
import json,pathlib,copy,hashlib
OUT=pathlib.Path(__file__).parent

def quote_order(side, observed_open, asof_inputs, now, contract):
    required=['tick','daily_lower','daily_upper','current_quote_lower','current_quote_upper']
    if side not in ['buy','sell']: return {'status':'UNKNOWN_SIDE'}
    if any(k not in asof_inputs for k in required) or observed_open is None:return {'status':'UNKNOWN_INPUT'}
    if now.time().isoformat()<'09:30:00':return {'status':'UNKNOWN_NOT_POST_OPEN_SUBMISSION'}
    if not contract.get('dated_rule_verified') or not contract.get('normal_finite_limit_session'):return {'status':'UNKNOWN_DATED_RULE_OR_SPECIAL_SESSION'}
    for item in [observed_open]+[asof_inputs[k] for k in required]:
        if not item.get('source') or not item.get('known_at') or datetime.fromisoformat(item['known_at'])>now:return {'status':'UNKNOWN_ASOF_INPUT'}
    op=D(observed_open['value']);tick=D(asof_inputs['tick']['value'])
    lo=max(D(asof_inputs['daily_lower']['value']),D(asof_inputs['current_quote_lower']['value']))
    hi=min(D(asof_inputs['daily_upper']['value']),D(asof_inputs['current_quote_upper']['value']))
    if tick<=0 or lo<=0 or hi<lo or not lo<=op<=hi:return {'status':'UNKNOWN_PRICE_ENVELOPE'}
    target=op*(D('1.0005') if side=='buy' else D('.9995'))
    p=(target/tick).to_integral_value(rounding=ROUND_CEILING if side=='buy' else ROUND_FLOOR)*tick
    p=min(max(p,lo),hi)
    if p%tick:return {'status':'UNKNOWN_INVALID_BOUND_TICK'}
    return {'status':'LEGAL_LIMIT_INTENT_ONLY','limit_price':str(p),'side':side,'known_at':now.isoformat(),'position_change':0,'fill_status':'UNKNOWN_NO_RECEIPT','note':'Clamp legal order limit, never clamp or create a fill. Quantity/reservation must be recalculated using this price and dated fees/lots before transmission.'}

def check_fill(intent,receipt,qmax,tick,lo,hi):
    if not receipt:return 'UNKNOWN_NO_RECEIPT'
    if not receipt.get('verified_exchange_execution_id'):return 'UNKNOWN_UNVERIFIED_RECEIPT'
    if intent['status']!='LEGAL_LIMIT_INTENT_ONLY':return 'REJECT_NO_VALID_ORDER'
    if datetime.fromisoformat(receipt['time'])<datetime.fromisoformat(intent['known_at']):return 'REJECT_RETROACTIVE_FILL'
    q=receipt['qty'];p=D(receipt['price'])
    if not isinstance(q,int) or q<=0 or q>qmax:return 'REJECT_FILL_QUANTITY'
    if p%D(tick) or not D(lo)<=p<=D(hi):return 'REJECT_FILL_PRICE'
    if (intent['side']=='buy' and p>D(intent['limit_price'])) or (intent['side']=='sell' and p<D(intent['limit_price'])):return 'REJECT_ORDER_LIMIT'
    return 'RECEIPT_VALID_IN_FIXTURE_ONLY'

now=datetime.fromisoformat('2024-09-25T09:30:01+08:00')
def item(v):return {'value':str(v),'source':'SYNTHETIC_FIXTURE_ONLY','known_at':'2024-09-25T09:25:01+08:00'}
x={k:item(v) for k,v in dict(tick='.01',daily_lower='12.66',daily_upper='18.98',current_quote_lower='18.60',current_quote_upper='18.98').items()};op=item('18.98');c={'dated_rule_verified':True,'normal_finite_limit_session':True};out=[]
def test(name,expr):assert expr,name;out.append(name)
a=quote_order('buy',op,x,now,c);test('synthetic_upper_open_quotes_18_98_but_never_fills',a['limit_price']=='18.98' and a['position_change']==0 and a['fill_status']=='UNKNOWN_NO_RECEIPT')
test('missing_limit_unknown',quote_order('buy',op,{k:v for k,v in x.items() if k!='daily_upper'},now,c)['status']=='UNKNOWN_INPUT')
y=copy.deepcopy(x);y['daily_upper']['known_at']='2024-09-25T15:00:01+08:00';test('future_limit_known_at_rejected',quote_order('buy',op,y,now,c)['status']=='UNKNOWN_ASOF_INPUT')
test('no_retroactive_auction_order',quote_order('buy',op,x,datetime.fromisoformat('2024-09-25T09:24:00+08:00'),c)['status']=='UNKNOWN_NOT_POST_OPEN_SUBMISSION')
test('special_ipo_or_relist_unknown',quote_order('buy',op,x,now,{**c,'normal_finite_limit_session':False})['status']=='UNKNOWN_DATED_RULE_OR_SPECIAL_SESSION')
test('no_receipt_never_books',check_fill(a,None,300,'.01','12.66','18.98')=='UNKNOWN_NO_RECEIPT')
r={'verified_exchange_execution_id':'SYNTHETIC_ID','time':'2024-09-25T09:30:02+08:00','qty':300,'price':'18.98949'}
test('old_yin_proxy_not_legal_execution_price',check_fill(a,r,300,'.01','12.66','18.98')=='REJECT_FILL_PRICE')
r2={**r,'price':'18.98'};test('synthetic_receipt_not_a_real_fill_claim',check_fill(a,r2,300,'.01','12.66','18.98')=='RECEIPT_VALID_IN_FIXTURE_ONLY')
test('receipt_before_order_rejected',check_fill(a,{**r2,'time':'2024-09-25T09:25:00+08:00'},300,'.01','12.66','18.98')=='REJECT_RETROACTIVE_FILL')
x2={k:item(v) for k,v in dict(tick='.01',daily_lower='10.00',daily_upper='12.00',current_quote_lower='10.00',current_quote_upper='10.20').items()};b=quote_order('sell',item('10.00'),x2,now,c);test('lower_limit_sell_intent_only',b['limit_price']=='10.00' and b['fill_status']=='UNKNOWN_NO_RECEIPT')
# Future full-day fields are outside the API and cannot enter the permission decision.
for future in [{'high':18.98,'low':18.98,'close':18.98,'volume':0},{'high':19,'low':1,'close':5,'volume':10**10}]:
    ignored=copy.deepcopy(x);ignored.update(future)
    test('future_HLCV_invariance_'+str(len(out)),quote_order('buy',op,ignored,now,c)==a)
result={'status':'PROPOSAL_SYNTHETIC_TESTS_ONLY_NOT_ENGINE_IMPLEMENTED','tests':len(out),'passed':out,'fixture_upper_intent':a,'real_case_inputs_not_certified':True,'historical_orders_or_accounts_run':0}
(OUT/'PROPOSED_GUARD_TEST_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
