"""Two fixed-prefix Decimal checks only; no producer import or account model."""
from decimal import Decimal as D, getcontext
from pathlib import Path
import hashlib, json
getcontext().prec = 60
O = Path(__file__).resolve().parent
P = O.parent/'paper'
rows = json.loads((P/'NINE_ORIGINAL_PREFIX_ARITHMETIC.json').read_text())
inputs = json.loads((P/'ORIGINAL_NINE_INPUTS.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fee(q, price, side, schedule):
    if not q: return D(0)
    n = D(q)*price
    total = D(0)
    for c in schedule['components']:
        if c.get('side', side) != side: continue
        assert c.get('amount_basis', 'notional') == 'notional'
        assert not c.get('rounding_unit')
        total += max(n*D(c['rate']), D(c.get('minimum_local', '0')))
    return total

out = []
for layer, proposed in [(69, 4500), (2017, 500)]:
    r = next(x for x in rows if x['layer'] == layer)
    x = r['OPEN_check']; inp = next(x for x in inputs if x['layer'] == layer)
    m = D(inp['original_actual_buy']['raw_open'])
    factor = D(inp['original_signal_authorization']['fill_factor'])
    mult = D(x['frozen_sigma_multiplier'])  # Frozen, previously audited scale is an input.
    schedule = x['dated_fee_schedule']; sell_mult = D('.9995')
    buys = {z['raw']['layer']: z['raw'] for z in inp['original_prior_buys']}
    old_R = D(0)
    for z in inp['original_live_layers_after_original_CLOSE_checks']:
        s = z['snapshot']; q = D(s['qty']); b = buys[s['id']]
        unit = D(b['gross_cny'])/D(b['shares'])
        h = D(s['last_core_line'] if s['kind'] == 'core' else s['floor'])/factor
        e = min(m,h)*mult*sell_mult
        old_R += max(q*unit,q*m)-q*e+fee(int(q),e,'sell',schedule)
    before_D = sum((D(z['raw']['fees_cny']) for z in inp['original_prior_buys']),D(0))
    assert not inp['original_prior_sells']  # Both chosen first-change prefixes have fees only.
    new_h = D(inp['original_frozen_intent']['floor'])/factor
    e = min(m,new_h)*mult*sell_mult
    p = m*D('1.0005'); B = D(x['B_fixed'])
    qset = [r['original_qty'], proposed, proposed+x['dated_quantity']['buy_step']]
    qout = []
    names = ['original_new_qty_check','risk_max_check','risk_next_legal_check']
    for q, name in zip(qset,names):
        total = before_D+old_R+fee(q,p,'buy',schedule)+D(q)*(p-e)+fee(q,e,'sell',schedule)
        expected = D(x[name]['total_D_plus_R'])
        assert abs(total-expected)<D('1e-35'),(layer,q,total,expected)
        qout.append({'q':q,'D_plus_R':str(total),'B':str(B),'fits_B':total<=B})
    assert not qout[0]['fits_B'] and qout[1]['fits_B'] and not qout[2]['fits_B']
    out.append({'layer':layer,'old_R_independent':str(old_R),'D_before_independent':str(before_D),'checks':qout})

# One requested post-sale D check: four buy fees and one aggregate sale receipt.
inp = next(x for x in inputs if x['layer']==113)
buy_by_layer={z['raw']['layer']:z['raw'] for z in inp['original_prior_buys']}
G=H=D(0); events=[]
all_events=[(z['book_trade_index'],'buy',z['raw']) for z in inp['original_prior_buys']]
all_events += [(z['book_trade_index'],'sell',z['raw']) for z in inp['original_prior_sells']]
for index,side,t in sorted(all_events):
    if side=='buy': delta=-D(t['fees_cny'])
    else:
        cost=sum((D(part['shares'])*D(buy_by_layer[part['layer']]['gross_cny'])/D(buy_by_layer[part['layer']]['shares']) for part in t['parts']),D(0))
        delta=D(t['gross_cny'])-cost-D(t['fees_cny'])
    G+=delta;H=max(H,G)
    events.append({'trade_index':index,'side':side,'delta_G':str(delta),'G':str(G),'H':str(H)})
assert H-G==D('7118.7240083567000')
result={'status':'PASS_TWO_FIXED_PREFIX_DECIMAL_CHECKS_WITH_LIMITS','two_points':out,
        'yin_after_sale_D':str(H-G),'yin_whole_receipt_updates':events,
        'source_sha256':{str(p):sha(p) for p in [P/'NINE_ORIGINAL_PREFIX_ARITHMETIC.json',P/'ORIGINAL_NINE_INPUTS.json',Path(__file__)]},
        'scope':'69/2017 OPEN original-q, selected-q and next legal unit only; plus Yin prior buy fees and one whole sell receipt. No other seven points or candidate path.',
        'limits':['Frozen sigma multiplier accepted as input; no history/volatility recomputation.', 'Raw OPEN proxy mark domain; IX latest_mark199-205 supports same-day observed OPEN after session begins. Real-market execution remains uncertified.', 'Other sector/pool/cash route gates not rebuilt; no full strategy maximum or performance claimed.'],
        'new_accounts':0,'new_models':0,'new_backtests':0,'new_parameter_searches':0}
(O/'TWO_POINT_DECIMAL_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'two_points':out,'yin_D':str(H-G)},ensure_ascii=False))
