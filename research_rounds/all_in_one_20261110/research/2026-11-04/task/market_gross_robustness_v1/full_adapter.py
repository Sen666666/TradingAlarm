"""Fixed full jobs; reuse the small-reviewed runner and all economic methods."""
import robust_adapter as R

A,N,J,L,IO,K=R.A,R.N,R.J,R.L,R.IO,R.K
JOBS={
 'cost1-long':dict(window='long',family='cost1',labels=['MA63_G05','MA63_G20','MA62_G10','MA64_G10']),
 'cost1-strong':dict(window='strong',family='cost1',labels=['MA62_G10','MA64_G10']),
 'cost15-long':dict(window='long',family='cost15',labels=['NO60_C15','MA63_G10_C15']),
 'cost15-strong':dict(window='strong',family='cost15',labels=['NO60_C15','MA63_G10_C15']),
}

def runner(job,shared,receipts,*,infos,fixed_end,**kw):
 spec=JOBS[job]
 cls=R.CostRunner if spec['family']=='cost15' else R.Runner
 result=cls(shared,receipts,infos=infos,family=spec['family'],fixed_end=fixed_end,
            labels=spec['labels'],technical_control=False,**kw)
 assert list(result.accounts)==spec['labels']
 assert result.planning.__func__ is R.Runner.planning
 assert result.restore.__func__ is R.Runner.restore
 assert result.opening.__func__ is (K.cost_opening if spec['family']=='cost15' else J.Runner.opening)
 assert not any(hasattr(a,'capacity_basis') for a in result.accounts.values())
 result.assert_native_wiring()
 return result
