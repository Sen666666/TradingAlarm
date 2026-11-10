"""Necessary exit-label envelope only; no EMA/floor counterfactual/basis."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import gzip,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0);SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def book(p):
 SRC[str(p.resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return json.load(f)
results={};allmothers={};tailsource=T/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json';tails=read(tailsource)
for win in ['long','strong']:
 p=T/f'capacity_cost_guard_v1/runs/{win}-v1/arms/B/pair/B.json.gz';b=book(p);lp=T/f'capacity_cost_guard_analysis_v1/full_{win}_v1/analysis/{win}/B/LAYERS.json';ls=read(lp);mobile=[l for l in ls if l['role']=='mobile'];req=defaultdict(list)
 for a in b['audit']:
  if a['kind']=='pilot_layer_exit':
   for lid in a['layers']:req[lid].append(a)
 rows=[]
 for l in mobile:
  r=req[l['layer']][0]if req[l['layer']]else None;rows.append(dict(**l,original_first_exit_request_at=r['at']if r else None,original_first_exit_request_reason=r['reason']if r else'NO_REQUEST_WITHIN_WINDOW',later_CP1_raise_dominant_exit='UNKNOWN_NOT_ENCODED_BY_REASON_OR_FLOOR_SNAPSHOT_ALONE'))
 def stats(rr):return dict(layers=len(rr),stocks=len({r['sid']for r in rr}),actual_buy_cash=sum((D(r['cost'])for r in rr),Z),actual_original_window_net=sum((D(r['net'])for r in rr),Z),positive_layers=sum(D(r['net'])>0 for r in rr),negative_layers=sum(D(r['net'])<0 for r in rr),zero_layers=sum(D(r['net'])==0 for r in rr),positive_contribution=sum((D(r['net'])for r in rr if D(r['net'])>0),Z),negative_contribution=sum((D(r['net'])for r in rr if D(r['net'])<0),Z))
 groups={k:stats([r for r in rows if r['original_first_exit_request_reason']==k])for k in sorted({r['original_first_exit_request_reason']for r in rows})};results[win]=dict(all_mobile=stats(rows),first_original_exit_reason_groups=groups,coverage='CP1_add_protection is only a necessary broad label; combines initial floor, later I raises, later CP1 raises. No count here proves laterCP1 strict dominance, winner truncation, EMA effect or achievable profit.');allmothers[win]=rows
(O/'NECESSARY_LABEL_ENVELOPE.json').write_text(json.dumps(dict(windows=results,new_accounts=0,new_EMA=0,new_financial_basis=0,strict_later_CP1_dominance_size='UNKNOWN_REQUIRES_ORIGINAL_FLOOR_UPDATE_PROVENANCE_JOIN',sources=SRC,script_sha256=sha(Path(__file__))),ensure_ascii=False,indent=2,default=str)+'\n')
(O/'FROZEN_TAIL_AND_ALL_MOBILE_MOTHERS.json').write_text(json.dumps(dict(original_fixed_tails_unchanged=tails,all_No60_mobile_layers=allmothers,scope='Original83/94 legacy tail IDs retained without forced match to No60; all No60 mobile positive/negative/zero/open layers retained. Original lifecycle contribution can include mark/AR, is not avoidable profit.'),ensure_ascii=False,indent=2,default=str)+'\n')
for w,r in results.items():print(w,r['all_mobile'],r['first_original_exit_reason_groups'].get('CP1_add_protection'),flush=True)
