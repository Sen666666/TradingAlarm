"""101 declared sector trajectories, technical diagnostic only; no accounts."""
from pathlib import Path
import json
import current_pool_bridge as b

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'sector-data-v2'
OUT=ROOT/'sector-trajectories-v1'


def save(path,obj):
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')


def main():
    source=json.loads((RAW/'manifest.json').read_text())
    negative=[]
    for folder in ('crossnode-sector-fx-01','crossnode-control-01','hk-sector-gap-check-01'):
        for path in sorted((ROOT/'diagnostics'/folder).rglob('*')):
            if path.is_file():negative.append({'path':str(path.resolve()),'sha256':b.sha256(path)})
    save(OUT/'negative-evidence.json',{'scope':'One root-authorized 9602 diagnostic ended with NetworkFailure on its first industry request; later industry/FX requests not sent. Controller resumed A parent queue. No new requests in this task.',
        'first_symbol':'UFIH871116','requests_reserved':1,'later_not_sent':['UFIH871117','UFXBHKDCNY'],
        'parent_resumed_at':'2026-10-23T00:30:34.999017+08:00','meaning':'No successful alternative source obtained; does not prove the node can never supply this series',
        'sources':negative,'network_requests_by_this_task':0})
    protocol={'scope_date':'2026-10-22','kind':'sector_only_technical_diagnostic','accounts_run':0,'algorithm_changes':0,
        'raw_manifest':{'path':str((RAW/'manifest.json').resolve()),'sha256':b.sha256(RAW/'manifest.json')},
        'upstream_sha256':{name:b.sha256(path) for name,path in b.UPSTREAM.items()},'bridge_sha256':b.sha256(b.__file__),
        'segmentation':'Use already declared source-break segments, independently warm up unchanged numeric and participation per segment. Unknown between segments and before ready; target=0 during warmup is never bearish evidence.',
        'mode':'volume','ranking':'Frozen 4x63 observation RS; missing/stale rank preserved',
        'same_six_charts':json.loads((RAW/'PROTOCOL.json').read_text())['selection_frozen_before_chart_review'],
        'not_authorized':'No accounts; no 8k stock states; no live network; no parameter changes; no full-pool production claim'}
    save(OUT/'PROTOCOL.json',protocol)
    selection={'snapshot_id':'SECTOR-ONLY-TECHNICAL-20261022','observed_at':'2026-10-22T23:49:26.064622+08:00',
        'source_id':'Current THS same-source industry maps; empty stock selection deliberately prevents account interpretation', 'lines':[]}
    save(OUT/'selection.json',selection)
    records=[];mapping={}
    for row in source['series']:
        record={'series_id':row['symbol'],'kind':'sector_index','status':'ready','currency':'INDEX_POINTS',
                'source_start':row['first'],'volume_unit':'source_index_units','price_adjustment':'raw',
                'close_available_time':'15:05:00' if row['market']=='A' else '16:10:00',
                'raw':{'path':row['bars']['path'],'sha256':row['bars']['sha256']},
                'adjustment':{'method':'unadjusted_index'},'segments':[
                    dict(start=p['start'],end=p['end'],reason='Reviewed source continuity boundary; diagnostic only')
                    for p in row['proposed_segments']]}
        records.append(record);mapping[row['sector_id']]=row['symbol']
    manifest={'schema_version':1,'scope_date':'2026-10-22','research_basis':b.RESEARCH_BASIS,
              'upstream_sha256':protocol['upstream_sha256'],
              'selection':{'path':str((OUT/'selection.json').resolve()),'sha256':b.sha256(OUT/'selection.json')},
              'series':records,'sector_series':mapping,'purpose':'101 industry-only technical trajectories; no stock universe and no economic admission'}
    save(OUT/'input-manifest.json',manifest)
    summary=b.write_bundle(b.load_bundle(OUT/'input-manifest.json',technical_sample=True),OUT/'prepared')
    print(json.dumps({'series':len(summary['series']),'blocked':sum(bool(x['blocked_reason']) for x in summary['series']),
                      'accounts_run':0,'production_signal_ready':summary['signal_ready']}))

if __name__=='__main__':main()
