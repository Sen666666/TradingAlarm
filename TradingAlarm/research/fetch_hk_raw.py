"""Bounded public HK raw-price paging; explicit empty sixth adjustment parameter."""
import argparse,json,subprocess,hashlib,re,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/hk-stock-raw'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--code',default='00700');parser.add_argument('--end',default='2026-10-16');parser.add_argument('--earliest',default='2013-01-01');parser.add_argument('--max-pages',type=int,default=12);args=parser.parse_args()
 if not re.fullmatch(r'\d{5}',args.code):raise ValueError('invalid HK code')
 for value in [args.end,args.earliest]:datetime.strptime(value,'%Y-%m-%d')
 OUT.mkdir(exist_ok=True);pages=[];records={};conflicts=[];end=args.end;reason='page_budget';name='hk'+args.code
 for i in range(min(args.max_pages,12)):
  url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={name},day,,{end},320,'
  response=subprocess.run(['/usr/bin/curl','--fail','--silent','--show-error','--max-time','20',url],check=True,capture_output=True).stdout
  d=json.loads(response)
  if d.get('code')!=0 or not isinstance(d.get('data'),dict):raise ValueError('provider error')
  rows=d['data'].get(name,{}).get('day')
  if not isinstance(rows,list) or not rows:raise ValueError('empty raw response')
  if any(len(r)<6 for r in rows) or [r[0] for r in rows]!=sorted({r[0] for r in rows}):raise ValueError('invalid page ordering/schema')
  added=0
  for r in rows:
   if r[0] in records and records[r[0]][1:6]!=r[1:6]:conflicts.append(dict(date=r[0],earlier_ohlcv=records[r[0]][1:6],new_ohlcv=r[1:6]))
   if r[0] not in records:records[r[0]]=r;added+=1
  pages.append(dict(url=url,rows=len(rows),first=rows[0][0],last=rows[-1][0],added=added,sha256=hashlib.sha256(response).hexdigest()))
  (OUT/f'{name}-page{i+1}.json').write_bytes(response)
  result=dict(symbol='HK'+args.code,source='Tencent public fqkline day,empty adjustment',pages=pages,rows=[records[k] for k in sorted(records)],conflicts=conflicts,complete=False,stop_reason='running',raw_semantics_independently_verified=False,account_ready=False)
  (OUT/f'{name}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  print(name,i+1,len(rows),rows[0][0],flush=True)
  if rows[0][0]<=args.earliest:reason='requested_earliest_reached';break
  if len(rows)<320:reason='short_page';break
  if not added or end==rows[0][0]:reason='no_progress';break
  end=rows[0][0];time.sleep(.2)
 result.update(stop_reason=reason,requested_earliest=args.earliest,complete=False)
 (OUT/f'{name}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print('rows',len(records),'conflicts',len(conflicts),'stop',reason,flush=True)
if __name__=='__main__':main()
