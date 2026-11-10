from pathlib import Path
import sys,json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
F=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
sys.path[:0]=[str(F/'TradingAlarm/research'),str(F/'TradingAlarm')]
import ths_readonly as ths
O=Path(__file__).resolve().parents[1]/'special-hk-search-01';O.mkdir(exist_ok=False)
patterns=['4332','4333','4335','4336','4337','4338']
(O/'plan.json').write_text(json.dumps({'patterns':patterns,'max_requests':6,'endpoint':'8.134.69.102:9605','purpose':'resolve 6 official HK Trading Only Security native identifiers','snapshot_date':'2026-10-22'},indent=2))
_,m=ths.session_candidates('auto')[0]
results=[]
with ths.Connection(ths.SEARCH,m,interval=.4,max_requests=6,read_timeout=20) as c:
 for q in patterns:
  query,body,records=c.search(q)
  (O/(q+'.bin')).write_bytes(body)
  (O/(q+'.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
  exact=[r for r in records if r['code'] in [q,'HK'+q,'0'+q]]
  results.append({'query':q,'rows':len(records),'exact_code_matches':exact,'observed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'response_sha256':hashlib.sha256(body).hexdigest()})
(O/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False))
