"""Pure causal entry-generation metadata; original market root is authoritative.
No orders, balances, sorting, industry permissions, or outcome labels are read.
"""
import numpy as np
import pandas as pd

def compute(q,x):
    assert q.index.equals(x.index) and not q.index.has_duplicates
    ohlc=q[['open','high','low','close']]
    valid=np.isfinite(ohlc).all(axis=1)&ohlc.gt(0).all(axis=1)&q.high.ge(ohlc.max(axis=1))&q.low.le(ohlc.min(axis=1))
    for c in ['price_eligible','observed_bar','is_observed_bar']:valid &= q[c].fillna(False).astype(bool)
    for c in ['source_invalid','synthetic_event_bar']:valid &= ~q[c].fillna(True).astype(bool)
    ids=q[['source_kind','source_path','segment_id']];valid &= ids.notna().all(axis=1)
    contiguous=(~valid|~valid.shift(fill_value=False)|~ids.eq(ids.shift()).all(axis=1)).cumsum()
    age=valid.groupby(contiguous).cumcount()
    hi=q.high.rolling(20,min_periods=20).max().shift(1).where(valid&age.ge(20))
    dates=q.index;out=[];root=None;active=False;gen=None;u=np.nan;birth=pd.NaT;root_identity=None;dead=False;ever=False;first=pd.NaT;lastretired=pd.NaT
    # Scalar transition consumes only today's CLOSE and past state.
    for i,(d,r) in enumerate(x.iterrows()):
        event='NONE';status='DENY_NO_PARENT_ROOT'
        identity=tuple(ids.iloc[i]);same=identity==root_identity
        if bool(r.root_unknown):
            active=False;dead=True;status='UNKNOWN_PARENT_ROOT';event='PARENT_UNKNOWN'
        elif bool(r.failed):
            active=False;dead=True;status='DENY_PARENT_FAILED';event='PARENT_FAILED'
        elif pd.isna(r.root_day) or not bool(r.active):
            root=None;active=False;gen=None;u=np.nan;birth=pd.NaT;root_identity=None;dead=False;ever=False;first=pd.NaT;lastretired=pd.NaT
        elif bool(r.born):
            root=pd.Timestamp(r.root_day);root_identity=identity;gen=1;u=float(r.U);birth=d;ever=False;first=pd.NaT;lastretired=pd.NaT
            if not valid.iloc[i] or not np.isfinite(hi.iloc[i]):
                active=False;dead=True;status='UNKNOWN_BIRTH_SOURCE';event='PARENT_BIRTH_UNKNOWN_SOURCE'
            else:
                assert q.close.iloc[i]>hi.iloc[i] and np.isclose(u,hi.iloc[i],rtol=1e-12,atol=1e-12),('BIRTH_ANCHOR_MISMATCH',d)
                active=True;dead=False;status='ALLOW';event='ORIGINAL_BIRTH'
        else:
            assert root is not None and pd.Timestamp(r.root_day)==root,('MISSING_OR_WRONG_PARENT_STATE',d,r.root_day,root)
            if dead:
                active=False;status='UNKNOWN_RETIRED_SOURCE_GENERATION'
            elif not valid.iloc[i] or not same:
                active=False;dead=True;status='UNKNOWN_SOURCE';event='SOURCE_UNKNOWN'
            else:
                c=float(q.close.iloc[i])
                if c<=float(r.U):
                    ever=True
                    if pd.isna(first):first=d
                if active:
                    if c<=u:active=False;lastretired=d;event='ENTRY_GENERATION_RETIRED'
                elif np.isfinite(hi.iloc[i]) and c>hi.iloc[i]:
                    active=True;gen+=1;u=float(hi.iloc[i]);birth=d;event='NEW_ENTRY_GENERATION'
                status='ALLOW' if active else 'DENY_ENTRY_GENERATION_INACTIVE'
        out.append(dict(day=d,generation=gen,generation_birth=birth,entry_U=u,entry_active=active,gate_status=status,event=event,ever_returned_to_root_U=ever,first_return_to_root_U=first,last_generation_retired=lastretired,contemporary_prior20_high=float(hi.iloc[i]),current20_high_break=bool(np.isfinite(hi.iloc[i]) and q.close.iloc[i]>hi.iloc[i]),gate_source_valid=bool(valid.iloc[i]),gate_known_at='CLOSE'))
    return pd.DataFrame(out).set_index('day')
