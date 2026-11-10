"""Freeze review package only; never releases or starts the economic run."""
from pathlib import Path
import json,hashlib,time,sys,csv,platform,importlib.metadata
HERE=Path(__file__).resolve().parent;B=HERE.parent;R=B.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(name,v):
    with (HERE/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def main():
    assert read(HERE/'BUDGET_BOUNDARY_QA.json')['status']=='PASS'
    qa=HERE/'qa_attempt_05';result=read(qa/'RESULT.json');assert result['status']=='AUTHOR_PASS_PENDING_INDEPENDENT_REVIEW'
    deps=read(qa/'SOURCE_HASHES.json')
    old=B/'known_halt_contract_v1';candidate=B/'known_halt_dividend_candidate_v1'
    deps.update(read(candidate/'PROTECTED_INPUT_HASHES_BEFORE.json'))
    deps.update(read(old/'RECOVERY_COHORT_CONTRACT_V2.json')['code_hashes'])
    for p,h in read(candidate/'AUTHOR_COMPLETION_SEAL.json')['files'].items():deps[str(candidate/p)]=h
    deps.update(read(B/'source_bridge_v1/SOURCE_MANIFEST.json')['sha256'])
    for directory in ['indexed_execution_v1','source_bridge_v1','execution_bridge_v1','shared_feasibility_v1','known_halt_contract_v1','known_halt_dividend_candidate_v1']:
        for p in (B/directory).glob('*.py'):deps.setdefault(str(p),sha(p))
    for p in [old/'RECOVERY_COHORT_CONTRACT_V2.json',old/'cohort_2022_recovery_v2/OUTPUT_SEAL.json',candidate/'AUTHOR_COMPLETION_SEAL.json',candidate/'DATE_ONLY_INDEX_ERRATUM_V1.md',candidate/'DATE_ONLY_INDEX_ERRATUM_V1_SEAL.json',B/'source_bridge_v1/SOURCE_MANIFEST.json']:
        deps[str(p)]=sha(p)
    assert sha(candidate/'AUTHOR_COMPLETION_SEAL.json')=='cb8bf5d8eb37d6fffc6eba20f52fb7e63d1f18f411eb8a231d7bafd7ddeb832c'
    assert sha(candidate/'DATE_ONLY_INDEX_ERRATUM_V1.md')=='e7de62219da68a769d5968342e16a164641f591e4d3291dcec97ce331a541cea'
    for p,h in deps.items():assert sha(p)==h,('Dependency changed',p)
    # Pin complete manifest as already included in deps; native loader checks each
    # consumed signal/facts/CP against it. No selecting or trimming universe rows.
    births=[]
    with (R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv').open() as f:
        births=[r for r in csv.DictReader(f) if r['window']=='2022' and r['event_type'] in ('A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR')]
    manifest=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    full_manifest=read(manifest);assert deps[str(manifest)]==sha(manifest)
    contract=dict(version='KNOWN_EVIDENCE_UNION_DIAGNOSTIC_V1',scope='RUN_2022_UNION_TO_FIRST_RESPONSIBILITY_UNKNOWN_ONCE',seed='1200000',start='2022-01-01',first_common_day='2022-01-04',birth_end='2022-12-31',end='2026-06-30',
        wall_seconds=900,peak_rss_bytes=6*1024**3,phase_stop_seconds=780,phase_stop_rss_bytes=5*1024**3,
        python=sys.executable,python_version=platform.python_version(),packages={p:importlib.metadata.version(p) for p in ('pandas','numpy','pyarrow')},
        financial_contract='Original daily eligibility, fees, sizing, AB/M3 permissions and NET80 convention unchanged',
        preserved_domain=dict(original_2022_birth_rows=len(births),original_2022_unique_birth_sids=len({r['sid'] for r in births}),full_stock_manifest_count=len(full_manifest),source_list_pruned=False),
        stop='First complete original OPEN/CLOSE containing new state or snapshot UNKNOWN plus actual assets/outstanding responsibility; all blockers at that phase retained',
        daily_only=True,force_liquidation=False,auto_evidence_repair_or_rerun=False,baseline_equivalence=False,
        dependencies=deps)
    save('RUN_CONTRACT.json',contract)
    attempts=[]
    for path in sorted(HERE.glob('qa_attempt_*')):
        failure=path/'FAILURE.json';res=path/'RESULT.json'
        attempts.append(dict(name=path.name,status='PASS' if res.exists() else 'FAILED',result=read(res) if res.exists() else read(failure)))
    save('ATTEMPT_HISTORY.json',dict(attempts=attempts,changes=[
        'Attempt 01: test wrongly expected freeze_unknown to mutate archived st. Production predicate already resolved lightweight UNKNOWN round_id to archive; fixed assertion and added positive/zero-liability cases.',
        'Attempt 02: reused conditional fixture exporter expected candidate_tape.audit. Added compatibility read-only property pointing at union tape, without widening original candidate domain.',
        'Attempt 03: passed 20+26+14, two slices and 68-day prefix. Final strengthened complete checkpoint writer and explicit failure statuses tested in attempt04; reviewer-requested absent-archive fail-closed and OPEN source-evidence allowlist then tested in attempt05.'
    ],old_files_not_written=True,diagnostic_economic_runs=0))
    save('AUTHOR_PRE_RUN_READOUT.json',dict(status='AUTHOR_PASS_PENDING_INDEPENDENT_REVIEW',qa=result,dependency_count=len(deps),all_dependencies_verified=True,
        prefix=read(qa/'PREFIX_COMPARISON.json'),known_original_EVENT_digest='c3302bfe1ad076cfbafbb9aaf44c41a1dc0f42bb1b0279e94a88f27c4eba85a7',
        lifecycle_boundary='UNKNOWN is a lightweight live-state; original archives remain intact and authoritative for responsibility. Checkpoint preserves both and existing alias identities.',
        review_attention=['Union mapping and old permission preservation','Evidence clock and future coordinate isolation','Lightweight UNKNOWN archive/layer/claim/order lookup','Same-phase complete stopping and all blockers order','Lossless checkpoint and OPEN report future-close isolation','Fail-closed fixed-byte gate, durable single-use lock and hard budget'],
        new_economic_runs=0,frozen_at_utc=time.time()))
    files=[p for p in HERE.rglob('*') if p.is_file() and p.name not in ('PRE_RUN_STAGE_SEAL.json','INDEPENDENT_REVIEW_RELEASE.json')]
    save('PRE_RUN_STAGE_SEAL.json',{str(p.relative_to(HERE)):sha(p) for p in sorted(files)})
    print(json.dumps(dict(stage_sha256=sha(HERE/'PRE_RUN_STAGE_SEAL.json'),files=len(files),dependencies=len(deps),qa=result),indent=2))
if __name__=='__main__':main()
