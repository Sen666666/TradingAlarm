"""Descriptive fixed-window signal diagnostics from sealed outputs only; no rerun."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert json.loads((O/'QA.json').read_text())['status']=='COMPLETE_MARKET_PREFLIGHT_PENDING_INDEPENDENT_AUDIT'
 inputs=['DAILY_STATES.parquet','FULL_WARM_BIRTHS.parquet','RECEIPTS.parquet','NEXT_OPEN_OBSERVATIONS.parquet','COVERAGE.csv','WINDOW_CARRY.csv','WINDOW_SUMMARY.csv']
 hashes={n:sha(O/n) for n in inputs};d=pd.read_parquet(O/'DAILY_STATES.parquet');b=pd.read_parquet(O/'FULL_WARM_BIRTHS.parquet');cal=sorted(d.day.unique());birthmap=b.set_index(['sid','root_day'])
 rows=[]
 for (w,sid,root),g in d[d.root_day.notna()].groupby(['window','sid','root_day'],sort=False):
  g=g.sort_values('day');born=g[g.born];cohort='NEW_WINDOW_BIRTH' if len(born) else 'PREWINDOW_ROOT'
  first=g.iloc[0];bb=birthmap.loc[(sid,root)];assert isinstance(bb,pd.Series)
  fresh=g[g.receipt];con=g[g.confirmed_now];known=g.confirmed_at.dropna();confday=known.min() if len(known) else pd.NaT
  failed=g[g.failed];unknown=g[g.root_unknown]
  terminal='PRICE_FAILED' if len(failed) else 'PRICE_ROOT_UNKNOWN' if len(unknown) else 'ACTIVE_AT_WINDOW_END' if g.iloc[-1].active else 'NO_ACTIVE_STATE_AT_WINDOW_END'
  samewindow=cohort=='NEW_WINDOW_BIRTH';birthphase=str(bb.phase)
  delayed=bool(samewindow and birthphase=='PROBE' and len(con))
  firstconfirm=con.day.min() if len(con) else pd.NaT
  wait=int((g.day.gt(root)&g.day.le(firstconfirm)).sum()) if delayed else np.nan
  if samewindow and birthphase=='PROBE':
   probe_outcome='CONFIRMED_LATER_IN_WINDOW' if delayed else 'UNCONFIRMED_PRICE_FAILED' if len(failed) else 'UNCONFIRMED_PRICE_ROOT_UNKNOWN' if len(unknown) else 'UNCONFIRMED_ACTIVE_AT_WINDOW_END'
  else:probe_outcome='NOT_NEW_KNOWN_PROBE'
  rows.append(dict(window=w,sid=sid,root_day=root,cohort=cohort,birth_phase=birthphase,first_window_root_observation=first.day,entry_phase=str(first.phase),first_confirmation_known_day=confday,first_new_confirmation_in_window=firstconfirm,already_confirmed_before_window=bool(pd.notna(confday) and confday<g.day.min()),new_probe_delayed_confirmation=delayed,confirmation_wait_common_days=wait,probe_outcome_at_window_end=probe_outcome,terminal_status=terminal,terminal_day=failed.day.min() if len(failed) else unknown.day.min() if len(unknown) else g.day.max(),receipts=len(fresh),post_birth_receipts=int((fresh.day>root).sum()),confirmed_receipts=int(fresh.phase.eq('CONFIRMED').sum()),probe_receipts=int(fresh.phase.eq('PROBE').sum()),amount_unknown_receipts=int(fresh.phase.eq('PROBE_AMOUNT_UNKNOWN').sum()),became_amount_unknown_unconfirmed=bool(g.phase.eq('PROBE_AMOUNT_UNKNOWN').any()),sector=str(bb.sector)))
 r=pd.DataFrame(rows);r.to_csv(O/'ROOT_VOLUME_ROLE.csv',index=False)
 out=[]
 for (w,cohort),g in r.groupby(['window','cohort'],sort=False):
  waiting=g.loc[g.new_probe_delayed_confirmation,'confirmation_wait_common_days']
  p=g[g.birth_phase.eq('PROBE')]
  out.append(dict(window=w,cohort=cohort,roots=len(g),birth_already_confirmed=int(g.birth_phase.eq('CONFIRMED').sum()),birth_probe=int(g.birth_phase.eq('PROBE').sum()),birth_amount_unknown=int(g.birth_phase.eq('PROBE_AMOUNT_UNKNOWN').sum()),birth_already_confirmed_fraction=float(g.birth_phase.eq('CONFIRMED').mean()),new_probe_confirmed_later=int(g.new_probe_delayed_confirmation.sum()),new_probe_still_unconfirmed_active=int(g.probe_outcome_at_window_end.eq('UNCONFIRMED_ACTIVE_AT_WINDOW_END').sum()),new_probe_unconfirmed_price_failed=int(g.probe_outcome_at_window_end.eq('UNCONFIRMED_PRICE_FAILED').sum()),new_probe_unconfirmed_price_unknown=int(g.probe_outcome_at_window_end.eq('UNCONFIRMED_PRICE_ROOT_UNKNOWN').sum()),confirmation_wait_median=float(waiting.median()) if len(waiting) else None,confirmation_wait_p90=float(waiting.quantile(.9)) if len(waiting) else None,confirmation_wait_max=int(waiting.max()) if len(waiting) else None,receipts=int(g.receipts.sum()),post_birth_receipts=int(g.post_birth_receipts.sum()),confirmed_receipts=int(g.confirmed_receipts.sum()),probe_receipts=int(g.probe_receipts.sum()),amount_unknown_receipts=int(g.amount_unknown_receipts.sum()),final_price_failed=int(g.terminal_status.eq('PRICE_FAILED').sum()),final_price_unknown=int(g.terminal_status.eq('PRICE_ROOT_UNKNOWN').sum()),final_active=int(g.terminal_status.eq('ACTIVE_AT_WINDOW_END').sum())))
 summary=pd.DataFrame(out);summary.to_csv(O/'VOLUME_ROLE_SUMMARY.csv',index=False)
 r[r.sector.eq('URFI881121')&r.window.eq('2026H1')].to_csv(O/'SEMICONDUCTOR_2026_ROOT_VOLUME_ROLE.csv',index=False)
 receipts=d[d.receipt];assert len(receipts)==int(summary.receipts.sum());assert not receipts.receipt_id.duplicated().any();assert not d.duplicated(['sid','day']).any()
 for w,g in r[r.cohort.eq('NEW_WINDOW_BIRTH')].groupby('window'):
  assert len(g)==int(d.loc[d.window.eq(w),'born'].sum())
  p=g[g.birth_phase.eq('PROBE')];assert p.probe_outcome_at_window_end.ne('NOT_NEW_KNOWN_PROBE').all()
 no=pd.read_parquet(O/'NEXT_OPEN_OBSERVATIONS.parquet');nos=[]
 for w,g in no.groupby('window'):
  nos.append(dict(window=w,receipts=len(g),next_raw_price_known=int(g.next_price_valid.sum()),source_factor_match=int(g.source_factor_match.fillna(False).sum()),source_factor_mismatch_known=int((g.next_price_valid&~g.source_factor_match.fillna(True)).sum()),next_raw_price_unknown=int((~g.next_price_valid).sum()),one_price_observations=int(g.all_day_one_price.fillna(False).sum()),open_above_floor=int(g.next_open_above_signal_floor.fillna(False).sum()),outside_frozen_horizon=int(g.observation_status.eq('OUTSIDE_FROZEN_INPUT_HORIZON').sum()),fills=0))
 pd.DataFrame(nos).to_csv(O/'NEXT_OPEN_SUMMARY.csv',index=False)
 assert all(sha(O/n)==h for n,h in hashes.items())
 audit=dict(status='PASS_DESCRIPTIVE_AGGREGATION',input_hashes=hashes,script_sha256=sha(Path(__file__)),new_probe_outcomes_exhaustive=True,receipt_ids_unique=True,stock_days_unique=True,upstream_market_not_recomputed=True,windows_right_censored=True,carry_cohort_separate=True,no_accounts_or_returns=True)
 (O/'VOLUME_ROLE_QA.json').write_text(json.dumps(audit,indent=2))
 print(summary.to_string(index=False));print(pd.DataFrame(nos).to_string(index=False))
if __name__=='__main__':main()
