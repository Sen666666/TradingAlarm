"""Audit only: do not change candidate formula or run another strategy."""
import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from analyze_stochastic import calc,clean,sha
O=Path(__file__).resolve().parent
c=pd.read_parquet(O/'CANDIDATE_FEATURES.parquet');sel=pd.read_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet')
assert c.score.isna().equals(c.original_PVR.isna());err=(c.score-c.original_PVR).abs().max();assert err<1e-10
assert np.allclose(c.WR,100*c.k-100,equal_nan=True)
# Label poison test uses only predeclared ranking columns and reproduces sealed sets.
def pick(g):
 base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(g));ks=base.head(K).groupby('sector').size().to_dict();ss=set()
 for sector,gg in base.groupby('sector',sort=False):
  ids=list(gg.index);pos=[j for j,i in enumerate(ids) if g.at[i,'known']];knownids=[ids[j] for j in pos];new=sorted(knownids,key=lambda i:(-round(float(g.at[i,'scoreK']),12),float(g.at[i,'original_priority_rank']),g.at[i,'sid']));alt=ids.copy()
  for j,i in zip(pos,new):alt[j]=i
  ss.update((g.at[i,'day'],g.at[i,'sid']) for i in alt[:ks.get(sector,0)])
 return ss
poisoned=c.copy();poisoned['ret20']=np.arange(len(c))[::-1]*999;poisoned['round_pnl']=-999999999.;poisoned['future_high']=1e50
out=set()
for d,g in poisoned.groupby('day'):out.update(pick(g))
ss=sel[sel.method.eq('STOCH')];assert out==set(zip(ss.day,ss.sid))
# Symmetric alternation in the upper part of a large H/L box: no net trend,
# but the custom directional weighting introduces a systematically positive score.
n=130;close=100+np.array([(-1.)**j for j in range(n)])
p=pd.DataFrame(dict(close=close,high=102.,low=90.,amount=1e8,segment_id=0,source_kind='synthetic'),index=pd.date_range('2000-01-01',periods=n))
z=calc(p,True);pd.testing.assert_frame_equal(calc(p.iloc[:95],True),z.iloc[:95],check_exact=True)
row=dict(name='upper_box_sideways',mean_original_score=z.score.dropna().mean(),mean_fused_score=z.scoreK.dropna().mean(),mean_k=z.k.dropna().mean(),mean_rangebias=z.rangebias.dropna().mean(),last=z.iloc[-1].to_dict())
z.to_csv(O/'SYNTHETIC_UPPER_BOX.csv');(O/'SYNTHETIC_UPPER_BOX_SUMMARY.json').write_text(json.dumps(clean(row),indent=2))
# HLC invalid resets range14 + complete21 fusion (34 rows to rebuild after last bad bar).
p2=p.copy();p2.loc[p2.index[90],'high']=np.nan;q=calc(p2)
assert q.loc[p2.index[90:124],'scoreK'].isna().all() and np.isfinite(q.loc[p2.index[124],'scoreK'])
# H/L change alone can generate bearish range divergence with an increasing close.
a=dict(C0=100,H0=101,L0=90,C1=101,H1=110,L1=90);a['K0']=(a['C0']-a['L0'])/(a['H0']-a['L0']);a['K1']=(a['C1']-a['L1'])/(a['H1']-a['L1']);assert a['C1']>a['C0'] and a['K1']<a['K0']
# No new rule: descriptive 60-common-session blocks of fixed20 paired outcomes.
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
cal=pd.DatetimeIndex(np.load(HP,allow_pickle=False)['dates']);cal=cal[cal>='2022-01-01'];pa=pd.read_csv(O/'PAIRED_DAILY.csv');pa=pa[pa.H.eq(20)].copy();pa['block']=[int(cal.get_loc(pd.Timestamp(d))//60) for d in pa.day]
blocks=pa.groupby('block').agg(days=('day','size'),delta_ret=('delta_ret','mean'),total_delta=('delta_ret','sum')).reset_index();blocks.to_csv(O/'BLOCK60_FIXED20.csv',index=False)
best=blocks.loc[blocks.total_delta.idxmax()];worst=blocks.loc[blocks.total_delta.idxmin()]
r=dict(baseline_missingness_exact=True,baseline_max_error=err,williams_equals_fastK_minus100=True,poisoned_future_labels_same_selection=True,poisoned_days=int(c.day.nunique()),HLC_reset_rewarm34=True,range_divergence_counterexample=a,common60_blocks=len(blocks),positive_blocks=int(blocks.delta_ret.gt(0).sum()),negative_blocks=int(blocks.delta_ret.lt(0).sum()),all20_delta=pa.delta_ret.mean(),leave_best_block20_delta=pa[pa.block.ne(best.block)].delta_ret.mean(),leave_worst_block20_delta=pa[pa.block.ne(worst.block)].delta_ret.mean(),extra_source_sha256={str(HP):sha(HP)})
(O/'SUPPLEMENT_CHECKS.json').write_text(json.dumps(clean(r),indent=2));print(json.dumps(clean(r)));print(json.dumps(clean(row)))
