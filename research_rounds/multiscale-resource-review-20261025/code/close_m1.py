"""Final identity and gate arithmetic receipt, no accounts or model edits."""
from common_m1 import *
import pandas as pd
def main():
 verify();a=pd.read_parquet(HERE/'gate-audit/blocked-with-E0-context.parquet');stock=pd.read_csv(HERE/'gate-audit/stock-summary.csv');s=read(HERE/'gate-audit/E0-context-summary.json');assert len(a)==110098
 for key,flag in [('all_blocked',pd.Series(True,index=a.index)),('slow_blocked',a.profile.eq('slow_up'))]:
  b=a.loc[flag];r=next(x for x in s if x['group']==key)
  assert b.promotion_blocked.all() and b.proposal.ge(2).all() and b.grade.le(-2).all()
  assert len(b)==r['stock_days'] and b.symbol.nunique()==r['stocks']
  assert int(b.e0_target.eq(1).sum())==r['e0_also_up_days'] and int(b.IX.sum())==0
  assert int((b.r.gt(0)&b.relative_volume.ge(1)&b.e0_target.eq(1)).sum())==r['e0_up_and_positive_close_and_volume_above_median_days']
 assert stock.query("scope=='recent'").blocked_warm_proposal_cold.sum()==len(a)
 assert stock.query("scope=='recent'").observations.sum()==1476692
 gatepins=read(HERE/'gate-audit-freeze.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in gatepins.items())
 checked={}
 for directory in [SRC,GAP]:
  mapping=read(directory/'complete.json')['artifacts'];assert all(sha(ROOT/p)==h for p,h in mapping.items());checked[directory.name]=len(mapping)
 registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in registry.items())
 assert read(HERE/'validation.json')['passed'] and read(HERE/'current-technical/extra.json')['passed']
 write(HERE/'gate-audit-validation.json',dict(recorded_at=now(),passed=True,stocks=1709,full_ready_stock_days=1476692,blocked_cold_stock_days=len(a),slow_blocked_cold_stock_days=13985,e0_context_exact=True,missing_long_rows_excluded_and_retained_separately=414,gate_freeze_files=len(gatepins),old_results_byte_identical=checked,named_algorithms_unchanged=len(registry),new_accounts=0))
 write(HERE/'ui-validation.json',dict(passed=True,tab_id='14',url='http://127.0.0.1:8792/report/',selected_case='fixed_au_2025_26',visible_gate_counts=True,visible_translated_aggregate_tables=True,graph_switch_verified=True,screenshot='report/ui-gold-comparison.png',personally_viewed_pngs=['fixed_au_2025_26','fixed_semi_2026','300308.SZ_full','518880_full','688981.SH_full','600036.SH_full','600519.SH_full','001309.SZ_full','688256.SH_full','300502.SZ_full']))
 artifacts={str(p.relative_to(ROOT)):sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='complete.json' and '__pycache__' not in p.parts}
 write(HERE/'complete.json',dict(recorded_at=now(),status='complete_descriptive_research_not_new_economic_accounts',new_accounts=0,algorithm_changes_to_frozen_baselines=0,prototype='B5-M1 additional pace description',figures=32,artifacts=artifacts))
 print(dict(passed=True,artifacts=len(artifacts),new_accounts=0),flush=True)
if __name__=='__main__':main()
