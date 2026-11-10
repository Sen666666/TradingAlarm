"""One exact observed read-only request; existing owner snapshot; no ticket output."""
import argparse
import hashlib
import json
import signal
import sys
from pathlib import Path
from datetime import datetime

REPO = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
sys.path.insert(0, str(REPO/'TradingAlarm/research'))
import ths_readonly as ths

def deadline(*_):
    raise TimeoutError('bounded metadata deadline')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    raw_plan=args.plan.read_bytes();plan=json.loads(raw_plan)
    request=plan['native_request']
    assert request['endpoint']==list(ths.QUOTE)
    assert request['kind']==211
    assert request['params']==dict(market='USZA',code='300033',start=-1,end=0,datatype='1,899,900',period=16384,fuquan='Q')
    assert plan['budget']['native_this_step_max']==1
    assert plan['budget']['native_before']+1<=plan['budget']['native_parent_limit']
    args.out.mkdir(parents=True,exist_ok=False)
    report={'started_at':datetime.now().astimezone().isoformat(),'plan_sha256':hashlib.sha256(raw_plan).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'requests':[],'credential_values_logged':False}
    conn=None
    signal.signal(signal.SIGALRM,deadline)
    try:
        signal.alarm(35)
        manager=ths.SessionManager(ths.PRIVATE_SNAPSHOT)
        if ths.fingerprint(manager) in ths.rejected_fingerprints():
            report['status']='previous_rejection_skipped'
            return
        if manager.status()['state']!='ready':
            report['status']='no_valid_private_snapshot'
            return
        conn=ths.Connection(ths.QUOTE,manager,interval=.4,max_requests=1,connect_timeout=5,read_timeout=8).open()
        report['handshake']='accepted'
        query,body,records=conn.quote(request['kind'],**request['params'])
        with (args.out/'shares-300033-211.bin').open('xb') as f:
            f.write(body)
        report['requests'].append({'query':query,'response':'shares-300033-211.bin','sha256':hashlib.sha256(body).hexdigest(),'records':records})
        report['status']='response_saved_semantics_unverified'
    except Exception as exc:
        report.update(status='failed',error_type=type(exc).__name__)
    finally:
        signal.alarm(0)
        if conn: conn.close()
        report['requests_sent']=conn.requests if conn else 0
        (args.out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status':report.get('status'),'requests_sent':report['requests_sent'],'rows':len(report['requests'][0]['records'] or []) if report['requests'] else 0},ensure_ascii=False))

if __name__=='__main__': main()
