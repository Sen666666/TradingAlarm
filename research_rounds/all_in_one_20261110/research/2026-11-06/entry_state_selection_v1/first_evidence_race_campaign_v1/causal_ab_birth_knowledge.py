"""Market-only three-valued original A/B birth knowledge. No economics.
UNKNOWN never silently becomes a known false birth. Shift on full warm calendar.
"""
from pathlib import Path
import hashlib,itertools,json
import numpy as np
import pandas as pd


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def bounds(cs,ps,cm,pm):
    lower=(cs==1)&(cm==1)&((ps==0)|((ps==1)&(pm==0)))
    upper=(cs!=0)&(cm!=0)&((ps!=1)|((ps!=0)&(pm!=1)))
    return lower,upper


def truth_table_check():
    records=[]
    for states in itertools.product([-1,0,1],repeat=4):
        cs,ps,cm,pm=states
        possibilities=[]
        for a,b,c,d in itertools.product(*[([0,1] if z==-1 else [z]) for z in states]):
            # Independent binary definition, not the bounds formula.
            A=(a==1 and b==0 and c==1)
            B=(a==1 and b==1 and d==0 and c==1)
            possibilities.append(A or B)
        lo,hi=bounds(cs,ps,cm,pm)
        # Independent Kleene three-valued logic for the ORIGINAL predicates.
        # This deliberately does not simplify A OR B using excluded middle.
        def eq(x,v):return None if x==-1 else x==v
        def tand(*args):
            if False in args:return False
            return None if None in args else True
        def tor(*args):
            if True in args:return True
            return None if None in args else False
        a=tand(eq(cs,1),eq(ps,0),eq(cm,1))
        b=tand(eq(cs,1),eq(ps,1),eq(pm,0),eq(cm,1))
        tri=tor(a,b)
        assert bool(lo)==(tri is True) and bool(hi)==(tri is not False),states
        assert (not lo or all(possibilities)) and (hi or not any(possibilities)),states
        records.append(dict(current_sector=cs,previous_sector=ps,current_stock=cm,previous_stock=pm,lower=bool(lo),upper=bool(hi),known=bool(lo==hi),kleene_result='UNKNOWN' if tri is None else str(tri),binary_completion_count=len(possibilities),binary_completion_all_true=all(possibilities),binary_completion_any_true=any(possibilities),binary_bounds_tight=bool(lo==all(possibilities) and hi==any(possibilities))))
    return records


def norm(x):
    return np.where(x==1,1,np.where(x==0,0,-1)).astype('int8')


def build_birth_knowledge(root):
    root=Path(root)
    d=root/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
    paths=[d/(n+'.parquet') for n in ['COMMON_K_COMPARISON','RIGHT3','KNOWN3','WARM_PREFIX_M_R','WARM_PREFIX_M_K']]+[root/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv',root/'m3_stock_birth_during_sector_v1/freeze_events.py',Path(__file__)]
    hashes={str(p):sha(p) for p in paths}
    panel=pd.read_parquet(paths[0]); roster=pd.read_csv(paths[5])
    rr=pd.concat([pd.read_parquet(d/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(d/'RIGHT3.parquet')]).sort_index()
    kk=pd.concat([pd.read_parquet(d/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(d/'KNOWN3.parquet')]).sort_index()
    assert rr.index.equals(kk.index) and rr.columns.equals(kk.columns) and not rr.index.duplicated().any()
    assert not panel.duplicated(['day','sector']).any() and not roster.sid.duplicated().any()
    assert set(roster.sid)<=set(rr.columns)
    m=rr.eq(True).astype('int8').where(kk.eq(True)&rr.notna(),-1)
    # Fill absent entries with UNKNOWN, not a historical market state.
    sectors=panel.pivot(index='day',columns='sector',values='M3_candidate').reindex(rr.index)
    sectors=pd.DataFrame(norm(sectors.to_numpy()),index=sectors.index,columns=sectors.columns)
    previous_sectors=sectors.shift().fillna(-1).astype('int8')
    previous_m=m.shift().fillna(-1).astype('int8')
    dates=rr.index[(rr.index>='2022-01-01')&(rr.index<='2026-06-30')]
    parts=[]
    for sec,ro in roster.groupby('sector_id'):
        ids=ro.sid.tolist();n=len(ids);nd=len(dates)
        cs=np.repeat(sectors.loc[dates,sec].to_numpy(),n)
        ps=np.repeat(previous_sectors.loc[dates,sec].to_numpy(),n)
        cm=m.loc[dates,ids].to_numpy().reshape(-1)
        pm=previous_m.loc[dates,ids].to_numpy().reshape(-1)
        lo,hi=bounds(cs,ps,cm,pm);known=lo==hi
        value=pd.array(lo,dtype='boolean');value[~known]=pd.NA
        reason=np.full(len(lo),'UNRESOLVED_UNKNOWN_INPUT',dtype=object)
        reason[known&~lo]='KNOWN_FALSE_NO_BIRTH'
        reason[known&~lo&(ps==1)&(pm==1)]='KNOWN_FALSE_PREVIOUS_SECTOR_AND_STOCK_TRUE'
        reason[known&~lo&(cm==0)]='KNOWN_FALSE_CURRENT_STOCK_FALSE'
        reason[known&~lo&(cs==0)]='KNOWN_FALSE_CURRENT_SECTOR_FALSE'
        reason[lo&(ps==0)]='KNOWN_TRUE_A_SECTOR_BIRTH'
        reason[lo&(ps==1)]='KNOWN_TRUE_B_STOCK_BIRTH'
        # Name all unknown input states for unresolved rows, not filled values.
        states=[cs,ps,cm,pm];names=['current_sector','previous_sector','current_stock','previous_stock']
        codes=sum((s==-1).astype('uint8')*(1<<j) for j,s in enumerate(states))
        for code in np.unique(codes[~known]):
            reason[(~known)&(codes==code)]='UNRESOLVED_UNKNOWN_INPUT:'+','.join(name for j,name in enumerate(names) if code&(1<<j))
        parts.append(pd.DataFrame(dict(day=np.repeat(dates.to_numpy(),n),sid=np.tile(ids,nd),sector=sec,ab_birth_known=known,ab_birth_true=value,ab_birth_reason=reason,current_sector_state=cs,previous_sector_state=ps,current_stock_state=cm,previous_stock_state=pm)))
    result=pd.concat(parts,ignore_index=True).sort_values(['day','sid']).reset_index(drop=True)
    assert not result.duplicated(['day','sid']).any()
    assert result.ab_birth_true.isna().equals(~result.ab_birth_known)
    result.attrs['source_hashes']=hashes
    result.attrs['calendar_start']=str(rr.index.min().date())
    result.attrs['calendar_end']=str(rr.index.max().date())
    return result


def main():
    out=Path(__file__).resolve().parent;root=out.parent
    truth=truth_table_check()
    e=build_birth_knowledge(root);hashes=e.attrs['source_hashes'].copy()
    cache=out/'ALL_MARKET_AB_INVITES.parquet';hashes[str(cache)]=sha(cache)
    inv=pd.read_parquet(cache,columns=['day','sid'])
    expected=pd.MultiIndex.from_frame(inv[['day','sid']])
    actual=pd.MultiIndex.from_frame(e.loc[e.ab_birth_true.fillna(False),['day','sid']])
    old_only=expected.difference(actual);new_only=actual.difference(expected)
    assert len(old_only)==len(new_only)==0
    assert len(expected)==len(actual)
    roster=pd.read_csv(root/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')
    qa=dict(market_only=True,no_economic_inputs=True,no_new_economics=True,truth_table_combinations=len(truth),independent_kleene_three_value_validation=True,truth_table_all_match=True,independent_binary_completion_sound_bounds=True,binary_completion_non_tight_combinations=sum(not t['binary_bounds_tight'] for t in truth),non_tight_semantics_note='Original predicate Kleene UNKNOWN is preserved when current sector=1, previous sector=UNKNOWN, current stock=1, previous stock=0; do not infer a new birth by excluded-middle simplification',full_warm_calendar_shift_before_date_filter=True,unknown_state=-1,ab_birth_true_nullable=True,unknown_birth_true_is_null=True,explicit_false_short_circuit=True,rows=len(e),symbols=e.sid.nunique(),universe_symbols=roster.sid.nunique(),days=e.day.nunique(),expected_cartesian_rows=int(roster.sid.nunique()*e.day.nunique()),start=str(e.day.min().date()),end=str(e.day.max().date()),warm_calendar_start=e.attrs['calendar_start'],birth_true=int(e.ab_birth_true.fillna(False).sum()),birth_known_false=int((e.ab_birth_known&~e.ab_birth_true.fillna(False)).sum()),birth_unknown=int((~e.ab_birth_known).sum()),invite_cache_rows=len(inv),cache_only=len(old_only),mask_only=len(new_only),exact_birth_identity=True,reason_counts={str(k):int(v) for k,v in e.ab_birth_reason.value_counts().items()},unknown_by_year={str(k):int(v) for k,v in e.loc[~e.ab_birth_known].groupby(e.day.dt.year).size().items()})
    assert qa['rows']==qa['expected_cartesian_rows']
    e.to_parquet(out/'AB_BIRTH_KNOWLEDGE.parquet',index=False)
    pd.DataFrame(truth).to_csv(out/'AB_BIRTH_KNOWLEDGE_TRUTH_TABLE.csv',index=False)
    (out/'AB_BIRTH_KNOWLEDGE_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
    (out/'AB_BIRTH_KNOWLEDGE_SOURCE_HASHES.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    names=['causal_ab_birth_knowledge.py','AB_BIRTH_KNOWLEDGE.parquet','AB_BIRTH_KNOWLEDGE_TRUTH_TABLE.csv','AB_BIRTH_KNOWLEDGE_QA.json','AB_BIRTH_KNOWLEDGE_SOURCE_HASHES.json']
    (out/'AB_BIRTH_KNOWLEDGE_ARTIFACT_HASHES.json').write_text(json.dumps({n:sha(out/n) for n in names},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(qa,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
