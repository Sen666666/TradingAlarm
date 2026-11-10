"""Isolated small candidate/liquidity checks, no full-source/model execution."""
from pathlib import Path
import hashlib,importlib.util,json
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    codepath=ROOT/'candidate_view.py';spec=importlib.util.spec_from_file_location('review_candidate_view',codepath)
    cv=importlib.util.module_from_spec(spec);spec.loader.exec_module(cv)
    source_sha=sha(codepath)
    dates=pd.date_range('2024-01-01',periods=30)
    b=pd.DataFrame({'trade_date':dates,'close':10.,'amount':np.arange(1,31,dtype=float),'source':'known-source'})
    target=str(dates[20].date());r=cv.prior_liquidity20(b,[target]).iloc[0]
    assert r.amount20_prior_native==10.5 and r.amount20_window_start==dates[0] and r.amount20_window_end==dates[19]
    mutate=b.copy();mutate.loc[20:,'amount']=999999.;mutate.loc[21:,'close']=999999.
    rr=cv.prior_liquidity20(mutate,[target]).iloc[0]
    assert r.equals(rr),'current/future value leak'
    assert cv.prior_liquidity20(b.iloc[:21],[target]).equals(cv.prior_liquidity20(b,[target]))
    changed=b.copy();changed.loc[10:,'source']='second-source'
    cr=cv.prior_liquidity20(changed,[target]).iloc[0]
    assert cr.amount20_prior_observations==10 and pd.isna(cr.amount20_prior_native)
    invalid=b.copy();invalid.loc[5,'amount']=0
    inv=cv.prior_liquidity20(invalid,[str(dates[24].date()),str(dates[26].date())])
    assert inv.iloc[0].amount20_prior_observations==18 and pd.isna(inv.iloc[0].amount20_prior_native)
    assert inv.iloc[1].amount20_prior_native==float(np.median(b.amount.iloc[6:26]))
    absent=cv.prior_liquidity20(b.drop(index=20),[target]).iloc[0]
    assert absent.amount20_status=='MISSING_TARGET_BAR' and pd.isna(absent.amount20_prior_native)
    unknown=b.copy();unknown['source']=None
    ur=cv.prior_liquidity20(unknown,[target]).iloc[0]
    unknown_guard_ok=ur.amount20_status!='KNOWN_PRIOR20_SOURCE_OBSERVATIONS' and pd.isna(ur.amount20_prior_native)
    f=pd.DataFrame({'sid':['000001.SZ','000002.SZ','000003.SZ','000004.SZ'],'day':[target]*4,'target_row_present':[True,True,True,False],'pvr_valid_observation':[True,True,True,None],'pvr_status':['KNOWN','KNOWN','KNOWN','MISSING_TARGET_BAR'],'score':[20.,30.,30.,np.nan],'current_close_qfq':[1.,2.,3.,np.nan],'raw_close':[1.,2.,3.,np.nan],'current_amount_passthrough':[1.,2.,3.,np.nan],'source':['known-source']*4,'current_block_observations_through_t':[100,100,100,np.nan],'cap':[0.,999999.,None,None],'in_current_roster':[False,False,False,True]})
    liq=f[['sid','day']].copy();liq['amount20_status']='INSUFFICIENT_PRIOR_VALID_BLOCK';liq['amount20_prior_native']=np.nan
    v=cv.candidate_view(f,liq)
    f2=f.copy();f2['cap']=[999999.,0.,999999.,999999.];f2['in_current_roster']=~f2.in_current_roster
    v2=cv.candidate_view(f2,liq);pd.testing.assert_frame_equal(v,v2)
    assert v.loc[v.no_cap_PVR_rank.notna()].sort_values('no_cap_PVR_rank').sid.tolist()==['000002.SZ','000003.SZ','000001.SZ']
    assert v.research_no_cap_pool.sum()==3 and v.executable_eligibility.eq('UNKNOWN_NOT_CERTIFIED').all()
    assert source_sha==sha(codepath),'candidate source changed during isolated checks'
    result={'status':'PASS_BOUNDED_SMALL_CASES'if unknown_guard_ok else'PASS_EXISTING_KNOWN_SOURCE_CASES_WITH_GENERIC_UNKNOWN_SOURCE_DEFECT','candidate_source_sha256':source_sha,'checks':{'prior20_exact_median_and_endpoints':True,'current_future_mutation_invariant':True,'prefix_invariant':True,'known_source_change_resets_block':True,'invalid_row_resets_no_skip':True,'missing_target_not_filled':True,'cap_roster_extra_columns_invariance':True,'liquidity_unknown_does_not_filter_queue':True,'raw_score_and_sid_tie_sort':True,'legal_status_never_execution_grant':True,'unknown_source_rejected':unknown_guard_ok},'unknown_source_observed_result':{'status':ur.amount20_status,'value':None if pd.isna(ur.amount20_prior_native)else float(ur.amount20_prior_native)},'limits':['Small synthetic function checks only, no account, historical price path simulation or full-market/model/feature recomputation.','Source=None defect is generic interface behavior; current canonical source has separate prior known-single-source producer checks. It must not be claimed as an observed defect in saved real numeric outputs.'],'source_sha256':{str(codepath.resolve()):source_sha,str(Path(__file__).resolve()):sha(Path(__file__)),str((ROOT/'run_comparison.py').resolve()):sha(ROOT/'run_comparison.py')}}
    p=OUT/'SMALL_CASES_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(p),'source_sha256':source_sha,'unknown_source':result['unknown_source_observed_result']},ensure_ascii=False))
if __name__=='__main__':main()
