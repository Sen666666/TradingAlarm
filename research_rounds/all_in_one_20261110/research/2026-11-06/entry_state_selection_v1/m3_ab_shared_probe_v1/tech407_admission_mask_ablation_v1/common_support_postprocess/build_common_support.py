"""Mechanical first-owned-UNKNOWN cutoff, actual path data only. No engine replay."""
from pathlib import Path
from decimal import Decimal as D
import collections,json,sys
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from runner import read,save
from analyze_outputs_v2 import describe,validate
ZERO=D(0);CLOSED='EXECUTION_AND_SETTLEMENT_CLOSED'
def day(x):return pd.Timestamp(x).normalize()
def asof(arm,cut):
    out=ROOT/('run_'+arm+'_once');validate(out)
    ar=read(out/'ARCHIVES.json');journal=read(out/'EXACT_TRADE_JOURNAL.json');cl=read(out/'CLAIM_LEDGER.json');claims=read(out/'CLAIMS.json');ledger=read(out/'DAY_LEDGER.json');dec=read(out/'DECISIONS.json');actions=read(out/'ACTIONS.json')
    records={};entry_ids=set();acts=[]
    def item(rid):
        return records.setdefault(rid,{k:dict(q=0,cash=ZERO,buy_cash=ZERO,receivable=ZERO,registered_claims=0,pending_claims=0) for k in ('core','add')})
    for a in journal:
        if day(a['day'])>cut:continue
        acts.append(a);r=item(a['round_id']);buy=a['side'].startswith('buy')
        if a['side']=='buy_core':entry_ids.add(a['round_id'])
        for kind,v in a['report_only_allocations'].items():
            r[kind]['q']+=int(v['q'])*(1 if buy else -1);r[kind]['cash']+=D(v['cash_delta'])
            if buy:r[kind]['buy_cash']-=D(v['cash_delta'])
    registered=[]
    for c in claims:
        if day(c['inventory_snapshot_day'])>cut:continue
        registered.append(c);r=item(c['owner_round_id'])
        events=[x for x in cl if x['round_id']==c['owner_round_id'] and x['economic_event_id']==c['economic_event_id'] and day(x['day'])<=cut]
        recognized=any(x['event']=='ACCRUE_NET80' for x in events);paid=any(x['event']=='PAY_CLOSE_TRANSFER' for x in events)
        for kind,amount in [('core',D(c['core_amount'])),('add',D(c['amount'])-D(c['core_amount']))]:
            if not amount:continue
            r[kind]['registered_claims']+=1;r[kind]['pending_claims']+=int(not paid)
            if recognized:r[kind]['receivable']+=amount
            if paid:r[kind]['cash']+=amount;r[kind]['receivable']-=amount
    rounds=[];layers=[]
    for rid in sorted(entry_ids):
        r=item(rid);q=sum(x['q'] for x in r.values());cash=sum(x['cash'] for x in r.values());recv=sum(x['receivable'] for x in r.values());cost=sum(x['buy_cash'] for x in r.values());pending=sum(x['pending_claims'] for x in r.values())
        status='OPEN_AT_CUTOFF' if q else 'EXECUTION_CLOSED_SETTLEMENT_OPEN' if recv or pending else CLOSED
        net=cash+recv if status==CLOSED else None
        rounds.append(dict(round_id=rid,sid=ar[rid]['sid'],event_id=ar[rid]['event_id'],signal_day=ar[rid]['signal_day'],status=status,qty=q,cash=cash,receivable=recv,pending_layer_claims=pending,NET=net,buy_cash=cost,return_on_buy_cash=net/cost if net is not None else None))
        for kind,v in r.items():
            if not v['buy_cash']:continue
            ls='OPEN_AT_CUTOFF' if v['q'] else 'EXECUTION_CLOSED_SETTLEMENT_OPEN' if v['receivable'] or v['pending_claims'] else CLOSED
            ln=v['cash']+v['receivable'] if ls==CLOSED else None
            layers.append(dict(round_id=rid,sid=ar[rid]['sid'],layer=kind,status=ls,**v,NET=ln,return_on_buy_cash=ln/v['buy_cash'] if ln is not None else None))
    last=next(x for x in ledger if day(x['day'])==cut);assert last['CLOSE']['certified']
    cash_total=D(1200000)+sum((v['cash'] for r in records.values() for v in r.values()),ZERO);recv_total=sum((v['receivable'] for r in records.values() for v in r.values()),ZERO)
    assert abs(cash_total-D(last['CLOSE']['cash']))<D('1e-7') and abs(recv_total-D(last['CLOSE']['receivable']))<D('1e-7')
    selected=[x for x in dec if day(x['day'])<=cut and x['selected']]
    domain_dec=[x for x in dec if day(x['day'])<=cut]
    pdint=[x for x in selected if day(x['day'])==cut]
    # End-of-run follow-up ONLY for births already in the common information domain.
    ids={x['round_id'] for x in selected};final_rounds=[x for x in read(out/'ROUND_REPORT.json') if x['round_id'] in ids];final_layers=[x for x in read(out/'LAYER_REPORT.json') if x['round_id'] in ids]
    future_first=[x for x in actions if x['side']=='buy_core' and x['round_id'] in ids and day(x['day'])>cut]
    risk_orders=[x for x in read(out/'ORDER_STATUS.json') if x['status']=='filled' and x['kind']=='INIT' and x['round_id'] in entry_ids]
    return dict(arm=arm,cutoff=str(cut.date()),common_calendar_birth_start='2024-09-02',cutoff_phase='CLOSE',
        coverage=dict(evaluated_member_decisions=len(domain_dec),decision_counts=dict(collections.Counter(x['decision'] for x in domain_dec)),selected_pending_births=len(selected),actual_initial_fills_asof=len(entry_ids),actual_ADD_fills_asof=sum(x['side']=='buy_add' for x in acts),new_initial_pending_at_cutoff_close=len(pdint),pending_at_cutoff_records=pdint),
        asof_whole=describe(rounds,'status','NET','return_on_buy_cash'),asof_core=describe([x for x in layers if x['layer']=='core'],'status','NET','return_on_buy_cash'),asof_ADD=describe([x for x in layers if x['layer']=='add'],'status','NET','return_on_buy_cash'),
        asof_phase_ledger=last['CLOSE'],asof_registered_claims=len(registered),asof_cash_receivable_reconciled=True,asof_round_records=rounds,asof_layer_records=layers,
        asof_initial_filled_mean_planned_risk=sum((D(x['risk']) for x in risk_orders),ZERO)/len(risk_orders) if risk_orders else None,
        same_birth_domain_final_followup=dict(end='2026-06-30',whole=describe(final_rounds,'status','whole_round_NET80','conditional_return_on_actual_buy_cash'),core=describe([x for x in final_layers if x['layer']=='core'],'layer_status','NET80','return_on_layer_buy_cash'),ADD=describe([x for x in final_layers if x['layer']=='add'],'layer_status','NET80','return_on_layer_buy_cash'),
            first_fills_after_common_cutoff=future_first,warning='These are later outcomes for the same signal birth domain, NOT information available at Nov27. Technology risk freeze changes later admissions/ADD and this is not a clean equal-opportunity follow-up comparison.'))
def main():
    a=read(ROOT/'run_all1709_once/RESULT.json');t=read(ROOT/'run_tech407_once/RESULT.json');first=pd.Timestamp(t['first_uncertified']['day'])
    assert t['first_uncertified']['OPEN']['unknown'] and any(x.get('core',0) or x.get('add',0) or D(str(x.get('receivable',0))) for x in t['first_uncertified']['OPEN']['unknown'])
    days=[day(x['day']) for x in read(ROOT/'run_all1709_once/DAY_LEDGER.json')];cut=max(d for d in days if d<first)
    assert str(cut.date())=='2024-11-27'
    value=dict(method='Cutoff chosen mechanically as the last common CLOSE strictly before the first owned-liability UNKNOWN phase in either arm, not selected for favorable outcomes. No forced liquidation, no future winning labels.',first_unsupported_phase=t['first_uncertified'],asof_cutoff=str(cut.date()),all1709=asof('all1709',cut),tech407=asof('tech407',cut))
    save(HERE/'COMMON_SUPPORT_ASOF_AND_FOLLOWUP.json',value)
    # A separate explicit report correction leaves all previously frozen output bytes intact.
    correction={}
    for arm in ['all1709','tech407']:
        out=ROOT/('run_'+arm+'_once');states=read(out/'STATES.json');rounds=read(out/'ROUND_REPORT.json');audit=read(out/'AUDIT.json')
        au=[x for x in audit if x['type']=='UNKNOWN'];u=[x for x in rounds if x['status']=='ASSET_UNKNOWN']
        correction[arm]=dict(bridge_audit_UNKNOWN_emissions=len(au),bridge_explicit_zero_liability_emissions=sum(x.get('liability_free_initial') is True for x in au),bridge_not_proved_zero_by_flag_emissions=sum(x.get('liability_free_initial') is not True for x in au),
            actual_terminal_UNKNOWN_states=[x for x in states.values() if x['state']=='UNKNOWN'],actual_terminal_asset_UNKNOWN_rounds=u,
            explanation='Bridge audit emission counts are not total UNKNOWN counts. Original source before_held can freeze a held asset directly without emitting a bridge type=UNKNOWN row. Zero emissions does not imply zero responsibility. Archived state fields are legacy snapshots; use ROUND_REPORT status plus current STATES for terminal status.')
    save(HERE/'REPORT_SEMANTICS_CORRECTION.json',correction)
    print('COMMON_SUPPORT_SAVED',cut)
if __name__=='__main__':main()
