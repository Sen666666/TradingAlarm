from study import *
import gzip,collections
STRICT_CACHE={}
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def contracts(aid,obj,ds,facts,records):
 mode=aid.split('__')[0];L=3 if mode=='SW3F' else 10 if mode=='SW10F' else 0;intents={};classes={};cnt=collections.Counter();active={}
 dates=sorted({x[:10] for x in read(PRIOR/'execution-rules-v2.json')['decision_cutoffs']}|{'2023-12-29','2026-10-23','2026-10-26','2026-10-27'})
 def strict_at(sid,day):
  if sid not in STRICT_CACHE:STRICT_CACHE[sid]=pd.read_parquet(SREF/'signals'/f'{sid}.parquet')
  return bool(STRICT_CACHE[sid].loc[day,'strict_target'])
 for r in obj['audit_log']:
  kind=r['kind']
  if kind=='intent_create':
   assert L and strict_at(r['sid'],r['day']) and bool(facts[r['sid']].loc[r['day'],'i_buy']);active[r['sid']]=dict(r);cnt['watch_created']+=1
  elif kind=='waiting_support_raise':
   w=active[r['sid']];assert r['previous']==w['floor'] and r['floor']>=r['previous'] and r['close']>r['floor'];w['floor']=r['floor'];cnt['watch_raised']+=1
  elif kind=='intent_end':active.pop(r['sid'],None);cnt['watch_end_'+r['reason']]+=1
  elif kind=='entry_contract':
   intents[r['order_id']]=r;sid=r['sid'];day=r['decision_at'][:10];assert D(r['budget'])<=D('.15')*D(r['nav'])+D('.01')
   if mode!='ACT':assert strict_at(sid,day)
   cnt['entry_budget_strict']+=1
  elif kind=='intent_entry_class':
   classes[r['order_id']]=r;sid=r['sid'];day=r['at'][:10];z=facts[sid].loc[day];assert r['original']==bool(z.i_buy)
   if r['origin']:
    assert L and 0<=dates.index(day)-dates.index(r['origin'])<L;assert strict_at(sid,r['origin']);assert D(intents[r['order_id']]['floor_signal'])>=D(str(r['waiting_floor']));cnt['waiting_contract']+=1
   if not r['original']:assert r['origin'] and z.i_target and z.g_ready and z.g_grade>=2;cnt['extended_entry']+=1
  elif kind=='fill' and r['receipt']['side']=='buy':
   z=intents[r['order_id']];f=r['receipt'];assert z['decision_at'][:10]<f['at'][:10];factor=facts[f['security_id']].loc[:f['at'][:10]].iloc[-1].factor;assert D(r['raw_open'])>D(z['floor_signal'])/D(str(factor));cnt['causal_open_above_protection']+=1
  elif kind=='waiting_support_inherited':assert r['floor']>=float(intents[r['order_id']]['floor_signal']) and classes[r['order_id']]['origin']==r['origin'];cnt['inherited']+=1
  elif kind=='fast_support_raise':assert r['previous'] is None or r['floor']>=r['previous'];cnt['held_monotone']+=1
  elif kind=='fast_support_exit':assert r['close']<=r['floor'];cnt['held_exit']+=1
 return {'passed':True,'checks':dict(cnt)}
def audit(c,stage,rank):
 A.CORE=PRIOR/'input';A.PREP=Path(read(PRIOR/'input.json')['snapshot']['path']);A.HERE=O/rank/c;A.check_contract=contracts;A.main(stage)
def controls(c,stage,rank):
 n=0
 if rank=='RS':
  root=O/rank/c/('technical/short-v2' if stage=='short' else 'accounts-v2');ds=rows(root/'daily.jsonl.gz');end=max(r['at'] for r in ds);old=SFREF/c/'accounts-v2';ref={(r['account'],r['at']):r for r in rows(old/'daily.jsonl.gz')}
  fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
  for r in ds:
   if r['account'].split('__')[0] not in ['ACT','SF']:continue
   for k in fields:assert r[k]==ref[r['account'],r['at']][k],(c,r['account'],r['at'],k)
   n+=1
  for mode in ['ACT','SF']:
   for p in root.glob(mode+'__*.json'):assert read(p)['fills']==[r for r in read(old/p.name)['fills'] if r['at']<=end]
 save(O/rank/c/('control-short.json' if stage=='short' else 'control-full.json'),{'passed':True,'daily_rows':n})
if __name__=='__main__':audit(sys.argv[1],sys.argv[2],sys.argv[3]);controls(sys.argv[1],sys.argv[2],sys.argv[3])
