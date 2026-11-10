"""Final scope: rank all current empty first-entry stock slots with current native CE."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
import numpy as np
from ce_adapter import CELookup
REQUIRED={'sid','rank','was_empty','has_mobile_intent','has_core_intent','PVR_score','PVR_ready'}

def load_empty_first_inputs(directory=None):
    """Verify final scope manifest and load immutable CE inputs; no account state."""
    root=Path(directory) if directory is not None else Path(__file__).resolve().parent
    manifest=json.loads((root/'EMPTY_FIRST_MANIFEST.json').read_text())
    for name,h in manifest['runtime_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=h:raise ValueError('Final empty-first artifact hash mismatch: '+name)
    return CELookup(root,verify_hashes=True)

def rank_empty_first_stock_slots(frame,signal_day,lookup):
    """Return (all stock rows with ce_stock_rank, audit). Never truncate.

    Required frame fields are actual current pending stock groups, after unchanged
    native planning. Only was_empty + finite/ready original PVR + known CURRENT
    original fresh-CP CE can exchange whole-stock slots. CORE is not excluded and
    MOBILE is not required. No old CE carry-forward. Caller retains original CORE
    before MOBILE role order, done-per-stock, qualification, cash, size and execution.
    Original fields including rank/priority_rank are preserved; only added
    ce_stock_rank is to be applied to pending execution rank by the caller.
    """
    if not REQUIRED<=set(frame):raise ValueError('Missing pending stock fields: '+str(REQUIRED-set(frame)))
    if frame.sid.duplicated().any():raise ValueError('One actual pending row per stock required')
    for c in ['was_empty','has_mobile_intent','has_core_intent','PVR_ready']:
        if frame[c].isna().any() or not frame[c].isin([True,False]).all():raise ValueError('Explicit Boolean required: '+c)
    original_columns=list(frame.columns);base=frame.copy().reset_index(drop=True)
    native=pd.to_numeric(base['rank'],errors='coerce')
    if native.isna().any() or not np.isfinite(native).all() or native.duplicated().any():raise ValueError('Unique finite native stock ranks required')
    base['_CE_original_rank_numeric']=native
    base=base.sort_values(['_CE_original_rank_numeric','sid'],kind='stable').reset_index(drop=True)
    q=[lookup.query(s,signal_day) for s in base.sid]
    base['CE']=pd.Series([r['CE'] for r in q],index=base.index,dtype=float)
    base['CE_known']=pd.Series([r['CE_known'] for r in q],index=base.index,dtype=bool)
    base['CE_status']=pd.Series([r['reason'] for r in q],index=base.index,dtype=object)
    base['CE_formation_n']=[r.get('formation_n',math.nan) for r in q]
    base['CE_variance_budget']=[r.get('variance_budget',math.nan) for r in q]
    pvr=pd.to_numeric(base.PVR_score,errors='coerce')
    pvr_ok=base.PVR_ready.astype(bool)&np.isfinite(pvr)
    base['CE_movable_stock_slot']=base.was_empty.astype(bool)&pvr_ok&base.CE_known
    base['_CE_PVR_numeric']=pvr
    known=base[base.CE_movable_stock_slot].copy();known['_CE_round12']=known.CE.round(12);known['_PVR_round12']=known._CE_PVR_numeric.round(12)
    known=known.sort_values(['_CE_round12','_PVR_round12','_CE_original_rank_numeric','sid'],ascending=[False,False,True,True],kind='stable')
    it=iter(known.index);ix=[next(it) if base.at[i,'CE_movable_stock_slot'] else i for i in base.index]
    out=base.loc[ix].copy();out['ce_stock_rank']=base['rank'].to_numpy();out=out.reset_index(drop=True)
    out=out.drop(columns=['_CE_original_rank_numeric','_CE_PVR_numeric'])
    pd.testing.assert_frame_equal(out[original_columns].sort_values('sid').reset_index(drop=True),frame[original_columns].sort_values('sid').reset_index(drop=True),check_exact=True)
    fixed=out[~out.CE_movable_stock_slot];assert fixed.ce_stock_rank.eq(fixed['rank']).all()
    assert sorted(pd.to_numeric(out.ce_stock_rank).tolist())==sorted(native.tolist()) and len(out)==len(frame)
    core=base.has_core_intent.astype(bool);mobile=base.has_mobile_intent.astype(bool);empty=base.was_empty.astype(bool)
    audit=dict(scope='ALL_CURRENT_EMPTY_FIRST_ENTRY_STOCK_SLOTS',signal_day=str(pd.Timestamp(signal_day).date()),stock_groups=len(base),empty_groups=int(empty.sum()),held_groups=int((~empty).sum()),empty_CORE_MOBILE=int((empty&core&mobile).sum()),empty_CORE_only=int((empty&core&~mobile).sum()),empty_MOBILE_only=int((empty&~core&mobile).sum()),empty_CORE_only_with_current_CE=int((empty&core&~mobile&base.CE_known).sum()),movable_stock_groups=int(base.CE_movable_stock_slot.sum()),empty_PVR_unknown=int((empty&~pvr_ok).sum()),empty_CE_unknown=int((empty&~base.CE_known).sum()),fixed_stock_groups=int((~base.CE_movable_stock_slot).sum()),changed_stock_groups=int(out.ce_stock_rank.ne(out['rank']).sum()),CORE_groups_moved=int((out.has_core_intent&out.ce_stock_rank.ne(out['rank'])).sum()),all_fixed_slots_exact=True,original_fields_unchanged=True,all_stock_groups_retained=True,K_applied=False)
    return out,audit
