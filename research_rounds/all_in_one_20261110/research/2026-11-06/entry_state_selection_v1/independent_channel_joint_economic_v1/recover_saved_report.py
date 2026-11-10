"""Read-only saved-ledger report recovery. No consumer/run/reset/finalize call.

Only representation repair: absent and null native keys are equivalent; literal
date fields are canonical calendar-day Timestamps. Nonempty fields are retained.
Frozen code, ledgers, prior failure record and unique run lock are never edited.
"""
from pathlib import Path
from types import SimpleNamespace as NS
from collections import defaultdict, Counter
import argparse
import hashlib
import json
import math
import re
import time
import pandas as pd

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def date_value(value):
    text=str(value)
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[ T]00:00:00(?:\.0+)?)?',text),('NON_LITERAL_OR_INTRADAY_DATE',text)
    stamp=pd.Timestamp(text)
    assert stamp==stamp.normalize(),text
    return stamp


def normalized_record(row):
    out={}
    for key,value in row.items():
        if value is None or (isinstance(value,float) and math.isnan(value)):
            continue
        if (key=='day' or key.endswith('_day') or key.endswith('_date')) and isinstance(value,(str,pd.Timestamp)):
            value=date_value(value)
        out[key]=value
    return out


def csv_rows(path):
    frame=pd.read_csv(path,float_precision='round_trip',low_memory=False)
    return [normalized_record(r) for r in frame.to_dict('records')]


def verify_manifest(directory):
    manifest=read(directory/'OUTPUT_HASHES.json')
    for name,digest in manifest.items():
        assert sha(directory/name)==digest,('SAVED_OUTPUT_HASH_DRIFT',str(directory/name))
    return manifest


def snapshot(directory, evidence, arm):
    rounds=[r for r in csv_rows(directory/'ROUNDS.csv') if r['arm']==arm]
    ids={r['round_id'] for r in rounds}
    actions=[r for r in csv_rows(directory/'ACTIONS.csv') if r['round_id'] in ids]
    claims=[normalized_record(r) for r in read(directory/'CLAIMS.json') if r['owner_round_id'] in ids]
    archives={}
    for r in rounds:
        lane=r.get('owner_lane','AB')
        r['owner_lane']=lane
        archives[r['round_id']]=dict(owner_lane=lane,cash=r.get('cash_after_payouts'),
            receivable=r.get('receivable_after_payouts'),last_known_mark_day=r.get('last_known_mark_day'),
            last_raw_close=r.get('last_raw_close'),core=r.get('core_qty',0),add=r.get('add_qty',0))
    s=NS(rounds=rounds,actions=actions,claims=claims,archives=archives,raw={},ev=evidence.ev)
    for name in ('manifest','getmeta','fee','local_actions','read','sha','EVENT_AT','END','cal'):
        setattr(s,name,getattr(evidence,name))
    return s


def tuples(value):
    return tuple(tuples(x) for x in value) if isinstance(value,list) else value


class SavedBook:
    def __init__(self,value):
        self._responsibility=value['responsibility']
        self.events=value['events']
        self.parents={}
        for role,p in value['parents'].items():
            target=dict(p['target'])
            target['role']=NS(value=target['role'])
            target['signal_receipt_id']=tuples(target['signal_receipt_id'])
            target['root_id']=tuples(target['root_id'])
            self.parents[role]=NS(target=NS(**target),filled_F=p['filled_F'])
    def responsibility(self):return dict(self._responsibility)


def group(rows,key):
    d=defaultdict(list)
    for r in rows:d[r[key]].append(r)
    return d


def independent_retained_check(b,j):
    br={r['event_id']:r for r in b.rounds}
    jr={r['event_id']:r for r in j.rounds if r['owner_lane']=='AB'}
    ba,ja=group(b.actions,'round_id'),group(j.actions,'round_id')
    bc,jc=group(b.claims,'owner_round_id'),group(j.claims,'owner_round_id')
    action_fields=sorted({k for a in b.actions+j.actions for k in a if k not in {'round_id','arm'}})
    claim_fields=['sid','economic_event_id','evidence_version','record_date','inventory_snapshot_day',
        'snapshot_kind','state','record_q','core_record_q','exitpending','amount','core_amount',
        'recognized','settled','ex_date','pay_date','d_cash']
    exit_fields=['status','exit_day','exit_price','exit_reason']
    mismatches=[]
    def projected(rows,fields):
        return [{k:r[k] for k in fields if k in r} for r in rows]
    for eid in sorted(set(br)&set(jr)):
        left,right=br[eid],jr[eid]
        for kind,l,r,fields in [('actions',ba[left['round_id']],ja[right['round_id']],action_fields),
                ('claims',bc[left['round_id']],jc[right['round_id']],claim_fields),
                ('exit',[left],[right],exit_fields)]:
            if projected(l,fields)!=projected(r,fields):
                mismatches.append(dict(event_id=eid,kind=kind,left=projected(l,fields),right=projected(r,fields)))
    return dict(retained_events=len(set(br)&set(jr)),mismatch_count=len(mismatches),mismatches=mismatches,
        action_columns=action_fields,claim_economic_columns=claim_fields,exit_columns=exit_fields,
        comparison='Exact native values after missing-key omission and literal calendar-day normalization; only arm/round identities excluded')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--window',choices=['2022','2024'],required=True)
    args=parser.parse_args();start=time.monotonic();dest=ROOT/('economic_'+args.window)
    assert (dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),'NO_COMPLETED_SAVED_LOOP'
    names=['COMPARISON_REPORT_RECOVERED.json','CORE_SUMMARY_RECOVERED.json','REPORT_RECOVERY_QA.json']
    assert not any((dest/n).exists() for n in names),'RECOVERY_OUTPUT_EXISTS_NO_OVERWRITE'
    protected=[ROOT/('ECONOMIC_RUN_ONCE_'+args.window+'.json'),dest/'FAILED_NO_RETRY.json']
    before={str(p):sha(p) for p in protected if p.exists()}
    auth=read(ROOT/'ROOT_ECONOMIC_AUTHORIZATION.json')
    assert sha(ROOT/'ROOT_ECONOMIC_AUTHORIZATION.json')==read(dest/'STARTED.json')['authorization_sha256']
    for name,digest in auth['code_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_CODE_DRIFT',name)
    for name,digest in auth['input_sha256'].items():assert sha(name)==digest,('FROZEN_INPUT_DRIFT',name)
    saved_manifest=verify_manifest(dest/'joint')
    audit_names=['PRICE_AUDIT.json','OFFER_AUDIT.json','AB_DECISION_AUDIT.json','EXECUTION_BOOKS.json','FROZEN_RESPONSIBILITIES.json','ECONOMIC_LOOP_COMPLETE.json']
    before.update({str(dest/name):sha(dest/name) for name in audit_names})
    print('RECOVERY_SOURCES_VERIFIED',flush=True)
    from baseline_regression import load_engine,BASE,CONFIG
    from report_adapter import build_comparison
    from run_economic import core_summary,save
    evidence=load_engine(args.window) # Static inputs/getmeta only, no consumer.
    folder,leaf,_,_=CONFIG[args.window];baseline_dir=BASE/folder/leaf
    baseline_manifest=verify_manifest(baseline_dir)
    baseline=snapshot(baseline_dir,evidence,'A_UNION_B')
    saved=snapshot(dest/'joint',evidence,'A_UNION_B_PLUS_PRICE')
    exact=independent_retained_check(baseline,saved)
    print('INDEPENDENT_RETAINED_AB',json.dumps(exact,default=str),flush=True)
    assert not exact['mismatches'],'SUBSTANTIVE_RETAINED_AB_DIFFERENCE_STOP'
    consumer=NS(s=saved,arm='A_UNION_B_PLUS_PRICE',states={},
        price_audit=[normalized_record(r) for r in read(dest/'PRICE_AUDIT.json')],
        offer_audit=[normalized_record(r) for r in read(dest/'OFFER_AUDIT.json')],
        ab_decision_audit=[normalized_record(r) for r in read(dest/'AB_DECISION_AUDIT.json')],
        books={rid:SavedBook(v) for rid,v in read(dest/'EXECUTION_BOOKS.json').items()})
    roster=pd.read_csv(ROOT.parent/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').sid.astype(str).tolist()
    assert len(roster)==len(set(roster))==1709
    report=build_comparison(baseline,consumer,roster,args.window)
    fatal={'ORIGINAL_AB_PERMITS_NOT_EXACT','RETAINED_AB_PATH_MISMATCH_REQUIRES_REVIEW'}
    assert not fatal.intersection(report['adapter_blockers']),('REPRESENTATION_REPAIR_INSUFFICIENT',report['adapter_blockers'])
    report['recovery_provenance']=dict(saved_ledger_only=True,no_new_consumer_execution=True,
        missing_null_keys_omitted=True,nonempty_fields_preserved=True,literal_dates_normalized=True,
        saved_exit_protection_not_available='UNKNOWN_NOT_RECONSTRUCTED',independent_retained_ab=exact)
    summary=core_summary(report)
    for p,digest in before.items():assert sha(p)==digest,('PROTECTED_INPUT_CHANGED',p)
    verify_manifest(dest/'joint');verify_manifest(baseline_dir)
    for name,digest in auth['code_sha256'].items():assert sha(ROOT/name)==digest
    save(dest/names[0],report);save(dest/names[1],summary)
    save(dest/names[2],dict(status='PASS_POSTERIOR_SAVED_LEDGER_RECOVERY',elapsed_seconds=time.monotonic()-start,
        recovered_script_sha256=sha(__file__),frozen_code_sha256=auth['code_sha256'],
        all_frozen_inputs_verified=len(auth['input_sha256']),saved_manifest=saved_manifest,
        baseline_manifest=baseline_manifest,protected_unchanged=before,retained_ab_exact=exact,
        new_economic_runs=0,consumer_calls=0,report_sha256=sha(dest/names[0]),summary_sha256=sha(dest/names[1])))
    print('RECOVERED_CORE_READY',json.dumps(summary,ensure_ascii=False,default=str),flush=True)


if __name__=='__main__':main()
