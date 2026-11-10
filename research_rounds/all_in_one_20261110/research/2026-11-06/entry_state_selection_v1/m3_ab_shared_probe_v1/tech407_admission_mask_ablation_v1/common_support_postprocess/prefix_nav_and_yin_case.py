"""Reported prefix NAV/DD and a fixed observed order, no replay or strategy changes."""
from pathlib import Path
from decimal import Decimal as D
import sys
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from runner import read,save
CUT=pd.Timestamp('2024-11-27');RID='2024_924|A_UNION_B_SHARED_ENGINEERING_V1|300085.SZ|2'
def main():
    paths=read(ROOT/'path_reporting/ACTUAL_PATH_REPORT.json');result={}
    for arm in ['all1709','tech407']:
        out=ROOT/('run_'+arm+'_once');days=[x for x in read(out/'DAY_LEDGER.json') if pd.Timestamp(x['day'])<=CUT]
        assert all(x['CLOSE']['certified'] and (x['OPEN'] is None or x['OPEN']['certified']) for x in days)
        peak=D(1200000);dd=D(0);peakday='SEED';trough=None;ddpeak=None
        for x in days:
            nav=D(x['CLOSE']['NAV'])
            if nav>peak:peak=nav;peakday=x['day']
            draw=(peak-nav)/peak
            if draw>dd:dd=draw;trough=x['day'];ddpeak=peakday
        nav=D(days[-1]['CLOSE']['NAV'])
        audit=read(out/'AUDIT.json');orders={x['order_id']:x for x in read(out/'ORDER_STATUS.json')};journal=read(out/'EXACT_TRADE_JOURNAL.json')
        stage=next(x for x in paths[arm]['resources_and_headroom']['fixed_window'] if x['day']=='2024-09-24')
        consumed_fees=D(0);prior_reserved=[];candidate=None
        for x in audit:
            if not str(x['day']).startswith('2024-09-24'):continue
            if x.get('round_id')==RID and x['type'] in ('RESERVED','BUDGET_REJECTED'):
                candidate=x;break
            if x['type']=='RESERVED':
                o=orders[x['order_id']];assert o['pool']=='confirmed','This exact fixed case expects no earlier probe reservation'
                consumed_fees+=D(o['fee']);prior_reserved.append(o)
        assert candidate is not None
        trial=next(x for x in candidate['trials'] if x['q']==100)
        nav_before=D(stage['NAV'])-consumed_fees
        headroom_before=nav_before*D('.005')-D(stage['probe_nominal_risk'])
        headroom_after_fee=(nav_before-D(trial['fee']))*D('.005')-D(stage['probe_nominal_risk'])
        entry=next((x for x in journal if x['round_id']==RID and x['side']=='buy_core' and str(x['day']).startswith('2024-09-24')),None)
        cost=None if entry is None else -D(entry['report_only_allocations']['core']['cash_delta'])
        result[arm]=dict(mechanical_data_blockage_before_phase=dict(start='SEED before 2024-09-02 CLOSE',end='2024-11-27 CLOSE',common_sessions=len(days),all_recorded_phases_certified=True,NAV=nav,return_from_seed=nav/D(1200000)-1,close_NAV_max_drawdown=dd,drawdown_peak_day=ddpeak,drawdown_trough_day=trough),
            yin_300085_20240924=dict(signal_day='2024-09-23',candidate_original_q=candidate['original_formula_q'],actual_filled_q=0 if entry is None else entry['q'],actual_fee_inclusive_buy_cash=cost,
                original_pre_all_buy_probe_nominal_risk_headroom=stage['probe_nominal_risk_headroom'],prior_reserved_confirmed_orders=prior_reserved,
                exact_before_Yin_proposal_effective_NAV=nav_before,exact_before_Yin_proposal_probe_nominal_risk_headroom=headroom_before,
                exact_minimum_100_share_trial_after_its_buy_fee_probe_nominal_headroom=headroom_after_fee,minimum_100_trial=trial,
                emitted_actual_decision=candidate['type'],actual_exact_journal=entry,
                distinction='Probe headroom is nominal mark-minus-floor risk, not the per-round fee-inclusive planned risk in the trial. No prior probe reservation exists at this particular proposal; the earlier technology ADD is confirmed-pool and only its fee lowers effective NAV.'))
    result['warning']='This prefix ends mechanically just before observed data blockage. It is not a prechosen investment window, an independent validation sample, or a complete strategy return. Full-window technology NAV/return/DD remain null. All figures use actual original recorded paths.'
    save(HERE/'MECHANICAL_PREFIX_NAV_AND_YIN_CASE.json',result);print('SAVED_MECHANICAL_PREFIX_AND_YIN')
if __name__=='__main__':main()
