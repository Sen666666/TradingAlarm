from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,math,sys
import pandas as pd
BASE=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent/'execution_source_check.json'
assert not OUT.exists()
freeze=json.loads((BASE/'run/SOURCE_FREEZE.json').read_text())
rows=[];total=0;t1=0;partial=0
for p in sorted((BASE/'run').glob('*/PATH.json.gz')):
 x=json.load(gzip.open(p,'rt'));sid=x['case']['sid'];rp=next(f for f in freeze if f.endswith('/bars/'+sid+'.parquet'))
 raw=pd.read_parquet(rp).set_index('trade_date').sort_index();buyby={l['id']:l for l in x['layers']}
 seen={};missing=[]
 for d in x['daily']:
  day=pd.Timestamp(d['at'][:10])
  if day not in raw.index or not math.isfinite(float(raw.loc[day,'open'])) or raw.loc[day,'open']<=0:missing.append(str(day.date()))
 for a in x['audit']:
  if a['kind']!='fill':continue
  t=a['receipt'];day=pd.Timestamp(t['at'][:10]);r=raw.loc[day];op=D(str(r['open']));side=t['side'];price=op*(D('1.0005')if side=='buy'else D('.9995'))
  assert abs(price-D(a['price']))<D('1e-8')
  prior=raw.loc[raw.index<day,'volume'];prior=prior[prior.map(lambda v:math.isfinite(v)and v>0)].tail(20);assert len(prior)==20
  capacity=int(prior.to_numpy(float).mean()*.01);assert t['shares']<=capacity
  oid=a['order_id'];seen[oid]=seen.get(oid,0)+1
  total+=1
 for t in x['trades']:
  if t['side']=='sell':
   for part in t['parts']:
    assert buyby[part['layer']]['opened'][:10]<t['at'][:10]
    t1+=1
 part_orders={k:v for k,v in seen.items()if v>1};partial+=len(part_orders)
 splitzero=[l['id']for l in x['layers']if l['qty']==0 and l['closed']is None]
 assert not splitzero
 rows.append(dict(case_id=x['case']['round_id'],sid=sid,arm=x['summary']['arm'],fills=sum(a['kind']=='fill'for a in x['audit']),
   missing_open_dates=missing,missing_open_days=len(missing),multiple_fill_order_counts=part_orders,split_zero_unclosed_layers=splitzero))
result=dict(passed=True,fill_OPEN_5bps_and_prior20_cap_checks=total,sell_parts_prior_day_layer_checks=t1,
 repeated_fill_orders=partial,scope='Executed fills only, independent raw OPEN/prior20 cap and layer T+1. Not an eligibility, order expiry, split-new-share sellability or real tradability audit.',
 source_status='UNKNOWN official tradability; NON-PIT frozen universe',paths=rows)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k!='paths'},ensure_ascii=False))
print('MISSING',json.dumps([r for r in rows if r['missing_open_days']],ensure_ascii=False))

