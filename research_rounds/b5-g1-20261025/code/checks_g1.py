"""Technical validation and finite behavioral diagnostics, before accounts."""
import math
import pandas as pd
import numpy as np
from g1util import *
from grade import classify
from policies_g1 import project

def main():
    out=HERE/'validation';out.mkdir(exist_ok=False);(out/'synthetic').mkdir()
    checks=[];diagnostics=[];prefixes=[];vol=[];api=b5()
    def check(name,ok,**detail):
        checks.append(dict(name=name,passed=bool(ok),**detail))
        if not ok:raise AssertionError(name)
    def exact(a,b):pd.testing.assert_frame_equal(a,b,check_exact=True,check_freq=False)
    for p in sorted((HERE/'inputs').glob('*.parquet')):
        symbol=p.stem;f=pd.read_parquet(p);e=pd.read_parquet(HERE/'replay'/f'{symbol}-evidence.parquet');base=pd.read_parquet(HERE/'replay'/f'{symbol}-E0.parquet');g=pd.read_parquet(HERE/'grading'/f'{symbol}.parquet')
        check(symbol+':upgrades_have_new_evidence',not ((g.transition=='upgrade')&~g.fresh_up).any())
        check(symbol+':score_is_ordinal_identity',g.score.dropna().eq(g.grade.dropna()*25).all())
        check(symbol+':acute_down_cannot_be_hot',g.loc[g.acute_down,'grade'].le(-3).all())
        # Deliberately poison old participation columns; strength must not use them.
        poisoned=e.copy();poisoned['target']=1e9;poisoned['floor']=-1e9;poisoned['pending']='nonsense'
        gg,_=classify(poisoned);exact(g,gg);check(symbol+':no_policy_feedback',True)
        for n in [65,len(f)//2,len(f)-1]:
            sub=f.iloc[:n].copy();a=api.run_b5(sub,enhancements=False);z,j=classify(a['evidence']);exact(z,g.iloc[:n])
            for policy in POLICIES[1:]:
                s=project(a['evidence'],a['state'],z,policy);full=pd.read_parquet(HERE/'grading'/f'{symbol}-{policy}.parquet');exact(s,full.iloc[:n])
            prefixes.append(dict(symbol=symbol,rows=n,last=str(sub.index[-1].date()),grade_exact=True,three_policies_exact=True))
        check(symbol+':three_physical_prefixes',True)
        # Units and constant-volume mechanism contrasts on a fixed prefix.
        sub=f.iloc[:min(600,len(f))].copy();a=api.run_b5(sub);gg,_=classify(a['evidence'])
        scaled=sub.copy();scaled[['open','high','low','close']]*=17;scaled.volume*=10000
        ab=api.run_b5(scaled);zz,_=classify(ab['evidence'])
        check(symbol+':price_and_volume_units',gg.grade.equals(zz.grade) and gg.fresh_up.equals(zz.fresh_up))
        fixed=sub.copy();fixed.volume=100.;v=api.run_b5(fixed);vg,_=classify(v['evidence'])
        mask=gg.ready&vg.ready
        vol.append(dict(symbol=symbol,observations=len(sub),grade_changed=int((gg.grade[mask]!=vg.grade[mask]).sum()),new_up_evidence_changed=int((gg.fresh_up[mask]!=vg.fresh_up[mask]).sum()),note='constant volume ablation, no economic conclusions'))
        # Interface behavior: skip an invalid row; restart a genuine new segment.
        sub=sub.iloc[:180].copy();sub.loc[sub.index[90],['open','high','low','close','volume']]=np.nan;sub.loc[sub.index[90],['valid_price_observation','valid_strength_observation']]=False
        a=api.run_b5(sub);zz,_=classify(a['evidence']);check(symbol+':invalid_row_unknown',not zz.ready.iloc[90] and pd.isna(zz.grade.iloc[90]))
        deleted=sub.drop(sub.index[90]);b=api.run_b5(deleted);zg,_=classify(b['evidence']);exact(zz.drop(zz.index[90]),zg);check(symbol+':invalid_row_no_clock_advance',True)
        two=f.iloc[:180].copy();two.loc[two.index[90]:,'segment_id']=1
        a=api.run_b5(two);zz,_=classify(a['evidence']);isolated=api.run_b5(two.iloc[90:]);zi,_=classify(isolated['evidence']);exact(zz.iloc[90:],zi);check(symbol+':source_reset',True)
    # Previously frozen, finite 25 synthetic paths. OHLC construction is a
    # declared adapter for descriptive tests only, never an account input.
    files=sorted((ROOT/'research_rounds/pv-strength-b4-20261025/validation/inputs').glob('*.parquet'))
    check('frozen_synthetic_count',len(files)==25,count=len(files))
    for p in files:
        raw=pd.read_parquet(p);f=raw[['close','volume','segment_id','valid_strength_observation']].copy();f['open']=f.close.shift().fillna(f.close)
        f['high']=f[['open','close']].max(axis=1)*1.001;f['low']=f[['open','close']].min(axis=1)*.999;f['valid_price_observation']=True
        a=api.run_b5(f);g,events=classify(a['evidence']);g.to_parquet(out/'synthetic'/p.name)
        check(p.stem+':no_unjustified_promotion',not ((g.transition=='upgrade')&~g.fresh_up).any())
        if p.stem in ['shock_then_static','shock_then_slow_decline','rise_then_static']:
            check(p.stem+':no_passive_recovery_after190',not g.iloc[191:].transition.eq('upgrade').any())
        if p.stem=='constant':check('constant:zero_after_warmup',g.grade.dropna().eq(0).all())
        if p.stem=='slow_decline':check('slow_decline:tail_cold',g.grade.iloc[-30:].le(-2).all())
        diagnostics.append(dict(path=p.stem,rows=len(g),tail_grade=int(g.grade.dropna().iloc[-1]),upgrades=int(g.transition.eq('upgrade').sum()),downgrades=int(g.transition.eq('downgrade').sum()),warm_observations=int(g.grade.ge(2).sum()),cold_observations=int(g.grade.le(-2).sum()),freeze=int(g.acute_down.sum())))
    # Direct policy units isolate genuine causality from a market fixture.
    ix=pd.bdate_range('2020-01-01',periods=8)
    e=pd.DataFrame(dict(close=100.,segment_id=0,valid_price_observation=True),index=ix)
    b=pd.DataFrame(dict(target=[0,1,1,1,1,0,1,1],entered=[0,1,0,0,0,0,1,0],floor=90.,entry_kind='original_event'),index=ix)
    g=pd.DataFrame(dict(ready=True,grade=[0,3,-2,1,3,-3,3,3],fresh_up=[False,True,False,False,True,False,True,False],acute_down=False),index=ix)
    si=project(e,b,g,'G1_I');sx=project(e,b,g,'G1_X');sc=project(e,b,g,'G1_IX')
    check('I_does_not_sell_on_cold',si.target.iloc[2]==1 and si.target.iloc[4]==1)
    check('X_exits_cold_waits_old_E0_cycle',sx.exited.iloc[2]==1 and sx.target.iloc[4]==0 and sx.entered.iloc[6]==1)
    check('IX_exits_then_restores_on_new_warm_evidence',sc.exited.iloc[2]==1 and sc.target.iloc[3]==0 and sc.entered.iloc[4]==1)
    g.loc[ix[4],'fresh_up']=False;ss=project(e,b,g,'G1_IX');check('IX_no_restore_from_hot_state_alone',ss.target.iloc[4]==0)
    check('I_orders_require_current_evidence',not si.buy_event.iloc[3] and si.buy_event.iloc[4])
    for policy,s in [('I',si),('X',sx),('IX',sc)]:
        check(policy+':never_outside_E0',not (s.target.astype(bool)&~b.target.astype(bool)).any())
        check(policy+':no_same_day_exit_entry',not (s.exited.astype(bool)&s.entered.astype(bool)).any())
    pd.DataFrame(prefixes).to_csv(out/'physical-prefixes.csv',index=False);pd.DataFrame(vol).to_csv(out/'volume-ablation.csv',index=False);pd.DataFrame(diagnostics).to_csv(out/'synthetic-behavior.csv',index=False)
    write(out/'checks.json',dict(recorded_at=now(),passed=all(x['passed'] for x in checks),technical_checks=len(checks),details=checks,physical_prefixes=len(prefixes),synthetic_paths=len(files),accounts=0))
    print(dict(passed=True,checks=len(checks),physical_prefixes=len(prefixes),synthetic_paths=len(files),volume_diagnostics=vol),flush=True)

if __name__=='__main__':main()
