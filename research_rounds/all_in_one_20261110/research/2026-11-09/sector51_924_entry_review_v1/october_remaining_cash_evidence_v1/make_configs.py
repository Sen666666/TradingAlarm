import json,sys
from pathlib import Path
O=Path(__file__).parent;src=json.loads((O/'SOURCE_RETRIEVAL.json').read_text())
if (O/'SOURCE_RETRIEVAL_EXTRA.json').exists():src.update(json.loads((O/'SOURCE_RETRIEVAL_EXTRA.json').read_text()))
rows=[]
for sid,dc,dr,rec,ex,sd,num,note,cashfrag in json.loads(Path(sys.argv[1]).read_text()):
 c=sid[:6];fr=[c,'实施公告',cashfrag];fr += [f'2024年10月{rec}日',f'2024年10月{ex}日'] if sid.endswith('SZ') else [f'2024/10/{rec}',f'2024/10/{ex}'];
 if dr:fr.append(dr)
 rows.append(dict(sid=sid,record_date=f'2024-10-{rec:02}',ex_date=f'2024-10-{ex:02}',pay_date=f'2024-10-{ex:02}',d_cash=dc,d_ref=dr,notice_date=src[c]['publication_date'],notice_signature_date=sd,notice_number=num,pdf_url=src[c]['url'],assert_fragments=fr,fact_notes=[note]))
Path(sys.argv[2]).write_text(json.dumps(rows,ensure_ascii=False,indent=2))
