#!/usr/bin/env python3
"""Prefix/poison and synthetic tests. Synthetic paths are not additional stock samples."""
import copy, json, hashlib, datetime
from decimal import Decimal as D, getcontext
from fractions import Fraction
from pathlib import Path
import analyze_fixed as m
getcontext().prec=80
O=m.OUT
def save(name,x):m.write_json(name,x)
def make(values,day="2000-01-04"):
    out=[]
    for i,val in enumerate(values):
        # Tuple is open, high, low, close, volume, amount.
        o,h,l,c,v,a=map(str,val);t=m.EXPECTED[i]
        out.append(dict(date=day,time=day.replace("-","")+t.replace(":","")+"00000",code="synthetic",open=o,high=h,low=l,close=c,volume=v,amount=a,adjustflag="3"))
    return out
def summary(rows):
    bs=m.evaluate(rows,"2000-01-04")
    return dict(nominal=m.signal_state(bs),quality=m.signal_state(bs,True),
        last_Q=bs[-1]["quality_available_Q"],last_flow=bs[-1]["bar_flow_state"],
        last_W=bs[-1]["W_current"],last_close=bs[-1]["close"],
        last_condition1=bs[-1]["W_not_falling"],last_condition2=bs[-1]["close_ge_W"],
        first_bad=bs[-1]["first_bad_time_so_far"]),bs

def main():
    source=m.load(O/"SOURCE_HASHES.json");assert all(m.sha(p)==h for p,h in source.items())
    per=m.load(O/"PER_BAR.json");by={}
    for b in per:by.setdefault((b["sid"],b["day"]),[]).append(b)
    checks=[];dec_checks=0;physical=0;poison=0
    for (sid,day),saved in by.items():
        _,rows=m.raw(sid,day,"5");full=m.evaluate(rows,day)
        for cut in range(1,49):
            pre=m.evaluate(copy.deepcopy(rows[:cut]),day);assert pre==full[:cut];physical+=1
            mutated=copy.deepcopy(rows)
            for r in mutated[cut:]:
                r.update(open="-100000",high="-100000",low="-100000",close="-100000",volume="-1",amount="-100000",adjustflag="7",date="1900-01-01")
            mut=m.evaluate(mutated,day)
            assert mut[:cut]==pre;poison+=1
            if m.signal_state(pre)[1] is not None:assert m.signal_state(mut)[1]==m.signal_state(pre)[1]
            if m.signal_state(pre,True)[1] is not None:assert m.signal_state(mut,True)[1]==m.signal_state(pre,True)[1]
        # Independent direct sums and exact rational comparison, not engine state.
        for i,r in enumerate(rows):
            A=sum((D(x["amount"]) for x in rows[:i+1]),D(0));V=sum((D(x["volume"]) for x in rows[:i+1]),D(0))
            Ap=sum((D(x["amount"]) for x in rows[:i]),D(0));Vp=sum((D(x["volume"]) for x in rows[:i]),D(0))
            a,v,c=D(r["amount"]),D(r["volume"]),D(r["close"])
            fW=Fraction(A)/Fraction(V) if V>0 else None
            fP=Fraction(Ap)/Fraction(Vp) if Vp>0 else None
            b=saved[i]
            assert D(b["cumulative_amount"])==A and D(b["cumulative_volume"])==V
            assert D(b["W_current"])==A/V
            assert b["W_not_falling"]==(fW>=fP if fP is not None else None)
            assert b["close_ge_W"]==(Fraction(c)>=fW)
            if Vp>0:
                x=A*Vp-Ap*V;y=a*Vp-Ap*v
                assert x==y
                assert Fraction(x)==Fraction(A)*Fraction(Vp)-Fraction(Ap)*Fraction(V)
                assert D(b["W_change_cross_product"])==x
                assert D(b["incremental_equivalence_cross_product"])==y
            assert D(b["close_minus_W_cross_product"])==c*V-A
            assert b["quality_available_Q"]==full[i]["quality_available_Q"]
            dec_checks+=1
        checks.append(dict(sid=sid,day=day,physical_prefixes=48,future_poison_cuts=48,independent_decimal_fraction_bars=48))
    tests=[]
    def test(name,vals,assertion):
        rows=make(vals);s,bs=summary(rows);assertion(s,bs);tests.append(dict(name=name,input_rows=rows,observed=s,passed=True,real_execution="UNKNOWN_NOT_SIMULATED"));return s,bs
    def demand(x):assert x
    test("flat_limit_price_equality_pass_without_execution",[(11,11,11,11,1,11)]*4,lambda s,b:demand(s["quality"]==("SIGNAL","09:50") and b[-1]["W_change_cross_product"]==0 and b[-1]["close_minus_W_cross_product"]==0))
    test("ordinary_flat_equality_pass_no_trend_evidence",[(10,10,10,10,1,10)]*4,lambda s,b:demand(s["quality"]==("SIGNAL","09:50")))
    # Hypothetical upper proxy 11, first 3 at 11; next bar reopens, then increment recovers below 11.
    reopen=[(11,11,11,11,1,11)]*3+[(11,11,9,9,3,27),(10,10.8,10,10.8,1,10.7)]
    test("reopen_decline_false_then_recover_below_limit_pass",reopen,lambda s,b:demand(b[3]["provider_nominal_Q"]=="FALSE" and s["quality"]==("SIGNAL","09:55") and D(b[4]["close"])<11))
    test("arbitrarily_small_positive_flow_can_pass",[(10,10,10,10,1000,10000)]*3+[(10,10,10,10,"0.000001","0.000010")],lambda s,b:demand(s["quality"]==("SIGNAL","09:50")))
    test("close_below_previous_close_can_pass",[(10,10,10,10,1,10),(10,10,10,10,1,10),(10,12,10,12,1,10),(11,11,11,11,1,11)],lambda s,b:demand(s["quality"]==("SIGNAL","09:50") and b[-1]["close_below_previous_close"]))
    test("rising_W_does_not_imply_close_ge_W",[(10,10,10,10,1,10)]*3+[(11,12,9,9,1,11)],lambda s,b:demand(s["last_condition1"] is True and s["last_condition2"] is False and s["quality"]==("NO_SIGNAL",None)))
    test("close_ge_W_does_not_imply_rising_W",[(10,10,10,10,1,10)]*3+[(9,11,9,11,1,9)],lambda s,b:demand(s["last_condition1"] is False and s["last_condition2"] is True and s["quality"]==("NO_SIGNAL",None)))
    test("bad_before_first_signal_absorbs_as_unknown",[(10,10,10,10,1,10),(10,10,10,10,1,"10.0000000000000000000000001"),(10,10,10,10,1,10),(11,11,11,11,1,11)],lambda s,b:demand(s["nominal"]==("SIGNAL","09:50") and s["quality"]==("UNKNOWN",None)))
    test("bad_after_first_signal_does_not_revoke",[(10,10,10,10,1,10)]*4+[(10,10,10,10,1,11)],lambda s,b:demand(s["quality"]==("SIGNAL","09:50") and s["last_Q"]=="UNKNOWN"))
    test("zero_volume_zero_amount_no_new_flow",[(10,10,10,10,1,10)]*3+[(10,10,10,10,0,0)],lambda s,b:demand(s["quality"]==("NO_SIGNAL",None) and s["last_flow"]=="ZERO_NO_NEW_FLOW"))
    test("zero_volume_positive_amount_unknown",[(10,10,10,10,1,10)]*3+[(10,10,10,10,0,1)],lambda s,b:demand(s["quality"]==("UNKNOWN",None)))
    test("no_cumulative_volume_unknown",[(10,10,10,10,0,0)]*4,lambda s,b:demand(s["quality"]==("UNKNOWN",None)))
    # Removing a physical bar invalidates its suffix, never earlier state.
    rows=make([(10,10,10,10,1,10)]*6);del rows[2];s,bs=summary(rows)
    assert s["quality"]==("UNKNOWN",None)
    tests.append(dict(name="missing_pre_signal_bar_unknown",observed=s,passed=True))
    rows=make([(10,10,10,10,1,10)]*6);del rows[4];s,bs=summary(rows)
    assert s["quality"]==("SIGNAL","09:50") and s["last_Q"]=="UNKNOWN"
    tests.append(dict(name="missing_post_signal_bar_preserves_earlier_permission",observed=s,passed=True))
    assert all(m.sha(p)==h for p,h in source.items())
    native=m.load(m.OLD/"NATIVE_SOURCE_HASHES.json")
    assert all(m.sha(p)==h for p,h in native.items())
    save("SYNTHETIC_TESTS.json",dict(tests=tests,count=len(tests),note="Algebra/quality edge cases, not expanded stock sample or parameter search. No order lifecycle simulated."))
    save("PREFIX_POISON_TESTS.json",dict(stock_days=32,physical_prefix_tests=physical,future_poison_tests=poison,independent_decimal_fraction_bars=dec_checks,cases=checks,passed=True))
    verification=dict(fixed_event_count=33,unique_stock_days=32,raw_bars_independent_checked=dec_checks,physical_prefix_tests=physical,future_poison_tests=poison,synthetic_tests=len(tests),source_hashes_unchanged=len(source),native_source_hashes_unchanged=len(native),exact_cross_product_equivalence=True,decimal_and_fraction_agree=True,errors_preserved=True,network_fetches=0,economic_runs=0,parameter_searches=0,status="PASS_TECHNICAL_ONLY_NOT_STRATEGY_PROMOTION")
    save("INTERNAL_VERIFICATION.json",verification);print(json.dumps(verification,ensure_ascii=False))
if __name__=="__main__":
    try:main()
    except Exception:
        import traceback
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        with (O/("TEST_ERROR_"+stamp+".txt")).open("x") as f:traceback.print_exc(file=f)
        raise
