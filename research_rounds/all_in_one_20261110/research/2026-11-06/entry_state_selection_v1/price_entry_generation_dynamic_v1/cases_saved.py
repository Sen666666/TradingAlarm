"""Complete old-cohort/new-path accounting, all saved ledgers; no economics."""
import argparse
from collections import defaultdict
import pandas as pd
from runtime import O,R,SOURCE,sha,read
from run_economic import save,clean

FIELDS=['round_id','sid','owner_lane','event_id','price_root','signal_day','entry_day','exit_day','status_day','status','entry_q','entry_open','entry_price','entry_fee','entry_floor_raw','added_q','fees','net_pnl','last_known_mark_day','last_mark_net','cash_after_payouts','receivable_after_payouts','dividend_net80_total','actual_ack','actual_fill','historical_tradability']

def build(window):
    folder=O/('report_'+window);dest=O/('cases_'+window);dest.mkdir(exist_ok=False)
    for n,h in read(folder/'OUTPUT_SHA256.json').items():assert sha(folder/n)==h
    report=read(folder/'COMPARISON_REPORT.json');metrics=pd.read_csv(folder/'ALL_ROUNDS.csv',float_precision='round_trip').to_dict('records')
    stocks={(r['sid'],r['arm']):r for r in report['stock_rows']};diff={r['sid']:r for r in report['differences']}
    source=R/'old_result_association_v1/COMMON_167_DENY_BUYS.csv';cohort=pd.read_csv(source,float_precision='round_trip');cohort=cohort[cohort.window.astype(str).eq('2022' if window=='2022' else '2024_924')]
    assert len(cohort)==(117 if window=='2022' else 50)
    paths={};raw={};actions={};claims={};books={}
    for arm,d in [('baseline',SOURCE/('economic_'+window)),('joint',O/('gate_'+window))]:
        raw[arm]=pd.read_csv(d/'joint/ROUNDS.csv',float_precision='round_trip').to_dict('records');actions[arm]=pd.read_csv(d/'joint/ACTIONS.csv',float_precision='round_trip').to_dict('records')
        claims[arm]=read(d/'joint/CLAIMS.json');books[arm]=read(d/'EXECUTION_BOOKS.json')
    def case(sid):
        result={}
        for arm in ['baseline','joint']:
            rs=sorted([r for r in raw[arm] if r['sid']==sid],key=lambda r:(str(r['signal_day']),r['round_id']))
            ids={r['round_id'] for r in rs};aa=[a for a in actions[arm] if a['round_id'] in ids]
            entered={a['round_id'] for a in aa if a['side']=='buy_core'}
            realized_cycle=False;seen_buy=False;typed=[]
            for r in rs:
                own=[a for a in aa if a['round_id']==r['round_id']];entered_now=r['round_id'] in entered
                label='NO_INITIAL_PROXY_FILL'
                if entered_now:
                    label='PROXY_REENTRY_AFTER_THIS_ARM_PRIOR_BUY_AND_SELL_ALL' if realized_cycle else 'CONDITIONAL_PROXY_FIRST_ENTRY' if not seen_buy else 'LATER_PROXY_ENTRY_WITHOUT_PROVED_PRIOR_SELL_ALL'
                    seen_buy=True
                if entered_now and any(a['side']=='sell_all' for a in own):realized_cycle=True
                typed.append(dict(**{k:r.get(k) for k in FIELDS},participation_identity=label,actions=own,independent_metrics=next((m for m in metrics if m['round_id']==r['round_id'] and m['arm']==arm),None),execution_book=books[arm].get(r['round_id'])))
            claim_rows=[c for c in claims[arm] if c.get('owner_round_id',c.get('round_id')) in ids] if isinstance(claims[arm],list) else claims[arm]
            result[arm]=dict(stock=stocks[sid,arm],rounds=typed,claims=claim_rows,proxy_initial_buy_rounds=len(entered),actions=aa)
        return dict(sid=sid,difference=diff[sid],paths=result,unknown_not_zero=True,old_cohort_does_not_imply_new_common=True)
    for sid in sorted(cohort.sid.unique()):paths[sid]=case(sid)
    rows=[]
    for r in cohort.to_dict('records'):
        sid=r['sid'];old=next(x for x in paths[sid]['paths']['baseline']['rounds'] if x['round_id']==r['round_id'])
        assert old['signal_day'][:10]==r['signal_day'][:10]
        nr=paths[sid]['paths']['joint']['rounds'];same=[n for n in nr if n['event_id']==old['event_id'] and n['owner_lane']==old['owner_lane']]
        later=[n for n in nr if n['participation_identity']!='NO_INITIAL_PROXY_FILL' and str(n['signal_day'])>=str(old['signal_day'])]
        rows.append(dict(old_round_id=r['round_id'],sid=sid,old_signal_day=r['signal_day'],old_root_day=r['root_day'],old_full_net=r['old_FULL_net'],old_gate_generation=r['generation'],same_original_receipt_new_registered=same,next_new_proxy_entry_on_or_after_old_signal=later[0] if later else None,new_total=stocks[sid,'joint']['known_total_pnl'],new_unknown=stocks[sid,'joint']['unknown_liability'],new_financial_covered=stocks[sid,'joint']['financial_covered'],whole_stock_path_key=sid))
    unique=[diff[sid] for sid in paths];comparable=[r for r in unique if r['common_covered']]
    # Fixed case selection is descriptive posterior, not a parameter change.
    oldordered=cohort.sort_values(['old_FULL_net','sid']);negative=oldordered[oldordered.old_FULL_net.lt(0)].head(3);positive=oldordered[oldordered.old_FULL_net.gt(0)].tail(3).iloc[::-1]
    picks=dict(old_losses3=[paths[s] for s in negative.sid],old_wins3=[paths[s] for s in positive.sid])
    focus=['688660.SH','002583.SZ','000977.SZ','002174.SZ']
    for s in focus:
        if (s,'baseline') in stocks and s not in paths:paths[s]=case(s)
    participation924={arm:[r for r in raw[arm] if str(r.get('entry_day',''))[:10]>='2024-09-20' and str(r.get('entry_day',''))[:10]<='2024-10-08' and any(a['round_id']==r['round_id'] and a['side']=='buy_core' for a in actions[arm])] for arm in ['baseline','joint']} if window=='2024' else {}
    out=dict(window=window,old_cohort_rounds=len(rows),old_cohort_unique_stocks=cohort.sid.nunique(),old_cohort_rows=rows,whole_stock_paths=paths,picked_cases=picks,participation_924=participation924,summary=dict(unique_cohort_common_stocks=len(comparable),unique_cohort_common_delta=sum(r['joint_minus_baseline'] for r in comparable),new_unknown_stocks=sum(stocks[s,'joint']['unknown_liability'] for s in cohort.sid.unique()),new_financial_uncovered_stocks=sum(not stocks[s,'joint']['financial_covered'] for s in cohort.sid.unique())),source_sha256={str(source):sha(source),str(folder/'COMPARISON_REPORT.json'):sha(folder/'COMPARISON_REPORT.json')},economic_runs=0,execution_model='CONDITIONAL_NEXT_COMMON_OPEN_5BP_FULL_FILL_NOT_ACTUAL',never_labels_delayed_first_entry_as_reentry=True)
    save(dest/'AFFECTED_OLD_COHORT_FULL_NEW_PATHS.json',out);save(dest/'OUTPUT_SHA256.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file()});print('CASES_READY',window,len(rows),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);build(p.parse_args().window)
