"""Finite post-audit boundary: all 17 frozen fixtures under declared unit change.

Never alters frozen sources or the previously delivered reference/audit.
"""
from pathlib import Path
import sys, json, hashlib
from collections import Counter
from datetime import datetime,timezone
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROUND=HERE.parents[1]
sys.path.insert(0,str(ROUND/'code-v1'))
from fixtures import fixtures
from model import three_axis_frame

DISCRETE=['pre_direction','pre_episode','direction','episode','episode_age','progress_age',
          'support_advances','structure_broken','structure_created','pivot_confirmed',
          'down_events','up_events','down_union_parts','up_union_parts','oldest_down_age',
          'oldest_up_age','impulse_created','init']
IDENTITIES=['observation','date','kind','direction','episode','event',
            'origin_observation','extreme_observation','pivot_observation',
            'birth_observation','birth_episode','birth']

def signature(e):return {k:e[k] for k in IDENTITIES if k in e}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    reports=[]
    for key,f in fixtures().items():
        base,jbase=three_axis_frame(f)
        scaled=f.copy();scaled['close']*=17.;scaled['volume']*=10000.
        altered,jaltered=three_axis_frame(scaled)
        cols=[c for c in base if not c.endswith('_price')]
        masks={};discrete={};large={}
        for c in cols:
            mm=base[c].isna()!=altered[c].isna()
            if mm.any():masks[c]=[str(d.date()) for d in base.index[mm]]
            if c in DISCRETE:
                diff=(base[c]!=altered[c]) & ~(base[c].isna() & altered[c].isna())
                if diff.any():
                    discrete[c]=[dict(date=str(d.date()),base=float(base.loc[d,c]),scaled=float(altered.loc[d,c]))
                                 for d in base.index[diff]]
            av,bv=base[c].to_numpy(),altered[c].to_numpy()
            if not np.allclose(av,bv,atol=1e-9,rtol=1e-9,equal_nan=True):
                z=np.abs(av-bv)
                large[c]=float(np.nanmax(z)) if np.isfinite(z).any() else None
        jb,ja=[signature(e) for e in jbase],[signature(e) for e in jaltered]
        first=None
        for i in range(max(len(jb),len(ja))):
            a,b=jb[i] if i<len(jb) else None,ja[i] if i<len(ja) else None
            if a!=b:first=dict(position=i,base=a,scaled=b);break
        row=dict(fixture=key,rows=len(f),nonprice_columns=len(cols),unknown_masks_identical=not masks,
                 lifecycle_discrete_identical=not discrete,event_time_identity_signatures_identical=jb==ja,
                 all_nonprice_columns_close_1e9=not large,unknown_mask_differences=masks,
                 discrete_differences=discrete,nonprice_not_close=large,
                 base_event_counts=dict(Counter(e['kind'] for e in jbase)),
                 scaled_event_counts=dict(Counter(e['kind'] for e in jaltered)),
                 first_event_signature_difference=first)
        row['passed']=not masks and not discrete and jb==ja and not large
        reports.append(row)
        if key=='flat_box' or not row['passed']:
            ff=f[['close','volume']].join(base.add_prefix('base_')).join(altered.add_prefix('unit17_'))
            ff.to_csv(HERE/(key+'-unit17-boundary.csv'))
            (HERE/(key+'-unit17-base-events.json')).write_text(json.dumps(jbase,ensure_ascii=False,indent=2)+'\n')
            (HERE/(key+'-unit17-scaled-events.json')).write_text(json.dumps(jaltered,ensure_ascii=False,indent=2)+'\n')
    out=dict(recorded_at=datetime.now(timezone.utc).isoformat(),
             scope='Finite additional unit boundary audit; does not replace earlier implementation/identity audit.',
             transformation=dict(price=17.,volume=10000.),frozen_code_sha256=sha(ROUND/'code-v1/model.py'),
             technical_revisions_applied=0,accounts=0,network_requests=0,
             fixtures=len(reports),passed=sum(r['passed'] for r in reports),reports=reports)
    (HERE/'all-fixture-unit-boundary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='reports'},ensure_ascii=False,indent=2))
    print(json.dumps([{k:r[k] for k in ['fixture','passed','unknown_masks_identical','lifecycle_discrete_identical',
         'event_time_identity_signatures_identical','base_event_counts','scaled_event_counts',
         'first_event_signature_difference']} for r in reports if not r['passed']],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
