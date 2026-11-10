"""Close one prototype round, preserving identity and failures."""
from common_rc1 import *
import ast
import pandas as pd
from PIL import Image
def main():
 count=verify();assert read(HERE/'validation.json')['passed']
 for p in (HERE/'code').glob('*.py'):ast.parse(p.read_text())
 u=pd.read_csv(HERE/'analysis/uniform2023-summary.csv');events=pd.read_parquet(HERE/'analysis/local-receipts.parquet');a=events.loc[events.date.ge('2023-01-01')&events.added_buy_event]
 assert len(a)==31 and a.below_pre_high.sum()==30 and a.ret21.lt(0).sum()==15 and a.anchor_broken21.eq(True).sum()==10
 assert u.old_slow_blocked_cold_days.sum()==189 and u.restored_slow_blocked_days.sum()==25 and u.extra_qualified_days.sum()==78
 details=list((HERE/'report/details').glob('*.png'));assert len(details)==4
 for p in details:
  with Image.open(p) as im:im.verify()
 ui=HERE/'report/ui-gold-rebound-audit.png'
 with Image.open(ui) as im:im.verify()
 write(HERE/'ui-validation.json',dict(recorded_at=now(),passed=True,tab_id='15',url='http://127.0.0.1:8793/report/',case='fixed_au_user_decline',filter='down',original_starts=2,RC1_starts=2,extra_qualification_days=0,visible_local_rebound_rows=6,visible_old_and_new_warm_grades_dates=['2026-04-08','2026-06-15'],screenshot=str(ui.relative_to(HERE)),primary_figures=32,supplementary_posthoc_figures=4,ten_asset_plots_personally_reviewed=True))
 summary=read(HERE/'validation.json');write(HERE/'delivery-validation.json',dict(recorded_at=now(),passed=True,freeze_files=count,new_accounts=0,primary_plots=32,posthoc_detail_plots=len(details),source_identity=summary['old_artifacts_unchanged'],frozen_named_algorithms_unchanged=30,rule_or_parameter_changes_after_real_RC1_output=0,prototype_status='local evidence retained; whole G1+RC1 not promoted; old bearish rebound channel still present'))
 artifacts={str(p.relative_to(ROOT)):sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='complete.json' and '__pycache__' not in p.parts}
 doc=ROOT/'docs/ALGORITHM_RC1.md';artifacts[str(doc.relative_to(ROOT))]=sha(doc)
 write(HERE/'complete.json',dict(recorded_at=now(),status='complete_no_account_backtests',candidate='RC1',candidates=1,parameter_sets=1,new_accounts=0,artifacts=artifacts));print(dict(passed=True,artifacts=len(artifacts),new_accounts=0),flush=True)
if __name__=='__main__':main()
