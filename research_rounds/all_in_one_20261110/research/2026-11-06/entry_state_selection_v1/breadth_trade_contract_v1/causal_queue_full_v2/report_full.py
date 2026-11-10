from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;V=O.parent;Z=O/'rounds';NAV=1200000
z=pd.read_csv(Z/'ALL_SHADOW_ROUNDS.csv');c=pd.read_csv(O/'ALL_CANDIDATES_CLOSE_CHECKS.csv');e=pd.read_csv(V/'ALL_EVENTS.csv');keys=['window','arm','event_type']
for df in [z,c,e]:
 for key in keys:df[key]=df[key].astype(str)
rows=[];addreasons=[]
for key,events in e.groupby(keys):
 keep=lambda a:a[(a.window==key[0])&(a.arm==key[1])&(a.event_type==key[2])]
 cc=keep(c);g=keep(z);entry=g[g.entry_status.eq('CONDITIONAL_OPEN_PROXY')];closed=entry[entry.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];opened=entry[entry.status.eq('OPEN_CENSORED_AT_2026_06_30')];unknown=entry[~entry.index.isin(closed.index|opened.index)] if False else entry[~entry.status.isin(['COMPLETE_CONDITIONAL_STOCK_ROUND','OPEN_CENSORED_AT_2026_06_30'])]
 win=closed[closed.net_pnl.gt(0)];loss=closed[closed.net_pnl.lt(0)];big=closed[closed.net_return_on_buy_cash.ge(.3)]
 d=dict(zip(keys,key));d.update(events=len(events),right3_candidate_rows=len(cc),I_valid_rows=int(cc.I_valid.sum()),close_price_size_proxy_pass=int(cc.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE').sum()),selected_at_close=len(g),conditional_next_open_entry=len(entry),next_open_not_entered=len(g)-len(entry),closed=len(closed),open_censored=len(opened),path_unknown=len(unknown),closed_wins=len(win),closed_losses=len(loss),closed_win_fraction=len(win)/len(closed) if len(closed) else np.nan,average_win_cny=win.net_pnl.mean(),average_loss_cny=loss.net_pnl.mean(),average_win_loss_cny_ratio=win.net_pnl.mean()/(-loss.net_pnl.mean()) if len(win) and len(loss) else np.nan,average_win_return=win.net_return_on_buy_cash.mean(),average_loss_return=loss.net_return_on_buy_cash.mean(),largest_loss_cny=loss.net_pnl.min(),largest_loss_reference_NAV_fraction=loss.net_pnl.min()/NAV,p95_loss_cny=-loss.net_pnl.quantile(.05) if len(loss) else np.nan,loss_beyond3000=int(loss.net_pnl.lt(-3000).sum()),hypothetical_loss_sum_NOT_ACCOUNT=loss.net_pnl.sum(),ever_net_profitable=int(entry.profitable_close_days.gt(0).sum()),ever_profit_fresh_CP=int(entry.positive_CP_close_days.gt(0).sum()),ever_qualified_add=int(entry.qualifying_CP_close_days.gt(0).sum()),ever_add_open_attempt=int(entry.add_open_attempts.gt(0).sum()),actual_adds_rounds=int(entry['adds'].gt(0).sum()),stock_rounds_minimum_or_remaining_risk_rejected=int(entry.add_minimum_budget_or_risk_reject.gt(0).sum()),stock_rounds_open_profit_or_floor_rejected=int(entry.add_open_profit_or_floor_reject.gt(0).sum()),closed_netreturn_ge30pct=len(big),closed_netreturn_ge30pct_added=int(big['adds'].gt(0).sum()),closed_ge30pct_mean_entry_NAV_fraction=(big.entry_gross/NAV).mean(),closed_ge30pct_mean_peak_mark_NAV_fraction=big.max_inventory_reference_fraction.mean(),conditional_open_mark_net_sum_NOT_ACCOUNT=opened.conditional_liquidation_net_pnl.sum(),next_open_reasons=json.dumps(g[~g.index.isin(entry.index)].status.value_counts().to_dict()),unknown_reasons=json.dumps(unknown.status.value_counts().to_dict()))
 rows.append(d)
 for r in entry.itertuples():
  if r.adds>0:why='ADDED'
  elif r.profitable_close_days==0:why='NEVER_NET_PROFIT'
  elif r.positive_CP_close_days==0:why='PROFIT_BUT_NO_POSITIVE_FRESH_CP'
  elif r.qualifying_CP_close_days==0:why='POSITIVE_FRESH_BUT_INDUSTRY_OR_FLOOR_NOT_QUALIFIED'
  elif r.add_open_attempts==0:why='NEXT_DAY_UNKNOWN_OR_CENSORED'
  elif r.add_minimum_budget_or_risk_reject>0 and r.add_open_profit_or_floor_reject>0:why='MIXED_OPEN_AND_SIZE_REJECTIONS'
  elif r.add_minimum_budget_or_risk_reject>0:why='MINIMUM_LOT_REMAINING_RISK_OR_CAPITAL'
  elif r.add_open_profit_or_floor_reject>0:why='NEXT_OPEN_PROFIT_OR_FLOOR_REJECT'
  else:why='OTHER_PENDING'
  addreasons.append(dict(event_id=r.event_id,sid=r.sid,window=r.window,arm=r.arm,event_type=r.event_type,reason=why))
assert sum(r['right3_candidate_rows'] for r in rows)==len(c);assert sum(r['selected_at_close'] for r in rows)==len(z)
pd.DataFrame(rows).to_csv(O/'FULL_FUNNEL_AND_RISK.csv',index=False);pd.DataFrame(addreasons).to_csv(O/'ADD_REASONS_EVERY_ROUND.csv',index=False);pd.DataFrame(addreasons).groupby(keys+['reason']).size().rename('n').reset_index().to_csv(O/'ADD_REASON_SUMMARY.csv',index=False)
closed=z[z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].copy();closed[closed.net_return_on_buy_cash.ge(.3)].to_csv(O/'DESCRIPTIVE_CLOSED_WINNERS_GE30PCT.csv',index=False)
z[z.window.eq('2026H1_SEMI')].to_csv(O/'ALL_2026H1_SEMI_ROUNDS.csv',index=False)
# Overlap is diagnostic. These repeated paper experiments are never summed into account NAV.
cl=closed.copy();cl.entry_day=pd.to_datetime(cl.entry_day);cl.exit_day=pd.to_datetime(cl.exit_day);ov=[]
for key,g in cl.groupby(['window','arm','sid']):
 prior=[]
 for r in g.sort_values('entry_day').itertuples():
  pairs=[p.event_id for p in prior if p.exit_day>=r.entry_day]
  if pairs:ov.append(dict(window=key[0],arm=key[1],sid=key[2],event_id=r.event_id,prior_overlapping_events='|'.join(pairs),pairs=len(pairs)))
  prior.append(r)
pd.DataFrame(ov).to_csv(O/'OVERLAPPING_SHADOW_ROUNDS.csv',index=False)
old=pd.read_csv(V/'SEALED_SELECTED.csv');ok=set(zip(old.event_id,old.sid));nk=set(zip(z.event_id,z.sid));change=dict(old_selected=len(ok),new_selected=len(nk),retained=len(ok&nk),added=len(nk-ok),removed=len(ok-nk));(O/'SELECTION_CHANGE_DIAGNOSTIC.json').write_text(json.dumps(change,indent=2)+'\n')
seal=json.load(open(O/'SELECTION_SEAL.json'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();assert all(sha(p)==h for p,h in seal['hashes'].items());assert all(sha(p)==h for p,h in seal['source_hashes'].items());assert len(z)==len(pd.read_csv(O/'SEALED_CLOSE_SELECTED.csv'))
(O/'FINAL_QA.json').write_text(json.dumps(dict(all5490_selected_evaluated=len(z)==5490,full28558_candidates_retained=len(c)==28558,selection_and_source_hashes_unchanged=True,all_branches_separate=True,actual_account_runs=0,overlapping_later_closed_rows=len(ov),overlap_pairs=sum(x['pairs'] for x in ov),capital_concurrency_simulated=False,major_winner_scope='Only net>=30% completed selected shadow rounds. Not all-universe major-event capture or all winning open trends; not a claim of35% full-strategy win rate.',loss_sum_warning='Hypothetical independent overlaps only; must not be used as account cumulative loss.',complete_utc=str(pd.Timestamp.now(tz='UTC'))),ensure_ascii=False,indent=2)+'\n');print(pd.DataFrame(rows)[keys+['events','right3_candidate_rows','I_valid_rows','selected_at_close','conditional_next_open_entry','closed','open_censored','path_unknown','closed_win_fraction','largest_loss_cny','ever_net_profitable','ever_profit_fresh_CP','ever_qualified_add','actual_adds_rounds']].to_string(index=False));print(change)
