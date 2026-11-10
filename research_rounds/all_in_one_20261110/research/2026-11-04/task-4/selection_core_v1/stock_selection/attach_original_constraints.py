"""Copy saved original ACT/resource/intent fields beside static ranks; no reallocation."""
from pathlib import Path
import csv,hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
base=pd.read_parquet(O/'ALL5127_STATIC_DIAGNOSTIC_WITH_REASONS.parquet')
dp=P/'original_candidates/ORIGINAL_DAILY_ACCOUNT_STATE.json';ip=P/'original_candidates/ORIGINAL_PENDING_INTENTS.csv'
daily={r['at'][:10]:r for r in json.loads(dp.read_text())}
intent={}
with ip.open() as f:
 for r in csv.DictReader(f):intent.setdefault((r['signal_date'],r['sid']),[]).append(r)
fields=[]
for r in base[['date','sid']].to_dict('records'):
 x=daily.get(r['date']);ii=intent.get((r['date'],r['sid']),[])
 z=dict(r);z.update(original_ACT_on=None if x is None else x.get('on'),original_account_state_at=None if x is None else x.get('at'),
  original_daily_source=None if x is None else x.get('source'),original_stock_qty=None if x is None else x.get('positions',{}).get(r['sid'],0),
  original_stock_pending_sell=None if x is None else r['sid'] in x.get('pending_sells',[]),
  saved_actual_pending_intents_json=json.dumps(ii,ensure_ascii=False),saved_pending_epoch_json=json.dumps([t.get('epoch') for t in ii],ensure_ascii=False),
  current_core_epoch=None,current_core_epoch_status='NOT_RECONSTRUCTED_FROM_PRICE_OR_POSTERIOR_LAYER')
 for k in ['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav']:
  z['original_account_'+k]=None if x is None else x.get(k)
 for k in ['pool_probe','pool_confirmed']:
  z['original_'+k+'_verbatim_json']=None if x is None else json.dumps(x.get(k))
 fields.append(z)
a=base.merge(pd.DataFrame(fields),on=['date','sid'],validate='one_to_one')
a[a.original_signal_legal_frozen].to_csv(O/'ALL_ORIGINAL_SIGNAL_LEGAL_WITH_CONSTRAINTS.csv',index=False)
focal=pd.read_parquet(O/'FOCAL_ORIGINAL_AND_SSTAR.parquet')[['date','sid']].merge(a,on=['date','sid'],validate='one_to_one')
focal.to_csv(O/'FOCAL_WITH_ACT_INTENTS_RESOURCES.csv',index=False)
summary={'rows':len(a),'focal_rows':len(focal),'all_three_ACT_on':bool(a.original_ACT_on.eq(True).all()),'no_resource_recomputation':True,'current_core_epoch_not_filled':True,
 'original_daily_state_source_sha256':hashlib.sha256(dp.read_bytes()).hexdigest(),'original_pending_intents_source_sha256':hashlib.sha256(ip.read_bytes()).hexdigest()}
(O/'ORIGINAL_CONSTRAINTS_OVERLAY_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
