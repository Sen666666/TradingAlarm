"""Only eight prespecified dates; comparison examples picked before reading fixed labels."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;B=O.parents[2]/'mobile_candidate_response_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
sc=pd.read_parquet(O/'CANDIDATE_CE.parquet');mov=pd.read_parquet(O/'FULL_QUEUE_ORDERS.parquet');cases=pd.read_csv(O/'FIXED_EIGHT_CASES.csv')
sealed=json.loads((O/'RANK_SEAL.json').read_text());assert sha(O/'CANDIDATE_CE.parquet')==sealed['score_sha256']
days=cases.day.tolist();preview=mov[(mov.account=='PVR') & mov.day.isin(days)].copy()
preview=preview.merge(sc[['account','day','sid','formation_n','variance_budget','sigma_frozen','sigma_recent','source_r','source_m','source_displacement','source_credit']],on=['account','day','sid'],validate='one_to_one')
preview['membership']=np.select([preview.CE_selected&~preview.original_selected,~preview.CE_selected&preview.original_selected,preview.CE_selected&preview.original_selected],['added','removed','both'],default='neither')
preview.to_csv(O/'FIXED_DATES_PVR_QUEUES_BEFORE_LABELS.csv',index=False)
q=pd.read_csv(O/'QUEUE_COUNTS.csv');q=q[(q.account=='PVR')&q.day.isin(days)];q.to_csv(O/'FIXED_DATES_PVR_COUNTS.csv',index=False)
selected=[]
for day in ['2022-01-04','2022-03-03','2022-03-30']:
    g=preview[preview.day==day]
    a=g[g.membership=='added'].sort_values('CE_rank').head(3).copy();a['preselected_side_order']=range(1,len(a)+1)
    b=g[g.membership=='removed'].sort_values('original_rank').head(3).copy();b['preselected_side_order']=range(1,len(b)+1)
    selected.extend([a,b])
picks=pd.concat(selected,ignore_index=True);picks.to_csv(O/'PRESPECIFIED_ADDED_REMOVED_BEFORE_LABELS.csv',index=False)
dump('FIXED_PREVIEW_SEAL.json',dict(queue_sha256=sha(O/'FIXED_DATES_PVR_QUEUES_BEFORE_LABELS.csv'),picks_sha256=sha(O/'PRESPECIFIED_ADDED_REMOVED_BEFORE_LABELS.csv'),script_sha256=sha(__file__),dates=['2022-01-04','2022-03-03','2022-03-30'],selection='per date: first 3 added by frozen CE rank; first 3 removed by original rank; all picked cases displayed, no outcome choice',picks=len(picks),future_labels_read_at_seal=False,full_evaluation_not_started=True))
# Explicitly authorized small diagnostic only, after exact examples are sealed.
labels=pd.read_parquet(B/'FIXED_NATIVE_PRICE_LABELS.parquet',columns=['sid','day','complete5','ret5','mae5','complete20','ret20','mae20'],filters=[('day','in',picks.day.unique().tolist()),('sid','in',picks.sid.unique().tolist())])
picked=picks.merge(labels,on=['sid','day'],validate='one_to_one');assert len(picked)==len(picks);picked.to_csv(O/'PRESPECIFIED_ADDED_REMOVED_WITH_FIXED_LABELS.csv',index=False)
dump('SMALL_PREVIEW_LABEL_READ.json',dict(full_evaluation_started=False,label_sha256=sha(B/'FIXED_NATIVE_PRICE_LABELS.parquet'),fixed_picks=len(picks),rows_read=len(labels),picks_unchanged=sha(O/'PRESPECIFIED_ADDED_REMOVED_BEFORE_LABELS.csv')==json.loads((O/'FIXED_PREVIEW_SEAL.json').read_text())['picks_sha256']))
caseq=cases.merge(preview[['sid','day','N']] if 'N' in preview else preview[['sid','day','original_PVR','original_rank','CE_rank','K','membership']],on=['sid','day'],how='left',validate='one_to_one');caseq.to_csv(O/'FIXED_EIGHT_WITH_PVR_RANKS.csv',index=False)
tr=pd.read_csv(O/'FIXED_CASE_PRE_SIGNAL_TRACES.csv');contrib=[]
for c in cases.itertuples():
    rows=tr[(tr.sid==c.sid)&(tr.case_day==c.day)&(tr.day>c.formation_anchor_day)&(tr.day<=c.day)].copy()
    rows['variance_contribution']=rows.sigma_recent**2;rows['variance_fraction']=rows.variance_contribution/c.variance_budget
    assert len(rows)==c.formation_n and abs(rows.variance_contribution.sum()-c.variance_budget)<1e-14
    rows['original_credit_increment']=rows.delta_frontier*rows.m
    contrib.append(rows[['sid','case_day','day','r','m','delta_frontier','original_credit_increment','sigma_recent','variance_contribution','variance_fraction','variance_budget','formation_n']])
pd.concat(contrib,ignore_index=True).to_csv(O/'FIXED_EIGHT_VARIANCE_DAILY_CONTRIBUTIONS.csv',index=False)
print('FIXED QUEUES');print(q.to_string(index=False));print('CASES');print(caseq[['sid','day','CE','formation_n','variance_budget','source_displacement','source_credit','sigma_frozen','sigma_recent','original_PVR','original_rank','CE_rank','K','membership']].to_string(index=False));print('PRESELECTED EXAMPLES');print(picked[['day','membership','sid','original_rank','CE_rank','CE','original_PVR','formation_n','source_r','ret5','ret20','mae5','mae20']].to_string(index=False))
