"""Correct a descriptive association population only, retaining the original mixed table."""
from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent
c=pd.read_parquet(O/'FEATURES.parquet');s=pd.read_parquet(O/'SEALED_PICKS.parquet')
a=pd.read_csv(O.parent/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv')
a=a[a.account.eq('PVR')&a.first_kind.eq('add')]
a=a.merge(c[['sid','day','row']],left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one')
out=[]
for method,g in s.groupby('method'):
 for year,z in a[a.closed&a.row.isin(set(g.row))].groupby('year'):
  out.append(dict(year=year,method=method,original_MOBILE_filled_closed_association=len(z),wins=int(z.round_pnl.gt(0).sum()),original_win_fraction=float(z.round_pnl.gt(0).mean()),not_counterfactual=True,first_kind='add'))
pd.DataFrame(out).to_csv(O/'ORIGINAL_MOBILE_ONLY_CLOSED_ASSOCIATION.csv',index=False)
j=dict(finding='ORIGINAL_CLOSED_ASSOCIATION_MIXED_CORE_AND_MOBILE',old_file_retained=True,old_file_invalid_for_MOBILE_only_claim=True,original_ranking_and_price_metrics_unchanged=True,corrected_description='Filter original first_kind=add before candidate intersection; still only old-path association, not new net win rate.',joined_MOBILE_firsts=len(a))
(O/'AUDIT_MOBILE_ASSOCIATION_ADDENDUM.json').write_text(json.dumps(j,ensure_ascii=False,indent=2))
print(pd.DataFrame(out).to_string(index=False))
