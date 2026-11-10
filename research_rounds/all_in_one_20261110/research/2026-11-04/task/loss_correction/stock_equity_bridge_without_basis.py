"""Basis-independent saved layer/stock wealth bridge for partial-cost coverage.
Never calls account/runner code. A nontrade/split branch does not prevent this
equity identity, but strict sale PnL and basis-dependent decomposition remain
UNKNOWN until separately audited. No entry/exit counterfactual is inferred.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
import argparse,json,gzip,hashlib
getcontext().prec=80
Z=D(0)
def load(path):
    p=Path(path);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b),hashlib.sha256(b).hexdigest()
def stocks(x):
    a=x['account'];g=defaultdict(lambda:dict(layer_equity=Z,booked_dividend=Z,held_market_value=Z,net_layer_cash=Z,layers=0,qty=0))
    for z in a['layers']:
        v=g[z['sid']];q=z['qty'];mark=D(a['market_marks'][z['sid']]) if q else Z
        v['layers']+=1;v['qty']+=q;v['net_layer_cash']+=D(z['cash']);v['booked_dividend']+=D(z['dividend']);v['held_market_value']+=D(q)*mark;v['layer_equity']+=D(z['cash'])+D(z['dividend'])+D(q)*mark
    assert abs(sum((z['layer_equity'] for z in g.values()),Z)-(D(a['balance']['nav'])-D(1000000)))<D('1e-12')
    return dict(g)
def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--challenger',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output);assert not out.exists();r,rh=load(args.reference);n,nh=load(args.challenger);rs=stocks(r);ns=stocks(n);rows=[]
    for sid in sorted(set(rs)|set(ns)):
        a=rs.get(sid,{});b=ns.get(sid,{});rows.append(dict(sid=sid,reference=a,NO_AR6=b,whole_stock_equity_delta=b.get('layer_equity',Z)-a.get('layer_equity',Z)))
    rows.sort(key=lambda z:z['whole_stock_equity_delta']);delta=sum((z['whole_stock_equity_delta'] for z in rows),Z)
    assert abs(delta-(D(n['account']['balance']['nav'])-D(r['account']['balance']['nav'])))<D('1e-12')
    out.mkdir(parents=True)
    (out/'STOCK_EQUITY_DELTA.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str))
    (out/'COVERAGE.json').write_text(json.dumps(dict(passed=True,NAV_delta=delta,strict_trade_realized_PNL='UNKNOWN_WITHOUT_BASIS_AUDIT',nontrade_writeoff_attribution='UNKNOWN_WITHOUT_BASIS_AUDIT',financial_events=0,account_imports=0,reference_sha256=rh,challenger_sha256=nh,not_an_avoidable_loss_or_trade_deletion_counterfactual=True),ensure_ascii=False,indent=2,default=str))
    print('BASIS_INDEPENDENT_STOCK_EQUITY_DELTA',delta)
if __name__=='__main__':main()
