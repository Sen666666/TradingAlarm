"""Account-safe stock-slot intervention; no indicator/account engine, K, or admission."""
import math
import pandas as pd
import numpy as np
from ce_adapter import CELookup

REQUIRED={'sid','rank','was_empty','has_mobile_intent','has_core_intent','PVR_score','PVR_ready'}

def rank_stock_slots(frame,signal_day,lookup):
    """Return (all original stock rows + ce_stock_rank/CE diagnostics, audit dict).

    `frame` is the actual counterfactual CLOSE pending queue aggregated per stock
    AFTER unchanged native planning. Role flags must describe actual pending intents,
    never CORE/MOBILE qualification flags. rank is the original shared native stock
    rank; PVR_score/PVR_ready are the original fields. The method does not modify rank,
    priority_rank, role order or any original field. Caller applies only ce_stock_rank
    to pending execution rank, preserving original priority_rank in its logs.

    Only empty, MOBILE-only, PVR-ready/finite, CE-known whole stock slots may exchange.
    Every other slot stays fixed, including any stock with actual CORE intent. There
    is no K or truncation, sizing, cash, budget, protection, exit, or acceptance logic.
    The CE key is strictly (sid, signal CLOSE day); no old receipt carry-forward.
    """
    if not REQUIRED<=set(frame):raise ValueError('Missing actual pending stock fields: '+str(REQUIRED-set(frame)))
    if frame.sid.duplicated().any():raise ValueError('Aggregate actual pending to one row per stock')
    if frame['rank'].isna().any() or not np.isfinite(frame['rank']).all() or frame['rank'].duplicated().any():raise ValueError('Original native stock rank must be unique finite values')
    for col in ['was_empty','has_mobile_intent','has_core_intent','PVR_ready']:
        if frame[col].isna().any() or not frame[col].isin([True,False]).all():raise ValueError('Explicit Boolean required: '+col)
    original_columns=list(frame.columns)
    base=frame.copy().sort_values(['rank','sid'],kind='stable').reset_index(drop=True)
    query=[lookup.query(s,signal_day) for s in base.sid]
    base['CE']=[q['CE'] for q in query];base['CE_known']=[q['CE_known'] for q in query];base['CE_status']=[q['reason'] for q in query]
    base['CE_formation_n']=[q.get('formation_n',math.nan) for q in query]
    base['CE_variance_budget']=[q.get('variance_budget',math.nan) for q in query]
    scope=base.was_empty.astype(bool)&base.has_mobile_intent.astype(bool)&~base.has_core_intent.astype(bool)
    finite_pvr=base.PVR_ready.astype(bool)&np.isfinite(base.PVR_score)
    base['CE_movable_stock_slot']=scope&finite_pvr&base.CE_known
    known=base[base.CE_movable_stock_slot].copy();known['_ce_r12']=known.CE.round(12);known['_pvr_r12']=known.PVR_score.round(12)
    known=known.sort_values(['_ce_r12','_pvr_r12','rank','sid'],ascending=[False,False,True,True],kind='stable')
    it=iter(known.index);ix=[next(it) if base.at[i,'CE_movable_stock_slot'] else i for i in base.index]
    out=base.loc[ix].copy();out['ce_stock_rank']=base['rank'].to_numpy();out=out.reset_index(drop=True)
    # Each assigned value is an original stock rank, not a new consecutive index.
    assert sorted(out.ce_stock_rank.tolist())==sorted(frame['rank'].tolist())
    fixed=out[~out.CE_movable_stock_slot];assert fixed.ce_stock_rank.eq(fixed['rank']).all()
    pd.testing.assert_frame_equal(out.set_index('sid')[original_columns[1:]].sort_index() if original_columns[0]=='sid' else out[original_columns].sort_values('sid').reset_index(drop=True),base.set_index('sid')[original_columns[1:]].sort_index() if original_columns[0]=='sid' else base[original_columns].sort_values('sid').reset_index(drop=True),check_exact=True)
    audit=dict(signal_day=str(pd.Timestamp(signal_day).date()),stock_groups=len(base),actual_CORE_groups=int(base.has_core_intent.sum()),actual_CORE_MOBILE_groups=int((base.has_core_intent&base.has_mobile_intent).sum()),actual_empty_CORE_MOBILE_groups=int((base.was_empty&base.has_core_intent&base.has_mobile_intent).sum()),empty_MOBILE_only_groups=int(scope.sum()),movable_stock_groups=int(base.CE_movable_stock_slot.sum()),scope_PVR_unknown=int((scope&~finite_pvr).sum()),scope_CE_unknown=int((scope&~base.CE_known).sum()),changed_stock_groups=int(out.ce_stock_rank.ne(out['rank']).sum()),all_fixed_slots_exact=True,all_original_fields_unchanged=True,all_groups_retained=True,K_applied=False)
    return out,audit
