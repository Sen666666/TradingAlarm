"""Current snapshot fields from saved shipped-client request metadata."""
from pathlib import Path
import sys,json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
F=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
sys.path[:0]=[str(F/'TradingAlarm/research'),str(F/'TradingAlarm')]
import ths_readonly as ths
import ths_readonly_fu as fu
O=Path(__file__).resolve().parents[1]/'current-cap-probe-01';O.mkdir(exist_ok=False)
plan={'created_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'source':str(F/'artifacts/ths-analysis-20261016/findings.json'),'source_sha256':hashlib.sha256((F/'artifacts/ths-analysis-20261016/findings.json').read_bytes()).hexdigest(),'metadata_keys':{'TOTALCAPITAL':2479,'CAPITAL':2480,'LTSZ':3475914,'ZSZ':3541450},'queries':[{'node':'9603','id':202,'market':'UHKM','codelist':'HK0700,HK2318','datatype':'2942,1771976,3475914,3541450'},{'node':'9603','id':200,'market':'UHKM','codelist':'HK0700,HK2318','datatype':'10,55,2479,2480'},{'node':'9602','id':202,'market':'USHA','codelist':'600000,601318','datatype':'2942,1771976,3475914,3541450'},{'node':'9602','id':200,'market':'USHA','codelist':'600000,601318','datatype':'10,55,2479,2480'}],'changes_from_template':'verified market and codelist substitution for current A/H samples; id200 uses observed names/price request with documented share fields','max_requests':4,'account_runs':0}
(O/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
results=[]
for node in ['9603','9602']:
 conn=None
 if node=='9603':conn,info=fu.open_fu(interval=.4,max_requests=2,read_timeout=15)
 else:
  for label,manager in ths.session_candidates():
   try:conn=ths.Connection(ths.QUOTE,manager,interval=.4,max_requests=2,read_timeout=15).open();break
   except (ths.HandshakeRejected,ths.SessionUnavailable,ths.NetworkFailure):break
 if conn is None:results.append({'node':node,'status':'unavailable'});continue
 with conn:
  for i,p in enumerate(plan['queries']):
   if p['node']!=node:continue
   try:
    q,b,records=conn.quote(p['id'],**{k:v for k,v in p.items() if k not in ['node','id']})
    (O/f'{i:02d}.bin').write_bytes(b);(O/f'{i:02d}.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    results.append({'node':node,'request':q,'body_sha256':hashlib.sha256(b).hexdigest(),'rows':len(records or []),'records':records})
   except (ValueError,ths.NetworkFailure) as exc:
    results.append({'node':node,'kind':p['id'],'error_type':type(exc).__name__});break
(O/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False))
