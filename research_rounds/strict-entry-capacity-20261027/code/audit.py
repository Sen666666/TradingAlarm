from study import *
import gzip,collections
# Keep accounting arithmetic untouched; only account-specific quota assertions differ.
src=inspect.getsource(A.old.audit_account)
assert src.count('len(held)<=6')==1
src=src.replace('len(held)<=6',"len(held)<=(12 if aid.split('__')[0].endswith('12') else 6)").replace("aid.startswith('S1')","'__S1_' in aid")
ns=dict(A.old.__dict__);exec(src,ns);A.old.audit_account=ns['audit_account']
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def contracts(aid,obj,ds,facts,records):
 mode=aid.split('__')[0];cap=12 if mode.endswith('12') else 6;counts=collections.Counter();intents={};strict={}
 for r in obj['audit_log']:
  if r['kind']=='entry_contract':
   intents[r['order_id']]=r;assert D(r['budget'])<=D('.9')/D(cap)*D(r['nav'])+D('.01');counts['initial_budget']+=1
   sid=r['sid'];day=r['decision_at'][:10];assert bool(facts[sid].loc[day,'i_buy'])
   if mode.startswith('S'):
    if sid not in strict:strict[sid]=pd.read_parquet(O/'signals'/f'{sid}.parquet')
    assert bool(strict[sid].loc[day,'strict_target']);counts['strict_gate']+=1
  elif r['kind']=='fill' and r['receipt']['side']=='buy':
   z=intents[r['order_id']];f=r['receipt'];assert z['decision_at'][:10]<f['at'][:10];factor=facts[f['security_id']].loc[:f['at'][:10]].iloc[-1].factor;assert D(r['raw_open'])>D(z['floor_signal'])/D(str(factor));counts['execution']+=1
 meta={r['symbol']:r for r in __import__('csv').DictReader((P.C.DESIGN/'proposed-pool.csv').open())}
 for r in ds:
  occupied=set(r['positions'])|set(r['pending_buys']);cnt=collections.Counter(meta[x]['sector_id'] for x in occupied);assert len(occupied)<=cap and len(cnt)<=3 and max(cnt.values(),default=0)<=(4 if cap==12 else 2);counts['capacity']+=1
 return {'passed':True,'checks':dict(counts)}
def audit(c,stage):
 A.CORE=PRIOR/'input';A.PREP=Path(read(PRIOR/'input.json')['snapshot']['path']);A.HERE=O/c;A.check_contract=contracts;A.main(stage)
def controls(c,stage):
 root=O/c/('technical/short-v2' if stage=='short' else 'accounts-v2');old=ROOT/'research_rounds/portfolio-correction-20261027'/c/'accounts-v2';ref={(r['account'],r['at']):r for r in rows(old/'daily.jsonl.gz')};ds=rows(root/'daily.jsonl.gz');n=0
 fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
 for r in ds:
  if not r['account'].startswith('A6__'):continue
  x=ref[r['account'].replace('A6__','ACT0__'),r['at']]
  for k in fields:assert r[k]==x[k],(c,r['at'],k)
  n+=1
 end=max(r['at'] for r in ds)
 for p in root.glob('A6__*.json'):
  assert read(p)['fills']==[r for r in read(old/p.name.replace('A6__','ACT0__'))['fills'] if r['at']<=end]
 save(O/c/('control-short.json' if stage=='short' else 'control-full.json'),{'passed':True,'daily':n})
if __name__=='__main__':audit(sys.argv[1],sys.argv[2]);controls(sys.argv[1],sys.argv[2])
