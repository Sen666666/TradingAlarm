"""Formal finite synthetic/causality checks, executed before any real B2 outputs."""
import math
import numpy as np,pandas as pd
from common import ROOT,OLD,read,write,sha,now,identity
from fixtures import fixtures,make
from model import three_axis_frame,Ledger,union_length

def maxdiff(a,b):
    av,bv=a.to_numpy(float),b.to_numpy(float)
    assert np.array_equal(np.isnan(av),np.isnan(bv))
    return float(np.max(np.abs(av[np.isfinite(av)]-bv[np.isfinite(bv)]),initial=0))

def main():
    identity();out=ROOT/'validation-v1';out.mkdir(exist_ok=False);checks=[];description=[];fs=fixtures();outputs={}
    def ok(name,condition,detail=None):
        assert condition,name
        checks.append(dict(name=name,passed=True,detail=detail))
    for k,f in fs.items():
        z,j=three_axis_frame(f);ab,_=three_axis_frame(f,joint=False);outputs[k]=z
        g=f.join(z);g['all_price_down_zone_log_pct']=ab.down_zone_log_pct;g['all_price_up_zone_log_pct']=ab.up_zone_log_pct
        g.to_parquet(out/(k+'.parquet'));write(out/(k+'-events.json'),j)
        ok(k+':warmup',z.iloc[:64].isna().all().all() and np.isfinite(z.pace_21.iloc[64]))
        unaffected=[c for c in z if not any(t in c for t in ['zone','events','union','oldest','impulse'])]
        ok(k+':P_R_identical_without_volume_gate',maxdiff(z[unaffected],ab[unaffected])==0.)
        h=z.dropna(subset=['pace_21']);active=h.direction.ne(0)
        ok(k+':retention_contract',h.loc[active,'retention'].between(0,1,inclusive='right').all())
        description.append(dict(path=k,rows=len(g),pace_5_min=float(h.pace_5.min()),pace_5_max=float(h.pace_5.max()),
            pace_21_min=float(h.pace_21.min()),pace_21_max=float(h.pace_21.max()),
            structure_changes=int(h.structure_broken.sum()),created=int(h.structure_created.sum()),
            down_zone_max=float(h.down_zone_log_pct.max()),up_zone_max=float(h.up_zone_log_pct.max()),
            note='Descriptive only. No true-label accuracy, strategy or threshold tuning.'))
    ok('constant_exact_pace',outputs['constant'].pace_21.dropna().abs().max()==0.)
    ok('constant_structure_unbuilt',outputs['constant'].direction.dropna().eq(0).all())
    f=make(np.full(180,.003));z,_=three_axis_frame(f)
    ok('linear_log_rise_speed',np.max(np.abs(z.speed_21.dropna()-.003))<1e-14)
    ok('linear_log_rise_units',np.max(np.abs(z.amplitude_21.dropna()-6.3))<1e-11)
    ok('linear_log_rise_normalized',np.max(np.abs(z.pace_21.dropna()-math.sqrt(21)))<1e-10)
    # Causal common prefix before later V/failed-bounce divergence.
    a,b=outputs['V_continues'],outputs['rebound_fails'];ok('V_and_failed_bounce_same_prefix',maxdiff(a.iloc[:190],b.iloc[:190])==0.)
    f=fs['bear_rebound'];z,_=three_axis_frame(f)
    scaled=f.copy();scaled['close']*=17;scaled['volume']*=10000;zs,_=three_axis_frame(scaled)
    cols=[c for c in z if not c.endswith('_price')]
    ok('price_and_volume_units',maxdiff(z[cols],zs[cols])<1e-9)
    rng=np.random.default_rng(42);future=f.copy();future.loc[future.index[190]:,'close']*=np.exp(rng.normal(0,.05,len(future)-190))
    zz,_=three_axis_frame(future);ok('mutated_future_same_prefix',maxdiff(z.iloc[:190],zz.iloc[:190])==0.)
    prefix_records=[]
    for key,cut in [('fast_start',124),('true_weakening',190),('bear_rebound',190),('flat_box',210)]:
        p=out/(key+'-physical-prefix.parquet');fs[key].iloc[:cut].to_parquet(p)
        short=pd.read_parquet(p);zs,js=three_axis_frame(short);_,jl=three_axis_frame(fs[key])
        ok(key+':physical_prefix',maxdiff(zs,outputs[key].iloc[:cut])==0.)
        ok(key+':journal_prefix',js==[x for x in jl if x['observation']<cut])
        prefix_records.append(dict(path=key,cut=cut,input_sha256=sha(p)))
    # Mirror test includes independent sign, endpoints, and both inventory directions.
    for key in ['fast_start','lowvol_selloff']:
        a,b=outputs[key],outputs['mirror_'+key]
        ok(key+':mirror_pace',maxdiff(a[['pace_5','pace_21']],-b[['pace_5','pace_21']])<1e-9)
        ok(key+':mirror_structure',maxdiff(a[['direction','signed_retention']],-b[['direction','signed_retention']])<1e-8)
        ok(key+':mirror_debt',maxdiff(a[['down_zone_log_pct','up_zone_log_pct']],b[['up_zone_log_pct','down_zone_log_pct']].set_axis(['down_zone_log_pct','up_zone_log_pct'],axis=1))<1e-10)
    # Exact ledger probes: no close -> clock heal; partial recovery -> revisit does not revive.
    log=[];ledger=Ledger(lambda t,k,f:log.append((t,k,f)))
    def step(p,prev,t,a=1,episode=1):return ledger.update(p,prev,t,.01,a,episode)
    x=step(-.08,0,0,4);ok('ledger_created_by_volume',abs(x['down_zone_log_pct']-8)<1e-12)
    x=step(-.05,-.08,1);ok('ledger_partial_recovery',abs(x['down_zone_log_pct']-5)<1e-12)
    x=step(-.09,-.05,2,episode=2);ok('ledger_no_revival_new_episode',abs(x['down_zone_log_pct']-5)<1e-12)
    x=step(-.09,-.09,500);ok('ledger_no_time_heal',abs(x['down_zone_log_pct']-5)<1e-12)
    x=step(0,-.09,501);ok('ledger_full_recovery',x['down_zone_log_pct']==0.)
    x=step(-.08,0,502);ok('ledger_low_volume_does_not_recreate',x['down_zone_log_pct']==0.)
    x=step(-.10,-.08,503,4);ok('ledger_only_new_region_added',abs(x['down_zone_log_pct']-2)<1e-12)
    neutral=Ledger(lambda *args:None);x=neutral.update(-.08,0,0,.01,1,1)
    ok('ledger_same_price_different_volume',x['down_zone_log_pct']==0.)
    length,n=union_length([(0,2),(1,3),(4,5)]);ok('union_defensive_tool',length==4 and n==2)
    # Unknown invalid rows do not act like zero returns or quiet markets.
    f=fs['fast_start'].drop(columns='b1_strength').copy();f.loc[f.index[[90,91,150]],'valid_strength_observation']=False
    z,j=three_axis_frame(f);short,js=three_axis_frame(f.loc[f.valid_strength_observation])
    ok('invalid_rows_unknown',z.loc[~f.valid_strength_observation].isna().all().all())
    ok('valid_observation_clock',maxdiff(z.loc[f.valid_strength_observation],short)==0.)
    f1=fs['lowvol_selloff'].drop(columns='b1_strength').iloc[:180].copy();f2=f1.copy()
    f2.index=pd.bdate_range(f1.index[-1]+pd.Timedelta(days=1),periods=len(f2));f2['segment_id']=1
    together,j=three_axis_frame(pd.concat([f1,f2]));single,_=three_axis_frame(f2)
    ok('segment_rewarm',maxdiff(together.loc[f2.index],single)==0.)
    archives=[x for x in j if x['kind']=='source_segment_start_unresolved_archive']
    ok('segment_unresolved_archive',len(archives)==1 and archives[0]['date']==str(f2.index[0].date()))
    bad=f1.copy();bad.iloc[90,bad.columns.get_loc('volume')]=0
    try:three_axis_frame(bad);rejected=False
    except ValueError:rejected=True
    ok('zero_volume_not_silently_valid',rejected)
    bad=f1.copy();bad.iloc[60:120,bad.columns.get_loc('segment_id')]=1
    try:three_axis_frame(bad);rejected=False
    except ValueError:rejected=True
    ok('noncontiguous_source_id_rejected',rejected)
    write(out/'synthetic-summary.json',description)
    write(out/'checks.json',dict(recorded_at=now(),technical_passed=True,technical_checks=len(checks),checks=checks,
        synthetic_paths=17,physical_prefixes=prefix_records,accounts=0,
        semantics='Tests validate contracts and describe trajectories, not five-class accuracy or economic advantage.',
        real_B2_outputs_have_not_been_generated=not (ROOT/'results').exists()))
    identity();print({'technical_checks':len(checks),'synthetic_paths':17,'passed':True},flush=True)

if __name__=='__main__':main()
