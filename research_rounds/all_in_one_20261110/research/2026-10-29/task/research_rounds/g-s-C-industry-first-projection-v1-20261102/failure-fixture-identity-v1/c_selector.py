"""Rank-only C wrapper over the frozen B pure selector; no account API."""
from pathlib import Path
from decimal import Decimal
import copy, sys, json, hashlib, math

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'g-s-B-joint-target-v2-20261102'
DESIGN=HERE.parent/'g-s-C-industry-first-target-design-20261102/CONTRACT_PROPOSAL.txt'
sys.path.insert(0,str(BASE))
import selector as B
J=B.J
BASE_SHA='44e7345ef2b3fc494e9854216579aa5faa0e0557b4ecbc207b1027b102e401a8'
JOINT_SHA='b76660a053a09a4e394b32b9ccc61f709cdc98ac6bf900a425f476700c7771cf'
CONTRACT_SHA='dafcf956c6ec888b3399bef04557e857a6fa54750014c9701a58847b66897802'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):J.N.IO.write_json(p,json.loads(json.dumps(x,ensure_ascii=False,default=str)))
def guard():
    assert sha(BASE/'selector.py')==BASE_SHA,'frozen B source changed'
    assert sha(J.__file__)==JOINT_SHA,'frozen joint guard changed'
    assert sha(DESIGN)==CONTRACT_SHA,'C contract changed'

def transform(s,ds,evidence):
    """Only lots[].rank_key and demands[].priority may differ in solver input."""
    J.schema(s,ds)
    if J.aware(evidence['known_at'])>J.aware(s['at']):raise ValueError('future industry H1')
    if evidence['day']!=s['at'][:10]:raise ValueError('industry H1 decision date mismatch')
    candidates={}
    def include(sid,sector,key):
        value=(sector,list(key))
        if sid in candidates and candidates[sid]!=value:raise ValueError('same stock original key/sector mismatch')
        candidates[sid]=value
    for z in s['lots']:
        if z['role']=='mobile' and z.get('B_donor_eligible'):include(z['sid'],z['sector'],z['rank_key'])
    for d in ds:include(d['sid'],d['sector'],d['priority'])
    sectors=sorted({v[0] for v in candidates.values()})
    unknown=[sec for sec in sectors if evidence['industry_H1'].get(sec) is None or not math.isfinite(float(evidence['industry_H1'][sec]))]
    if unknown:raise ValueError('UNKNOWN industry H1; full comparison not ready: '+','.join(unknown))
    ordered=sorted(sectors,key=lambda sec:(-round(float(evidence['industry_H1'][sec]),12),sec))
    sr={sec:i for i,sec in enumerate(ordered)}
    keys={sid:[sr[sec],*old] for sid,(sec,old) in candidates.items()}
    ss=copy.deepcopy(s);dd=copy.deepcopy(ds)
    for z in ss['lots']:
        if z['sid'] in keys:z['rank_key']=keys[z['sid']]
    for d in dd:d['priority']=keys[d['sid']]
    # Prove rank-only change; prices, floors, quantity, fees, receipts and assets stay exact.
    recovered_s=copy.deepcopy(ss);recovered_d=copy.deepcopy(dd)
    for a,b in zip(recovered_s['lots'],s['lots']):a['rank_key']=copy.deepcopy(b['rank_key'])
    for a,b in zip(recovered_d,ds):a['priority']=copy.deepcopy(b['priority'])
    assert J.digest(recovered_s)==J.digest(s) and J.digest(recovered_d)==J.digest(ds)
    audit=dict(industry_order=ordered,industry_H1={sec:evidence['industry_H1'][sec] for sec in sectors},
        stock_priority={sid:dict(sector=candidates[sid][0],original_key=candidates[sid][1],C_key=key) for sid,key in keys.items()},
        original_snapshot_sha256=J.digest(s),original_demands_sha256=J.digest(ds),industry_evidence_sha256=J.digest(evidence),
        financial_fields_and_receipts_exact=True,no_new_scores=True)
    return ss,dd,audit

def solve_C(s,ds,evidence,**kwargs):
    guard();before=J.digest((s,ds,evidence));ss,dd,audit=transform(s,ds,evidence)
    result=B.solve_B(ss,dd,**kwargs)
    inherited=result.pop('result_id')
    result.update(policy='C_INDUSTRY_FIRST',base_B_result_id=inherited,C_rank_binding=audit,
        C_selector_sha256=sha(__file__),C_contract_sha256=sha(DESIGN),industry_evidence_sha256=J.digest(evidence),
        source_joint_guard_unchanged=True,submit_allowed=False,financial_events=0)
    result['result_id']=J.digest(result)
    assert J.digest((s,ds,evidence))==before
    return result

def verify_result(x,r):
    guard()
    assert r['result_id']==J.digest({k:v for k,v in r.items() if k!='result_id'}),'result body changed'
    assert r['C_selector_sha256']==sha(__file__),'C source binding changed'
    assert r['C_contract_sha256']==CONTRACT_SHA
    assert r['selector_sha256']==BASE_SHA and r['joint_guard_sha256']==JOINT_SHA
    assert r['C_rank_binding']['original_snapshot_sha256']==J.digest(x['snapshot'])
    assert r['C_rank_binding']['original_demands_sha256']==J.digest(x['B_demands'])
    assert r['industry_evidence_sha256']==J.digest(x['industry_evidence'])
    return True

if __name__=='__main__':
    # Cross-process verification/recomputation of a static projection only.
    ip=Path(sys.argv[1]);assert sha(ip)==sys.argv[2],'trusted input bytes changed'
    x=read(ip);r=read(sys.argv[3]);verify_result(x,r)
    rerun=solve_C(x['snapshot'],x['B_demands'],x['industry_evidence'])
    assert rerun['result_id']==r['result_id'],'restored pure target mismatch'
    save(sys.argv[4],dict(exact=True,result_id=rerun['result_id'],Q=rerun['Q'],D=rerun['D'],financial_events=0))
