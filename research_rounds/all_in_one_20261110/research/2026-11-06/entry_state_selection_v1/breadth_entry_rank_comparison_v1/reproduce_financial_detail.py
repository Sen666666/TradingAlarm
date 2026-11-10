from pathlib import Path
import pandas as pd
O=Path(__file__).resolve().parent
z=pd.read_csv(O/'rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False);base=pd.read_csv(O/'FULL_COMPARISON.csv');keys=['window','arm','event_type','ranking_strategy'];extra=[]
for key,g in z.groupby(keys):
 d=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];tail=d[d.net_return_on_buy_cash.ge(.3)];ordinary=d[d.net_return_on_buy_cash.lt(.3)];entry=g[g.entry_status.eq('CONDITIONAL_OPEN_PROXY')];f=entry.original_resource_screen.fillna('')
 extra.append(dict(zip(keys,key))|dict(mean_closed_net_cny=d.net_pnl.mean(),mean_closed_tail_net_cny=tail.net_pnl.mean(),mean_closed_ordinary_net_cny=ordinary.net_pnl.mean(),cash_or_reserve_rejected=int(f.str.contains('cash_or_original_10pct_reserve',regex=False).sum()),all_old_resource_necessary_screen_pass=int(f.eq('NECESSARY_SCREEN_ONLY_NOT_FULL_ADMISSION').sum()),old_resources_unknown=int(f.eq('UNKNOWN_AFTER_ACCOUNT_END').sum()),stage='INDEPENDENT_CONDITIONAL_SHADOW_NOT_ACCOUNT_ADMISSION',ACT_or_new_shared_account_not_simulated=True))
expected=base.merge(pd.DataFrame(extra),on=keys,validate='one_to_one');actual=pd.read_csv(O/'FINANCIAL_DETAIL.csv')
pd.testing.assert_frame_equal(expected,actual,check_dtype=False,rtol=1e-12,atol=1e-8)
print('42 financial detail groups independently reproduced, no outputs overwritten')
