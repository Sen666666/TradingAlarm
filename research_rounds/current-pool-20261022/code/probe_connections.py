"""Six bounded observed quote requests; never persists authentication frames."""
from pathlib import Path
import sys,json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

FORMAL=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
sys.path[:0]=[str(FORMAL/'TradingAlarm/research'),str(FORMAL/'TradingAlarm')]
import ths_readonly as ths
import ths_readonly_fu as fu

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'connections-01'
OUT.mkdir(exist_ok=False)
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
plan={'created_at':now(),'end':'20261022','max_requests':6,'symbols':{'9602':'USHA600000','9603':'UHKMHK0700'},'kinds':[200,210,211], 'algorithm_changes':0,'account_runs':0}
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
reports=[]
for node,symbol in plan['symbols'].items():
    conn=None; attempts=[]
    if node=='9603':
        conn,info=fu.open_fu(interval=.4,max_requests=3,read_timeout=15)
        attempts=info.get('attempts',[])
    else:
        for label,manager in ths.session_candidates():
            try:
                conn=ths.Connection(ths.QUOTE,manager,interval=.4,max_requests=3,read_timeout=15).open()
                break
            except ths.HandshakeRejected:
                attempts.append({'source':label,'error':'rejected_latched'})
            except ths.SessionUnavailable:
                attempts.append({'source':label,'error':'session_unavailable'})
            except ths.NetworkFailure:
                attempts.append({'source':label,'error':'network_failure'});break
    report={'node':node,'symbol':symbol,'attempts':attempts,'responses':[]}
    if conn is None:
        report['status']='unavailable'; reports.append(report);continue
    with conn:
        for kind in plan['kinds']:
            params={'market':symbol[:4]}
            if kind==200:params.update(codelist=symbol[4:],datatype='55')
            elif kind==210:params.update(code=symbol[4:],start=-9,end='20261022',datatype='1,7,8,9,11,13,19,74',period=16384)
            else:params.update(code=symbol[4:],start=0,end=0,datatype='1,471',period=16384)
            try:
                query,body,records=conn.quote(kind,**params)
                raw=OUT/f'{node}-{kind}.bin';raw.write_bytes(body)
                decoded=OUT/f'{node}-{kind}.json';decoded.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
                row={'kind':kind,'received_at':now(),'query':query,'body_sha256':hashlib.sha256(body).hexdigest(),'records':len(records or [])}
                if kind==210:
                    bars=ths.daily_bars(records);row.update(rows=len(bars),first=bars[0]['date'] if bars else None,last=bars[-1]['date'] if bars else None)
                report['responses'].append(row)
            except (ValueError,ths.NetworkFailure) as exc:
                report['responses'].append({'kind':kind,'error_type':type(exc).__name__})
                if isinstance(exc,ths.NetworkFailure):break
    report['requests']=conn.requests;report['status']='responses_saved';reports.append(report)
(OUT/'results.json').write_text(json.dumps({'finished_at':now(),'reports':reports},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(reports,ensure_ascii=False))
