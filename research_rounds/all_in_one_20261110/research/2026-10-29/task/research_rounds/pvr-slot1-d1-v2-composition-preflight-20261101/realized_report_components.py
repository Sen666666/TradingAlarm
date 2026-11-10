"""Narrow saved-four-cell reporting split; not portfolio/account logic."""
from decimal import Decimal as D
from collections import defaultdict

def components(book, original_bridge):
    raw=original_bridge(book)
    assert not raw['open_layers_with_partial_sales'], 'this fixed-report helper requires no partial-sold live layer'
    incl=raw.pop('realized_trading_net')
    strict=sum((D(str(l['cash'])) for l in book['layers'] if not l['qty']),D(0))
    costs=defaultdict(lambda:D(0));gross=defaultdict(lambda:D(0));writeoffs=[]
    for t in book['trades']:
        if t['side']=='buy':
            costs[t['layer']]+=D(str(t['gross_cny']))+D(str(t['fees_cny']))
            gross[t['layer']]+=D(str(t['gross_cny']))
    for l in book['layers']:
        if not l['qty']:continue
        basis=D(l['qty'])*D(str(book['metadata'][str(l['id'])]['unit_cost']))*costs[l['id']]/gross[l['id']]
        nontrade=D(str(l['cash']))+basis
        if abs(nontrade)<=D('.00000001'):continue
        actions=[a for a in book['audit'] if a['kind']=='split_fraction_floor_proxy' and a['sid']==l['sid'] and a['at']>=l['opened']]
        assert len(actions)==1 and nontrade<0,'unexplained nontrade remaining-cost change'
        writeoffs.append(dict(layer=l['id'],sid=l['sid'],known_at=actions[0]['at'],
            fractional_shares_written_off=actions[0]['fractional_shares_written_off'],
            nontrade_realized_cost_writeoff=nontrade,full_buy_cost=costs[l['id']],remaining_basis=basis))
    writeoff=sum((r['nontrade_realized_cost_writeoff'] for r in writeoffs),D(0))
    rounding=incl-strict-writeoff
    assert abs(rounding)<D('.00000001'),'nontrade realized amount unexplained'
    return dict(raw,realized_including_nontrade_writeoffs=incl,
        strict_actual_closed_trade_realized=strict,nontrade_fractional_writeoff=writeoff,
        nontrade_writeoff_rows=writeoffs,rounding_residual_realized_reconciliation=rounding,
        method_scope='fixed saved four-cell books: no partial-sold live layers; closed fractional writeoffs absent as independently audited')
