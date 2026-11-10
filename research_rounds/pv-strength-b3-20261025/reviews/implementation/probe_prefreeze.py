"""Finite artificial implementation probes, separate from formal scenario results."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from reference import reference,evidence,NUMERIC,TABLE

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('b3_candidate',ROOT/'code/model.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
checks=[];facts={}
def record(name,passed,detail=None):
    checks.append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed: raise AssertionError(name)
def frame(returns,volumes=None):
    prices=100*np.exp(np.r_[0.,np.cumsum(returns)])
    return pd.DataFrame({'close':prices,'volume':100. if volumes is None else volumes,
                         'segment_id':'A','valid_strength_observation':True},index=pd.date_range('2000-01-01',periods=len(prices)))
def compare(a,b,name):
    record(name+'_shape',a.index.equals(b.index) and set(a.columns)==set(b.columns))
    record(name+'_phase',a.phase.equals(b.phase))
    record(name+'_unknown',a[NUMERIC].isna().equals(b[NUMERIC].isna()))
    delta=(a[NUMERIC]-b[NUMERIC]).abs().max().max()
    record(name+'_numeric',np.allclose(a[NUMERIC],b[NUMERIC],rtol=1e-11,atol=1e-9,equal_nan=True),float(delta))
def json_equal(a,b):
    if isinstance(a,dict):return a.keys()==b.keys() and all(json_equal(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(json_equal(x,y) for x,y in zip(a,b))
    if isinstance(a,(float,int)) and not isinstance(a,bool):return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-9)
    return a==b

if (HERE/'prefreeze_probe_results.json').exists(): raise SystemExit('Refuse to overwrite existing result')
points=[-2.,-1.-1e-10,-1.,-1.+1e-10,-.5-1e-10,-.5,-.5+1e-10,0.,.5-1e-10,.5,.5+1e-10,1.-1e-10,1.,1.+1e-10,2.]
record('direction_boundary_45',all(core.direction(z,old)==evidence(z,old) for z in points for old in (-1,0,1)))
record('nine_normal_table_cells',all(core.normal_grade(B,L)==TABLE[(B,L)] for B in (-1,0,1) for L in (-1,0,1)))
record('table_monotone',all(TABLE[(B,L)][0]<=TABLE[(B+1,L)][0] for B in (-1,0) for L in (-1,0,1)) and
       all(TABLE[(B,L)][0]<=TABLE[(B,L+1)][0] for B in (-1,0,1) for L in (-1,0)))

# One deterministic mixed path. This is not one of the formal 24 semantic fixtures.
r=np.array([.004*math.sin(i*.71)+.002*math.cos(i*.17)+(.001 if i<190 else -.001) for i in range(380)])
r[[140,143,221,300]]=[-.035,-.015,-.04,-.025];r[[147,235,302]]=[.035,.04,.026]
v=np.array([100*(1+(i%7)/10) for i in range(381)]);v[[144,222,301]]=400
f=frame(r,v)
for joint in (True,False):
    a,j=core.strength_frame(f,joint);b,k=reference(f,joint);compare(a,b,f'independent_joint_{joint}')
    record(f'journal_joint_{joint}',json_equal(j,k),len(j))
a,j=core.strength_frame(f)
record('first_output_t64',a.grade.iloc[:64].isna().all() and math.isfinite(a.grade.iloc[64]))
changed=f.copy();changed.iloc[64,changed.columns.get_loc('close')]*=1.04
c,_=core.strength_frame(changed)
record('current_close_excluded_from_sigma',a.sigma.iloc[64]==c.sigma.iloc[64])
changed=f.copy();changed.iloc[64,changed.columns.get_loc('volume')]*=3
c,_=core.strength_frame(changed)
record('current_volume_excluded_from_median',math.isclose(c.activity.iloc[64],3*a.activity.iloc[64],rel_tol=1e-13))
scaled=f.copy();scaled['close']*=17;scaled['volume']*=10000
c,k=core.strength_frame(scaled);adjusted=c.copy();adjusted[['freeze_anchor_price','freeze_low_price']]/=17
compare(a,adjusted,'unit_equivalence');record('unit_journal',json_equal(j,k))
prefix=HERE/'artificial-physical-prefix.parquet';f.iloc[:247].to_parquet(prefix)
c,k=core.strength_frame(pd.read_parquet(prefix))
record('physical_prefix_exact',a.loc[c.index].equals(c) and k==[e for e in j if e['date']<=str(c.index[-1].date())])

# Insert invalid observations while retaining exactly the same valid observations.
expanded=pd.concat([f,pd.DataFrame({'close':[np.nan],'volume':[np.nan],'segment_id':['A'],
                                  'valid_strength_observation':[False]},index=[f.index[177]+pd.Timedelta(hours=12)])]).sort_index()
c,k=core.strength_frame(expanded)
record('invalid_row_no_clock',c.loc[f.index].equals(a) and k==j and c.loc[expanded.index.difference(f.index),NUMERIC].isna().all().all())

# Fixed event lifecycle path: 4x volume lets modest price shocks remain below directional entry.
w=[.01,-.01]*60
path=frame(w+[-.012,0.,0.,-.012,.012]+[0.]*30)
path.loc[path.index[[121,124]],'volume']=400.
c,k=core.strength_frame(path);d,l=reference(path);compare(c,d,'multiple_events_reference')
record('multiple_events_journal',json_equal(k,l))
record('second_event_does_not_replace_first',c.freeze_count.iloc[124]==2 and c.freeze_anchor.iloc[124]>np.log(path.close.iloc[123]/path.close.iloc[0]))
record('partial_anchor_recovery',any(e['event']==2 and e['kind']=='price_recovered' and e['observation']==125 for e in k) and c.freeze_count.iloc[125]==1)
facts['multiple_events']=k
expiry=frame(w+[-.012]+[0.]*25);expiry.loc[expiry.index[121],'volume']=400.
c,k=core.strength_frame(expiry)
record('age_21_expiry',c.freeze_active.iloc[141]==1 and c.freeze_active.iloc[142]==0 and any(e['kind']=='outside_current_scale' and e['age']==21 for e in k))
facts['expiry_events']=k

# Isolate simultaneous predicates by stubbing only the directional reader; these are
# lifecycle branch tests, explicitly not full-model or semantic scenario outputs.
original_direction=core.direction
def controlled_directions(f,overrides):
    counter={'n':0}
    def stub(z,prior):
        t=64+counter['n']//2;axis='B' if counter['n']%2==0 else 'L';counter['n']+=1
        return overrides.get((t,axis),0)
    core.direction=stub
    try:return core.strength_frame(f)
    finally:core.direction=original_direction
recovered=expiry.copy();recovered.loc[recovered.index[142],'close']=recovered.close.iloc[120]
c,k=controlled_directions(recovered,{(142,'L'):-1})
record('recovery_beats_takeover_and_expiry',any(e['observation']==142 and e['kind']=='price_recovered' for e in k))
c,k=controlled_directions(expiry,{(142,'L'):-1})
record('takeover_beats_expiry',any(e['observation']==142 and e['kind']=='downtrend_takeover' for e in k))
c,k=controlled_directions(path,{(124,'L'):-1})
at=[e for e in k if e['observation']==124]
record('new_shock_dominates_today',len(at)==2 and at[0]['kind']=='downtrend_takeover' and at[1]['kind']=='freeze_created' and c.grade.iloc[124]==-2)

# New source segment restarts warmup and archives live damage on source break.
seg=expiry.iloc[:130].copy();other=f.iloc[:80].copy();other.index=pd.date_range(seg.index[-1]+pd.Timedelta(days=1),periods=len(other));other['segment_id']='B'
joined=pd.concat([seg,other]);c,k=core.strength_frame(joined);d,l=reference(joined);compare(c,d,'segments_reference')
record('segments_journal',json_equal(k,l));record('segments_new_warmup',c.loc[other.index[:64],'grade'].isna().all())
record('segment_archive',sum(e['kind']=='source_discontinuity' for e in k)==1)

bad=[]
z=f.copy();z.index=list(f.index[:-1])+[f.index[-2]];bad.append(('duplicate_date',z))
bad.append(('reverse_date',f.iloc[::-1]))
z=f.copy();z.index=f.index.astype(str);bad.append(('string_index',z))
z=f.copy();z.index=f.index.tz_localize('UTC');bad.append(('tz_index',z))
z=f.copy();z.index=pd.DatetimeIndex([pd.NaT]+list(f.index[1:]));bad.append(('nat_index',z))
z=f.copy();z.loc[z.index[4],'segment_id']=None;bad.append(('missing_segment',z))
z=f.copy();z.loc[z.index[4],'segment_id']='B';bad.append(('segment_reappearance',z))
z=f.copy();z['valid_strength_observation']=z.valid_strength_observation.astype(int);bad.append(('int_validity',z))
z=f.copy();z['valid_strength_observation']=pd.array(z.valid_strength_observation,dtype='boolean');z.loc[z.index[4],'valid_strength_observation']=pd.NA;bad.append(('null_validity',z))
for field in ('close','volume'):
    for value in (0.,-1.,math.nan,math.inf):
        z=f.copy();z.loc[z.index[4],field]=value;bad.append((f'{field}_{value}',z))
for name,z in bad:
    try:core.strength_frame(z)
    except ValueError:record('reject_'+name,True)
    else:record('reject_'+name,False)
empty=f.iloc[:0];c,k=core.strength_frame(empty);record('empty_input',c.empty and not k)
z=f.copy();z['valid_strength_observation']=False;c,k=core.strength_frame(z);record('all_invalid',c[NUMERIC].isna().all().all() and not k)

receipt={'scope':'prefreeze artificial technical probes only; no real input or formal fixture outputs',
         'candidate_sha256':hashlib.sha256((ROOT/'code/model.py').read_bytes()).hexdigest(),
         'protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest(),
         'reference_sha256':hashlib.sha256((HERE/'reference.py').read_bytes()).hexdigest(),
         'checks':checks,'facts':facts,'all_passed':all(x['passed'] for x in checks)}
(HERE/'prefreeze_probe_results.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
print(json.dumps({'checks':len(checks),'all_passed':receipt['all_passed'],'candidate_sha256':receipt['candidate_sha256']}))
