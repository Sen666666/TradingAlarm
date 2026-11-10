"""Additional diagnostic anchored only at original receipts; no replacement CP/G state."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd

OUT=Path(__file__).resolve().parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
START='2022-01-04';END='2022-02-08';SID='000620.SZ'
def clean(x):
    if isinstance(x,dict):return{k:clean(v)for k,v in x.items()}
    if isinstance(x,list):return[clean(v)for v in x]
    if hasattr(x,'item'):return clean(x.item())
    if isinstance(x,float)and not math.isfinite(x):return None
    return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
rec=next(r for r in json.loads(MANIFEST.read_text())if r['symbol']==SID)
ip=Path(rec['refs']['CP1_input']);zp=Path(rec['refs']['CP1'])
for p in [ip,zp]:assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['output_sha256'][str(p)]
f=pd.read_parquet(ip).loc[:END];z=pd.read_parquet(zp).reindex(f.index)
local_path=OUT/'ALL21_ORIGINAL_ANCHOR_ER_PATH.json';local={r['day']:r for r in json.loads(local_path.read_text())}
state=None;previous_p=None;previous_segment=None;rows=[]
for dt,r in f.iterrows():
    day=str(dt.date());q=z.loc[dt];p=math.log(float(r.close));segment=r.segment_id
    changed=previous_segment is not None and segment!=previous_segment
    if changed:state=None
    dp=p-previous_p if previous_p is not None and not changed else None
    old=dict(state)if state is not None else None
    pre=None
    if old is not None:
        assert dp is not None
        L=math.fsum((old['L'],abs(dp)));high=max(old['high'],p);A=p-old['log_price']
        pre=dict(A=A,L=L,ER=A/L if L else None,DD=high-p,
                 observations=old['observations']+1,high=high)
    valid=bool(r.e0_valid)
    main=pre if valid else None
    if not valid:state=None
    elif old is not None:
        state=dict(old,L=pre['L'],high=pre['high'],observations=pre['observations'])
    # main is output BEFORE receipt reset, including a negative net advance.
    receipt=bool(q.receipt)
    if receipt:
        assert valid
        state=dict(day=day,log_price=p,close_a=float(r.close),L=0.,high=p,observations=0)
    if START<=day<=END:
        original=local[day]
        row=dict(day=day,sid=SID,close_a=float(r.close),close_raw=original['close_raw'],factor=original['factor'],
                 original_receipt=receipt,original_I_domain_active=valid,original_e0_down=bool(r.e0_down),
                 original_local_reset_reason=original['original_reset_reason'],
                 original_local_anchor_day=original['original_anchor_day_pre_receipt'],
                 original_local_A=original['A_pre_receipt_under_original_current_anchor'],
                 original_local_L=original['L_pre_receipt_including_every_observation'],
                 original_local_ER=original['ER_pre_receipt_L0_is_null'],
                 last_original_receipt_anchor_day_before_current_receipt=old['day']if valid and old else None,
                 last_original_receipt_anchor_close_a=old['close_a']if valid and old else None,
                 observations_after_last_original_receipt=main['observations']if main else None,
                 A_before_original_receipt_reset=main['A']if main else None,
                 L_all_observations_before_original_receipt_reset=main['L']if main else None,
                 ER_before_original_receipt_reset_L0_is_null=main['ER']if main else None,
                 DD_from_known_peak_since_last_original_receipt=main['DD']if main else None,
                 no_previous_receipt_in_this_I_source_domain=valid and old is None,
                 original_down_or_lower_does_not_reset_this_diagnostic=original['original_reset_reason']in['E0_down_reset','lower_anchor'],
                 anchor_before_I_clear=old['day']if not valid and old else None,
                 A_before_I_clear=pre['A']if not valid and pre else None,
                 L_before_I_clear=pre['L']if not valid and pre else None,
                 ER_before_I_clear=pre['ER']if not valid and pre else None,
                 DD_before_I_clear=pre['DD']if not valid and pre else None,
                 next_last_original_receipt_anchor_day=state['day']if state else None,
                 next_L_after_original_receipt_or_domain_clear=state['L']if state else None,
                 original_CORE_qty=original['original_CORE_qty'],original_MOBILE_qty=original['original_MOBILE_qty'],
                 diagnostic_follows_original_receipts_even_if_negative_ER=True,
                 not_a_new_G_candidate_anchor_state=True)
        rows.append(row)
    previous_p=p;previous_segment=segment
assert len(rows)==21
save('LAST_ORIGINAL_RECEIPT_ANCHOR_ALL21.json',rows)
with(OUT/'LAST_ORIGINAL_RECEIPT_ANCHOR_ALL21.csv').open('w',newline='')as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))
receipt_rows=[r for r in rows if r['original_receipt']]
summary=dict(rows=21,original_receipt_rows=9,
             previous_receipt_anchor_defined_receipt_rows=sum(r['ER_before_original_receipt_reset_L0_is_null']is not None for r in receipt_rows),
             positive_ER1_receipt_rows=sum(r['ER_before_original_receipt_reset_L0_is_null']==1 for r in receipt_rows),
             negative_ER_receipt_rows=sum(r['ER_before_original_receipt_reset_L0_is_null']is not None and r['ER_before_original_receipt_reset_L0_is_null']<0 for r in receipt_rows),
             missing_prior_receipt_first_receipt_days=[r['day']for r in receipt_rows if r['no_previous_receipt_in_this_I_source_domain']],
             receipt_diagnostics=receipt_rows,
             resets='Only original receipt after output, or original I/source domain off. Down and SEEK lower_anchor do not reset this diagnostic.',
             clarification='9/9 ER1 belongs ONLY to separate original-local-reset anchor table, NOT this last-original-receipt anchor.',
             new_model_clock_warning='If a new G model rejects original Jan20 receipt, Jan20 cannot reset that model candidate anchor; Jan21 must be recomputed under its retained state. This table intentionally resets at original Jan20 and is not that model.',
             no_new_CP_or_G_rule=True,new_accounts=0,new_orders=0,new_backtests=0)
save('LAST_ORIGINAL_RECEIPT_ANCHOR_SCOPE_AND_KEYS.json',summary)
save('LAST_RECEIPT_DIAGNOSTIC_SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in[MANIFEST,ip,zp,local_path,Path(__file__)]])
print(json.dumps(clean({k:v for k,v in summary.items()if k!='receipt_diagnostics'}),ensure_ascii=False))
print(json.dumps(clean([r for r in rows if r['day']in['2022-01-19','2022-01-20','2022-01-21','2022-01-24','2022-01-27']]),ensure_ascii=False))
