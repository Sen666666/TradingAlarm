"""Small independent failed-exit identity reconciliation; strict v3 already audited."""
from pathlib import Path
from decimal import Decimal, getcontext, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict
from datetime import datetime
import ast, gzip, hashlib, json
import pandas as pd
getcontext().prec=70
D=Decimal;Z=D(0);O=Path(__file__).resolve().parent;P=O.parent/'local_high';Q=P/'failure_only_reconciliation'
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
checks=defaultdict(int)
# Reuse only this reviewer's already-audited independent fee/quantity arithmetic.
names={'read','n','dt','eq','version','fee','risk','qmax','aggregate','checkagg','frame'}
nodes=[x for x in ast.parse((O/'audit.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name in names]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'independent_review_helpers','exec'),globals())
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};frames={};rules=read(R/'pvr-act-comparison-20261027/execution-rules-v2.json')
manifest=read(Q/'SOURCE_MANIFEST.json');assert manifest['script_sha256']==hashlib.sha256((Q/'analyze.py').read_bytes()).hexdigest()
for path,sha in manifest['sources'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
results=read(Q/'RESULTS.json');differences={};logic_only=[]
for ref,root in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024'),('strong',B/'pvr_pool_feasibility/runs/2025_26')]:
    strict=read(P/(ref+'_ROWS.json'));actual=read(Q/(ref+'_ROWS.json'));byid={x['layer']:x for x in strict};byactual={x['layer']:x for x in actual}
    book=read(root/'pair/B.json.gz');layercash=defaultdict(lambda:Z);selltimes=defaultdict(list)
    for t in book['trades']:
        if t['side']=='buy':layercash[t['layer']]-=n(t['gross_cny'])+n(t['fees_cny'])
        else:
            for part in t['parts']:layercash[part['layer']]+=n(part['net_cash']);selltimes[part['layer']].append(dt(t['at']))
    cp=B/('loss_correction/continuation2024_layers/PVR_NO60-CAMPAIGNS.json' if ref=='2022_2024' else 'loss_correction/pvr_no60_2025_26/PVR_NO60-CAMPAIGNS.json')
    candidates=[]
    for c in read(cp):
        if not c['closed']:continue
        assert max(t for lid in c['layer_ids'] for t in selltimes[lid])==dt(c['closed'])
        if sum((layercash[lid] for lid in c['layer_ids']),Z)<0:candidates.append(dict(opened=c['opened'],closed=c['closed'],layers=c['layer_ids'],kind='full_stock_campaign'))
    bysid=defaultdict(list)
    for e in strict:bysid[e['sid']].append(e)
    for sid,seq in bysid.items():
        cycles=[]
        for e in sorted([x for x in seq if x['role']=='mobile'],key=lambda x:(dt(x['opened']),x['layer'])):
            if not cycles or cycles[-1]['closed'] is not None and dt(e['opened'])>=dt(cycles[-1]['closed']):cycles.append(dict(opened=e['opened'],closed=e['closed'],layers=[e['layer']],kind='mobile_only_subcycle'))
            else:
                c=cycles[-1];c['layers'].append(e['layer']);c['closed']=None if c['closed'] is None or e['closed'] is None else max(c['closed'],e['closed'])
        for c in cycles:
            if not c['closed']:continue
            assert max(t for lid in c['layers'] for t in selltimes[lid])==dt(c['closed'])
            if sum((layercash[lid] for lid in c['layers']),Z)<0:candidates.append(c)
    expectedrows=[];changed=[]
    for e in strict:
        out=byactual[e['layer']];sid=e['sid'];clock=dt(e['decision_at']);day=pd.Timestamp(e['decision_at'][:10]);f=frame(sid);cur=f.loc[day]
        prior=[c for c in candidates if byid[c['layers'][0]]['sid']==sid and dt(c['closed'])<clock]
        prev=max(prior,key=lambda c:(dt(c['closed']),c['kind']=='full_stock_campaign')) if prior else None
        assert prev==out['previous_failed_cycle'];checks['failed_cash_cycle_identity']+=1
        hist=f[(f.index>=pd.Timestamp(prev['opened'][:10]))&(f.index<pd.Timestamp(prev['closed'][:10]))] if prev else f.iloc[0:0]
        exit_same=hist.empty or hist.segment_id.eq(cur.segment_id).all();fh=None if hist.empty or not exit_same else float(hist.close.max())
        assert fh==out['previous_failed_high'];checks['failed_H_excludes_exit_day']+=1
        last=e['last_actual_buy_at'];hh=f[(f.index>=pd.Timestamp(last[:10]))&(f.index<day)] if last else f.iloc[0:0]
        post_same=hh.empty or hh.segment_id.eq(cur.segment_id).all();high=e['post_entry_high_excluding_current']
        if e['role']=='core':label='CORE_UNCHANGED'
        elif not e['baseline_live_layer_ids']:label='FLAT_FIRST_TRIAL'
        elif not post_same or not exit_same:label='UNKNOWN_PRICE_DOMAIN'
        elif not e['original_I_alive']:label='I_PROTECTION_NOT_ALIVE'
        elif not e['old_live_mobile_protection_alive']:label='OLD_MOBILE_PROTECTION_NOT_ALIVE'
        elif high is None or float(cur.close)<=high:label='NO_NEW_POST_ENTRY_CLOSE_HIGH'
        elif prev is not None and (fh is None or float(cur.close)<=fh):label='NOT_RECOVERED_PREVIOUS_FAILED_HIGH'
        else:label='MATURE_LOCAL_AND_FAILED_HIGH_PROOF'
        if label!=out['proof_class']:logic_only.append(dict(ref=ref,layer=e['layer'],expected=label,producer=out['proof_class']))
        assert label==out['proof_class'],logic_only[-1]
        q0=e['actual_fill_quantity'];expected=None;why=[]
        if e['role']=='core' or label=='MATURE_LOCAL_AND_FAILED_HIGH_PROOF':expected=q0
        elif label=='UNKNOWN_PRICE_DOMAIN':why=['price_source_domain_changed']
        elif not e['trial_available_in_baseline']:expected=0
        else:
            why=list(e['reference_unknown_reasons'])
            if not e['original_I_alive']:why.append('original_I_floor_not_valid')
            if n(e['signal_factor'])!=n(e['fill_factor']):why.append('factor_changed_no_new_trial_mapping')
            if not why:
                floor=n(cur.i_floor)/n(e['signal_factor']);pr=n(e['signal_close_raw'])*D('1.0005');po=n(e['actual_execution_price']);riskbudget=n(e['decision_NAV'])*D('.0025')
                qr=version(rules['quantity_versions'][sid],e['opened'][:10])['rule'];venue=version(rules['venue_versions'][sid],e['opened'][:10])['venue'];schedule=version(rules['fee_versions'][venue],e['opened'][:10])['schedule'];par=n(rules['security_metadata'][sid]['par_value']);cap=min(q0,e['frozen_intent']['cap'])
                expected=0 if floor<=0 or floor>=n(e['signal_close_raw']) or floor>=n(e['actual_raw_open']) else qmax(cap,qr['buy_minimum'],qr['buy_step'],lambda q:risk(q,pr,floor,schedule['components'],par)<=riskbudget and risk(q,po,floor,schedule['components'],par)<=riskbudget)
        assert expected==out['qnew'] and why==out['quantity_unknown'];checks['failed_only_q_and_unknown']+=1
        merged=dict(e,proof_class=label,qnew=expected,quantity_unknown=why,cut=Z if expected is None else D(q0-expected)/D(q0));expectedrows.append(merged)
        if expected!=e['qnew']:changed.append(dict(layer=e['layer'],sid=sid,name=e['name'],decision_at=e['decision_at'],strict_q=e['qnew'],failed_only_q=expected,original_net=e['net'],strict_anchor=e['previous_completed_mobile_cycle'],failed_anchor=prev))
    scopes={'ALL':expectedrows}
    if ref=='2022_2024':
        scopes['2022_2023']=[x for x in expectedrows if x['opened'][:10]<='2023-12-29'];scopes['strict303_postOct8_newfills']=[x for x in expectedrows if x['opened'][:10]>'2024-10-08']
    for name,sr in scopes.items():
        r=results[ref][name];checkagg(sr,r['all'])
        for a,g in r['by_action'].items():checkagg([x for x in sr if x['action']==a],g)
    tails=read(P/(ref+'_FIXED_TAILS.json'));ids={x['layer'] for t in tails for x in t['matched_actual_No60_rows']};checkagg([x for x in expectedrows if x['layer'] in ids],results[ref]['fixed_tail_matches'])
    differences[ref]=dict(quantity_changed_rows=changed,scopes={k:results[ref][k]['all'] for k in scopes},fixed_tail_matches=results[ref]['fixed_tail_matches'])
output=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(checks),differences=differences,actual_data_price_domain_mismatches=logic_only,
    conclusion='The failure-only semantic reconciliation retains the stop-before-account result. New quantities are still baseline-path static sensitivity, never policy NAV.',
    source_script_sha256=manifest['script_sha256'],script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    code_note='Producer UNKNOWN_PRICE_DOMAIN branch depends on strict prior proof class; an older failed anchor crossing source domains would need an unconditional domain guard. The independent unconditional guard finds no mismatch in these actual mothers, so published numerical results are unaffected. Do not reuse code as general account logic without this guard.')
(O/'FAILURE_ONLY_AUDIT.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps(dict(status=output['status'],checks=checks,quantity_changes={k:len(v['quantity_changed_rows']) for k,v in differences.items()}),default=str,indent=2))
