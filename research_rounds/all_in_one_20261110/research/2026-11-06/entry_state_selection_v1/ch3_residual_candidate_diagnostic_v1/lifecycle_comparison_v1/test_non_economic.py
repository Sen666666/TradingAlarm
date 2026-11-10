"""Synthetic queue tests, source derivation tests, and full feature-domain checks only."""
from pathlib import Path
import ast,json,copy,random,hashlib
import numpy as np
import pandas as pd
from adapter import O, E, ARMS, ENGINES, reorder_known, sha, save, KNOWN
from prepare_features import inputs,load_formula

def run():
    results={}
    for name in ['prepare_features.py','adapter.py','report.py','run.py',Path(__file__).name]:
        ast.parse((O/name).read_text())
    rows=[dict(event_id=str(i),window='2022',day=pd.Timestamp('2022-05-12'),sid=str(i),sector='S',PVR_score=100-i,relative_known=False) for i in range(6)]
    features={(str(i),'2022-05'):dict(status=KNOWN if i!=2 else 'UNKNOWN_MONTH_END_PRICE',RM=-10+i,RAW_MOM11=10-i) for i in range(6)}
    audit=[];out=reorder_known(copy.deepcopy(rows),{'0','2','3','5'},'CH3_RM',features,audit)
    # original feasible slots [0,2,3,5] -> [5,2,3,0], compressing holes at infeasible 1 and 4.
    assert [r['event_id'] for r in out]==['5','1','2','3','4','0']
    picked={r['event_id'] for r in audit if r['new_slot_selected']};assert picked=={'5','2'}
    unknown=next(x for x in audit if x['event_id']=='2');assert unknown['old_feasible_rank']==unknown['new_feasible_rank']==2
    results['compressed_feasible_slots_before_K2_unknown_fixed_negative_scores_allowed']=True
    broken=dict(features);broken.pop(('3','2022-05'))
    try:reorder_known(copy.deepcopy(rows),{'0'},'CH3_RM',broken,[])
    except AssertionError as e:assert 'MISSING_PRECOMPUTED_FEATURE_IS_FATAL' in str(e)
    else:raise AssertionError('Missing cache accepted')
    results['missing_cache_is_fatal_even_for_currently_infeasible_event']=True
    tie={k:dict(v,RM=1,RAW_MOM11=1) for k,v in features.items()};out=reorder_known(copy.deepcopy(rows),{str(i) for i in range(6)},'CH3_RM',tie,[])
    assert [r['event_id'] for r in out]==list(map(str,range(6)))
    rng=random.Random(20261108)
    for _ in range(2000):
        n=rng.randrange(1,15);rs=[dict(event_id=str(i),window='2024_924',day=pd.Timestamp('2024-10-08'),sid=str(i).zfill(3),sector='S',PVR_score=n-i,relative_known=False) for i in range(n)]
        ff={(r['sid'],'2024-10'):dict(status=KNOWN if rng.random()>.4 else 'UNKNOWN_MONTH_END_PRICE',RM=rng.randrange(-3,4),RAW_MOM11=rng.randrange(-3,4)) for r in rs}
        feasible={r['event_id'] for r in rs if rng.random()>.3}
        for arm in ARMS:
            aa=[];out=reorder_known(copy.deepcopy(rs),feasible,arm,ff,aa)
            assert sorted(x['event_id'] for x in out)==sorted(x['event_id'] for x in rs)
            for i,r in enumerate(rs):
                if r['event_id'] not in feasible:assert out[i]['event_id']==r['event_id']
            au=pd.DataFrame(aa);uk=au[au.feasible&~au.known]
            assert uk.old_feasible_rank.equals(uk.new_feasible_rank)
            assert int(au.new_slot_selected.sum())==min(2,len(feasible))
            if arm=='A_UNION_B':assert [r['event_id'] for r in out]==[r['event_id'] for r in rs]
    results['synthetic_permutation_cases']=6000
    # AST proves the approved 2024 change affects only the sole arm assertion.
    source=ENGINES['2024_924'].read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='run_window')
    original=ast.get_source_segment(source,node);needle=" assert arm=='A_UNION_B','Only unchanged A+B baseline authorized'\n"
    assert original.count(needle)==1;changed=original.replace(needle,' assert arm in APPROVED_CH3_ARMS\n')
    before=ast.parse(original).body[0];after=ast.parse(changed).body[0]
    assert isinstance(before.body[0],ast.Assert) and ast.dump(ast.Module(body=before.body[1:],type_ignores=[]))==ast.dump(ast.Module(body=after.body[1:],type_ignores=[]))
    results['2024_derivation_only_first_arm_assertion']=True
    f,ev,manifest=inputs();feat=pd.read_csv(O/'ALL_MARKET_STOCK_MONTH_FEATURES.csv');sealed=json.loads((O/'FEATURE_SEAL.json').read_text())
    for name,h in sealed['files'].items():assert sha(O/name)==h
    covered=ev.merge(feat,on=['sid','month'],validate='many_to_one');assert len(covered)==19795 and covered.status.notna().all()
    assert feat.loc[feat.status.eq(KNOWN),['RM','RAW_MOM11']].notna().all().all()
    results['market_event_coverage']=len(covered);results['stock_month_coverage']=len(feat)
    results['known_support_identical_RM_RAW']=True;results['no_economic_engine_imported']=True;results['no_economic_paths_executed']=True
    save(O/'NON_ECONOMIC_QA.json',results);print(json.dumps(results,indent=2))
if __name__=='__main__':run()
