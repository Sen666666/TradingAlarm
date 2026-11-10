"""Read-only saved-run binding audit. Never imports strategy code or unpickles.

The checkpoint opcode receipt records the already completed nonexecuting scan.
--rescan-pickle reproduces that scan, but is unnecessary for the default audit.
"""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import hashlib
import json
import pickletools

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parents[1]
RR = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
R29 = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R04 = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
RUNS = ENTRY/'trend_exit_controls_v1/runs/BASELINE'
BRIDGE_MANIFEST = RR/'rs-h1-execution-20261025/inputs-v2/input-manifest.json'
PACKAGE = RR/'a-share-selection-e0-20261024/inputs-v2/package.json'
RAW_CAP = RR/'a-share-selection-e0-20261024/downloads/current-cap-all/snapshot.json'
TERMS = ['company_cap_cny', 'SelectionFact', 'SelectionEvidence', 'snapshot_id',
         'A-roster22-resolved-nonempty-industry-tree22-cap24', 'observed_at',
         'selection.json', 'PoolLine']
INITIAL_SCAN = {
    '2022_2024': dict(opcodes=65317869, elapsed_seconds=31.12672599963844,
        checkpoint_sha256='7e328f82b84747a34191635d9e9c3777eebf0754bd1ca992129df0d77386cd98'),
    'strong': dict(opcodes=26772614, elapsed_seconds=12.485754707828164,
        checkpoint_sha256='013d8ec7d12a1a033782dedc6d3af6a56bda518a923f0b6983ae787331d9a908'),
}
SOURCES = [
    (ENTRY/'trend_exit_controls_v1/run_control.py', [(14,29)]),
    (R04/'pvr_pool_feasibility/native_adapter.py', [(27,58)]),
    (R29/'pvr-slot1-native-readiness-20261101/native_rank.py', [(115,119),(142,149)]),
    (R29/'case-stage-ledger-20261031/v3/launch_v3.py', [(14,17),(35,38),(53,57),(61,76)]),
    (R04/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/loader_2024.py', [(31,35),(46,61)]),
    (R29/'case-stage-ledger-20261031/wire.py', [(7,10)]),
    (R29/'mainline-I-quarter-2025Q3-20261031/adapter.py', [(6,12),(58,77)]),
    (RR/'tech-finite-compound-20261026/code/common.py', [(6,15)]),
    (RR/'rs-h1-execution-20261025/code/current_pool_bridge.py', [(52,58),(397,421),(433,439)]),
    (RR/'rs-h1-execution-20261025/code/current_fixed_pool.py', [(60,101),(147,162)]),
    (RR/'rs-h1-execution-20261025/code/sector_stock_admission.py', [(185,220)]),
    (RR/'actual-risk-recovery-20261027/code/engine.py', [(31,47)]),
    (RR/'a-share-selection-e0-20261024/code/build_inputs.py', [(23,35)]),
    (R29/'_shared/research_output_io.py', [(86,113)]),
]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def main(rescan_pickle=False):
    manifest = read(BRIDGE_MANIFEST)
    ref = manifest['selection']
    selected = Path(ref['path'])
    assert sha(selected) == ref['sha256']
    selection = read(selected)
    by = {r['security_id']: r for r in selection['lines']}
    raw = read(RAW_CAP)
    rawby = {r['code']: r for r in raw['rows']}
    current_leafs = [BRIDGE_MANIFEST, selected, PACKAGE, RAW_CAP] + [p for p,_ in SOURCES]
    all_binding = {}
    result = {}
    dump_scan = {}
    for window in ['2022_2024', 'strong']:
        d = RUNS/window
        metadata, provenance, checkpoint = [read(d/f) for f in
            ['RUN_METADATA.json','checkpoint.provenance.json','checkpoint.json']]
        sf = metadata['source_freeze']
        statuses = [dict(path=p, expected_sha256=h, actual_sha256=sha(p), matches=sha(p)==h)
                    for p,h in sf.items()]
        assert all(x['matches'] for x in statuses)
        assert sf == checkpoint['source_freeze']
        actual_cp_sha = sha(d/'checkpoint.pkl')
        assert actual_cp_sha == provenance['checkpoint_sha256'] == checkpoint['sha256']
        identity = metadata['input_identity']
        ids = identity.get('fixed_ids', identity.get('fixed_stock_ids'))
        sectors = identity.get('sectors', identity.get('sector_ids'))
        counts = Counter('MISSING_SELECTION' if sid not in by else
                         'UNKNOWN_CAP' if by[sid]['company_cap_cny'] is None else
                         'GT10BN' if by[sid]['company_cap_cny'] > 10_000_000_000 else
                         'NOT_GT10BN' for sid in ids)
        expected_known = {sid for sid,r in by.items()
                          if r['company_cap_cny'] is not None and r['company_cap_cny'] > 10_000_000_000}
        result[window] = dict(
            metadata_path=str(d/'RUN_METADATA.json'), metadata_sha256=sha(d/'RUN_METADATA.json'),
            provenance_path=str(d/'checkpoint.provenance.json'), provenance_sha256=sha(d/'checkpoint.provenance.json'),
            checkpoint_json_sha256=sha(d/'checkpoint.json'), checkpoint_actual_sha256=actual_cp_sha,
            checkpoint_hash_matches_generation_provenance=True,
            created_at_UTC=provenance['created_at_UTC'], last_completed_event=provenance['last_completed_event'],
            window_start=metadata['start'], window_end=metadata['end'], fixed_stock_count=len(ids),
            sector_count=len(sectors), source_freeze_count=len(sf), all_source_freeze_current_match=True,
            source_freeze=statuses, engine_identity=provenance['engine_identity'],
            current_context_leaf_directly_frozen={str(p): str(p) in sf for p in current_leafs},
            fixed_ids_current_loaded_selection_cap_counts=dict(counts),
            fixed_ids_equal_current_loaded_selection_known_gt10bn=set(ids)==expected_known,
            cap_value_or_cap_ref_in_input_identity=False,
            identity_comparison_scope='Saved original fixed IDs vs the current exact referenced selection file; not original per-value runtime logging.')
        all_binding.update(sf)
        cp_scan = dict(INITIAL_SCAN[window])
        assert cp_scan['checkpoint_sha256'] == actual_cp_sha
        cp_scan['method'] = 'pickletools.genops; opcode parsing only; no pickle.load/loads and no strategy imports'
        cp_scan['string_argument_substring_counts'] = {t:0 for t in TERMS}
        cp_scan['receipt_origin'] = 'Completed initial read-only scan in this audit; tied to verified checkpoint SHA'
        if rescan_pickle:
            n = 0
            hits = Counter()
            with (d/'checkpoint.pkl').open('rb') as f:
                for op,arg,pos in pickletools.genops(f):
                    n += 1
                    if isinstance(arg,str):
                        hits.update(t for t in TERMS if t in arg)
            assert n == cp_scan['opcodes'] and not hits
            cp_scan['reproduced_now'] = True
        book_path = d/'pair/B.json.gz'
        text = gzip.decompress(book_path.read_bytes())
        book_counts = {t:text.count(t.encode()) for t in TERMS}
        assert not any(book_counts.values())
        book = json.loads(text)
        dump_scan[window] = dict(checkpoint=cp_scan,
            book=dict(path=str(book_path), sha256=sha(book_path), uncompressed_bytes=len(text),
                      top_level_keys=list(book), literal_substring_counts=book_counts),
            limitation='Zero named-field/string occurrences supports absence of a directly recoverable cap/evidence dump; does not reconstruct a missing runtime SelectionFact object. Book intent.cap is a share-quantity cap, not company_cap_cny.')
    save('RUN_BINDINGS.json', result)
    save('SAVED_DUMP_SCAN.json', dump_scan)
    examples = []
    for sid in ['600000.SH','000620.SZ','300085.SZ','002583.SZ']:
        r = rawby[sid[:6]]
        examples.append(dict(security_id=sid, selection_company_cap_cny=by[sid]['company_cap_cny'],
            raw_3541450=r['raw_fields']['3541450'], equals_raw_3541450=by[sid]['company_cap_cny']==r['raw_fields']['3541450'],
            raw_market_timestamp=r['market_timestamp'], raw_historical_point_in_time=r['historical_point_in_time'],
            raw_request202_observed_at=r['observations']['202']['observed_at'],
            currency_certification_label=r['market_cap_currency']))
    package=read(PACKAGE)
    pref=package['bridge_manifest']
    save('CURRENT_REFERENCE_CHAIN.json', dict(
        evidence_level='Current source/transitive references and hashes; leafs not directly included in original run source_freeze',
        context_source=str(R29/'mainline-I-quarter-2025Q3-20261031/adapter.py')+':59',
        context_loads_package_json=False,
        context_loads_manifest=dict(path=str(BRIDGE_MANIFEST),actual_sha256=sha(BRIDGE_MANIFEST)),
        current_selection_ref=ref, selection_actual_sha256=sha(selected), selection_ref_matches=True,
        selection_header={k:v for k,v in selection.items() if k not in ['lines','all_roster_dispositions','industry_resolution_evidence']},
        selection_lines=len(by), selection_cap_counts=dict(Counter(
            'UNKNOWN' if r['company_cap_cny'] is None else 'GT10BN' if r['company_cap_cny']>10_000_000_000 else 'NOT_GT10BN'
            for r in by.values())),
        package_corroboration=dict(path=str(PACKAGE),sha256=sha(PACKAGE),bridge_manifest_ref=pref,
            current_referenced_manifest_sha256=sha(pref['path']), same_contents_as_context_manifest=sha(pref['path'])==sha(BRIDGE_MANIFEST)),
        raw_snapshot=dict(path=str(RAW_CAP),sha256=sha(RAW_CAP),rows=len(raw['rows']),
            header={k:v for k,v in raw.items() if k!='rows'}), predetermined_examples=examples))
    excerpts=[]
    inventory=[]
    for path,ranges in SOURCES:
        h=sha(path)
        inventory.append(dict(path=str(path),current_sha256=h,
            directly_in_original_run_source_freeze=str(path)in all_binding,
            original_run_expected_sha256=all_binding.get(str(path))))
        lines=path.read_text().splitlines()
        excerpts.append('\n'+str(path)+'\nSHA256 '+h+'\n')
        for lo,hi in ranges:
            excerpts.append('\n'.join(f'{i:5d} {lines[i-1]}' for i in range(lo,min(hi,len(lines))+1))+'\n')
    (HERE/'SOURCE_EXCERPTS.txt').write_text('\n'.join(excerpts))
    save('SOURCE_INVENTORY.json',inventory)
    print(json.dumps(dict(run_binding_counts={w:r['source_freeze_count'] for w,r in result.items()},
        fixed_ids_match_current_selection={w:r['fixed_ids_equal_current_loaded_selection_known_gt10bn'] for w,r in result.items()},
        selection_sha256=sha(selected),book_and_checkpoint_cap_named_fields_found=False),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--rescan-pickle',action='store_true')
    main(p.parse_args().rescan_pickle)
