"""Matched old blocked states and uniform display window, post-freeze only."""
from common_rc1 import *
import pandas as pd
def main():
 verify();rows=[];contexts=[]
 for sid in NAMES:
  z=pd.read_parquet(HERE/'analysis'/f'{sid}-trace.parquet').loc['2023-01-01':];old=pd.read_parquet(HERE/'inputs'/sid/'G1.parquet').loc[z.index];m=pd.read_parquet(HERE/'inputs'/sid/'M1.parquet').loc[z.index]
  blocked=m.profile.eq('slow_up')&old.promotion_blocked&old.proposal.ge(2)&old.grade.le(-2);restored=blocked&z.new_grade.ge(2)
  rows.append(dict(symbol=sid,name=NAMES[sid],start=str(z.index[0].date()),end=str(z.index[-1].date()),rows=len(z),original_ix_starts=int(z.ix_entered.sum()),rc1_ix_starts=int(z.nix_entered.sum()),new_only_starts=int(z.new_only_entry.sum()),extra_qualified_days=int(z.extra_qualified.sum()),rc_only_buy_events=int(z.added_buy_event.sum()),warm_promotions_below_high=int((z.new_rc_promoted_to_warm&z.rc_below_pre_high).sum()),old_slow_blocked_cold_days=int(blocked.sum()),restored_slow_blocked_days=int(restored.sum()),remaining_slow_blocked_days=int((blocked&~restored).sum()),extra_qual_down_background=int((z.extra_qualified&z.rc_context.eq('down')).sum())))
  for dt in z.index[blocked]:
   r=z.loc[dt];contexts.append(dict(symbol=sid,date=str(dt.date()),restored=bool(restored.loc[dt]),context=r.rc_context,local_progress_over_d5=r.rc_x/r.rc_delta5,volume_credit_over_d5=r.rc_credit/r.rc_delta5,old_grade=r.old_grade,new_grade=r.new_grade))
 df=pd.DataFrame(rows);df.to_csv(HERE/'analysis/uniform2023-summary.csv',index=False);write(HERE/'analysis/uniform2023-summary.json',rows);pd.DataFrame(contexts).to_csv(HERE/'analysis/matched-slow-blocked-states.csv',index=False)
 ev=pd.read_parquet(HERE/'analysis/local-receipts.parquet');new=ev.loc[ev.date.ge('2023-01-01')&ev.added_buy_event]
 examples=new[['symbol','name','date','context','tier','below_pre_high','old_grade','new_grade','ret21','anchor_broken21','ret63','anchor_broken63']].sort_values(['date','symbol'])
 examples.to_csv(HERE/'analysis/all-added-opportunities2023.csv',index=False)
 write(HERE/'analysis/diagnosis-receipt.json',dict(recorded_at=now(),passed=True,uniform_from='2023-01-01',assets=10,matched_blocked_stock_days=len(contexts),restored_stock_days=int(df.restored_slow_blocked_days.sum()),added_opportunity_events=len(examples),new_accounts=0,no_rule_changes=True))
 print(df.to_string(index=False),flush=True);print(examples.to_string(index=False),flush=True)
if __name__=='__main__':main()
