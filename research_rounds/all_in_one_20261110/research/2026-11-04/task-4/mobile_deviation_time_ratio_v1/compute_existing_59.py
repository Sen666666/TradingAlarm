"""Scalar diagnostic on frozen59 metrics only; no account/model/price rebuild."""
from pathlib import Path
import csv,json,math,sys,hashlib
O=Path(__file__).resolve().parent;P=O.parent/'mobile_trend_measurements_v1/MOBILE_SIGNAL_METRICS_AND_ORIGINAL_ACTIONS.csv'
rows=list(csv.DictReader(P.open()));out=[]
for src in rows:
 r=dict(src)
 try:D=float(r['close_deviation_ema20_pct']);S=float(r['ema20_five_observation_slope_pct_per_observation'])
 except (TypeError,ValueError):D=S=math.nan
 finite=math.isfinite(D)and math.isfinite(S);R=D/S if finite and S!=0 else None
 status='INPUT_MISSING'if not finite else'ZERO_SLOPE_UNDEFINED'if S==0 else'NONPOSITIVE_SLOPE_NOT_POSITIVE_PROGRESS_TIME'if S<0 else'POSITIVE_SLOPE_DEFINED'
 r.update(deviation_time_ratio=R,signed_ratio=R,ratio_definition_status=status,slope_abs_bps_per_observation=abs(S)*100 if finite else None,slope_below_1bp_display_alert=finite and abs(S)<.01,slope_machine_near_zero_alert=finite and abs(S)<=32*sys.float_info.epsilon*max(1,abs(S)),small_slope_economic_cutoff='NOT_DEFINED_OR_FITTED',R_if_denominator_plus_1bp=D/(S+.01)if finite and S+.01>0 else None,R_if_denominator_minus_1bp=D/(S-.01)if finite and S-.01>0 else None)
 if R is not None and r['R_if_denominator_plus_1bp']is not None and r['R_if_denominator_minus_1bp']is not None:
  r['max_relative_R_change_for_1bp_slope_perturbation_pct']=100*max(abs(r['R_if_denominator_plus_1bp']/R-1),abs(r['R_if_denominator_minus_1bp']/R-1))if R else None
 else:r['max_relative_R_change_for_1bp_slope_perturbation_pct']=None
 out.append(r)
assert len(out)==59
with (O/'all59.csv').open('w',newline='')as h:
 w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
(O/'all59.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
summary={'rows':len(out),'ratio_defined':sum(r['deviation_time_ratio']is not None for r in out),'status_counts':{s:sum(r['ratio_definition_status']==s for r in out)for s in sorted({r['ratio_definition_status']for r in out})},'slope_under_1bp_display_alert_count':sum(r['slope_below_1bp_display_alert']for r in out),'slope_machine_nearzero_count':sum(r['slope_machine_near_zero_alert']for r in out),'minimum_slope_pct_per_observation':min(float(r['ema20_five_observation_slope_pct_per_observation'])for r in out),'maximum_1bp_perturbation_relative_R_change_pct':max(r['max_relative_R_change_for_1bp_slope_perturbation_pct']for r in out if r['max_relative_R_change_for_1bp_slope_perturbation_pct']is not None),'source':str(P),'source_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'no_outcomes_used_for_ratio':True,'new_accounts_backtests_parameter_search':0,'display_alert_is_not_a_trading_threshold':True}
(O/'RATIO_SCOPE_AND_DENOMINATORS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
