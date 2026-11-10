"""Bounded gold identifier discovery using the already-authorized THS session."""
from pathlib import Path
import json,sys,datetime,hashlib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'TradingAlarm'))
from search import SearchClient
from sessions import SessionManager,DEFAULT_PREFERENCES
def main():
    plan={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'purpose':'Identify the gold futures/index underlying the user screenshot; refresh only gold series and compare causal signal timing. No accounts, no changes to existing algorithms.',
      'chart_period':['2025-01-01','2026-10-23'],'warmup_start':'2024-01-01',
      'search_patterns':['黄金','AU'],'search_max_requests':2,'search_endpoint':'8.134.69.102:9605',
      'history_max_series':5,'history_max_pages_per_series':2,'history_max_requests':10,
      'history_endpoints':['119.3.43.91:9602','119.3.4.152:9603'],
      'scope':'At most four native futures/spot/index identity candidates plus existing 518880 proxy, raw OHLCV only, reuse local history and keep overlap differences. No broad refresh, no third-party credentials.',
      'unknowns':'Screenshot says commodity futures/gold, index pricing; no contract ID or roll rule. Candidate identity must be checked, ETF cannot be called the same instrument.'}
    with (HERE/'data-plan.json').open('x') as f:json.dump(plan,f,ensure_ascii=False,indent=2)
    manager=SessionManager(ROOT/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
    client=SearchClient(manager);result=[]
    for pattern in plan['search_patterns']:
        try:
            matches=client.search(pattern)
            row={'query':pattern,'status':'ok','matches':[{k:r[k] for k in ['symbol','code','name','market']} for r in matches]}
        except Exception as e:row={'query':pattern,'status':'failed','error_type':type(e).__name__}
        result.append(row)
        (HERE/'identifier-search.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        if row['status']=='failed':break
if __name__=='__main__':main()
