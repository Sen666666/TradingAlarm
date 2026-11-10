"""Delta-only data for the unchanged 1709-stock/90-industry RS-H1 reference."""
from pathlib import Path
import csv,json,subprocess,sys,time
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def main():
    limit=time.time()+900
    while not (HERE/'tail-v3/retrieval.json').exists():
        if time.time()>limit:raise RuntimeError('prior bounded collection did not finish')
        time.sleep(1)
    previous=json.loads((HERE/'tail-v3/retrieval.json').read_text());stopped=set(previous['stopped_nodes'])
    out=HERE/'reference-tail';out.mkdir(exist_ok=False)
    roster=list(csv.DictReader((ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').open()))
    core={r['symbol'] for r in roster};core_sectors={r['sector_id'] for r in roster}
    selection=json.loads((ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/selection.json').read_text())
    master={r['symbol']:r for r in csv.DictReader((ROOT/'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv').open())}
    remaining=sorted(x['security_id'] for x in selection['lines'] if (x.get('company_cap_cny') or 0)>1e10 and x['security_id'] not in core)
    records=json.loads((ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json').read_text())['series']
    sectors=sorted(r['series_id'] for r in records if r['kind']=='sector_index' and r['series_id'] not in core_sectors)
    items=[dict(symbol=master[s]['ths_symbol'],node='9602',end='2026-10-26',earliest='2026-10-15',mode='tail',rights=True,max_pages=1) for s in remaining]
    chunks=[items[:24]]+[items[i:i+100] for i in range(24,len(items),100)]
    chunks.append([dict(symbol=s,node='9603',end='2026-10-26',earliest='2026-10-15',mode='tail',rights=False,max_pages=1) for s in sectors])
    receipts=[]
    for i,chunk in enumerate(chunks):
        if chunk[0]['node'] in stopped:continue
        plan=dict(schema_version=1,items=chunk,max_requests=len(chunk)*2+2,request_interval_seconds=.3,read_timeout_seconds=15,session_preference='snapshot')
        p=out/f'plan-{i:02d}.json';p.write_text(json.dumps(plan,indent=2)+'\n');target=out/f'batch-{i:02d}'
        cmd=[sys.executable,str(HERE/'code/delta_batch.py'),'--plan',str(p),'--output',str(target),'--research-root','/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research']
        with (out/f'batch-{i:02d}.log').open('x') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
        q=target/'run-summary.json';rc=json.loads(q.read_text()) if q.exists() else dict(error='process_failed',returncode=r.returncode)
        receipts.append(dict(batch=i,receipt=rc));stopped.update(rc.get('stopped_nodes_this_run',[]));print(json.dumps(receipts[-1]),flush=True)
        if r.returncode:break
    (out/'retrieval.json').write_text(json.dumps(dict(results=receipts,stopped_nodes=sorted(stopped),requested_end='2026-10-26',reference_only=True,stocks=len(remaining),industries=len(sectors),new_full_history_download=False),indent=2)+'\n')
if __name__=='__main__':main()
