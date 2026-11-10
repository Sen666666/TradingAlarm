"""Public anonymous financial API audit, not strategy-ready point-in-time data."""
import json,signal,socket
from datetime import datetime,timezone
from pathlib import Path
import baostock as bs
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/fundamental-vintage-pilot'
def timeout(*args):raise TimeoutError('bounded financial query timeout')
def main():
 OUT.mkdir(exist_ok=True);signal.signal(signal.SIGALRM,timeout);socket.setdefaulttimeout(20)
 tasks=[('sh.600519',2017,4),('sh.600518',2017,4),('sz.000780',2020,4),('sh.600000',2023,4)]
 (OUT/'protocol.json').write_text(json.dumps(dict(tasks=tasks,purpose='Probe publicationdate/value/revision semantics across ordinary,restatement-prone,retired,financialissuer cases; not returnselected researchuniverse',credentials='Public baostock anonymous default, no THS credential',point_in_time_certified=False),indent=2))
 signal.alarm(25);login=bs.login();signal.alarm(0)
 if login.error_code!='0':raise RuntimeError(login.error_msg)
 try:
  for code,year,q in tasks:
   for method in ['query_profit_data','query_growth_data']:
    key=f'{code}-{year}Q{q}-{method}';path=OUT/f'{key}.json'
    if path.exists():continue
    record=dict(code=code,year=year,quarter=q,method=method,retrieved_at=datetime.now(timezone.utc).isoformat(),point_in_time_certified=False)
    try:
     signal.alarm(25);rs=getattr(bs,method)(code,year,q);record.update(error_code=rs.error_code,error_msg=rs.error_msg,fields=rs.fields);rows=[]
     while rs.error_code=='0' and rs.next():rows.append(dict(zip(rs.fields,rs.get_row_data())))
     record['rows']=rows
    except Exception as e:record['exception']=type(e).__name__+':'+str(e)
    finally:signal.alarm(0)
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2));print(key,'rows',len(record.get('rows',[])),record.get('exception',''),flush=True)
 finally:
  signal.alarm(10)
  try:bs.logout()
  finally:signal.alarm(0)
if __name__=='__main__':main()
