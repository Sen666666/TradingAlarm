#!/usr/bin/env python3
"""Frozen single-rule, finite-cache condition diagnostic. No network, account or economics."""
import csv, json, hashlib, datetime, sys
from collections import Counter, defaultdict
from decimal import Decimal as D, getcontext, ROUND_HALF_UP
from pathlib import Path
getcontext().prec = 80
R = Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
OLD = R / "opening_range_first_probe_preflight_v1"
OUT = R / "intraday_cost_acceptance_preflight_v1"
OJ = R / "price_next_open_receipt_preflight_v1/FIXED19_INPUT_RESULT.json"
PROTOCOL_HASH = "e8be017794c1c36f0d8c6b3ec256428defcb53bfc60d9666ec632c438839643e"
FIELDS_NUM = ("open", "high", "low", "close", "volume", "amount")
EXPECTED = [f"{h:02d}:{m:02d}" for h, ms in [(9,range(35,60,5)),(10,range(0,60,5)),(11,range(0,35,5)),(13,range(5,60,5)),(14,range(0,60,5)),(15,[0])] for m in ms]
assert len(EXPECTED) == 48

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(), parse_float=D)
def string(x): return None if x is None else format(x, "f") if isinstance(x,D) else str(x)
def enc(x):
    if isinstance(x,D): return string(x)
    raise TypeError(type(x).__name__)
def write_json(name, obj):
    with (OUT/name).open("x") as f: json.dump(obj,f,ensure_ascii=False,indent=2,default=enc,allow_nan=False)
def write_csv(name, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open("x",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v,ensure_ascii=False,default=enc) if isinstance(v,(dict,list)) else string(v) if isinstance(v,D) else v for k,v in row.items()})
def csvrows(p): return list(csv.DictReader(Path(p).open()))
def clock(r): return r["time"][8:10]+":"+r["time"][10:12]
def raw(sid,day,freq):
    j=load(OLD/"raw"/f"{sid}_{day}_{freq}.json")
    assert j["error_code"]=="0" and j["adjustflag"]=="3"
    return j,[dict(zip(j["fields"],r)) for r in j["rows"]]

def evaluate(rows, day):
    # All state updates use only this bar and prior bars. No daily QA or next bar.
    A=V=D(0); first_bad=None; nominal_tau=None; quality_tau=None; output=[]
    flat_price=None; same_price_prefix=True
    for i,r in enumerate(rows):
        p={k:D(r[k]) for k in FIELDS_NUM}
        o,h,l,c,v,a=(p[k] for k in FIELDS_NUM); t=clock(r)
        ap,vp=A,V;A+=a;V+=v
        wp=ap/vp if vp>0 else None; wk=A/V if V>0 else None
        inc=a/v if v>0 else None
        reasons=[]
        if i>=48 or t!=EXPECTED[i]: reasons.append("MISSING_DUPLICATE_OR_OUT_OF_ORDER_BAR")
        if r["date"]!=day or r["time"][:8]!=day.replace("-",""): reasons.append("DATE_MISMATCH")
        if r["adjustflag"]!="3": reasons.append("ADJUSTFLAG_NOT_3")
        if any(p[k]<=0 for k in ("open","high","low","close")) or not l<=o<=h or not l<=c<=h: reasons.append("INVALID_OHLC")
        if v<0 or a<0: reasons.append("NEGATIVE_VOLUME_OR_AMOUNT")
        if v==0 and a!=0: reasons.append("ZERO_VOLUME_NONZERO_AMOUNT")
        if v>0 and not l*v<=a<=h*v: reasons.append("BAR_AMOUNT_VOLUME_OUTSIDE_LOW_HIGH")
        if V<=0: reasons.append("NO_POSITIVE_CUMULATIVE_VOLUME")
        if reasons and first_bad is None: first_bad=i
        # Integer-scale finite decimals make these cross products exact at this precision.
        dw=A*vp-ap*V if V>0 and vp>0 else None
        dc=c*V-A if V>0 else None
        di=a*vp-ap*v if v>0 and vp>0 else None
        cond1=dw>=0 if dw is not None else None
        cond2=dc>=0 if dc is not None else None
        eligible="09:50"<=t<="14:50"
        flow = "POSITIVE" if v>0 else "ZERO_NO_NEW_FLOW" if v==0 and a==0 else "INVALID"
        nominal_q=(cond1 and cond2 and v>0) if cond1 is not None and cond2 is not None else None
        nominal = "TRUE" if nominal_q else "FALSE" if nominal_q is not None else "UNDEFINED"
        available = "NOT_EVALUATED" if not eligible else "UNKNOWN" if first_bad is not None else nominal
        if eligible and nominal_q:
            if nominal_tau is None: nominal_tau=i
            if first_bad is None and quality_tau is None: quality_tau=i
        if i==0: flat_price=c
        same_price_prefix=same_price_prefix and o==h==l==c==flat_price
        q=dict(sid="",day=day,bar_index=i,clock=t,eligible=eligible,**r,
            cumulative_amount=A,cumulative_volume=V,previous_cumulative_amount=ap,previous_cumulative_volume=vp,
            W_previous=wp,W_current=wk,incremental_average=inc,
            W_change=wk-wp if wk is not None and wp is not None else None,
            close_minus_W=c-wk if wk is not None else None,
            incremental_average_minus_W_previous=inc-wp if inc is not None and wp is not None else None,
            W_change_cross_product=dw,incremental_equivalence_cross_product=di,close_minus_W_cross_product=dc,
            W_not_falling=cond1,close_ge_W=cond2,volume_positive=v>0,
            provider_nominal_Q=nominal,quality_available_Q=available,
            bar_flow_state=flow,bar_quality_reasons=reasons,prefix_quality="UNKNOWN" if first_bad is not None else "COMPATIBLE",
            first_bad_index_so_far=first_bad,first_bad_time_so_far=clock(rows[first_bad]) if first_bad is not None else None,
            nominal_tau_so_far=clock(rows[nominal_tau]) if nominal_tau is not None else None,
            quality_tau_so_far=clock(rows[quality_tau]) if quality_tau is not None else None,
            same_price_entire_prefix=same_price_prefix,
            close_below_previous_close=(c<D(rows[i-1]["close"])) if i else None,
            actual_source_available_at="UNKNOWN",publication_delay="UNKNOWN",real_execution="UNKNOWN")
        output.append(q)
    return output

def signal_state(bars, quality=False):
    key="quality_tau_so_far" if quality else "nominal_tau_so_far"
    tau=bars[-1][key] if bars else None
    if tau: return "SIGNAL",tau
    if quality and any(b["eligible"] and b["prefix_quality"]=="UNKNOWN" for b in bars): return "UNKNOWN",None
    return "NO_SIGNAL",None

def prices(prefix, casespec, bars, rawrows, upper, lower):
    state,tau=signal_state(bars,quality=prefix=="quality")
    z={prefix+"_status":state,prefix+"_tau":tau}
    if tau is None:return z
    i=next(i for i,b in enumerate(bars) if b["clock"]==tau)
    b=bars[i]; n=rawrows[i+1];nopen=D(n["open"]); oldopen=D(str(casespec["old_raw_open"]))
    floor=casespec["original_initial_floor_raw"];floor=D(str(floor)) if floor is not None else None
    end=datetime.datetime.strptime(n["time"],"%Y%m%d%H%M%S%f")
    values=dict(tau_close=D(b["close"]),tau_W=b["W_current"],tau_incremental_average=b["incremental_average"],
        tau_W_change=b["W_change"],tau_close_minus_W=b["close_minus_W"],
        tau_prefix_quality=b["prefix_quality"],next_bar_end=clock(n),
        next_bar_interval_start=(end-datetime.timedelta(minutes=5)).strftime("%H:%M"),
        next_bar_raw_open=nopen,next_open_minus_tau_close=nopen-D(b["close"]),
        next_open_minus_old_open=nopen-oldopen,next_open_vs_old_open_pct=100*(nopen/oldopen-1),
        next_open_vs_original_floor="UNKNOWN" if floor is None else "ABOVE" if nopen>floor else "EQUAL" if nopen==floor else "BELOW",
        next_open_minus_original_floor=nopen-floor if floor is not None else None,
        next_open_at_upper_limit_proxy=nopen==upper,next_open_in_limit_proxy=lower<=nopen<=upper,
        next_open_plus_5bp=nopen*D("1.0005"),next_open_plus_5bp_above_upper_illegal_proxy=nopen*D("1.0005")>upper,
        next_bar_one_price=D(n["high"])==D(n["low"]),
        next_bar_flat_at_upper_proxy=D(n["high"])==D(n["low"])==upper,
        next_bar_positive_volume=D(n["volume"])>0,next_bar_price_use="DESCRIPTION_ONLY_NOT_A_FILL",
        order_earliest_time="STRICTLY_AFTER_RECEIPT_OF_COMPLETED_TAU_BAR; RECEIPT_TIME_UNKNOWN")
    z.update({prefix+"_"+k:v for k,v in values.items()});return z

def main():
    assert sha(OUT/"PROTOCOL.md")==PROTOCOL_HASH
    cases=load(OLD/"FROZEN_CASES.json")
    assert len(cases)==33 and len({(c["sid"],c["entry_day"]) for c in cases})==32
    orb={r["case_id"]:r for r in csvrows(OLD/"FIXED_CASE_RESULTS.csv")}
    old_qa={(r["sid"],r["day"]):r for r in csvrows(OLD/"SOURCE_QA.csv")}
    oj=load(OJ)["cases"]; assert len(oj)==19
    ojmap={(r["sid"],r["day"],r["next_day"]):r for r in oj};assert len(ojmap)==19
    inputs=sorted(p for p in OLD.rglob("*") if p.is_file())+[OJ,OUT/"PROTOCOL.md"]
    before={str(p):sha(p) for p in inputs}
    # Validate old frozen cached hashes before use; never rewrite a source.
    oldhash=load(OLD/"OUTPUT_HASHES.json")
    assert all(sha(OLD/p)==h for p,h in oldhash.items())
    allbars=[]; dayqa=[]; results=[]
    for sid,day in sorted({(c["sid"],c["entry_day"]) for c in cases}):
        j,rows=raw(sid,day,"5");jd,dr=raw(sid,day,"d");assert len(dr)==1
        d=dr[0]; ratio=D(".20") if sid.startswith(("300","301","688")) else D(".05") if d["isST"]=="1" else D(".10")
        upper=(D(d["preclose"])*(1+ratio)).quantize(D(".01"),rounding=ROUND_HALF_UP)
        lower=(D(d["preclose"])*(1-ratio)).quantize(D(".01"),rounding=ROUND_HALF_UP)
        bars=evaluate(rows,day);seen_upper=False
        for b in bars:
            b["sid"]=sid
            b["standard_limit_proxy_ratio"]=ratio;b["upper_limit_proxy"]=upper;b["lower_limit_proxy"]=lower
            b["close_at_upper_proxy"]=D(b["close"])==upper
            b["flat_at_upper_proxy"]=D(b["high"])==D(b["low"])==upper
            b["bar_range_in_limit_proxy"]=lower<=D(b["low"])<=D(b["high"])<=upper
            seen_upper=seen_upper or D(b["high"])>=upper
            b["upper_proxy_touched_in_prefix"]=seen_upper
            b["below_upper_after_touch_in_prefix"]=seen_upper and D(b["low"])<upper
            b["close_plus_5bp_above_upper_illegal_proxy"]=D(b["close"])*D("1.0005")>upper
        firstbad=next((b for b in bars if b["bar_quality_reasons"]),None)
        bads=[b for b in bars if b["bar_quality_reasons"]]
        qa=dict(sid=sid,day=day,bars=len(bars),grid_exact=[clock(r) for r in rows]==EXPECTED,
            first_bad_time=firstbad["clock"] if firstbad else None,
            incompatible_bar_count=len(bads),incompatible_bar_times=[b["clock"] for b in bads],
            final_prefix_quality=bars[-1]["prefix_quality"],**{"old_full_day_audit_"+k:v for k,v in old_qa[(sid,day)].items() if k not in ("sid","day")},
            minute_daily_volume_difference_exact=sum(D(r["volume"]) for r in rows)-D(d["volume"]),
            minute_daily_amount_difference_exact=sum(D(r["amount"]) for r in rows)-D(d["amount"]),
            minute_daily_ohlc_maxdiff_exact=max(abs(a-D(d[k])) for k,a in {
                "open":D(rows[0]["open"]),"high":max(D(r["high"]) for r in rows),
                "low":min(D(r["low"]) for r in rows),"close":D(rows[-1]["close"])}.items()),
            limit_proxy=upper,limit_lower_proxy=lower,limit_certification="UNKNOWN_HISTORICAL_EXCEPTIONS_NOT_CERTIFIED",
            source_full_trade_coverage="UNKNOWN",publication_delay="UNKNOWN")
        dayqa.append(qa);allbars.extend(bars)
        for c in [c for c in cases if c["sid"]==sid and c["entry_day"]==day]:
            z=dict(c);z["old_label_contract"]="NOACT_ORIGINAL_FIRST_LAYER_NET" if c["contract"]=="NOACT_ORIGINAL_MOBILE" else "PRICE_ORIGINAL_FIXED_ROLE_LABEL"
            z["old_label"]=("OLD_NET_NEGATIVE" if c["old_pnl"]<0 else "OLD_NET_POSITIVE") if c["old_pnl"] is not None else "OLD_FAILURE" if "失败" in c["tag"] else "OLD_WINNER" if "盈利" in c["tag"] else "UNLABELED_PRICE_POINT"
            z.update(upper_limit_proxy=upper,lower_limit_proxy=lower,old_open_at_upper_proxy=D(str(c["old_raw_open"]))==upper,
                old_open_plus_5bp=D(str(c["old_raw_open"]))*D("1.0005"),
                old_open_plus_5bp_above_upper_illegal_proxy=D(str(c["old_raw_open"]))*D("1.0005")>upper,
                first_bad_time=qa["first_bad_time"],incompatible_bar_count=len(bads),final_prefix_quality=bars[-1]["prefix_quality"],
                full_day_qa_audit_only=True,source_full_trade_coverage="UNKNOWN",publication_delay="UNKNOWN",
                official_limit_certification="UNKNOWN",real_execution="UNKNOWN",new_economics="NOT_COMPUTED")
            z.update(prices("nominal",c,bars,rows,upper,lower));z.update(prices("quality",c,bars,rows,upper,lower))
            z["later_bad_does_not_revoke_earlier_quality_signal"]=bool(firstbad and z["quality_tau"] and firstbad["clock"]>z["quality_tau"])
            b=orb[c["case_id"]]
            assert (b["sid"],b["signal_day"],b["entry_day"])==(sid,c["signal_day"],day)
            for k in ("signal_status","signal_time","threshold","next_bar_raw_open","proxy_price_change_vs_original_open_pct"):
                z["original_ORB_"+k]=b[k]
            z["original_ORB_source"]=str(OLD/"FIXED_CASE_RESULTS.csv")
            mapped=ojmap.get((sid,c["signal_day"],day)) if c["contract"]=="PRICE_FIXED_INPUT" else None
            z["old_O_gt_J_mapping"]="EXACT_PRICE_CONTRACT_SID_SIGNAL_DAY_ENTRY_DAY" if mapped else "UNKNOWN_NO_SAME_CONTRACT_MAPPING"
            z["old_O_gt_J_status"]="PASS" if mapped and mapped["known"] and mapped["open_above_J"] else "NO_PASS" if mapped and mapped["known"] else "UNKNOWN"
            z["old_O_gt_J_source"]=str(OJ) if mapped else None
            if mapped:
                assert D(str(c["old_raw_open"]))==mapped["next_open_raw"]
                for k in ("J_raw","J_native","next_open_raw","next_open_native","open_above_J","known","phase","E0","I","root_day"):
                    z["old_O_gt_J_"+k]=mapped[k]
            results.append(z)
    order={c["case_id"]:i for i,c in enumerate(cases)};results.sort(key=lambda c:order[c["case_id"]])
    assert len(allbars)==1536 and len(results)==33
    assert all(sha(p)==h for p,h in before.items())
    contracts={}
    for contract in sorted({c["contract"] for c in cases}):
        rr=[c for c in results if c["contract"]==contract]
        contracts[contract]=dict(events=len(rr),nominal_status_counts=dict(Counter(r["nominal_status"] for r in rr)),
            quality_status_counts=dict(Counter(r["quality_status"] for r in rr)),
            original_ORB_counts=dict(Counter(r["original_ORB_signal_status"] for r in rr)),
            old_O_gt_J_counts=dict(Counter(r["old_O_gt_J_status"] for r in rr)),
            old_label_by_quality_status={lab:dict(Counter(r["quality_status"] for r in rr if r["old_label"]==lab)) for lab in sorted({r["old_label"] for r in rr})})
    summary=dict(protocol_sha256=PROTOCOL_HASH,events=33,unique_stock_days=32,minute_bars=1536,
        contracts=contracts,stock_days_with_incompatible_bars=sum(q["incompatible_bar_count"]>0 for q in dayqa),
        incompatible_bars=sum(q["incompatible_bar_count"] for q in dayqa),
        unknown_prefix_bars=sum(b["prefix_quality"]=="UNKNOWN" for b in allbars),
        later_bad_after_quality_signal_events=sum(r["later_bad_does_not_revoke_earlier_quality_signal"] for r in results),
        old_input_files_hashed=len(before),old_output_hash_entries_checked=len(oldhash),
        new_network_fetches=0,new_account_runs=0,new_economic_calculations=0,parameter_searches=0,
        disposition="DO_NOT_PROMOTE_NO_SEPARATION_EXECUTION_UNCERTIFIED",
        interpretation="Condition and descriptive source prices only. No new win rate, pnl, saved loss, fills or execution certification.")
    write_json("SOURCE_HASHES.json",before)
    write_json("PER_BAR.json",allbars);write_csv("PER_BAR.csv",allbars)
    write_json("FIXED_CASE_RESULTS.json",results);write_csv("FIXED_CASE_RESULTS.csv",results)
    write_json("SOURCE_QA.json",dayqa);write_csv("SOURCE_QA.csv",dayqa)
    write_json("SUMMARY.json",summary)
    print(json.dumps(summary,ensure_ascii=False,default=enc,indent=2))
    for z in results:
        print(z["case_id"],z["name"],z["quality_status"],z["quality_tau"],z.get("quality_next_bar_raw_open"),z.get("quality_next_open_vs_old_open_pct"))

if __name__=="__main__":
    try:main()
    except Exception:
        import traceback
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        with (OUT/("ERROR_"+stamp+".txt")).open("x") as f:traceback.print_exc(file=f)
        raise
