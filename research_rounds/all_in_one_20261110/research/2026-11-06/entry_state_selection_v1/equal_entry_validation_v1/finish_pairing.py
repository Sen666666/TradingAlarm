from pathlib import Path
import pandas as pd,numpy as np,json,time,hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/equal_entry_validation_v1')
sel=pd.read_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet')
lab=pd.read_parquet(O/'SHARED_STOCKDAY_LABELS.parquet')
cand=pd.read_parquet(O/'ALL_ORIGINAL_I_BUY_WITH_STATES.parquet')
receipt=json.loads((O/'RANK_SEAL.json').read_text())
assert hashlib.sha256((O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet').read_bytes()).hexdigest()==receipt['selection_sha256']
joined=sel.merge(lab,on=['sid','day'],validate='many_to_one')
support=pd.to_numeric(joined.S,errors='coerce').astype(float)
joined['support_risk']=(joined.entry_open-support)/joined.entry_open
joined.loc[~np.isfinite(joined.support_risk)|(joined.support_risk<=0),'support_risk']=np.nan
joined['I_net_R']=joined.I_net/joined.support_risk
joined.to_parquet(O/'SELECTED_SAME_PATH_LABELS.parquet',index=False)
entry=cand[cand.original_I_entered&cand.pvr_known&cand.original_epoch.notna()].copy()
ent=entry.merge(lab,on=['sid','day'],validate='one_to_one')
ent['big60']=ent.complete60&ent.mfe60.ge(.3)&ent.ret60.ge(.2)
ent.to_parquet(O/'FIXED_ORIGINAL_I_ENTRY_LABELS.parquet',index=False)
status=dict(status='COMPLETE_PRICE_PATH_PAIRING_NOT_ACCOUNT',stocks=5517,original_i_buy=len(cand),pvr_known=int(cand.pvr_known.sum()),selection_rows=len(sel),shared_labels=len(lab),fixed_original_entry_rows=len(ent),account_runs=0,original_signal_reruns=0,state_rule_changes=0,parameter_searches=0,technical_correction='Original run finished and sealed all ranks, then saved all shared labels; final merge failed because S with None inferred object dtype. This finish script only casts S numeric and reuses saved ranks/labels. No economic rerun or ranking change.',selection_hash_unchanged=True)
(O/'GENERATION_COMPLETION.json').write_text(json.dumps(status,indent=2))
print(json.dumps(status,indent=2))
