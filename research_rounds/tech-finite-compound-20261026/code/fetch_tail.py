"""Bounded incremental retrieval from the project's already authorized THS nodes."""
from pathlib import Path
import csv,json,subprocess,sys

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def main():
    out=HERE/'tail-v3';out.mkdir(parents=True,exist_ok=False)
    roster=list(csv.DictReader((ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').open()))
    meta=json.loads((ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/metadata.json').read_text())
    master={r['symbol']:r for r in csv.DictReader((ROOT/'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv').open())}
    items=[dict(symbol=master[r['symbol']]['ths_symbol'],node='9602',end='2026-10-26',earliest='2026-10-15',mode='tail',rights=True,max_pages=1) for r in roster]
    chunks=[items[:24]]+[items[i:i+100] for i in range(24,len(items),100)]
    sectors=sorted({r['sector_id'] for r in roster})
    chunks.append([dict(symbol=s,node='9603',end='2026-10-26',earliest='2026-10-15',mode='tail',rights=False,max_pages=1) for s in sectors])
    results=[];stopped=set()
    for i,chunk in enumerate(chunks):
        if chunk[0]['node'] in stopped:continue
        plan=dict(schema_version=1,items=chunk,max_requests=len(chunk)*2+2,request_interval_seconds=.3,
                  read_timeout_seconds=15,session_preference='snapshot')
        p=out/f'plan-{i:02d}.json';p.write_text(json.dumps(plan,indent=2)+'\n');target=out/f'batch-{i:02d}'
        cmd=[sys.executable,str(ROOT/'research_rounds/current-pool-20261022/code/history_batch.py'),'--plan',str(p),'--output',str(target),'--research-root','/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research']
        with (out/f'batch-{i:02d}.log').open('x') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
        q=target/'run-summary.json';receipt=json.loads(q.read_text()) if q.exists() else dict(error='process_failed',returncode=r.returncode)
        results.append(dict(batch=i,receipt=receipt));stopped.update(receipt.get('stopped_nodes_this_run',[]))
        print(json.dumps(results[-1]),flush=True)
        if r.returncode:break
    (out/'retrieval.json').write_text(json.dumps(dict(results=results,stopped_nodes=sorted(stopped),requested_end='2026-10-26',new_full_history_download=False),indent=2)+'\n')

if __name__=='__main__':main()
