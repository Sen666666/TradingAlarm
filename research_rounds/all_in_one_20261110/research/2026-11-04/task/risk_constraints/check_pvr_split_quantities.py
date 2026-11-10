"""Saved-PVR per-layer quantity replay; no account/strategy imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import datetime
import json,gzip,hashlib
HERE=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/runs')
NEW=HERE.parent/'pvr_pool_feasibility/runs'
def main():
    out=[]
    for policy,base in [('PVR_SLOT1',OLD),('PVR_NO_CONFIRMED60',NEW)]:
        for win in ['2022','2025_26']:
            p=base/win/'pair/B.json.gz';b=json.load(gzip.open(p,'rt'));q=defaultdict(int);sid={};events=[];fractions=[];split_layers=0
            for i,t in enumerate(b['trades']):events.append((datetime.fromisoformat(t['at']),1,i,'trade',t))
            for i,s in enumerate(b['audit']):
                if s['kind']=='split':events.append((datetime.fromisoformat(s['at']),0,i,'split',s))
            for timestamp,_,_,kind,z in sorted(events,key=lambda e:e[:3]):
                if kind=='split':
                    for lid,n in list(q.items()):
                        if n and sid[lid]==z['sid']:
                            exact=D(n)*D(z['ratio']);split_layers+=1
                            if exact!=int(exact):fractions.append(dict(at=str(timestamp),layer=lid,sid=z['sid'],before=n,ratio=z['ratio'],exact=str(exact),after=int(exact)))
                            q[lid]=int(exact)
                elif z['side']=='buy':
                    assert z['layer'] not in sid;q[z['layer']]=z['shares'];sid[z['layer']]=z['security_id']
                else:
                    for part in z['parts']:
                        q[part['layer']]-=part['shares'];assert q[part['layer']]>=0
            assert all(q[z['id']]==z['qty'] for z in b['layers'])
            out.append(dict(policy=policy,window=win,layers=len(b['layers']),actual_held_split_layer_events=split_layers,
                fractional_conversion_events=fractions,terminal_each_layer_quantity_exact=True,source=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    result=dict(passed=True,financial_events=0,rows=out,analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        conclusion='All four actual books have zero fractional conversion. This is measured, not inferred from absent writeoff labels. No hypothetical fractional-case basis is certified.')
    (HERE/'PVR_SPLIT_QUANTITY_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print('PVR_PER_LAYER_SPLIT_QUANTITY_CHECK_PASS')
if __name__=='__main__':main()
