"""One gated fixed three-consumer lifecycle comparison. No retries or parameter scans."""
from pathlib import Path
import json, datetime
import numpy as np
import pandas as pd
from adapter import O, ARMS, ENGINES, load_engine, install, sha, save, bridge_compare
from report import report_arm, aggregate
CODE_FILES=['prepare_features.py','adapter.py','report.py','run.py','test_non_economic.py','CONTRACT.json']
def main():
    audit=json.loads((O/'PRE_ECONOMIC_AUDIT.json').read_text())
    assert audit['result']=='PASS_PRE_ECONOMIC_IMPLEMENTATION'
    for name in CODE_FILES: assert audit['implementation_hashes'][name]==sha(O/name),(name,'audit code drift')
    authorization=json.loads((O/'EXECUTION_AUTHORIZATION.json').read_text())
    assert authorization['explicit_parent_start'] is True
    assert authorization['arms']==ARMS and authorization['windows']==['2022','2024_924']
    seal=json.loads((O/'FEATURE_SEAL.json').read_text())
    for name,h in seal['files'].items():assert sha(O/name)==h,(name,'feature drift')
    for path,h in seal['source_hashes'].items():assert sha(path)==h,(path,'source drift')
    contract=json.loads((O/'CONTRACT.json').read_text())
    for path,h in contract['source_hashes'].items(): assert sha(path)==h,(path,'economic source drift')
    features=pd.read_csv(O/'ALL_MARKET_STOCK_MONTH_FEATURES.csv',float_precision='round_trip')
    assert len(features)==14635
    with (O/'RUN_ONCE.json').open('x') as f:
        json.dump(dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),arms=ARMS,windows=['2022','2024_924'],implementation_hashes={n:sha(O/n) for n in CODE_FILES},audit_sha256=sha(O/'PRE_ECONOMIC_AUDIT.json'),authorization_sha256=sha(O/'EXECUTION_AUTHORIZATION.json'),feature_seal_sha256=sha(O/'FEATURE_SEAL.json')),f,indent=2)
    for window in ['2022','2024_924']:
        s=load_engine(window);install(s,features);(O/window).mkdir(exist_ok=False)
        for arm in ARMS:
            print('BEGIN_FIXED_CONSUMER',window,arm,flush=True)
            s.reset(True,'FULL');s.ch3_audit=[];s.run_window(arm)
            z=pd.DataFrame(s.rounds);a=pd.DataFrame(s.actions);d=pd.DataFrame(s.decisions)
            assert d.groupby(['day','sector']).selected.sum().le(2).all()
            assert not z.round_id.duplicated().any() and set(z.round_id)==set(d.loc[d.selected,'round_id'])
            assert a[a.side.eq('buy_add')].prior_round_net.gt(0).all()
            assert a[a.side.eq('buy_add')].groupby('round_id').size().le(1).all()
            assert all(x['arm']==arm for x in s.claims.values())
            if arm=='A_UNION_B':
                checks=bridge_compare(s,window)
                legal=d[d.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])]
                assert (len(legal),int(legal.selected.sum()))==({'2022':(5728,2732),'2024_924':(3505,1354)}[window])
            else:
                q=pd.DataFrame(s.ch3_audit);u=q[q.feasible&~q.known]
                assert u.old_feasible_rank.equals(u.new_feasible_rank)
                feasible=q[q.feasible].set_index('event_id')
                actual=d[d.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])].set_index('event_id')
                assert set(feasible.index)==set(actual.index)
                assert feasible.new_slot_selected.sort_index().equals(actual.selected.sort_index())
                checks=dict(unknown_feasible_slots_fixed=True,actual_selection_matches_compressed_K2=True,full_feature_domain_asserted=True)
            dest=O/window/arm;s.dump(dest)
            save(dest/'CONSUMER_QA.json',checks)
            pd.DataFrame(s.ch3_audit).to_csv(dest/'CH3_QUEUE_AUDIT.csv',index=False)
            report_arm(s,window,arm,dest)
            save(dest/'COMPLETE_OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file()})
            print('FIXED_CONSUMER_DONE',window,arm,len(z),flush=True)
    aggregate()
    save(O/'COMPLETION.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),one_fixed_run=True,no_parameter_search=True,arms=ARMS,windows=['2022','2024_924']))
if __name__=='__main__':main()
