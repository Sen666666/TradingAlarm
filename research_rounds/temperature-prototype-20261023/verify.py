"""Independent contracts, real prefix replay, and counterfactual volume tests."""
from pathlib import Path
import sys,json,hashlib,datetime
import numpy as np
import pandas as pd
from temperature import temperature_frame
HERE=Path(__file__).resolve().parent
OUT=HERE/'results/v0'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replay(d,volume=True):
    return pd.concat([temperature_frame(z,use_volume=volume)[0] for _,z in d.groupby('segment_id',sort=False)]).reindex(d.index)
def synthetic():
    c=100+.2*np.sin(np.arange(90));c=np.r_[c,110.]
    def bars(close,vol):
        prior=np.r_[close[0],close[:-1]]
        return pd.DataFrame({'open':prior,'high':np.maximum(prior,close)+.1,'low':np.minimum(prior,close)-.1,'close':close,'volume':vol},index=pd.bdate_range('2020-01-01',periods=len(close)))
    v=np.ones(len(c))*100;high=v.copy();high[-1]=300
    a,_=temperature_frame(bars(c,high));b,_=temperature_frame(bars(c,v));p,_=temperature_frame(bars(c,v),use_volume=False)
    assert a.level.iloc[-1]>=4 and a.entered.iloc[-1]==1 and b.level.iloc[-1]==2
    assert p.level.iloc[-1]>=4
    # A slow follow-through needs no fresh volume spike on its confirmation day.
    cc=np.r_[c,110.1,110.2];q,_=temperature_frame(bars(cc,np.ones(len(cc))*100))
    assert q.accepted.iloc[-1] and q.level.iloc[-1]>=4 and q.q.iloc[-1]==1
    # A high-participation adverse response changes the judgment, not the price floor.
    cc=np.r_[c,100.5,110.5];vv=np.r_[high,300.,100.]
    g,_=temperature_frame(bars(cc,vv))
    assert g.guard.iloc[-2]==1 and g.level.iloc[-2]<=3 and g.target.iloc[-2]==1
    assert g.guard_recovered.iloc[-1] and not g.guard.iloc[-1] and g.q.iloc[-1]==1
    # A new price breakdown must win over stored evidence and cannot reenter that day.
    cc=np.r_[c,99.];vv=np.r_[high,100.]
    d,_=temperature_frame(bars(cc,vv))
    assert d.structural_invalidated.iloc[-1] and d.target.iloc[-1]==0 and d.entered.iloc[-1]==0
    flat=bars(np.full(100,100.),np.full(100,100.));ff,_=temperature_frame(flat)
    assert ff.level.iloc[-1]==0 and ff.er20.iloc[-1]==0
    return {'same_price_different_volume':'高量突破可立态，普通量突破先待验','quiet_followthrough':'普通量守位可接受','adverse_memory':'量价冲突降温，普通量收复可解除，原参与不被降温清零','breakdown':'结构破坏撤销','flat':'横盘不伪造高效率','rapid':'无需回抽即可从冷跳至有效推进以上'}

def main():
    fr=json.loads((HERE/'input-freeze.json').read_text());prot=json.loads((HERE/'protocol.json').read_text())
    assert sha(HERE/'temperature.py')==prot['code_sha256']
    checks=[];invariants={};units=[]
    for rec in fr['series']:
        sid=rec['symbol'];d=pd.read_parquet(HERE/'inputs'/(sid+'.parquet'));t=pd.read_parquet(OUT/'daily'/(sid+'.parquet'))
        assert t.index.equals(d.index)
        assert t.level.between(-1,6).all()
        assert (t.loc[t.target.eq(1),'structure']==1).all()
        assert t.loc[t.structure.eq(1),'close'].gt(t.loc[t.structure.eq(1),'floor']).all()
        assert t.loc[t.level.ge(4),'guard'].eq(0).all()
        assert t.loc[t.level.ge(5),'long'].eq(1).all()
        assert t.loc[t.level.eq(6),'expansion'].eq(1).all()
        assert t.loc[t.entered.eq(1),'level'].ge(4).all()
        assert not (t.entered.eq(1)&t.structural_invalidated.eq(1)).any()
        assert t.loc[~t.ready,'level'].eq(-1).all()
        # No repeated participation within a source segment and structural episode.
        n=t.loc[t.structure.eq(1)].groupby(['segment_id','structure_id']).entered.sum()
        assert n.le(1).all()
        for _,z in t.loc[t.structure.eq(1)].groupby(['segment_id','structure_id']):assert z.floor.diff().dropna().ge(0).all()
        for cutoff in ['2024-09-20','2024-09-30','2025-12-31','2026-09-30']:
            sub=d.loc[:cutoff]
            if sub.empty:continue
            a=replay(sub)
            pd.testing.assert_frame_equal(a,t.loc[a.index,a.columns],check_exact=True)
            checks.append({'symbol':sid,'cutoff':cutoff,'rows':len(a)})
        # Unit checks are finite numerical diagnostics, not a universal theorem.
        selected=d.loc[:'2024-12-31'].copy()
        base=replay(selected)
        for price_scale,volume_scale in [(100.,1.),(.01,1.),(1.,100.),(1.,.01)]:
            z=selected.copy();z[['open','high','low','close']]*=price_scale;z['volume']*=volume_scale
            a=replay(z);cols=['level','structure','target','entered','exited','guard']
            diffs={k:int(a[k].ne(base[k]).sum()) for k in cols}
            units.append({'symbol':sid,'price_scale':price_scale,'volume_scale':volume_scale,'differences':diffs})
        invariants[sid]={'rows':len(t),'levels':{str(k):int(v) for k,v in t.level.value_counts().sort_index().items()},'entries':int(t.entered.sum())}
    synthetic_checks=synthetic()
    result={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'prefix_replays':checks,
      'invariants':invariants,'unit_diagnostics':units,'unit_state_differences':sum(sum(x['differences'].values()) for x in units),
      'synthetic_checks':synthetic_checks,'old_baseline_exact':json.loads((OUT/'baseline-verification.json').read_text()),
      'temperature_sha256':sha(HERE/'temperature.py'),'protocol_sha256':sha(HERE/'protocol.json'),'account_runs':0}
    with (OUT/'verification.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'prefix_replays':len(checks),'series':len(invariants),'synthetic_groups':len(synthetic_checks),'unit_state_differences':result['unit_state_differences']},ensure_ascii=False))
if __name__=='__main__':main()
