"""Translate the offline cache plan to the shared collector schema; no network."""
from pathlib import Path
import argparse, csv, hashlib, importlib.util, json


def encoded(x):
    return (json.dumps(x, ensure_ascii=False, indent=2) + '\n').encode()


def run(prepared, out, collector, completed_batch=None):
    requests = json.loads((prepared/'history-request-plan.json').read_text())['requests']
    spec = importlib.util.spec_from_file_location('history_batch_offline', collector)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    out.mkdir(parents=True, exist_ok=False)
    batches=[]; skip=set()
    if completed_batch:
        for file in (completed_batch/'checkpoints').glob('*.json'):
            cp=json.loads(file.read_text())
            history=json.loads((completed_batch/'history'/file.name).read_text())
            if cp['history_status']=='complete' and cp['rights_status']=='received' and history['requested_end']=='20261022':
                skip.add(cp['symbol'])
    groups=[('01-tail-and-new', [r for r in requests if r['kind']!='head_availability_probe' and r['ths_symbol'] not in skip]),
            ('02-start-boundary', [r for r in requests if r['kind']=='head_availability_probe'])]
    for group, rows in groups:
        for offset in range(0,len(rows),100):
            chunk=rows[offset:offset+100]
            if any(not r['ths_symbol'] for r in chunk): raise ValueError('Unresolved native symbol')
            items=[dict(symbol=r['ths_symbol'], node='9602', end=r['end'], earliest=r['earliest'],
                        mode='tail' if r['kind']=='tail_with_overlap' else 'full',
                        rights=group=='01-tail-and-new', max_pages=r['max_pages']) for r in chunk]
            plan=dict(schema_version=1, items=items,
                      max_requests=sum(r['max_pages']+int(r['rights']) for r in items),
                      request_interval_seconds=0.3, session_preference='auto')
            module.validate_plan(plan)
            name=f'{group}-{offset//100+1:03d}.json'; data=encoded(plan)
            (out/name).write_bytes(data)
            batches.append(dict(path=str((out/name).resolve()), group=group, securities=len(items),
                                max_requests=plan['max_requests'],sha256=hashlib.sha256(data).hexdigest()))
    index=dict(status='offline_validated_not_executed', network_requests=0,
               prepared=str(prepared.resolve()),collector=str(collector.resolve()),
               collector_sha256=hashlib.sha256(collector.read_bytes()).hexdigest(),
               batches=batches, batch_count=len(batches),securities_in_tail_and_new=len(groups[0][1]),
               securities_in_start_boundary=len(groups[1][1]),
               total_max_requests=sum(b['max_requests'] for b in batches),
               skipped_completed_tail_symbols=sorted(skip),completed_batch=str(completed_batch.resolve()) if completed_batch else None,
               rights_policy='id211 once in each tail/new symbol request; received is not a complete economic action ledger',
               ordering='Pilot native markets first; then 01 tail/new, then 02 source-start boundary. No source response is synthesized.',
               node_caveat='9602 follows existing A-share fetcher; USHT/USTM must be proven by the separate pilot before broad execution.')
    (out/'index.json').write_bytes(encoded(index))
    return index


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--collector',type=Path,required=True);p.add_argument('--completed-batch',type=Path);a=p.parse_args()
    result=run(a.prepared,a.out,a.collector,a.completed_batch)
    print(json.dumps({k:v for k,v in result.items() if k!='batches'},ensure_ascii=False,indent=2))
