"""Report-only exact fee attribution; never called by a trading decision."""
from decimal import Decimal as D
from collections import defaultdict
ZERO=D(0)
def reports(b,end):
    s=b.s;records={};journal=[]
    def item(rid):
        if rid not in records:
            records[rid]={k:dict(q=0,cash=ZERO,receivable=ZERO,buy_cash=ZERO,fees=ZERO,dividend_total=ZERO,dividend_paid=ZERO) for k in ('core','add')}
        return records[rid]
    for action in s.actions:
        rid=action['round_id'];row=item(rid);sid=action['sid'];day=s.pd.Timestamp(action['day']);q=int(action['q']);side=action['side']
        op=D(str(s.raw[sid].get(day)['raw_open']));px=op*(1+s.SLIP if side.startswith('buy') else 1-s.SLIP)
        _,fs,par=s.getmeta(sid,day);fee=s.fee(q,px,fs,'buy' if side.startswith('buy') else 'sell',par)
        assert abs(float(px)-action['price'])<1e-10 and abs(float(fee)-action['fee'])<1e-10
        allocations={}
        if side.startswith('buy'):
            kind='core' if side=='buy_core' else 'add';cost=D(q)*px+fee
            row[kind]['q']+=q;row[kind]['cash']-=cost;row[kind]['buy_cash']+=cost;row[kind]['fees']+=fee
            allocations[kind]=dict(q=q,fee=fee,cash_delta=-cost)
        else:
            cq=row['core']['q'] if side=='sell_all' else 0;aq=row['add']['q']
            assert q==cq+aq
            cf=fee*D(cq)/D(q) if cq else ZERO;af=fee-cf
            for kind,n,allocated in [('core',cq,cf),('add',aq,af)]:
                if not n:continue
                row[kind]['q']-=n;delta=D(n)*px-allocated;row[kind]['cash']+=delta;row[kind]['fees']+=allocated
                allocations[kind]=dict(q=n,fee=allocated,cash_delta=delta)
            assert sum((x['fee'] for x in allocations.values()),ZERO)==fee
        journal.append(dict(action_id=action['execution_action_id'],round_id=rid,day=day,side=side,q=q,exact_price=px,exact_whole_order_fee=fee,report_only_allocations=allocations))
    for claim in s.claims.values():
        row=item(claim['owner_round_id']);core=claim['core_amount'];add=claim['amount']-core
        for kind,amount in [('core',core),('add',add)]:
            if claim['recognized']:
                row[kind]['receivable']+=amount;row[kind]['dividend_total']+=amount
            if claim['settled']:
                assert claim['recognized'];row[kind]['cash']+=amount;row[kind]['receivable']-=amount;row[kind]['dividend_paid']+=amount
    rounds=[];layers=[]
    for rid,st in s.archives.items():
        if rid not in records:continue
        row=records[rid];qty=sum(x['q'] for x in row.values());cash=sum(x['cash'] for x in row.values());recv=sum(x['receivable'] for x in row.values())
        assert qty==int(st.get('core',0))+int(st.get('add',0))
        assert abs(cash-st['cash'])<=D('1e-7') and recv==st['receivable']
        # The whole-round source ledger stays authoritative. Attribution arithmetic
        # uses fixed residual recipients without modifying trading state or fees.
        residual_kind='add' if row['add']['buy_cash']>0 else 'core'
        cash_residual=st['cash']-cash
        row[residual_kind]['cash']+=cash_residual
        cash=st['cash'];recv=st['receivable']
        owned_claims=[c for c in s.claims.values() if c['owner_round_id']==rid]
        pending_claim_count=sum(not c['settled'] for c in owned_claims)
        unrecognized_claim_count=sum(not c['recognized'] for c in owned_claims)
        state=b.states.get(st['sid'],{});unknown=state.get('state')=='UNKNOWN' and state.get('round_id')==rid
        status='ASSET_UNKNOWN' if unknown and qty else 'OPEN_CENSORED' if qty else 'EXECUTION_CLOSED_SETTLEMENT_OPEN' if recv or pending_claim_count else 'EXECUTION_AND_SETTLEMENT_CLOSED'
        net=None;liquid_px=None;exitfee=None;alloc_exit={'core':ZERO,'add':ZERO}
        if not qty:net=cash+recv;liquid_px=ZERO;exitfee=ZERO
        elif not unknown:
            z=s.raw[st['sid']].get(end,{})
            if s.finite(z.get('raw_close')) and z['raw_close']>0 and s.lineage(z)==st['origin'] and s.np.isclose(z.get('adjustment_factor'),st['factor'],rtol=1e-11):
                liquid_px=D(str(z['raw_close']))*(1-s.SLIP);_,fs,par=s.getmeta(st['sid'],end);exitfee=s.fee(qty,liquid_px,fs,'sell',par)
                alloc_exit['core']=exitfee*D(row['core']['q'])/D(qty);alloc_exit['add']=exitfee-alloc_exit['core']
                net=cash+recv+D(qty)*liquid_px-exitfee
        base=dict(pending_claim_count=pending_claim_count,unrecognized_claim_count=unrecognized_claim_count,round_id=rid,sid=st['sid'],sector=st['sector'],status=status,terminal_qty=qty,cashflow_including_paid_dividend=cash,
            recognized_unpaid_receivable=recv,paid_dividend=st['dividend_paid'],whole_round_NET80=net,
            whole_round_actual_buy_cash=st['spent'],conditional_return_on_actual_buy_cash=None if net is None else net/st['spent'],
            known_terminal_mark=net is not None,actual_trade_fees=st['fees'],hypothetical_whole_inventory_sell_fee=exitfee,
            entry_day=st['entry_day'],Nd=b.caps[rid],pool=b.pools.get(rid),unknown_reason=state.get('unknown_reason') if unknown else None)
        rounds.append(base);layer_total=ZERO;round_layers=[]
        for kind,values in row.items():
            if values['buy_cash']==0:continue
            layer_claims=[c for c in owned_claims if (c['core_amount'] if kind=='core' else c['amount']-c['core_amount'])>0]
            layer_pending=sum(not c['settled'] for c in layer_claims)
            layer_unrecognized=sum(not c['recognized'] for c in layer_claims)
            layer_status='ASSET_UNKNOWN' if values['q'] and unknown else 'OPEN_CENSORED' if values['q'] else 'EXECUTION_CLOSED_SETTLEMENT_OPEN' if values['receivable'] or layer_pending else 'EXECUTION_AND_SETTLEMENT_CLOSED'
            ln=(values['cash']+values['receivable']) if not values['q'] else None if net is None else values['cash']+values['receivable']+D(values['q'])*liquid_px-alloc_exit[kind]
            if ln is not None:layer_total+=ln
            round_layers.append(dict(round_id=rid,sid=st['sid'],layer=kind,scope='FIRST_PROBE' if kind=='core' else 'UNIQUE_ADD',
                round_status=status,layer_status=layer_status,execution_closed=not values['q'],
                settlement_closed=not layer_pending and values['receivable']==0,
                pending_claim_count=layer_pending,unrecognized_claim_count=layer_unrecognized,
                **values,NET80=ln,return_on_layer_buy_cash=None if ln is None else ln/values['buy_cash'],
                cash_report_arithmetic_residual=cash_residual if kind==residual_kind else ZERO,
                terminal_hypothetical_sell_fee_allocation=alloc_exit[kind] if net is not None else None,
                fee_allocation_policy='Whole fee once; core=fee*core_q/total_q unrounded Decimal; ADD=fee-core; report only'))
        if net is not None:
            target=next(x for x in round_layers if x['layer']==residual_kind)
            delta=net-layer_total
            target['NET80']+=delta;target['NET80_report_arithmetic_residual']=delta
            target['return_on_layer_buy_cash']=target['NET80']/target['buy_cash']
            layer_total=sum(x['NET80'] for x in round_layers)
        layers.extend(round_layers)
        if net is not None:assert abs(layer_total-net)<D('1e-18')
    return dict(rounds=rounds,layers=layers,exact_trade_journal=journal,
        counts=dict(filled_rounds=len(rounds),first_probe_layers=sum(x['layer']=='core' for x in layers),ADD_layers=sum(x['layer']=='add' for x in layers),
                    execution_closed_settlement_open=sum(x['status']=='EXECUTION_CLOSED_SETTLEMENT_OPEN' for x in rounds),open_censored=sum(x['status']=='OPEN_CENSORED' for x in rounds),asset_unknown=sum(x['status']=='ASSET_UNKNOWN' for x in rounds)))
