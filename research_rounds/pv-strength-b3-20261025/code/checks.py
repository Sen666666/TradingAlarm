"""Frozen finite synthetic checks. Behavior failures are saved, never asserted away."""
import json
import math
import traceback
import numpy as np
import pandas as pd
from common import ROOT, B2, write, sha, now, identity
from fixtures import fixtures, fixture_manifest, transforms, moderate_volume_inputs, INPUT_COLUMNS
from model import strength_frame, direction, normal_grade, FIELDS

ATOL=1e-9
PRICE_COLUMNS=['freeze_anchor_price','freeze_low_price']
DISCRETE=['local','background','normal_grade','grade','freeze_active','freeze_created',
          'freeze_released','freeze_count','freeze_id','freeze_age','rapid_up']
MARKET=['sigma','activity','shock','speed_21','speed_63','z_21','z_63',
        'amplitude_21','amplitude_63','return_21','return_63','local','background','normal_grade']
SIGNED=['shock','effective_shock','speed_21','speed_63','z_21','z_63','amplitude_21',
        'amplitude_63','local','background']

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(np.bool_,bool)):return bool(x)
    if isinstance(x,(np.integer,int)):return int(x)
    if isinstance(x,(np.floating,float)):return float(x) if math.isfinite(float(x)) else None
    if isinstance(x,pd.Timestamp):return x.isoformat()
    return x

def frame_comparison(a,b,atol=ATOL):
    if list(a.columns)!=list(b.columns) or not a.index.equals(b.index):
        return False,dict(reason='index_or_columns_differ')
    differences={};max_error=0.
    for col in a:
        av,bv=a[col],b[col]
        if not av.isna().equals(bv.isna()):differences[col]='unknown_mask';continue
        if pd.api.types.is_numeric_dtype(av) and pd.api.types.is_numeric_dtype(bv):
            aa,bb=av.to_numpy(float),bv.to_numpy(float);good=np.isfinite(aa)&np.isfinite(bb)
            if not np.array_equal(np.isfinite(aa),np.isfinite(bb)):
                differences[col]='finite_mask';continue
            d=float(np.max(np.abs(aa[good]-bb[good]),initial=0.));max_error=max(max_error,d)
            if d>atol:differences[col]=d
        elif not av.fillna('__NA__').equals(bv.fillna('__NA__')):differences[col]='value'
    return not differences,dict(max_abs_difference=max_error,differing_columns=differences,tolerance=atol)

def object_comparison(a,b,atol=ATOL):
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(object_comparison(a[k],b[k],atol) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(object_comparison(x,y,atol) for x,y in zip(a,b))
    if isinstance(a,(float,np.floating)) or isinstance(b,(float,np.floating)):
        return isinstance(a,(float,int,np.number)) and isinstance(b,(float,int,np.number)) and abs(float(a)-float(b))<=atol
    return a==b

def first_occurrence(series,value,start=0):
    part=series.iloc[start:];where=np.flatnonzero(part.to_numpy()==value)
    return None if not len(where) else dict(observation=start+int(where[0]),
        offset=int(where[0])+1,date=str(part.index[where[0]].date()))

def grade_counts(z):
    return {str(int(k)):int(v) for k,v in z.grade.value_counts(dropna=True).sort_index().items()}

def main():
    out=ROOT/'validation';out.mkdir(exist_ok=False)
    for name in ['inputs','transforms','prefixes']:(out/name).mkdir()
    technical=[];behavior=[];descriptions=[];prefixes=[];transformed=[];outputs={};journals={};fs={}
    def record(name,passed,detail=None):
        technical.append(dict(name=name,passed=bool(passed),detail=clean(detail)))
    def checked(name,fn):
        try:
            value=fn()
            if isinstance(value,tuple):record(name,value[0],value[1])
            else:record(name,value)
        except Exception as exc:record(name,False,dict(error=repr(exc),traceback=traceback.format_exc()))
    def observed(name,passed,detail=None,expectation='frozen_behavior_contract'):
        behavior.append(dict(name=name,assessment='supported' if passed is True else 'violated' if passed is False else 'descriptive',
            passed=passed,expectation=expectation,detail=clean(detail)))
    def save_frame(path,frame):
        if path.exists():raise FileExistsError(str(path))
        frame.to_parquet(path)
    def save_run(folder,key,f,z,j):
        save_frame(folder/(key+'.parquet'),f.join(z))
        write(folder/(key+'-events.json'),clean(j))
    try:
        checked('frozen_and_old_identities_before',identity)
        if not technical[-1]['passed']:raise RuntimeError('Identity preflight failed; no candidate execution allowed')
        fs=fixtures();write(out/'fixture-manifest.json',fixture_manifest())
        record('fixed_fixture_count',len(fs)==24,dict(names=list(fs)))
        for key,f in fs.items():
            save_frame(out/'inputs'/(key+'.parquet'),f)
            try:
                z,j=strength_frame(f);ab,aj=strength_frame(f,joint=False)
                outputs[key]=z;journals[key]=j
                g=f.join(z);g['price_grade']=ab.grade;g['price_freeze_created']=ab.freeze_created
                save_frame(out/(key+'.parquet'),g);write(out/(key+'-events.json'),clean(j))
                write(out/(key+'-price-events.json'),clean(aj))
                record(key+':warmup_unknown',z.iloc[:64][FIELDS].isna().all().all() and
                    z.phase.iloc[:64].eq('unknown').all() and pd.notna(z.grade.iloc[64]))
                record(key+':grade_domain',z.grade.dropna().isin([-2,-1,0,1,2]).all())
                checked(key+':volume_ablation_preserves_price_evidence',lambda z=z,ab=ab:frame_comparison(z[MARKET],ab[MARKET],0.))
                valid=z.grade.notna();active=z.freeze_count.gt(0)&valid
                record(key+':freeze_and_normal_readout_consistent',
                    z.loc[active,'grade'].eq(-2).all() and z.loc[valid&~active,'grade'].equals(z.loc[valid&~active,'normal_grade']) and
                    z.loc[valid,'freeze_active'].eq(active.loc[valid].astype(float)).all())
                descriptions.append(dict(path=key,rows=len(f),grade_counts=grade_counts(z),
                    first_hot=first_occurrence(z.grade,2),first_cold=first_occurrence(z.grade,-1),
                    first_freeze=first_occurrence(z.grade,-2),freeze_created=int(z.freeze_created.sum()),
                    volume_changed_grade_days=int((z.grade.ne(ab.grade)&valid).sum()),
                    max_abs_amplitude_21=float(z.amplitude_21.abs().max()),
                    max_abs_amplitude_63=float(z.amplitude_63.abs().max()),
                    input_sha256=sha(out/'inputs'/(key+'.parquet')),output_sha256=sha(out/(key+'.parquet'))))
            except Exception as exc:
                record(key+':execution',False,dict(error=repr(exc),traceback=traceback.format_exc()))
        record('all_24_outputs_preserved',len(outputs)==24,dict(completed=list(outputs)))

        for name,key,kind,f,meta in transforms(fs):
            try:
                z,j=strength_frame(f);save_run(out/'transforms',name,f,z,j)
                base=outputs[key];bj=journals[key]
                transformed.append(dict(name=name,base=key,kind=kind,metadata=meta,
                    output_sha256=sha(out/'transforms'/(name+'.parquet'))))
                if kind=='units':
                    cols=[c for c in base if c not in PRICE_COLUMNS]
                    checked(name+':continuous_and_labels',lambda base=base,z=z,cols=cols:frame_comparison(base[cols],z[cols]))
                    checked(name+':discrete_exact',lambda base=base,z=z:frame_comparison(base[DISCRETE+['phase']],z[DISCRETE+['phase']],0.))
                    checked(name+':price_coordinates',lambda base=base,z=z:frame_comparison(base[PRICE_COLUMNS],z[PRICE_COLUMNS]/17.))
                    record(name+':event_identity',object_comparison(bj,j))
                elif kind=='reflection':
                    checked(name+':signed_direction',lambda base=base,z=z:frame_comparison(base[SIGNED],-z[SIGNED]))
                    checked(name+':scale_and_activity',lambda base=base,z=z:frame_comparison(base[['sigma','activity']],z[['sigma','activity']]))
                    # Simple endpoint percent returns are not odd under log reflection.
                    reciprocal=(1.+base[['return_21','return_63']]/100.)*(1.+z[['return_21','return_63']]/100.)
                    record(name+':simple_return_reciprocal',np.max(np.abs(reciprocal.dropna().to_numpy()-1.),initial=0.)<ATOL)
                    observed(name+':long_only_temperature',None,dict(base_grade_counts=grade_counts(base),
                        reflected_grade_counts=grade_counts(z)),expectation='Temperature is intentionally not sign-symmetric; raw direction is.')
                elif kind=='perturbation':
                    delta=np.log(f.close/fs[key].close)
                    record(name+':fixed_input_perturbation',np.max(np.abs(delta.iloc[:120].to_numpy()),initial=0.)<1e-12 and
                        np.max(np.abs(np.abs(delta.iloc[120:].to_numpy())-1e-7),initial=0.)<1e-12)
                    changed=base.grade.ne(z.grade)&base.grade.notna()&z.grade.notna()
                    details=[]
                    for date in base.index[changed]:
                        details.append(dict(date=str(date.date()),before=float(base.at[date,'grade']),after=float(z.at[date,'grade']),
                            z21_before=float(base.at[date,'z_21']),z21_after=float(z.at[date,'z_21']),
                            z63_before=float(base.at[date,'z_63']),z63_after=float(z.at[date,'z_63'])))
                    observed(name+':state_sensitivity',len(details)==0,dict(changes=details),
                        expectation='Diagnostic: distinguish evidence-boundary crossings from unrelated noise; no automatic rejection or retuning.')
                elif kind=='high_volume':
                    unaffected=[c for c in MARKET if c!='activity']
                    checked(name+':same_price_evidence',lambda base=base,z=z,unaffected=unaffected:frame_comparison(base[unaffected],z[unaffected],0.))
                    record(name+':severe_shock_not_exempted',base.grade.iloc[190]==-2 and z.grade.iloc[190]==-2)
                    observed(name+':volume_counterfactual',None,dict(base_shock=float(base.shock.iloc[190]),
                        high_shock=float(z.shock.iloc[190]),base_effective=float(base.effective_shock.iloc[190]),
                        high_effective=float(z.effective_shock.iloc[190]),
                        grade_changed_days=int((base.grade.ne(z.grade)&base.grade.notna()).sum())),
                        expectation='Both severe shocks must remain visible; a state difference is not required for every volume change.')
            except Exception as exc:record(name+':execution',False,dict(error=repr(exc),traceback=traceback.format_exc()))
        record('exact_32_finite_transforms',len(transformed)==32,dict(count=len(transformed)))
        write(out/'transform-manifest.json',clean(transformed))

        # Four physically written/reloaded prefix inputs, including the ambiguous V,
        # troublesome box, severe low-volume crash, and 21st slow-decline observation.
        for key,cut in [('V_continues',190),('flat_box',230),('shock_then_static',191),('slow_decline',211)]:
            try:
                path=out/'prefixes'/(key+'-input.parquet');save_frame(path,fs[key].iloc[:cut])
                short=pd.read_parquet(path);zs,js=strength_frame(short)
                save_run(out/'prefixes',key+'-output',short,zs,js)
                checked(key+':physical_prefix',lambda zs=zs,key=key,cut=cut:frame_comparison(zs,outputs[key].iloc[:cut],0.))
                expect=[e for e in journals[key] if e['observation'] is None or e['observation']<cut]
                record(key+':physical_journal_prefix',js==expect)
                prefixes.append(dict(path=key,cut=cut,input_sha256=sha(path)))
            except Exception as exc:record(key+':prefix_execution',False,dict(error=repr(exc),traceback=traceback.format_exc()))
        for a,b,cut in [('V_continues','rebound_fails',190),('shock_then_static','shock_then_recovery',191)]:
            checked(a+':common_input_prefix',lambda a=a,b=b,cut=cut:frame_comparison(fs[a].iloc[:cut],fs[b].iloc[:cut],0.))
            checked(a+':common_output_prefix',lambda a=a,b=b,cut=cut:frame_comparison(outputs[a].iloc[:cut],outputs[b].iloc[:cut],0.))
            checked(a+':common_event_prefix',lambda a=a,b=b,cut=cut:
                [e for e in journals[a] if e['observation']<cut]==[e for e in journals[b] if e['observation']<cut])

        def future_probe():
            f=fs['V_continues'].copy();cut=190
            f.loc[f.index[cut]:,'close']*=np.exp(np.linspace(.01,.35,len(f)-cut));f.loc[f.index[cut]:,'volume']*=3.
            z,j=strength_frame(f);save_run(out/'prefixes','mutated_future',f,z,j)
            passed,detail=frame_comparison(outputs['V_continues'].iloc[:cut],z.iloc[:cut],0.)
            detail['event_prefix_equal']=[e for e in j if e['observation']<cut]==[e for e in journals['V_continues'] if e['observation']<cut]
            return passed and detail['event_prefix_equal'],detail
        checked('mutated_future_does_not_rewrite_prefix',future_probe)

        def invalid_probe():
            f=fs['fast_start'].copy();bad=f.index[[90,91,150]]
            f.loc[bad,'valid_strength_observation']=False;f.loc[bad,'close']=np.nan;f.loc[bad,'volume']=0.
            z,j=strength_frame(f);compressed,jc=strength_frame(f.loc[f.valid_strength_observation])
            save_run(out/'prefixes','invalid_rows',f,z,j)
            passed,detail=frame_comparison(z.loc[f.valid_strength_observation],compressed,0.)
            detail['unknown_rows']=bool(z.loc[bad,FIELDS+PRICE_COLUMNS].isna().all().all() and z.loc[bad,'phase'].eq('unknown').all())
            detail['journal_same_as_valid_clock']=j==jc
            return passed and detail['unknown_rows'] and detail['journal_same_as_valid_clock'],detail
        checked('invalid_rows_unknown_and_valid_clock',invalid_probe)

        def segment_probe():
            first=fs['shock_then_static'].iloc[:191].copy();second=first.copy()
            second.index=pd.bdate_range(first.index[-1]+pd.Timedelta(days=1),periods=len(second),name='date');second['segment_id']=1
            together=pd.concat([first,second]);z,j=strength_frame(together);separate,_=strength_frame(second)
            save_run(out/'prefixes','two_source_segments',together,z,j)
            passed,detail=frame_comparison(z.loc[second.index],separate,0.)
            archives=[e for e in j if e['kind']=='source_discontinuity']
            detail['unresolved_archive']=len(archives)==1 and bool(archives[0].get('unresolved'))
            detail['archive_does_not_claim_price_recovery']=all('price_recovered' not in e for e in archives)
            return passed and detail['unresolved_archive'] and detail['archive_does_not_claim_price_recovery'],detail
        checked('source_segment_rewarm_and_unresolved_archive',segment_probe)

        def reject_probe(kind):
            f=fs['fast_start'].copy()
            if kind=='zero_valid_volume':f.iloc[90,f.columns.get_loc('volume')]=0.
            elif kind=='noncontiguous_segment':f.iloc[60:120,f.columns.get_loc('segment_id')]=1
            elif kind=='non_boolean_validity':f['valid_strength_observation']=1
            elif kind=='duplicate_index':f.index=pd.DatetimeIndex([f.index[0]]+list(f.index[:-1]),name='date')
            else:raise ValueError(kind)
            try:strength_frame(f)
            except ValueError:return True
            return False
        for kind in ['zero_valid_volume','noncontiguous_segment','non_boolean_validity','duplicate_index']:
            checked('input_rejects_'+kind,lambda kind=kind:reject_probe(kind))

        # Direct readout probes are part of the contract, not additional paths.
        cases=[(1.,0,1),(-1.,0,-1),(.5,1,0),(-.5,-1,0),(.6,1,1),(-.6,-1,-1),
               (.6,0,0),(-.6,0,0),(0.,1,0),(0.,-1,0),(1.,-1,1),(-1.,1,-1)]
        record('declared_hysteresis_boundaries',all(direction(z,prior)==want for z,prior,want in cases),dict(cases=cases))
        wanted={(-1,-1):-1,(0,-1):-1,(1,-1):-1,(-1,0):-1,(0,0):0,(1,0):1,(-1,1):0,(0,1):1,(1,1):2}
        record('declared_normal_table',all(normal_grade(B,L)[0]==want for (B,L),want in wanted.items()))

        def volume_probe():
            low,high=moderate_volume_inputs();zl,jl=strength_frame(low);zh,jh=strength_frame(high);za,ja=strength_frame(high,joint=False)
            detail=dict(probe_only=True,base_paths_not_incremented=True,
                low=dict(shock=zl.shock.iloc[-1],effective_shock=zl.effective_shock.iloc[-1],grade=zl.grade.iloc[-1],created=zl.freeze_created.iloc[-1]),
                high=dict(shock=zh.shock.iloc[-1],effective_shock=zh.effective_shock.iloc[-1],grade=zh.grade.iloc[-1],created=zh.freeze_created.iloc[-1]),
                no_volume=dict(grade=za.grade.iloc[-1],created=za.freeze_created.iloc[-1]),
                high_created_events=[e for e in jh if e['kind']=='freeze_created' and e['observation']==190])
            write(out/'moderate-volume-probe.json',clean(detail))
            same,_=frame_comparison(zl[[c for c in MARKET if c!='activity']],zh[[c for c in MARKET if c!='activity']],0.)
            return same and zl.freeze_created.iloc[-1]==0 and zh.freeze_created.iloc[-1]==1 and zh.grade.iloc[-1]==-2 and za.freeze_created.iloc[-1]==0,detail
        checked('same_price_moderate_volume_creation_mechanism',volume_probe)

        # Behavioral evidence below NEVER asserts or modifies the candidate.
        def behavior_suite():
            slow=outputs['slow_decline'];first=first_occurrence(slow.grade,-1,190)
            observed('slow_decline_cold_within_21',first is not None and first['offset']<=21,
                dict(first_cold=first,grade_counts_first_21=grade_counts(slow.iloc[190:211])))
            static=outputs['rise_then_static'];tail=static.iloc[190+63-1:]
            observed('static_not_hot_after_63',not tail.grade.eq(2).any(),dict(first_static_observation=190,
                evaluation_start=252,grade_counts=grade_counts(tail)))
            a=outputs['shock_then_static'];b=outputs['shock_then_recovery']
            observed('hot_to_freeze_same_severe_low_volume_day',a.grade.iloc[189]==2 and a.grade.iloc[190]==-2,
                dict(before=a.grade.iloc[189],shock=a.shock.iloc[190],activity=a.activity.iloc[190],after=a.grade.iloc[190]))
            after=[e for e in journals['shock_then_static'] if e['observation']>=190]
            false_recovery=[e for e in after if e['kind']=='price_recovered']
            observed('unchanged_price_is_not_price_repair',not false_recovery,
                dict(events=after,hot_after_shock=int(a.grade.iloc[190:].eq(2).sum()),
                     note='Scale expiry and downtrend takeover are not price recovery.'))
            observed('unrecovered_static_does_not_reheat_hot',not a.grade.iloc[190:].eq(2).any(),
                dict(grade_counts=grade_counts(a.iloc[190:])),expectation='Behavioral anti-reheating expectation, separate from event accounting.')
            recovery=[e for e in journals['shock_then_recovery'] if e['kind']=='price_recovered' and e['observation']==194]
            earlier_handover=[e for e in journals['shock_then_recovery'] if e['kind'] in ['downtrend_takeover','outside_current_scale'] and 190<e['observation']<194]
            observed('ordinary_volume_complete_recovery_accounted',bool(recovery) or bool(earlier_handover),dict(events=recovery,
                grade_on_full_recovery=b.grade.iloc[194],freeze_count_on_full_recovery=b.freeze_count.iloc[194],
                earlier_handover=earlier_handover,
                alternative_release_events=[e for e in journals['shock_then_recovery'] if 190<=e['observation']<=194]),
                expectation='An active event must recognize actual recovery. Earlier explicit handover is separately allowed, and must not be retroactively renamed price recovery.')
            m=outputs['micro_rise'];o=outputs['ordinary_rise'];rows=slice(183,None)
            ratio_error=float(np.max(np.abs(o.amplitude_63.iloc[rows].to_numpy()-100*m.amplitude_63.iloc[rows].to_numpy()),initial=0.))
            same_temp=bool(m.grade.iloc[rows].equals(o.grade.iloc[rows]))
            observed('100x_path_amplitude_remains_visible',ratio_error<ATOL,dict(amplitude_ratio_error=ratio_error,
                same_temperature=same_temp,micro_final_amplitude=m.amplitude_63.iloc[-1],ordinary_final_amplitude=o.amplitude_63.iloc[-1],
                note='Equal temperature is allowed: this version measures upward evidence, not absolute opportunity size.'))
            micro=outputs['micro_box'].iloc[-63:]
            observed('micro_box_last_63_no_directional_temperature',micro.grade.eq(0).all(),
                dict(grade_counts=grade_counts(micro),max_abs_amplitude_21=micro.amplitude_21.abs().max()),
                expectation='Finite low-amplitude oscillation diagnostic; no market false-positive rate implied.')
            constant=outputs['constant'].dropna(subset=['grade'])
            observed('constant_zero_current_progress',constant.grade.eq(0).all() and constant.z_21.eq(0).all() and constant.z_63.eq(0).all(),
                dict(grade_counts=grade_counts(constant)))
            for key in ['flat_box','consolidation','true_weakening','one_pulse','V_continues','rebound_fails']:
                z=outputs[key];known=z.grade.dropna();changes=known.ne(known.shift())
                observed(key+':complete_trajectory',None,dict(grade_counts=grade_counts(z),
                    state_changes=int(max(0,changes.sum()-1)),last_grade=z.grade.iloc[-1],
                    first_hot_after_common_rebound=first_occurrence(z.grade,2,180) if key in ['V_continues','rebound_fails'] else None,
                    event_exit_reasons={kind:sum(e['kind']==kind for e in journals[key]) for kind in ['price_recovered','downtrend_takeover','outside_current_scale']}),
                    expectation='Descriptive comparison; fewer changes and later eventual success do not prove the state correct.')
        try:behavior_suite()
        except Exception as exc:observed('behavior_collection_error',False,dict(error=repr(exc),traceback=traceback.format_exc()),expectation='Collection failure; missing behavior must not be called passed.')
        checked('frozen_and_old_identities_after',identity)
    except Exception as exc:
        record('runner_failure',False,dict(error=repr(exc),traceback=traceback.format_exc()))
    finally:
        write(out/'synthetic-summary.json',clean(descriptions))
        write(out/'behavior.json',dict(recorded_at=now(),behavior=clean(behavior),
            supported=sum(x['assessment']=='supported' for x in behavior),violated=sum(x['assessment']=='violated' for x in behavior),
            descriptive=sum(x['assessment']=='descriptive' for x in behavior),accounts=0,
            meaning='Finite behavior observations, not market accuracy, profitability, or promotion. Behavior failures do not abort the runner.'))
        passed=bool(technical) and all(x['passed'] for x in technical)
        write(out/'checks.json',dict(recorded_at=now(),technical_passed=passed,technical_checks=len(technical),
            technical_failed=sum(not x['passed'] for x in technical),checks=clean(technical),synthetic_paths=24,
            completed_base_paths=len(outputs),finite_transforms=32,completed_transforms=len(transformed),
            physical_prefixes=prefixes,accounts=0,real_B3_outputs_have_not_been_generated=not (ROOT/'results').exists(),
            meaning='Technical contracts only. See behavior.json and all 24 trajectories before semantic conclusions.'))
        print(json.dumps(dict(technical_passed=passed,technical_checks=len(technical),
            technical_failed=sum(not x['passed'] for x in technical),base_outputs=len(outputs),
            transforms=len(transformed),behavior_violations=sum(x['assessment']=='violated' for x in behavior)),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
