"""Read-only pure-projection equivalence and Decimal memo-context test."""
import pickle,time
from decimal import localcontext
import adapter_v2 as A
def main():
    rows=[]
    for window in ['2025_26','2022']:
        p=A.HERE/'gates'/window/'OFF-physical/FINAL.pkl';s=A.read(p.with_suffix('.provenance.json'))
        A.E.require(A.sha(p)==s['checkpoint_sha256'],'original prefix bytes changed')
        r=pickle.loads(p.read_bytes());r.account.owner=r
        A.E.require(r.binding()==s['binding'],'original adapter1 identity changed')
        row=r.results[-1];c=row['certificate'];v=r.trusted[c['trusted_id']]
        original=row['projection'];r.__class__=A.Runner;t=time.perf_counter()
        args=(v['snapshot'],v['demands'],v['evidence'],v['budget_before'])
        n=r._memo_misses;first=r._solve(*args);A.E.require(first==original,'memo v2 changes default-context pure result')
        A.E.require(r._memo_misses==n+1,'v2 first source did not recompute')
        n=r._memo_misses;r._solve(*args);A.E.require(r._memo_misses==n,'same-context immutable memo missed')
        with localcontext() as context:
            context.prec+=1;r._solve(*args);A.E.require(r._memo_misses==n+1,'different Decimal precision reused cached result')
        r._solve(*args);A.E.require(r._memo_misses==n+2,'restored Decimal precision reused changed-context result')
        rows.append(dict(window=window,original_prefix_sha256=A.sha(p),default_context_result_exact=True,same_context_hit=True,changed_context_miss=True,restored_context_miss=True,seconds=time.perf_counter()-t))
    A.save(A.HERE/'MEMO_V2_GATE.json',dict(passed=True,rows=rows,account_events=0,base_adapter_sha256=A.sha(A.V1.__file__),memo_adapter_sha256=A.sha(A.__file__),economic_changes=0))
if __name__=='__main__':main()
