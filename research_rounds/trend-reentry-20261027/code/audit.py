from study import *
import gzip,copy
original_check=A.check_contract

def check(aid,obj,ds,facts,records):
 # Expand independent allowed-event table ONLY for audited additional contracts;
 # original ledger, raw prices, fees and open-support checks remain unchanged.
 enriched={s:f.copy() for s,f in facts.items()};local={};checks=0
 for r in obj['audit_log']:
  if r['kind']=='local_entry_contract':
   sid=r['sid'];day=pd.Timestamp(r['signal_at'][:10]);q=pd.read_parquet(O/VERSION/'signals'/f'{sid}.parquet').loc[day]
   assert bool(q.event) and not bool(facts[sid].loc[day,'i_buy']);assert D(r['local_floor'])==D(str(q.floor));assert r['anchor']==q.anchor;assert r['kind'] # source event verified
   enriched[sid].loc[day,'i_buy']=True;local[r['order_id']]=r;checks+=1
  elif r['kind']=='local_handoff':
   assert D(r['e0_floor'])>D(r['entry_e0_floor']) and D(r['e0_floor'])>=D(r['local_floor']);assert D(r['stop'])>=D(r['local_floor']);checks+=1
  elif r['kind']=='local_stop_trigger':assert D(r['close'])<=D(r['stop']);checks+=1
 result=original_check(aid,obj,ds,enriched,records);result['local_checks']=checks;return result

def audit(v,stage):
 global VERSION
 VERSION=v;root=O/v;A.CORE=PRIOR/'input';A.PREP=Path(read(PRIOR/'input.json')['snapshot']['path']);A.HERE=root;A.check_contract=check if v!='ACT' else original_check
 A.main('short' if stage=='short' else 'full')
FIELDS=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def admission():
 assert read(O/'signal-checks.json')['passed'];assert read(O/'graph-review.json')['reviewed'];assert read(O/'tests.json')['passed']
 for v in ['ACT','PB','BOX','BOTH']:assert read(O/v/'technical/short-analysis/accounting.json')['passed']
 ref={(r['account'],r['at']):r for r in rows(PRIOR/'RS/accounts-v2/daily.jsonl.gz')}
 for r in rows(O/'ACT/technical/short-v2/daily.jsonl.gz'):
  for k in FIELDS:assert r[k]==ref[r['account'],r['at']][k]
 for sc in ['base','cost2','delay1']:
  aid='I__S0_'+sc;assert read(O/'ACT/technical/short-v2'/f'{aid}.json')['fills']==[r for r in read(PRIOR/'RS/accounts-v2'/f'{aid}.json')['fills'] if r['at'][:10]<='2024-06-28']
 save(O/'admission.json',{'passed':True,'short_paths':12,'control_paths':3})
if __name__=='__main__':admission() if sys.argv[1]=='admission' else audit(sys.argv[1],sys.argv[2])
