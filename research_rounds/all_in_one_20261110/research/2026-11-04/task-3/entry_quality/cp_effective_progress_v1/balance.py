"""Fixed market-only CP path-loss balance. No account, sizing or return model."""
import math
import pandas as pd

LAMBDA=20.0/21.0
EPS=4*2**-53/(1-4*2**-53)
RESET_DISCARD_POSITIVE={'start','E0_down_reset','lower_anchor','E0_invalid'}

def ge(a,b):
    return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)

def calculate(cp, cp_input):
    if not cp.index.equals(cp_input.index):
        raise ValueError('exact original CP/input index required')
    if not cp.index.is_unique or not cp.index.is_monotonic_increasing:
        raise ValueError('ordered unique original observation clock required')
    required={'ready','r','m','delta_frontier','scale','receipt','reset_reason'}
    if not required<=set(cp) or 'segment_id' not in cp_input:
        raise ValueError('original used features/source identity absent')
    balance=0.0
    segment=None
    out=[]
    for day,c in cp.iterrows():
        q=cp_input.loc[day]
        if pd.isna(q.segment_id):
            raise ValueError(f'unknown source at {day}')
        changed=segment!=q.segment_id
        if changed:
            balance=0.0
            segment=q.segment_id
        before=balance
        reason=None if pd.isna(c.reset_reason) else str(c.reset_reason)
        if not bool(c.ready):
            balance=0.0
            out.append(dict(balance_before=before,loss=None,innovation=None,
                pre_balance=0.0,threshold=None,effective_advance=False,
                balance_after=balance,status='ORIGINAL_CP_UNPREPARED',
                reset_discarded_positive=False,source_changed=changed))
            continue
        vals=[c.r,c.m,c.delta_frontier]
        if not all(math.isfinite(float(v)) for v in vals):
            raise ValueError(f'unknown ready CP path facts at {day}')
        r,m,fresh=map(float,vals)
        if fresh<0:
            raise ValueError('original frontier innovation must be nonnegative')
        loss=max(-r,0.0)
        innovation=fresh*m
        pre=LAMBDA*before+innovation-loss
        discarded=reason in RESET_DISCARD_POSITIVE and pre>0
        if reason in RESET_DISCARD_POSITIVE:
            pre=min(pre,0.0)
        raw_receipt=bool(c.receipt)
        threshold=None
        accepted=False
        if raw_receipt:
            if not math.isfinite(float(c.scale)) or float(c.scale)<=0:
                raise ValueError(f'unknown original receipt used_scale at {day}')
            threshold=math.sqrt(5.0)*float(c.scale)
            accepted=ge(pre,threshold)
        balance=0.0 if accepted else pre
        out.append(dict(balance_before=before,loss=loss,innovation=innovation,
            pre_balance=pre,threshold=threshold,effective_advance=accepted,
            balance_after=balance,status='ADVANCE' if accepted else
            'RAW_CP_REJECTED_BALANCE' if raw_receipt else 'NO_RAW_CP',
            reset_discarded_positive=discarded,source_changed=changed))
    return pd.DataFrame(out,index=cp.index)
