"""Same saved per-layer replay as check_pvr_split_quantities.py, two matched-D1 books."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import datetime
import json,gzip,hashlib
HERE=Path(__file__).resolve().parent
def main():
    paths=[('PVR_SLOT1',Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-d1-v2-composition-preflight-20261101/run-PVR-D1/pair/B.json.gz')),
        ('PVR_NO_CONFIRMED60',HERE.parent/'pvr_pressure_readiness/run-D1-strong/pair/B.json.gz')]
    out=[]
    for policy,p in paths:
        b=json.load(gzip.open(p,'rt'));q=defaultdict(int);sid={};events=[];fractions=[];split_layers=0
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
            elif z['side']=='buy':assert z['layer'] not in sid;q[z['layer']]=z['shares'];sid[z['layer']]=z['security_id']
            else:
                for part in z['parts']:q[part['layer']]-=part['shares'];assert q[part['layer']]>=0
        assert all(q[z['id']]==z['qty'] for z in b['layers'])
        out.append(dict(policy=policy,scope='matched_D1_strong',layers=len(b['layers']),actual_held_split_layer_events=split_layers,
            fractional_conversion_events=fractions,terminal_each_layer_quantity_exact=True,source=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    result=dict(passed=True,financial_events=0,rows=out,analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reused_algorithm_source=str(HERE/'check_pvr_split_quantities.py'),reused_algorithm_source_sha256=hashlib.sha256((HERE/'check_pvr_split_quantities.py').read_bytes()).hexdigest())
    (HERE/'PVR_D1_SPLIT_QUANTITY_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
