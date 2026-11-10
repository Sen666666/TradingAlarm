"""Pure post-processing of existing records and frozen source fee/size definitions.
Never calls run_window, entry_open, held_open, close_phase, or open_phase.
"""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace
import sys,json,hashlib,collections,time,traceback,gc
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'indexed_execution_v1'
sys.path.insert(0,str(HERE.parent/'source_bridge_v1'))
import bridge
ZERO=D(0)
def save(path,x):
    with path.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def mean(x):return sum(x,ZERO)/D(len(x)) if x else None
def read(d,n):return json.loads((d/(n+'.json')).read_text())
def ratio(n,d):return D(n)/D(d) if d else None
def quantities_before_proof(journal,rid,day,pd):
    q={'core':0,'add':0}
    for a in journal:
        if a['round_id']!=rid:continue
        ad=pd.Timestamp(a['day'])
        if ad>day or ad==day and a['side'].startswith('buy'):continue
        side=a['side'];n=int(a['q'])
        if side=='buy_core':q['core']+=n
        elif side=='buy_add':q['add']+=n
        elif side=='sell_add':q['add']-=n
        else:assert n==q['core']+q['add'];q={'core':0,'add':0}
    return q
def add_diagnostics(s,d,archive,journal,audit,nd):
    rows=[];proofs=[a for a in audit if a['type']=='PROMOTION_PROOF'];byorder={(a['round_id'],a['day']):a for a in audit if a['type'] in ('RESERVED','BUDGET_REJECTED') and a['kind']=='ADD'}
    for a in proofs:
        if a['reason']!='eligible':continue
        rid=a['round_id'];st=archive[rid];sid=st['sid'];day=s.pd.Timestamp(a['day']);prev=s.cal[s.cal<day][-1];s.load(sid)
        q=quantities_before_proof(journal,rid,day,s.pd)
        op=D(str(s.raw[sid].get(day)['raw_open']));px=op*(1+s.SLIP);fac=D(str(s.raw[sid].get(day)['adjustment_factor']))
        pf=s.facts[sid].get(prev,{}).get('i_floor');cap=s.capacity[sid].get(prev)
        row=dict(round_id=rid,event_id=st['event_id'],sid=sid,day=day,CP_id=a['proof']['cp']['consumption_id'],common_snapshot_certified=a['nav_certified'],core_q=q['core'],add_q=q['add'],Nd=nd[rid])
        if not s.finite(pf) or not s.finite(cap):
            row.update(source_prepare_unknown=True,reason='PREVIOUS_FLOOR_OR_CAPACITY_UNKNOWN');rows.append(row);continue
        pf=D(str(pf))/fac;round_nd=D(nd[rid]);qr,fs,par=s.getmeta(sid,day)
        slot=max(ZERO,round_nd*D('.04')-D(q['core']+q['add'])*op);budget=min(round_nd*D('.02'),slot)
        existing=max(ZERO,D(q['core'])*(px-pf*(1-s.SLIP))+D(st['initial_fee'])+s.fee(q['core'],pf*(1-s.SLIP),fs,'sell',par))
        remaining=max(ZERO,round_nd*D('.0025')-existing);floor=D(a['proof']['effective_floor'])
        source_q,buyfee,planrisk,_,_=s.size(sid,day,px,floor,budget,remaining,int(cap))
        order=byorder.get((rid,a['day']))
        if order is not None:assert source_q==int(order['original_formula_q'])
        else:assert source_q==0
        last_reasons=order['trials'][-1]['reasons'] if order is not None and order['trials'] else []
        shared_q=int(order['shared_q']) if order is not None else 0
        row.update(source_prepare_unknown=False,original_I_floor_raw=pf,OPEN=op,buy_reference=px,effective_ADD_floor=floor,
            slot_available=slot,ADD_buy_budget=budget,existing_fee_risk=existing,remaining_fee_risk=remaining,
            zero_remaining_risk=remaining==0,zero_slot=slot==0,source_q=source_q,shared_q=shared_q,
            shared_positive_q_rejected=source_q>0 and shared_q==0,
            shared_rejection_is_NAV_unknown=source_q>0 and shared_q==0 and 'NAV_OR_ASSET_UNKNOWN' in last_reasons,
            shared_positive_q_shrunk=shared_q>0 and shared_q<source_q,
            final_minimum_q_reasons=last_reasons,source_minimum_quantity=qr.buy_minimum,
            prior_quantity_capacity=int(cap),order_type=None if order is None else order['type'])
        rows.append(row)
    valid=[r for r in rows if not r['source_prepare_unknown']]
    n=len(rows);origpositive=[r for r in valid if r['source_q']>0]
    flags=['zero_remaining_risk','zero_slot','shared_positive_q_rejected','shared_rejection_is_NAV_unknown','shared_positive_q_shrunk']
    summary=dict(pending_CLOSE_CP_attempts=len(proofs),OPEN_proof_reasons=dict(collections.Counter(a['reason'] for a in proofs)),
        legal_double_positive_phase_valid_CP_attempts=n,distinct_qualified_rounds=len({r['round_id'] for r in rows}),
        source_positive_quantity_attempts=len(origpositive),source_zero_quantity_attempts=sum(r['source_q']==0 for r in valid),
        source_unknown_attempts=n-len(valid),actual_ADD_fills=sum(a['side']=='buy_add' for a in journal),
        flag_counts={f:sum(r[f] for r in valid) for f in flags},
        flag_share_of_qualified_attempts={f:ratio(sum(r[f] for r in valid),n) for f in flags},
        shared_rejected_share_of_source_positive=ratio(sum(r['shared_positive_q_rejected'] for r in valid),len(origpositive)),
        rejected_minimum_reason_counts=dict(collections.Counter(reason for r in valid if r['shared_positive_q_rejected'] for reason in r['final_minimum_q_reasons'])),
        note='Attempt counts, not independent stocks. risk0 and slot0 may overlap. NAV_UNKNOWN is a certification block, not lack of cash. Pure original size arithmetic on existing proofs, not account replay.')
    return rows,summary
def initial_fees(s,journal):
    rows=[]
    for a in journal:
        if a['side']!='buy_core':continue
        sid=a['round_id'].split('|')[-2];day=s.pd.Timestamp(a['day']);q=int(a['q']);px=D(a['exact_price']);gross=D(q)*px
        qr,fs,par=s.getmeta(sid,day);parts=fs.incremental('buy',gross,{}, {},1,shares=q,par_value=par);fee=sum(parts.values(),ZERO)
        assert fee==D(a['exact_whole_order_fee'])
        component=next(c for c in fs.components if c.name=='net_brokerage')
        no_min=s.FeeSchedule(fs.schedule_id+':REPORT_ONLY_NO_MIN',(replace(component,minimum_local=ZERO),)).incremental('buy',gross,{}, {},1,shares=q,par_value=par)['net_brokerage']
        commission=parts['net_brokerage'];uplift=commission-no_min
        rows.append(dict(round_id=a['round_id'],sid=sid,day=day,q=q,minimum_quantity=qr.buy_minimum,exactly_minimum_quantity=q==qr.buy_minimum,
            gross=gross,buy_fee=fee,buy_fee_fraction_of_gross=fee/gross,net_brokerage=commission,brokerage_minimum_binding=uplift>0,
            minimum_brokerage_uplift=uplift,fee_components=parts,schedule_id=fs.schedule_id))
    def aggregate(rs):
        gross=sum((x['gross'] for x in rs),ZERO);fee=sum((x['buy_fee'] for x in rs),ZERO);broker=sum((x['net_brokerage'] for x in rs),ZERO);up=sum((x['minimum_brokerage_uplift'] for x in rs),ZERO)
        return dict(n=len(rs),gross=gross,buy_fees=fee,net_brokerage=broker,minimum_uplift=up,
            weighted_buy_fee_fraction_of_gross=None if not gross else fee/gross,
            mean_order_buy_fee_fraction=mean([x['buy_fee_fraction_of_gross'] for x in rs]),
            maximum_order_buy_fee_fraction=max((x['buy_fee_fraction_of_gross'] for x in rs),default=None),
            brokerage_share_of_buy_fees=None if not fee else broker/fee,minimum_uplift_share_of_buy_fees=None if not fee else up/fee)
    return rows,dict(total=aggregate(rows),minimum_quantity=aggregate([x for x in rows if x['exactly_minimum_quantity']]),
        above_minimum_quantity=aggregate([x for x in rows if not x['exactly_minimum_quantity']]),
        minimum_quantity_fraction=ratio(sum(x['exactly_minimum_quantity'] for x in rows),len(rows)),
        brokerage_minimum_binding_count=sum(x['brokerage_minimum_binding'] for x in rows),
        brokerage_minimum_binding_fraction=ratio(sum(x['brokerage_minimum_binding'] for x in rows),len(rows)),
        note='Actual filled initial probes only. Buy-side fee/gross; not round-trip cost or return. Minimum uplift is same-order fee arithmetic decomposition, not changed quantities or a no-minimum-fee strategy run.')
def capital_2024(s,d,archive,journal,audit):
    daily=[];q=collections.defaultdict(lambda:{'core':0,'add':0});pools={};actions=collections.defaultdict(list);promotions=collections.defaultdict(list)
    for a in journal:actions[s.pd.Timestamp(a['day'])].append(a)
    for a in audit:
        if a['type']=='PROMOTED':promotions[s.pd.Timestamp(a['day'])].append(a)
    entries=[]
    for row in read(d,'DAY_LEDGER'):
        day=s.pd.Timestamp(row['day'])
        for x in promotions[day]:pools[x['round_id']]='confirmed'
        for x in actions[day]:
            rid=x['round_id'];n=int(x['q']);side=x['side'];pools.setdefault(rid,'probe')
            if side=='buy_core':
                q[rid]['core']+=n;st=archive[rid];entries.append(dict(round_id=rid,event_id=st['event_id'],sid=st['sid'],signal_day=st['signal_day'],entry_day=day,initial_buy_cash=D(n)*D(x['exact_price'])+D(x['exact_whole_order_fee'])))
            elif side=='buy_add':q[rid]['add']+=n
            elif side=='sell_add':q[rid]['add']-=n
            else:assert n==sum(q[rid].values());q[rid]={'core':0,'add':0}
        values={'probe':ZERO,'confirmed':ZERO};held=0
        for rid,parts in q.items():
            n=sum(parts.values())
            if not n:continue
            sid=archive[rid]['sid'];s.load(sid);price=D(str(s.raw[sid].get(day)['raw_close']))
            values[pools[rid]]+=D(n)*price;held+=1
        rec=row['CLOSE'];assert rec['certified']
        nav=D(rec['NAV']);gross=sum(values.values(),ZERO)
        assert gross==D(rec['gross_inventory']) and nav==D(rec['cash'])+D(rec['receivable'])+gross
        daily.append(dict(day=day,year=day.year,quarter=str(day.year)+'Q'+str((day.month-1)//3+1),NAV=nav,cash=rec['cash'],receivable=rec['receivable'],
            probe_gross=values['probe'],confirmed_gross=values['confirmed'],total_gross=gross,
            probe_NAV_fraction=values['probe']/nav,confirmed_NAV_fraction=values['confirmed']/nav,total_NAV_fraction=gross/nav,held_rounds=held))
    grouped=[]
    for field in ('year','quarter'):
        for period in sorted({x[field] for x in daily}):
            rows=[x for x in daily if x[field]==period]
            val=dict(grouping=field,period=period,covered_start=rows[0]['day'],covered_end=rows[-1]['day'],common_trading_days=len(rows),days_with_inventory=sum(x['total_gross']>0 for x in rows))
            for pool in ('probe','confirmed','total'):
                money=[x[pool+'_gross'] for x in rows];frac=[x[pool+'_NAV_fraction'] for x in rows]
                val[pool]=dict(mean_close_gross_CNY=mean(money),maximum_close_gross_CNY=max(money),capital_CNY_trading_days=sum(money,ZERO),mean_close_NAV_fraction=mean(frac),maximum_close_NAV_fraction=max(frac))
            val['new_core_entries']=sum(rows[0]['day']<=x['entry_day']<=rows[-1]['day'] for x in entries);grouped.append(val)
    timing=dict(first_signal=min(x['signal_day'] for x in entries),last_signal=max(x['signal_day'] for x in entries),first_entry=min(x['entry_day'] for x in entries),last_entry=max(x['entry_day'] for x in entries),
        first_inventory_close=min(x['day'] for x in daily if x['total_gross']>0),last_inventory_close=max(x['day'] for x in daily if x['total_gross']>0),
        last_actual_trade=max(s.pd.Timestamp(x['day']) for x in journal),entry_month_counts=dict(collections.Counter(str(x['entry_day'].date())[:7] for x in entries)),
        birth_month_counts=dict(collections.Counter(str(x['signal_day'])[:7] for x in entries)),
        no_new_birth_after='2024-12-31',definition='Actual original birth cohort only; later ADD/exit/rights are not new births. Close-valued capital occupation, averaged across covered common trading days, including idle days.')
    return daily,grouped,entries,timing
def main():
    out=HERE/'diagnostics';out.mkdir(exist_ok=False);start=time.monotonic()
    save(out/'STARTED.json',dict(mode='EXISTING_OUTPUT_POSTPROCESS_ONLY_NO_ACCOUNT_REPLAY',script_sha256=bridge.sha(__file__),source_seals={w:bridge.sha(BASE/('cohort_'+w)/'OUTPUT_SEAL.json') for w in ('2022','2024_924')}))
    try:
        summary={}
        for window in ('2022','2024_924'):
            d=BASE/('cohort_'+window);oldhash=read(d,'SOURCE_HASHES');s=bridge.load_original(window)
            archive=read(d,'ARCHIVES');journal=read(d,'EXACT_TRADE_JOURNAL');audit=read(d,'AUDIT');nd=read(d,'ROUND_ND')
            rows,stats=add_diagnostics(s,d,archive,journal,audit,nd);save(out/(window+'_ADD_ATTEMPTS.json'),rows)
            fees,cost=initial_fees(s,journal);save(out/(window+'_INITIAL_FEE_DETAIL.json'),fees)
            summary[window]=dict(ADD=stats,initial_fees=cost)
            if window=='2024_924':
                daily,groups,entries,timing=capital_2024(s,d,archive,journal,audit)
                save(out/'2024_DAILY_CAPITAL.json',daily);save(out/'2024_YEAR_QUARTER_CAPITAL.json',groups);save(out/'2024_ENTRY_DETAIL.json',entries);save(out/'2024_ENTRY_TIMING.json',timing)
            for p,h in s.hashes.items():assert oldhash.get(p)==h and bridge.sha(p)==h,(window,p)
            save(out/(window+'_READ_SOURCE_HASHES.json'),s.hashes)
            del sys.modules[s.__name__];del s;gc.collect()
        save(out/'DIAGNOSTIC_SUMMARY.json',summary);save(out/'RESULT.json',dict(status='AUTHOR_POSTPROCESS_PASS',elapsed_seconds=time.monotonic()-start,no_account_replay=True))
        save(out/'OUTPUT_SEAL.json',{p.name:bridge.sha(p) for p in out.iterdir() if p.is_file()})
        print(json.dumps(summary,default=str))
    except BaseException as e:
        if not (out/'RESULT.json').exists():save(out/'RESULT.json',dict(status='FAILED',error=repr(e),traceback=traceback.format_exc()))
        raise
if __name__=='__main__':main()
