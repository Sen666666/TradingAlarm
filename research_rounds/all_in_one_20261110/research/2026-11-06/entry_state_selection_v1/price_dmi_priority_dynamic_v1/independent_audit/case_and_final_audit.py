"""Independent case-export consistency and final two-snapshot seal audit."""
from pathlib import Path
import hashlib,json,math,sys
import pandas as pd
O=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent;S=O.parent/'independent_channel_joint_economic_v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    if isinstance(v,float) and not math.isfinite(v):return None
    if hasattr(v,'item'):return clean(v.item())
    return v
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False)
allresults={}
for w in ['2022','2024']:
    reportdir=O/('report_'+w);d=read(reportdir/'REQUESTED_STOCK_CASES.json');report=read(reportdir/'COMPARISON_REPORT.json')
    for p,h in read(reportdir/'CASE_OUTPUT_SHA256.json').items():assert sha(reportdir/p)==h
    for p,h in d['source_sha256'].items():assert sha(p)==h
    assert d['script_sha256']==sha(O/'cases_saved.py')
    stocks={(r['sid'],r['arm']):r for r in report['stock_rows']};diff={r['sid']:r for r in report['differences']}
    native={};ent={}
    for arm,base in [('baseline',S/('economic_'+w)),('joint',O/('dmi_'+w))]:
        native[arm]=pd.read_csv(base/'joint/ROUNDS.csv',float_precision='round_trip').to_dict('records')
        acts=pd.read_csv(base/'joint/ACTIONS.csv',float_precision='round_trip').to_dict('records')
        ent[arm]={r['round_id'] for r in acts if r['side'].startswith('buy') and r['q']>0}
    cols=['round_id','event_id','owner_lane','signal_day','entry_day','exit_day','status_day','status','entry_q','added_q','net_pnl','last_known_mark_day','last_mark_net','cash_after_payouts','receivable_after_payouts','dividend_net80_total']
    common=[r for r in report['differences'] if r['common_covered']]
    up=sorted([r for r in common if r['joint_minus_baseline']>0],key=lambda r:(-r['joint_minus_baseline'],r['sid']))[:5]
    down=sorted([r for r in common if r['joint_minus_baseline']<0],key=lambda r:(r['joint_minus_baseline'],r['sid']))[:5]
    assert [r['sid'] for r in d['improved_top5']]==[r['sid'] for r in up]
    assert [r['sid'] for r in d['worsened_top5']]==[r['sid'] for r in down]
    assert {r['sid'] for r in d['named_cases']}=={'300229.SZ','300607.SZ','300024.SZ','002241.SZ'}
    cases=d['improved_top5']+d['worsened_top5']+d['named_cases'];paths_checked=lost_checked=0
    for c in cases:
        sid=c['sid'];assert c['old_stock']==stocks[sid,'baseline'] and c['new_stock']==stocks[sid,'joint'] and c['difference']==diff[sid]
        expected={}
        for arm in ['baseline','joint']:
            expected[arm]=clean([{k:r.get(k) for k in cols} for r in native[arm] if r['sid']==sid and r['round_id'] in ent[arm]])
            assert c['actual_entered_paths'][arm]==expected[arm],(w,sid,arm,'PATH')
            assert c[('old' if arm=='baseline' else 'new')+'_participation']['entered_rounds']==len(expected[arm])
            paths_checked+=len(expected[arm])
        newids={r['event_id'] for r in expected['joint']};lost=[r for r in expected['baseline'] if r['event_id'] not in newids]
        assert [r['old_entered_event'] for r in c['old_entered_events_not_retained']]==[r['event_id'] for r in lost]
        for x,r in zip(c['old_entered_events_not_retained'],lost):
            later=sorted([r for r in expected['joint'] if r['entry_day']>x['old_entry_day']],key=lambda r:r['entry_day'])
            assert x['subsequent_new_participation']==(later[0] if later else None)
            assert 'not proof' in x['meaning'];lost_checked+=1
        if c['old_stock']['known_total_pnl'] is None or c['new_stock']['known_total_pnl'] is None:
            assert c['difference']['joint_minus_baseline'] is None
    result=dict(status='PASS_CASE_EXPORT_EXACT_TO_SAVED_LEDGER',window=w,cases_checked=len(cases),entered_paths_checked=paths_checked,lost_event_later_entry_links_checked=lost_checked,common_top5_exact=True,named_unknown_not_zero=True,case_output_seal_sha256=sha(reportdir/'CASE_OUTPUT_SHA256.json'),named_case_deltas={r['sid']:r['difference']['joint_minus_baseline'] for r in d['named_cases']},economic_runs=0)
    save(A/('CASE_AUDIT_'+w+'.json'),result);allresults[w]=result
auth=read(O/'ROOT_DMI_AUTHORIZATION.json')
assert sha(O/'ROOT_DMI_AUTHORIZATION.json')=='73fdb4955bd5da760e98bc74b51b3f7e872326248c9d505e73cad4e14de61536'
for p,h in auth['code_sha256'].items():assert sha(O/p)==h
for p,h in auth['input_sha256'].items():assert sha(p)==h
snapshots={};audits={}
for w in ['2022','2024']:
    dest=O/('dmi_'+w);complete=read(dest/'COMPLETE_SAVED_SNAPSHOT.json')
    assert complete['output_seal_sha256']==sha(dest/'OUTPUT_SEAL.json')
    for p,h in read(dest/'OUTPUT_SEAL.json').items():assert sha(dest/p)==h
    assert not (dest/'FAILED_NO_RETRY.json').exists()
    audits[w]={p:sha(A/(p+'_'+w+'.json')) for p in ['POSTERIOR','SOURCE_BINDINGS','CASE_AUDIT']}
    binding=read(A/('SOURCE_BINDINGS_'+w+'.json'));assert binding['post_economic_audit_sha256']==audits[w]['POSTERIOR']
    assert read(A/('POSTERIOR_'+w+'.json'))['status']=='PASS_INDEPENDENT_POST_ECONOMIC_AUDIT'
    snapshots[w]=dict(complete_sha256=sha(dest/'COMPLETE_SAVED_SNAPSHOT.json'),output_seal_sha256=sha(dest/'OUTPUT_SEAL.json'),once_lock_sha256=sha(O/('DMI_RUN_ONCE_'+w+'.json')))
out=dict(status='PASS_BOTH_WINDOWS_FINAL_POSTERIOR',frozen_code_count=len(auth['code_sha256']),frozen_input_count=len(auth['input_sha256']),original_frozen_code_inputs_outputs_verified_in_source_bindings=True,both_new_snapshots_unchanged=True,root_authorization_sha256=sha(O/'ROOT_DMI_AUTHORIZATION.json'),audits=audits,snapshots=snapshots,cases=allresults,new_dmi_economic_runs_per_window=1,historical_economic_runs_by_auditor=0,source_assertion_scope='Recorded run locks and exactly two completed snapshot directories; no retries or new economic work by this auditor.')
save(A/'FINAL_POSTERIOR_COMPLETION.json',out)
print(json.dumps(out,indent=2,ensure_ascii=False))
