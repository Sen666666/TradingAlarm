from common import *
from decimal import Decimal as D
def main(mode):
 source=HERE/('accounts-v1' if mode=='economic' else 'technical/'+mode);end=read(source/'summary.json')['days'];cutoff='2015-03-31' if mode=='short' else '2026-10-22';old={};numeric=['available','order_reserved','sale_receivable','dividend_receivable','inventory','nav','fees_cny','peak_funding'];n=0
 for r in rows(PREV/'accounts-v1/daily.jsonl.gz'):
  if r['at'][:10]>cutoff:break
  if r['account'].startswith('E0__'):old[(r['account'].replace('E0__','F100__'),r['at'])]=r
 for r in rows(source/'daily.jsonl.gz'):
  if not r['account'].startswith('F100__'):continue
  ref=old.pop((r['account'],r['at']))
  for k in numeric:assert abs(D(r[k])-D(ref[k]))<D('1e-8'),(r['account'],r['at'],k,r[k],ref[k])
  assert r['positions']==ref['positions'],(r['account'],r['at'],'positions')
  for k in ['pending_buys','pending_sells']:assert set(r[k])==set(ref[k]),(r['account'],r['at'],k)
  n+=1
 assert not old
 def fills(path,old=False):
  out={}
  for r in rows(path):
   if r['at'][:10]>cutoff:break
   if not r['account'].startswith('E0__' if old else 'F100__'):continue
   aid=r['account'].replace('E0__','F100__');key=(aid,r['at'],r['security_id'],r['side']);assert key not in out
   out[key]=(r['shares'],D(r['gross_cny']),D(r['fees_cny']),r['execution_basis'])
  return out
 a=fills(PREV/'accounts-v1/fills.jsonl.gz',True);b=fills(source/'fills.jsonl.gz');assert a==b,('fill identity',len(a),len(b),next((k for k in a if a[k]!=b.get(k)),None))
 write(HERE/f'technical/{mode}-identity.json',dict(passed=True,source=str(source.relative_to(ROOT)),days=end,paths=3,daily_rows=n,all_fill_checks=len(a),canonical_fill_exact=True,all_positions_exact=True,numeric_tolerance_cny='1e-8',order_identifier_and_cross_stock_ordering_ignored=True))
 print(dict(passed=True,mode=mode,daily_rows=n,fills=len(a)),flush=True)
if __name__=='__main__':main(sys.argv[1])
