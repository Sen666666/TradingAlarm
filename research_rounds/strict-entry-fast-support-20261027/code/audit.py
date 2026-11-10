from study import *
import gzip,collections

def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]

def contracts(aid,obj,ds,facts,records):
 intents={};classes={};counts=collections.Counter();mode=aid.split('__')[0];L=3 if mode=='W3' else 10 if mode in ['W10','W10F'] else 0
 dates=sorted({x[:10] for x in read(PRIOR/'execution-rules-v2.json')['decision_cutoffs']}|{'2023-12-29','2026-10-23','2026-10-26','2026-10-27'})
 for r in obj['audit_log']:
  if r['kind']=='entry_contract':
   intents[r['order_id']]=r
   assert bool(facts[r['sid']].loc[r['decision_at'][:10],'i_buy'])
   if mode in ['S','SF']:assert bool(pd.read_parquet(SREF/'signals'/f"{r['sid']}.parquet").loc[r['decision_at'][:10],'strict_target']);counts['strict_gate']+=1
   assert D(r['budget'])<=D('.15')*D(r['nav'])+D('.01');counts['budget']+=1
  elif r['kind']=='intent_entry_class':
   classes[r['order_id']]=r;f=facts[r['sid']];day=r['at'][:10];z=f.loc[day];assert r['original']==bool(z.i_buy)
   if not r['original']:
    assert L and r['origin'] and 0<=dates.index(day)-dates.index(r['origin'])<L
    assert bool(z.i_target and z.g_ready and z.g_grade>=2);assert bool(f.loc[r['origin'],'i_buy']);counts['extended_entry']+=1
  elif r['kind']=='fill' and r['receipt']['side']=='buy':
   f=r['receipt'];z=intents[r['order_id']];assert r['order_id'] in classes;assert z['decision_at'][:10]<f['at'][:10];ff=facts[f['security_id']];factor=ff.loc[:f['at'][:10]].iloc[-1].factor;assert D(r['raw_open'])>D(z['floor_signal'])/D(str(factor));counts['execution']+=1
  elif r['kind']=='fast_support_raise':
   assert mode in ['F','SF'];assert r['previous'] is None or r['floor']>=r['previous'];counts['support_monotone']+=1
  elif r['kind']=='fast_support_exit':assert mode in ['F','SF'] and r['close']<=r['floor'];counts['fast_exit']+=1
 return dict(passed=True,checks=dict(counts))

def audit(c,stage):
 A.CORE=PRIOR/'input';A.PREP=Path(read(PRIOR/'input.json')['snapshot']['path']);A.HERE=O/c;A.check_contract=contracts;A.main(stage)

def controls(c,stage):
 root=O/c/('technical/short-v2' if stage=='short' else 'accounts-v2');ds=rows(root/'daily.jsonl.gz');end=max(r['at'] for r in ds);n=0
 fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
 for mode,ref,oldmode in [('ACT',FREF,'ACT'),('F',FREF,'F'),('S',SREF,'S6')]:
  old=ref/c/'accounts-v2';rr={(r['account'],r['at']):r for r in rows(old/'daily.jsonl.gz')}
  for r in ds:
   if not r['account'].startswith(mode+'__'):continue
   z=rr[r['account'].replace(mode+'__',oldmode+'__'),r['at']]
   for k in fields:assert r[k]==z[k],(c,mode,r['at'],k)
   n+=1
  for p in root.glob(mode+'__*.json'):
   assert read(p)['fills']==[r for r in read(old/p.name.replace(mode+'__',oldmode+'__'))['fills'] if r['at']<=end]
 save(O/c/('control-short.json' if stage=='short' else 'control-full.json'),{'passed':True,'daily_rows':n,'control_policies':3})
if __name__=='__main__':audit(sys.argv[1],sys.argv[2]);controls(sys.argv[1],sys.argv[2])
