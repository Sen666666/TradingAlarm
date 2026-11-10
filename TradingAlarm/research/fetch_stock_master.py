"""Public BaoStock master; no personal credentials, local source preserved."""
import json,signal,socket
from datetime import datetime
from pathlib import Path
import baostock as bs
ROOT=Path(__file__).resolve().parent
socket.setdefaulttimeout(15)
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('120second public-query budget exhausted')))
signal.alarm(120)
try:
 login=bs.login()
 if login.error_code!='0':raise RuntimeError('Public service login failed:'+login.error_msg)
 rs=bs.query_stock_basic()
 if rs.error_code!='0':raise RuntimeError('Master query failed:'+rs.error_msg)
 rows=[]
 while rs.next():rows.append(dict(zip(rs.fields,rs.get_row_data())))
 result={'source':'BaoStock query_stock_basic public service','fetched_at':datetime.now().astimezone().isoformat(),'rows':rows,'limitations':'Current master snapshot including provider-retained delisted codes;not proof of complete historical listings or dated name/ST state.'}
 if not rows:raise ValueError('Empty master')
 (ROOT/'data/baostock-master.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({'rows':len(rows),'status_counts':{s:sum(r['status']==s for r in rows) for s in sorted(set(r['status'] for r in rows))}},ensure_ascii=False),flush=True)
finally:
 bs.logout();signal.alarm(0)
