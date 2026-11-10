"""Read saved CP action classes and layer outcomes; no price/strategy/model run."""
from pathlib import Path
from decimal import Decimal
from collections import Counter
import json
import hashlib

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
HASH={}
def read(path):
    p=Path(path).resolve();HASH[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

original=read(ROOT/'mobile_trend_measurements_v1/MOBILE_SIGNAL_METRICS_AND_ORIGINAL_ACTIONS.json')
lookup={}
for p in ['mobile_trend_measurements_v1/case_links/002583.SZ.json',
          'mobile_trend_measurements_v1/case_links/000547.SZ.json']:
    for r in read(ROOT/p):
        if r['CP_present']:lookup[(r['sid'],r['day'])]=dict(status=r['connection_status'],funding=r['next_OPEN_original_MOBILE_funding'],fills=r['next_OPEN_original_MOBILE_fills'])
for r in read(ROOT/'mobile_trend_measurements_v1/case_links_yingxin_shandong/ALL_DAILY_LINKS.json'):
    if not r['original_CP_receipt']:continue
    translate={'ACTUAL_MOBILE_FILL':'ORIGINAL_MOBILE_FILL','ORIGINAL_OPEN_REJECTION':'ORIGINAL_MOBILE_OPEN_REJECTED','SAME_SID_CORE_FUNDED_FIRST_DONE_SKIPS_MOBILE':'MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED'}
    lookup[(r['sid'],r['day'])]=dict(status=translate[r['next_OPEN_status']],
        original_source_status=r['next_OPEN_status'],
        original_funding_reasons=r['next_OPEN_original_mobile_results'],
        original_filled_layer_ids=r['next_OPEN_actual_mobile_layer_ids'])
layers=[]
for window in ['long','strong']:
    layers.extend(dict(original_account=window+'_OFF',**r)for r in read(ROOT/f'new_price_trend_v1/analysis/{window}_OFF_LAYERS.json'))
matched=[]
for r in original:
    key=(r['sid'],r['date']);source=lookup[key]
    assert source['status']==r['original_mobile_next_OPEN_status']
    row=dict(sid=r['sid'],date=r['date'],original_status=source['status'],
        original_next_OPEN=r['next_original_OPEN'],original_rejection_union=r['original_mobile_next_OPEN_funding_results'],
        source_classification=source,
        original_mobile_role=r['original_mobile_role'],original_mobile_intent_count=r['original_mobile_intent_count'],
        original_mobile_filled_shares=r['original_mobile_filled_shares'])
    if row['original_status']=='ORIGINAL_MOBILE_FILL':
        exact=[l for l in layers if l['sid']==r['sid']and l['signal_day']==r['date']and l['role']=='mobile']
        assert len(exact)==1
        row['original_saved_layer_outcome_evaluation_only']=exact[0]
        row['original_saved_layer_net_sign']='negative'if Decimal(exact[0]['net'])<0 else'positive'if Decimal(exact[0]['net'])>0 else'zero'
    else:
        assert row['original_mobile_filled_shares']==0
    matched.append(row)
counts=Counter(r['original_status']for r in matched)
assert counts=={'ORIGINAL_MOBILE_FILL':19,'ORIGINAL_MOBILE_OPEN_REJECTED':38,'MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED':2}
save('ORIGINAL_CLASSIFICATION_59.json',matched)
save('ORIGINAL_CLASSIFICATION_COUNTS.json',dict(total=len(matched),counts=dict(counts),
    filled_saved_net_signs=dict(Counter(r['original_saved_layer_net_sign']for r in matched if r['original_status']=='ORIGINAL_MOBILE_FILL')),
    skipped=[r for r in matched if r['original_status']=='MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED'],
    risk_clock='Net outcomes are original saved layer evaluation, never R inputs or counterfactual returns.',
    ratio_source='Parent frozen all59.csv required; no R or new slopes calculated here.',
    new_accounts=0,new_indicators=0,new_financial_models=0))
save('CLASSIFICATION_SOURCE_SHA256.json',HASH)
