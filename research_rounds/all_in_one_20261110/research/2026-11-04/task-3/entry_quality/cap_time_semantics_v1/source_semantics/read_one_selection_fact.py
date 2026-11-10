"""One real pure SelectionFact, three clocks. No account/runner/model imports."""
from pathlib import Path
import hashlib,importlib.util,json,sys
from datetime import datetime,timedelta

OUT=Path(__file__).resolve().parent
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
CODE=RR/'rs-h1-execution-20261025/code';INPUT=RR/'a-share-selection-e0-20261024/inputs-v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def pure_module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
    A=pure_module('sector_stock_admission',CODE/'sector_stock_admission.py')
    F=pure_module('cap_audit_current_fixed_pool',CODE/'current_fixed_pool.py')
    selection=load(INPUT/'selection.json');manifest=load(INPUT/'input-manifest.json')
    assert Path(manifest['selection']['path'])==INPUT/'selection.json'
    assert sha(INPUT/'selection.json')==manifest['selection']['sha256']
    row=next(r for r in selection['lines']if r['security_id']=='000620.SZ')
    evidence=F.SelectionEvidence(selection['snapshot_id'],sha(INPUT/'selection.json'),datetime.fromisoformat(selection['observed_at']),selection['source_id'])
    fact=F.SelectionFact('company_cap_cny',row['company_cap_cny'],evidence)
    ordinary=A.Fact(row['company_cap_cny'],evidence.observed_at,evidence.observed_at,observed_at=evidence.observed_at,basis='snapshot',source_id='comparison:same_cap_same_observed_at')
    assert not hasattr(evidence,'read')
    calls=[]
    for day in ['2024-09-24','2026-01-15','2026-10-26']:
        at=datetime.fromisoformat(day+'T15:10:00+08:00');execution=(at+timedelta(days=1)).replace(hour=9,minute=30)
        clock=A.Clock(at,execution,at.date())
        z={'decision_at':at.isoformat(),'earliest_execution_at':execution.isoformat(),'selection_read':fact.read(clock),'selection_read_for_execution':fact.read(clock,for_execution=True),'ordinary_snapshot_fact_read':ordinary.read(clock),'ordinary_snapshot_fact_read_for_execution':ordinary.read(clock,for_execution=True)}
        assert z['selection_read']==z['selection_read_for_execution']==16617237000
        expected=None if at<evidence.observed_at else 16617237000
        assert z['ordinary_snapshot_fact_read']==z['ordinary_snapshot_fact_read_for_execution']==expected
        calls.append(z)
    snapshotpath=RR/'a-share-selection-e0-20261024/downloads/current-cap-all/snapshot.json'
    snapshot=load(snapshotpath);raw=next(r for r in snapshot['rows']if r['symbol']=='USZA000620')
    assert raw['raw_fields']['3541450']==row['company_cap_cny'] and raw['market_timestamp']is None and raw['historical_point_in_time']is False
    receiptpath=snapshotpath.parent/raw['observations']['202']['response_attempt']/'receipt.json'
    receipt=load(receiptpath)
    assert receipt['received_at']==raw['observations']['202']['observed_at']
    assert receipt['sha256']==raw['observations']['202']['response_sha256']
    construction=load(INPUT/'construction-summary.json')
    files=[CODE/'current_fixed_pool.py',CODE/'sector_stock_admission.py',CODE/'current_pool_bridge.py',INPUT/'selection.json',INPUT/'input-manifest.json',INPUT/'construction-summary.json',snapshotpath,receiptpath,RR/'a-share-selection-e0-20261024/code/build_inputs.py',RR/'a-share-selection-e0-20261024/code/repair_classification.py',RR/'current-pool-20261022/code/snapshot_batch.py',Path(__file__)]
    result={'status':'PASS_BOUNDED_CURRENT_SELECTION_TIME_SEMANTICS','execution_scope':'Original pure field classes only; one SelectionFact and one ordinary Fact comparison. No bundle/account/runner/model/eligibility execution.','module_paths':{'selection':str(Path(F.__file__).resolve()),'admission':str(Path(A.__file__).resolve())},'sample_security':row,'evidence_observed_at':evidence.observed_at.isoformat(),'selection_evidence_has_read_method':False,'clock_calls':calls,'data_times':{'selection_observed_at':selection['observed_at'],'selection_roster_asof':selection['roster_asof'],'selection_cap_observed_date':selection['cap_observed_date'],'selection_market_timestamp_unknown':selection['market_timestamp_unknown'],'snapshot_updated_at':snapshot['updated_at'],'snapshot_as_of_date_label':snapshot['as_of_date_label'],'label_is_not_observed_timestamp':snapshot['label_is_not_observed_timestamp'],'raw_sample_cap_receipt_received_at':receipt['received_at'],'raw_sample_market_timestamp':raw['market_timestamp'],'raw_sample_historical_point_in_time':raw['historical_point_in_time'],'construction_created_at':construction['created_at'],'selection_has_createdAt':('createdAt'in selection),'sample_raw_has_createdAt':('createdAt'in raw)},'unknown_cap_symbols':[r['security_id']for r in selection['lines']if r['company_cap_cny']is None],'source_findings':['SelectionEvidence is manifest identity with aware observed_at; there is no SelectionEvidence.read.','SelectionFact.read directly returns value, ignoring decision/execution clocks by explicit current-pool historical-development design; source date is preserved, not backdated.','Ordinary Fact gates known_at by decision cut even for execution reads, and validity by decision or earliest-execution time. Snapshot observed_at is also checked.','Rank.read gates known/observation timestamps and exact session date, rounds12. It has no for_execution argument.','build_security wraps issuer/sector/cap in SelectionFact; dynamic readiness/trend use ordinary Fact, buy_allowed combines selected_market with historical market Fact.','Cap unknown remains None. Active S0 uses None if cap unknown else cap>10bn; any unknown yields eligibility.q=None even alongside other false checks.','build_inputs reads snapshot raw field3541450; invalid/nonpositive rawcap becomes None; cap/date are not reconstructed from historical stock closes. It keeps currentcap>10bn or unknown and freezes selection.','Snapshot updated_at is local export time; per-symbol observed_at inherits response receipt received_at. Roster/asof labels are separate; construction created_at is generation time. No actual exchange price timestamp is supplied by the sample.'], 'scope_limits':['Code semantics and referenced inputs-v2 identity only; this audit does not authenticate every sealed No60 account runtime import/manifest binding. Coordinate with the separate runtime-lineage owner for that claim.','The source explicitly declares current surviving stock/cap/industry historical development, not PIT/unseen. Do not misdescribe its deliberate research override as an accidental ordinary Fact time-clock bypass, and do not promote it to historical observable cap.','No current cap update, earlier historical cap, original-account eligibility result, source truth or economic certification is established.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_accounts':0,'new_runners':0,'new_models':0,'network_calls':0,'remaining_blocks':[]}
    (OUT/'ONE_FIELD_READ_EVIDENCE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'clock_calls':calls,'sha256':sha(OUT/'ONE_FIELD_READ_EVIDENCE.json')},ensure_ascii=False))
if __name__=='__main__':main()
