"""Read-only reporting of the frozen full run. No policy, signal, orders, or replay."""
from campaign_engine import *
import sys

def main(stage='full'):
 out=O/stage;dest=out/'report';assert not dest.exists();dest.mkdir()
 z=pd.read_csv(out/'CAMPAIGNS.csv');attempts=pd.read_csv(out/'ATTEMPTS.csv');actions=pd.read_csv(out/'ACTIONS.csv')
 baseline=pd.read_csv(R/'cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv',dtype={'window':str},low_memory=False)
 pre=pd.read_csv(R/'first_evidence_race_preflight_v1/RACE_WITH_OLD_LABELS.csv',dtype={'window':str},low_memory=False)
 if stage=='full':assert len(z)==4086*4
 pair_rows=[]
 for window,g in z.groupby('window'):
  for left,right in [('A','B'),('B','C'),('B','D'),('A','C'),('A','D')]:
   a=g[g.arm.eq(left)&g.evidence_usable_closed].set_index('campaign_key');b=g[g.arm.eq(right)&g.evidence_usable_closed].set_index('campaign_key');ids=a.index.intersection(b.index)
   assert not a.index.duplicated().any() and not b.index.duplicated().any()
   x=a.loc[ids];y=b.loc[ids];delta=y.net-x.net
   pair_rows.append(dict(window=window,left=left,right=right,common_known_campaigns=len(ids),left_net=x.net.sum(),right_net=y.net.sum(),delta_net=delta.sum(),mean_delta=delta.mean(),left_win_rate=x.net.gt(0).mean(),right_win_rate=y.net.gt(0).mean(),worse=int(delta.lt(-1e-7).sum()),equal=int(delta.abs().le(1e-7).sum()),better=int(delta.gt(1e-7).sum()),left_winner_to_nonpositive=int((x.net.gt(0)&y.net.le(0)).sum()),left_nonpositive_to_winner=int((x.net.le(0)&y.net.gt(0)).sum()),delta_fees=(y.total_fees-x.total_fees).sum(),delta_close_holding_days=(y.holding_close_days-x.holding_close_days).sum(),delta_capital_cost_close_days=(y.capital_close_days-x.capital_close_days).sum(),left_mean_known_prefix_drawdown=x.max_drawdown_known_prefix.mean(),right_mean_known_prefix_drawdown=y.max_drawdown_known_prefix.mean()))
 pd.DataFrame(pair_rows).to_csv(dest/'PAIRWISE_COMMON_KNOWN.csv',index=False)
 first=attempts.sort_values('round_id').groupby(['baseline_round_id','policy_arm'],sort=False).head(1)
 # Numeric suffix sort is unnecessary for first: suffix |1 precedes all later positive integers.
 first=first.set_index(['baseline_round_id','policy_arm'])
 metrics=[]
 for scope in ['ARM_KNOWN','ALL_ARM_COMMON_KNOWN']:
  eligible=z[z.evidence_usable_closed] if scope=='ARM_KNOWN' else z[z.all_arm_common_known]
  for (window,arm),g in eligible.groupby(['window','arm']):
   fi=first.loc[list(zip(g.baseline_round_id,g.arm))];fw=fi[fi.net_pnl>0];fl=fi[fi.net_pnl<=0];w=g[g.net>0];loss=g[g.net<=0]
   metrics.append(dict(window=window,arm=arm,scope=scope,campaigns=len(g),first_attempt_win_rate=fi.net_pnl.gt(0).mean(),first_attempt_mean_net=fi.net_pnl.mean(),first_attempt_payoff=fw.net_pnl.mean()/-fl.net_pnl.mean() if len(fw) and len(fl) and fl.net_pnl.mean()!=0 else None,campaign_win_rate=g.net.gt(0).mean(),campaign_mean_net=g.net.mean(),campaign_net_sum=g.net.sum(),campaign_payoff=w.net.mean()/-loss.net.mean() if len(w) and len(loss) and loss.net.mean()!=0 else None,mean_attempts=g.attempts.mean(),max_attempts=g.attempts.max(),total_attempts=g.attempts.sum(),total_fees=g.total_fees.sum(),close_holding_days=g.holding_close_days.sum(),capital_cost_close_days=g.capital_close_days.sum(),mean_known_prefix_drawdown=g.max_drawdown_known_prefix.mean(),max_known_prefix_drawdown=g.max_drawdown_known_prefix.max(),mark_path_unknown=int(g.mark_path_unknown.sum()),cash_unsettled=int((~g.cash_settled).sum()),pending_receivables=g.receivable.sum()))
 pd.DataFrame(metrics).to_csv(dest/'FIRST_ATTEMPT_AND_CAMPAIGN.csv',index=False)
 coverage=[]
 for (window,arm),g in z.groupby(['window','arm']):
  aa=attempts[attempts.policy_arm.eq(arm)&attempts.window.astype(str).eq(str(window))]
  coverage.append(dict(window=window,arm=arm,original_permits=len(g),zero_filled_permits=int(g.filled_attempts.eq(0).sum()),known_root=int(g.root_known.sum()),unknown_root=int((~g.root_known).sum()),later_root_unknown=int(g.root_unknown.sum()),recovery_opportunity_unknown=int(g.recovery_opportunity_unknown.sum()),execution_closed=int(g.execution_closed.sum()),rights_coverage_unknown=int((~g.coverage_known).sum()),complete_accrual_known=int(g.evidence_usable_closed.sum()),cash_settled=int(g.cash_settled.sum()),receivable_pending=int(g.receivable_pending.sum()),known_prefix_mark_only=int(g.mark_path_unknown.sum()),unknown_attempts=int(aa.status.str.contains('UNKNOWN').sum()),censored_attempts=int(aa.status.str.contains('CENSORED').sum()),nofill_attempts=int(aa.status.str.contains('NOFILL').sum())))
 pd.DataFrame(coverage).to_csv(dest/'ALL_PERMIT_COVERAGE.csv',index=False)
 tailids=set(pre.loc[pre.evidence_usable_closed.eq(True)&pre.core_return.ge(.5)&pre.race.eq('DOWN_FIRST'),'round_id']);assert len(tailids)==19
 tails=z[z.baseline_round_id.isin(tailids)].merge(pre[['round_id','name','core_net','core_return','entry_day','exit_day','race_day']].rename(columns={'round_id':'baseline_round_id','core_net':'old_initial_net','core_return':'old_initial_return','entry_day':'old_entry_day','exit_day':'old_exit_day'}),on='baseline_round_id',validate='many_to_one')
 tails['conditionally_executed_path_net']=tails.net;tails['complete_known_campaign_net']=tails.net.where(tails.evidence_usable_closed)
 tails.to_csv(dest/'TAIL19_CAMPAIGNS.csv',index=False)
 alltailids=set(pre.loc[pre.evidence_usable_closed.eq(True)&pre.core_return.ge(.5),'round_id']);assert len(alltailids)==108
 alltails=z[z.baseline_round_id.isin(alltailids)].merge(pre[['round_id','name','core_net','core_return','entry_day','exit_day','race','race_day']].rename(columns={'round_id':'baseline_round_id','core_net':'old_initial_net','core_return':'old_initial_return','entry_day':'old_entry_day','exit_day':'old_exit_day'}),on='baseline_round_id',validate='many_to_one')
 alltails['conditionally_executed_path_net']=alltails.net;alltails['complete_known_campaign_net']=alltails.net.where(alltails.evidence_usable_closed)
 alltails.to_csv(dest/'ALL108_OLD_TAIL_CAMPAIGNS.csv',index=False)
 attempts[attempts.baseline_round_id.isin(tailids)].to_csv(dest/'TAIL19_ACTUAL_ATTEMPTS.csv',index=False)
 # All initial/no-fill/unknown permits remain in the full tables. Positive fills are never new campaign denominators.
 counts=[]
 for window,g in baseline.groupby('window'):
  c=g[g.evidence_usable_closed]
  counts.append(dict(window=window,old_permits=len(g),old_usable=len(c),old_initial_wins=int(c.core_net.gt(0).sum()),old_initial_net=c.core_net.sum()))
 pd.DataFrame(counts).to_csv(dest/'AUTHORITATIVE_OLD_INITIAL_BASELINE.csv',index=False)
 note='''# Local initial-layer campaign comparison\n\nFour independent-stock conditional arms share the original initial permits. A holds original I; B exits if DOWN wins and stays cash; C retries original A/B births; D retries original native FAST CORE/flat fresh CP, retaining actual-fill consumption and CP role protection. No additional layer and no shared account. D was added after the fixed 33-permit ABC technical sample and before the full run.\n\nAll trading ends with the same original I root. The experiment does not test continuous following across later I roots. Selling before a later rally or buying back at a higher price is not a verdict; use complete campaign net, expectancy, payoff, coverage, capital-days and drawdown.\n\nPAIRWISE_COMMON_KNOWN.csv gives A-B, B-C, B-D, A-C and A-D on their own common-known samples. FIRST_ATTEMPT_AND_CAMPAIGN.csv separates first attempt and full campaign on each arm's known and four-arm common-known sets. ALL_PERMIT_COVERAGE.csv retains no-fill, unknown, censored and unpaid rights.\n\nCapital-days mean purchase cash including fee held at each common-day close, not market-value exposure. Drawdown is local cash plus conditional net liquidation plus recognized receivable, and is only a known-prefix statistic where marks fail. It is not portfolio/account drawdown. Receivables are not spendable; closed accrual outcomes may still have unpaid claims. Conditional C/D recovery omits cross-stock top-two allocation and shared cash and may overstate executable recovery availability.\n'''
 (dest/'READOUT.md').write_text(note)
 (dest/'OUTPUT_HASHES.json').write_text(json.dumps({p.name:sha(p) for p in dest.iterdir() if p.is_file()},indent=2)+'\n')
 print(pd.DataFrame(pair_rows).to_string(index=False));print(pd.DataFrame(metrics).to_string(index=False))
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'full')
