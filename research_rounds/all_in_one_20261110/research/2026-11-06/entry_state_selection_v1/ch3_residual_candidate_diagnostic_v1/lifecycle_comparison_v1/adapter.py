"""Bounded queue adapter over unchanged repaired economic engines."""
from pathlib import Path
import ast, importlib.util, hashlib, json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parent.parent/'m3_stock_birth_during_sector_v1'
ENGINES={'2022':E/'relative_priority_equity_run_2022_v1/engine.py','2024_924':E/'cash_equity_baseline_2024_v1/engine.py'}
OLD_OUTPUTS={'2022':ENGINES['2022'].parent/'dynamic','2024_924':ENGINES['2024_924'].parent/'economic'}
ARMS=['A_UNION_B','RAW_MOM11','CH3_RM'];KNOWN='CALENDAR_COMPUTABLE_RELEASE_UNKNOWN'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def load_engine(window):
    p=ENGINES[window];spec=importlib.util.spec_from_file_location('repaired_engine_'+window,p)
    s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
    if window=='2024_924':
        text=p.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='run_window')
        code=ast.get_source_segment(text,node)
        line=" assert arm=='A_UNION_B','Only unchanged A+B baseline authorized'\n"
        assert code.count(line)==1;code=code.replace(line,' assert arm in APPROVED_CH3_ARMS\n')
        s.APPROVED_CH3_ARMS=ARMS
        exec(compile(code,str(p)+':only_arm_assertion_expanded','exec'),s.__dict__)
    return s

def reorder_known(rows,feasible,arm,feature_lookup,audit):
    assert arm in ARMS
    base=[r for r in rows if r['event_id'] in feasible]
    for r in rows:
        key=(r['sid'],str(pd.Period(r['day'],freq='M')))
        assert key in feature_lookup, ('MISSING_PRECOMPUTED_FEATURE_IS_FATAL',key,r['event_id'])
        r['ch3_feature']=feature_lookup[key]
    known=[r for r in base if r['ch3_feature']['status']==KNOWN]
    score='RM' if arm=='CH3_RM' else 'RAW_MOM11'
    promoted=sorted(known,key=lambda r:(-r['ch3_feature'][score],-r['PVR_score'],r['sid'])) if arm!='A_UNION_B' else known
    it=iter(promoted);ordered=[next(it) if r['ch3_feature']['status']==KNOWN else r for r in base]
    old={r['event_id']:i+1 for i,r in enumerate(base)};new={r['event_id']:i+1 for i,r in enumerate(ordered)}
    assert sorted(new.values())==list(range(1,len(base)+1))
    K=min(2,len(base))
    for r in rows:
        eid=r['event_id'];feat=r['ch3_feature'];k=feat['status']==KNOWN
        r.update(feasible_at_ranking=eid in feasible,original_feasible_rank=old.get(eid,np.nan),new_feasible_rank=new.get(eid,np.nan),relative_unknown=not bool(r.get('relative_known') is True or r.get('relative_known')==1))
        if eid in feasible and not k: assert old[eid]==new[eid]
        audit.append(dict(window=r['window'],arm=arm,event_id=eid,day=r['day'],sid=r['sid'],sector=r['sector'],feature_status=feat['status'],known=k,RM=feat.get('RM'),RAW_MOM11=feat.get('RAW_MOM11'),PVR_score=r['PVR_score'],feasible=eid in feasible,old_feasible_rank=old.get(eid),new_feasible_rank=new.get(eid),K=K,baseline_slot_selected=eid in old and old[eid]<=K,new_slot_selected=eid in new and new[eid]<=K,feature_max_input_date=feat.get('max_input_date'),historical_release_known=False))
    it=iter(ordered)
    return [next(it) if r['event_id'] in feasible else r for r in rows]

def install(s,features):
    lookup={(r['sid'],r['month']):r for r in features.to_dict('records')};s.ch3_audit=[]
    native=s.queue
    # Baseline queue is not rewritten: bridge reproduction includes its original ranking receipts.
    text=s.SOURCE.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='queue')
    code=ast.get_source_segment(text,node);needle="out=reorder(rows,feasible,relative=arm=='RELATIVE_UP_PRIORITY')"
    assert code.count(needle)==1
    code=code.replace('def queue(','def ch3_queue(').replace(needle,'out=ch3_reorder(rows,feasible,arm)')
    s.ch3_reorder=lambda rows,feasible,arm:reorder_known(rows,feasible,arm,lookup,s.ch3_audit)
    exec(compile(code,str(s.SOURCE)+':queue_reorder_only','exec'),s.__dict__)
    def dispatch(g,states,arm):
        return native(g,states,arm) if arm=='A_UNION_B' else s.ch3_queue(g,states,arm)
    s.queue=dispatch
    s.hashes[str(Path(__file__))]=sha(Path(__file__))
    return lookup

def compare_table(actual,expected,keys,columns=None):
    a=actual.sort_values(keys).reset_index(drop=True);b=expected.sort_values(keys).reset_index(drop=True)
    assert len(a)==len(b),(len(a),len(b),keys)
    for c in columns or list(b.columns):
        if c not in a:assert b[c].isna().all(),c;a[c]=np.nan
        x=a[c];y=b[c]
        if pd.api.types.is_numeric_dtype(y) and not pd.api.types.is_bool_dtype(y):
            ok=np.isclose(pd.to_numeric(x,errors='coerce').to_numpy(float),pd.to_numeric(y,errors='coerce').to_numpy(float),atol=1e-7,rtol=1e-12,equal_nan=True)
        else:
            def norm(v):
                if pd.isna(v) or (c=='duration_bucket' and str(v)=='nan'):return ''
                t=str(v);return t[:10] if len(t)>10 and t[4:5]=='-' and t[7:8]=='-' and t[10:11] in (' ','T') else t
            ok=x.map(norm).eq(y.map(norm)).to_numpy()
        assert ok.all(),(c,[(a.iloc[j][keys].to_dict(),x.iloc[j],y.iloc[j]) for j in np.where(~ok)[0][:3]])
    return dict(rows=len(a),columns=len(columns or b.columns),match=True)

def bridge_compare(s,window):
    root=OLD_OUTPUTS[window];checks={}
    for name,arr in [('ROUNDS',s.rounds),('ACTIONS',s.actions),('DECISIONS',s.decisions),('RANKING_AUDIT',s.ranking_audit),('END_STATES',s.blocks),('REGISTRATIONS',s.registrations),('CLAIM_LEDGER',s.claim_ledger),('PROFIT_GATES',s.marks)]:
        b=pd.read_csv(root/(name+'.csv'),float_precision='round_trip',low_memory=False)
        b=b[b.arm.eq('A_UNION_B')];a=pd.DataFrame(arr);a=a[a.arm.eq('A_UNION_B')]
        # Preserve source order; duplicate same-round/day gate calls remain identity-sensitive.
        checks[name]=compare_table(a.assign(_row=range(len(a))),b.assign(_row=range(len(b))),['_row'])
    for name,obj in [('CLAIMS',list(s.claims.values())),('BRIDGES',s.bridges)]:
        expected=json.loads((root/(name+'.json')).read_text());expected=[x for x in expected if x['arm']=='A_UNION_B']
        actual=[x for x in json.loads(json.dumps(obj,default=str)) if x['arm']=='A_UNION_B']
        assert actual==expected,(window,name,'exact JSON identity mismatch')
        checks[name]=dict(rows=len(actual),exact_match=True)
    return checks
