from pathlib import Path
from decimal import Decimal as D
import json,collections,hashlib
import engine_v2 as E
HERE=Path(__file__).resolve().parent
OUT=HERE/'bounded_attempt_02'
def load(name):return json.loads((OUT/name).read_text())
def save(name,v):
    with (HERE/name).open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,default=str);f.write('\n')
def main():
    s=E.bridge.load_original('2022')
    actions=load('ACTIONS.json');audit=load('AUDIT.json');archives=load('ROUND_ARCHIVES.json');nds=load('ROUND_ND.json')
    for sid in {a['sid'] for a in actions}:s.load(sid)
    reports=[];qty=collections.defaultdict(int);pools={};cash=D('1200000');cursor=0
    opens=load('OPEN_PHASES.json')
    for phase in opens:
        day=s.pd.Timestamp(phase['day']);previous=s.cal[s.cal<day][-1]
        for a in [x for x in actions if s.pd.Timestamp(x['day'])==day]:
            q=int(a['q']);rid=a['round_id'];qty[rid]+=q if a['side'].startswith('buy') else -q
            amount=D(q)*D(str(a['price']));fee=D(str(a['fee']))
            cash+=-amount-fee if a['side'].startswith('buy') else amount-fee
            pools.setdefault(rid,'probe')
        for a in audit:
            if a['type']=='PROMOTED' and s.pd.Timestamp(a['day'])<=day:pools[a['round_id']]='confirmed'
        rows=[]
        for rid,q in qty.items():
            if not q:continue
            st=archives[rid];sid=st['sid'];op=D(str(s.raw[sid].get(day)['raw_open']))
            fl=D(str(s.facts[sid].get(previous)['i_floor']))/D(str(s.raw[sid].get(day)['adjustment_factor']))
            rows.append(dict(sid=sid,round_id=rid,pool=pools[rid],sector=st['sector'],q=q,raw_OPEN=op,
                original_previous_I_floor_raw=fl,gross=D(q)*op,nominal_line_risk=D(q)*max(D(0),op-fl),round_Nd=nds[rid]))
        rc=phase['reconciliation'];gross=sum(x['gross'] for x in rows)
        assert gross==D(rc['gross_inventory']) and abs(cash-D(rc['cash']))<=D('1e-7')
        assert D(rc['NAV'])==D(rc['cash'])+gross+D(rc['receivable'])
        nav=D(rc['NAV'])
        aggregates={}
        for pool in ('probe','confirmed'):
            part=[x for x in rows if x['pool']==pool]
            aggregates[pool]=dict(gross=sum((x['gross'] for x in part),D(0)),nominal_line_risk=sum((x['nominal_line_risk'] for x in part),D(0)))
        sectors={}
        for sector in sorted({x['sector'] for x in rows}):
            part=[x for x in rows if x['sector']==sector]
            sectors[sector]=dict(ALL_gross=sum(x['gross'] for x in part),ALL_nominal_risk=sum(x['nominal_line_risk'] for x in part),
                next_probe_cap_reference=nav*D('.02'),next_confirmed_cap_reference=nav*D('.10'),risk_reference=nav*D('.01'))
        order_events=[x for x in audit if s.pd.Timestamp(x['day'])==day]
        marker=next(i for i,x in enumerate(order_events) if x['type']=='ALL_RESERVATIONS_COMPLETE')
        assert all(i<marker for i,x in enumerate(order_events) if x['type']=='RESERVED')
        assert all(i>marker for i,x in enumerate(order_events) if x['type']=='CONDITIONAL_FILLED')
        reports.append(dict(day=day,cash_from_exported_action_floats=cash,actual_decimal_cash=rc['cash'],cash_tolerance='1e-7',
            gross_inventory=gross,receivable=rc['receivable'],NAV=nav,holdings=rows,pools=aggregates,industries=sectors,
            reserve_ALL_before_fill_ALL=True,live_orders_after_fills=rc['live_orders'],
            note='Post-fill raw-OPEN marking, not a claim that passive appreciation forces liquidation. Admission used pending-fee-adjusted pre-fill NAV separately.'))
    save('POST_FILL_POOL_RISK_AUDIT.json',reports)
    proof=next(x for x in audit if x['type']=='PROMOTION_PROOF')
    st=archives[proof['round_id']];sid=st['sid'];day=s.pd.Timestamp(proof['day']);previous=s.cal[s.cal<day][-1]
    op=D(str(s.raw[sid].get(day)['raw_open']));px=op*(1+s.SLIP);q=int(st['core'])
    pf=D(str(s.facts[sid].get(previous)['i_floor']))/D(str(st['fac']))
    qr,fs,par=s.getmeta(sid,day);exitfee=s.fee(q,pf*(1-s.SLIP),fs,'sell',par)
    initialfee=D(st['initial_fee']);price_component=D(q)*(px-pf*(1-s.SLIP))
    existing=max(D(0),price_component+initialfee+exitfee);riskcap=D(nds[proof['round_id']])*D('.0025');remaining=max(D(0),riskcap-existing)
    budget=min(D(nds[proof['round_id']])*D('.02'),max(D(0),D(nds[proof['round_id']])*D('.04')-D(q)*op))
    aq,af,ar,_,_=s.size(sid,day,px,D(proof['proof']['effective_floor']),budget,remaining,int(s.capacity[sid][previous]))
    assert aq==0 and remaining==0 and st['added']==False
    save('REAL_PROMOTION_NO_ADD_DIAGNOSTIC.json',dict(sid=sid,day=day,round_id=proof['round_id'],source='Exact original ADD preparation formula, post-run read-only reconstruction',
        first_fill=proof['proof']['first_fill_day'],fresh_CP=proof['proof']['signal_day'],CLOSE_net=proof['proof']['close_net'],OPEN_net=proof['proof']['open_net'],
        effective_ADD_floor=proof['proof']['effective_floor'],OPEN=op,buy_reference_price=px,core_q=q,
        previous_I_floor_raw=pf,core_price_risk=price_component,initial_buy_fee=initialfee,whole_core_stop_sell_fee=exitfee,
        existing_fee_risk=existing,frozen_round_fee_risk_cap=riskcap,remaining_fee_risk=remaining,
        ADD_buy_budget=budget,original_size_q=aq,reason='ORIGINAL_AB_REMAINING_ROUND_RISK_ZERO_NOT_SHARED_CASH_OR_PROOF_FAILURE',
        real_promotion=True,real_conditional_ADD_fill=False))
    save('FINALIZATION_SOURCE_HASHES.json',s.hashes)
if __name__=='__main__':main()
