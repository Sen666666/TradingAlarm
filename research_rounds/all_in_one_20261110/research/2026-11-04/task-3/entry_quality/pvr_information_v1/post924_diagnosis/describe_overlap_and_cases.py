"""Frozen descriptive central80% overlap and systematic paired controls only."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,math
import numpy as np
O=Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
save('OVERLAP_SCOPE.json',dict(status='DESCRIPTIVE_FIXED_CENTRAL80_NO_THRESHOLD_SEARCH',quantiles=[.1,.9],loss_domain='post303 terminal net negative layers; evaluation only',winner_domain='strong actual net/cost >= .3 layers; evaluation only',weight='absolute negative original contribution on loss side; positive original contribution on tail side',not_a_policy=True,new_factors=False,new_accounts=0))
rows=read('ALL_JOINED_LAYER_ROWS.json');post=[r for r in rows['2022_2024'] if r['opened'][:10]>'2024-10-08'];loss=[r for r in post if D(r['net'])<0];tails=[r for r in rows['strong'] if D(r['net'])/D(r['cost'])>=D('.3')]
fields={
 'PVR_score':lambda r:r['PVR_score'],
 'daily_r':lambda r:r['direction_snapshot']['pvr_r'],
 'E':lambda r:r['direction_snapshot']['pvr_E'],
 'daily_amount_multiplier_m':lambda r:r['direction_snapshot']['cp1_m'],
 'CP_delta_frontier':lambda r:r['CP_delta_frontier'],
 'CP_credit':lambda r:r['CP_credit'],
 'industry_last_receipt_age':lambda r:r['industry_last_receipt_age_observations'],
 'entry_gap_pct':lambda r:r['entry_gap_pct'],
 'actual_initial_risk_pct_NAV':lambda r:r['actual_initial_risk_pct_decisionNAV'],
}
out={}
for name,fn in fields.items():
 a=[r for r in loss if fn(r) is not None and math.isfinite(float(fn(r)))];b=[r for r in tails if fn(r) is not None and math.isfinite(float(fn(r)))];av=[float(fn(r)) for r in a];bv=[float(fn(r)) for r in b];aq=np.quantile(av,[.1,.5,.9]);bq=np.quantile(bv,[.1,.5,.9]);wa=sum((-D(r['net']) for r in a),D(0));wb=sum((D(r['net']) for r in b),D(0));ha=[r for r in a if bq[0]<=float(fn(r))<=bq[2]];hb=[r for r in b if aq[0]<=float(fn(r))<=aq[2]]
 out[name]=dict(loss_count=len(a),tail_count=len(b),loss_p10_median_p90=aq.tolist(),tail_p10_median_p90=bq.tolist(),loss_negative_money_inside_tail_central80=sum((-D(r['net']) for r in ha),D(0))/wa,tail_positive_money_inside_loss_central80=sum((D(r['net']) for r in hb),D(0))/wb,loss_layers_inside_tail_central80=len(ha),tail_layers_inside_loss_central80=len(hb))
save('DESCRIPTIVE_CENTRAL80_OVERLAP.json',out)
campaigns=read('POST303_ALL_CAMPAIGN_CHAINS.json');pairs=[]
for c in campaigns[:10]:
 rr=c['post_layer_rows'];largest=min(rr,key=lambda r:D(r['net']));same=[r for r in tails if r['sector']==largest['sector'] and r['simple_action']==largest['simple_action']];scope='same_industry_and_actual_action'
 if not same:same=[r for r in tails if r['simple_action']==largest['simple_action']];scope='same_action_only_no_same_industry_tail'
 winner=max(same,key=lambda r:D(r['net']));pairs.append(dict(post_campaign=c['campaign']['campaign_id'],post_campaign_new_layer_contribution=c['post303_layers'],selected_loss_largest_contributor=largest,tail_control=winner,control_match_scope=scope,selection='top10 post-new campaign net ascending; largest losing original layer per chain paired to maximum actual tail contribution within fixed industry+action match; evaluation only no signal'))
save('SYSTEMATIC_TOP10_AND_TAIL_CONTROLS.json',pairs)
save('POST_OWN13_TAIL_CONTROLS.json',[r for r in post if D(r['net'])/D(r['cost'])>=D('.3')])
print(json.dumps({k:dict(loss_money_overlap=str(v['loss_negative_money_inside_tail_central80']),tail_money_overlap=str(v['tail_positive_money_inside_loss_central80'])) for k,v in out.items()},ensure_ascii=False))
