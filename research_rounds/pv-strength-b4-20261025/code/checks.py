"""Finite synthetic diagnostics; technical correctness is not model usefulness."""
import numpy as np
import pandas as pd
from common import ROOT,B3,write,now,identity,sha
from model import strength_frame,FIELDS

INPUT=['close','volume','segment_id','valid_strength_observation']

def equal(a,b,atol=1e-8):
    try:
        pd.testing.assert_frame_equal(a,b,check_exact=False,atol=atol,rtol=1e-10,check_dtype=False,check_names=False)
        return True
    except AssertionError:return False

def invariants(z,j):
    receipts=[e for e in j if e['kind']=='structure_confirmed']
    ok=True
    for e in receipts:
        c=e['receipt'];d=e['direction'];eps=1e-11
        ok &= d*e['r']>0 and c['new_frontier']==1 and c['frontier_increment']>0
        ok &= c['x']>=c['threshold']-eps and c['credit']>=c['threshold']-eps
        ok &= .5*c['frontier']-eps<=c['credit']<=2*c['frontier']+eps
    for h in [21,63]:
        for side in ['up','down']:
            f=z[f'{side}_frontier_{h}'].dropna();q=z.loc[f.index,f'{side}_credit_{h}']
            ok &= bool((q>=.5*f-1e-11).all() and (q<=2*f+1e-11).all())
        s=z[f'S{h}'].dropna();changes=s.ne(s.shift()).copy()
        if len(s):
            changes.iloc[0]=False
            ok &= bool(z.loc[s.index[changes],f'confirmed_{h}'].eq(1).all())
    return bool(ok),dict(confirmations=len(receipts),up=sum(e['direction']==1 for e in receipts))

def main():
    identity();out=ROOT/'validation';out.mkdir(exist_ok=False)
    for d in ['inputs','transforms','prefixes','probes']:(out/d).mkdir()
    checks=[];descriptions=[];fs={};zs={};js={}
    def record(name,passed,detail=None):checks.append(dict(name=name,passed=bool(passed),detail=detail))
    def save(folder,name,f,z,j):
        f.join(z).to_parquet(folder/(name+'.parquet'));write(folder/(name+'-events.json'),j)
    for p in sorted((B3/'validation/inputs').glob('*.parquet')):
        name=p.stem;f=pd.read_parquet(p)[INPUT];fs[name]=f
        f.to_parquet(out/'inputs'/p.name)
        z,j=strength_frame(f);ab,_=strength_frame(f,False);zs[name]=z;js[name]=j
        g=z.copy();g['price_S21']=ab.S21;g['price_S63']=ab.S63;g['price_acute_down']=ab.acute_down
        save(out,name,f,g,j)
        record(name+':warmup',z.iloc[:64][FIELDS].isna().all().all() and z.S21.iloc[64]==z.S21.iloc[64])
        passed,detail=invariants(z,j);record(name+':new_evidence_invariants',passed,detail)
        record(name+':volume_preserves_physical_pace',equal(z[['mu5','mu21','r','s']],ab[['mu5','mu21','r','s']],0))
        descriptions.append(dict(path=name,rows=len(f),confirmations=detail['confirmations'],
            up_confirmations=detail['up'],phases=z.phase.value_counts().to_dict(),
            volume_structure_difference=int(((z.S21.ne(ab.S21)|z.S63.ne(ab.S63))&z.S21.notna()).sum()),
            joint_aligned_up_negative_mu21=int((z.S21.eq(1)&z.S63.eq(1)&z.mu21.lt(0)).sum()),
            input_sha256=sha(out/'inputs'/p.name)))
    assert len(fs)==24
    # One predeclared derivative: old crash is allowed to leave every old window,
    # but all subsequent returns are strictly negative.
    f=fs['shock_then_static'].copy();f.loc[f.index[191]:,'close']=f.close.iloc[190]*np.exp(-.001*np.arange(1,len(f)-190))
    f.loc[f.index[191]:,'volume']=100.
    f.to_parquet(out/'inputs/shock_then_slow_decline.parquet');z,j=strength_frame(f)
    zs['shock_then_slow_decline']=z;js['shock_then_slow_decline']=j;fs['shock_then_slow_decline']=f
    save(out,'shock_then_slow_decline',f,z,j)
    record('derived:no_positive_confirmation_after_crash',not any(e['kind']=='structure_confirmed' and e['direction']==1 and e['observation']>=190 for e in j))
    for name in ['rise_then_static','shock_then_static','slow_decline']:
        record(name+':no_false_up_after_190',not any(e['kind']=='structure_confirmed' and e['direction']==1 and e['observation']>=190 for e in js[name]))
    transforms=[]
    for name in sorted(k for k in fs if k!='shock_then_slow_decline'):
        f=fs[name].copy();f.close*=17.;f.volume*=10000.;z,j=strength_frame(f)
        save(out/'transforms',name+'__units',f,z,j);a=z.copy()
        for c in a:
            if c.endswith('_price') or '_price_' in c:a[c]/=17.
            if 'volume_reference' in c:a[c]/=10000.
        record(name+':units',equal(zs[name],a));transforms.append(name+'__units')
    for name in ['micro_box','ordinary_rise','slow_decline','shock_then_static']:
        f=fs[name].copy();f.close=float(f.close.iloc[0])**2/f.close;z,j=strength_frame(f)
        save(out/'transforms',name+'__reflection',f,z,j)
        cols=['r','mu5','mu21','q','qeff','S21','S63']
        record(name+':reflection',equal(z[cols],-zs[name][cols]));transforms.append(name+'__reflection')
    for sign,label in [(1,'plus'),(-1,'minus')]:
        f=fs['micro_box'].copy();f.loc[f.index[120]:,'close']*=np.exp(sign*1e-7*(-1.)**np.arange(len(f)-120))
        z,j=strength_frame(f);key='micro_box__perturb_'+label;save(out/'transforms',key,f,z,j)
        descriptions.append(dict(path=key,structure_changes=int(((z.S21.ne(zs['micro_box'].S21)|z.S63.ne(zs['micro_box'].S63))&z.S21.notna()).sum())))
        transforms.append(key)
    for name in ['shock_then_static','shock_then_recovery']:
        f=fs[name].copy();f.iloc[190,f.columns.get_loc('volume')]=400.;z,j=strength_frame(f)
        save(out/'transforms',name+'__high_volume',f,z,j)
        record(name+':severe_shock_low_and_high_volume',z.acute_down.iloc[190]==1 and zs[name].acute_down.iloc[190]==1)
        transforms.append(name+'__high_volume')
    record('finite_32_transforms',len(transforms)==32)
    for name,n in [('V_continues',190),('shock_then_static',191),('fast_start',160),('slow_decline',211)]:
        f=fs[name].iloc[:n];p=out/'prefixes'/(name+'.parquet');f.to_parquet(p)
        z,j=strength_frame(pd.read_parquet(p));record(name+':physical_prefix',equal(z,zs[name].iloc[:n],0))
        write(out/'prefixes'/(name+'-events.json'),j)
    record('V_shared_prefix',equal(zs['V_continues'].iloc[:190],zs['rebound_fails'].iloc[:190],0))
    record('shock_shared_prefix',equal(zs['shock_then_static'].iloc[:191],zs['shock_then_recovery'].iloc[:191],0))
    # Input handling is tested without changing algorithms or market outcomes.
    f=fs['slow_decline'].copy();f.iloc[80,f.columns.get_loc('valid_strength_observation')]=False
    f.iloc[80,f.columns.get_loc('close')]=np.nan;z,j=strength_frame(f);d,_=strength_frame(f.loc[f.valid_strength_observation])
    record('unknown_skip_and_bridge',z.iloc[80][FIELDS].isna().all() and equal(z.loc[f.valid_strength_observation],d,0))
    f=fs['slow_decline'].copy();f.loc[f.index[150]:,'segment_id']=1;z,j=strength_frame(f);d,_=strength_frame(f.iloc[150:])
    record('segment_restarts',equal(z.iloc[150:],d,0))
    for case in ['negative_price','zero_volume','bad_index','empty_segment','reused_segment','nonbool_valid']:
        f=fs['slow_decline'].copy()
        if case=='negative_price':f.iloc[90,f.columns.get_loc('close')]=-1
        elif case=='zero_volume':f.iloc[90,f.columns.get_loc('volume')]=0
        elif case=='bad_index':f=f.iloc[::-1]
        elif case=='empty_segment':f['segment_id']=' '
        elif case=='reused_segment':f.loc[f.index[50]:f.index[100],'segment_id']=1
        else:f['valid_strength_observation']=1
        try:strength_frame(f);good=False
        except ValueError:good=True
        record('reject_'+case,good)
    # A priori fixed volume probe. Same prices, only the new rising frontier's
    # participation changes; it is not an additional searched market path.
    base=fs['ordinary_rise'].iloc[:150].copy();variants={}
    for label,vol in [('low',25.),('normal',100.),('high',400.)]:
        f=base.copy();f.loc[f.index[120]:,'volume']=vol;z,j=strength_frame(f);variants[label]=z
        save(out/'probes','frontier_'+label,f,z,j)
    record('volume_changes_creation',any(variants['low'].S21.ne(variants['normal'].S21)&variants['low'].S21.notna()))
    # Bounds/eligibility are audited on every derivative as well.
    passed,detail=invariants(zs['shock_then_slow_decline'],js['shock_then_slow_decline']);record('derived:invariants',passed,detail)
    identity();write(out/'descriptions.json',dict(recorded_at=now(),paths=descriptions,transforms=transforms))
    result=dict(recorded_at=now(),technical_passed=all(c['passed'] for c in checks),checks=checks,
        base_paths=24,derived_paths=1,transforms=32,accounts=0)
    write(out/'checks.json',result);print({'passed':result['technical_passed'],'checks':len(checks),'failed':[c for c in checks if not c['passed']]},flush=True)
    if not result['technical_passed']:raise SystemExit(1)

if __name__=='__main__':main()
