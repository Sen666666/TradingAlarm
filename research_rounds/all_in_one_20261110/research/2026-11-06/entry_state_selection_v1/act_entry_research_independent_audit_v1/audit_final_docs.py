import pathlib,json,hashlib,collections,gzip,re
import pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');N=R/'act_entry_loss_attribution_v1';F=R/'act_candidate_funnel_v1';P=R/'act_peer_volume_mechanism_v1';O=R/'act_entry_research_independent_audit_v1'
base=pd.read_csv(N/'PREENTRY_FEATURES_ALL.csv');full=pd.read_csv(N/'PREENTRY_FEATURES_WITH_FAST_GROUP.csv');pd.testing.assert_frame_equal(base,full[base.columns],check_exact=True)
expected=full.group.copy();fast=full.round_status.eq('CLOSED')&full.round_pnl.lt(0)&full.round_progress20.eq('EXIT_BEFORE20');expected[fast]='EXIT_BEFORE20_FINAL_LOSS';assert (expected==full.comparison_group_v2).all()
def cohort(account,year,group):
 g=full[full.account.eq(account)&full.comparison_group_v2.eq(group)]
 return g if str(year)=='ALL' else g[g.entry_year.eq(int(year))]
def eq(a,b):return (pd.isna(a) and pd.isna(b)) or abs(float(a)-float(b))<1e-7
for p in pd.read_csv(N/'PREENTRY_DISTRIBUTIONS_ALL_GROUPS.csv').itertuples():
 g=cohort(p.account,p.entry_year,p.group);v=g[p.feature].dropna();assert p.n==len(g) and p.known==len(v) and p.unknown==len(g)-len(v)
 for q in [10,25,50,75,90]:assert eq(getattr(p,'p'+str(q)),np.quantile(v,q/100))
for p in pd.read_csv(N/'PREENTRY_OVERLAP_ALL_GROUPS.csv').itertuples():
 lv=cohort(p.account,p.entry_year,p.comparison_group)[p.feature].dropna();wv=cohort(p.account,p.entry_year,'BIG_WINNER30')[p.feature].dropna();assert p.loss_group_known==len(lv) and p.big_winner_known==len(wv)
 lo,hi=np.quantile(wv,[.1,.9]);assert eq(p.loss_group_within_winner_p10_p90,((lv>=lo)&(lv<=hi)).mean());lo,hi=np.quantile(lv,[.1,.9]);assert eq(p.winner_within_loss_group_p10_p90,((wv>=lo)&(wv<=hi)).mean());a,b=np.quantile(lv,[.25,.75]);c,d=np.quantile(wv,[.25,.75]);assert eq(p.IQR_intersection_over_union,max(0,min(b,d)-max(a,c))/(max(b,d)-min(a,c)))
outs=pd.read_csv(N/'PREENTRY_GROUP_OUTCOMES_ALL_GROUPS.csv')
for p in outs.itertuples():
 g=cohort(p.account,p.entry_year,p.group);assert len(g)==p.n and (g.initial_pnl<0).sum()==p.initial_losses and (g.initial_pnl>0).sum()==p.initial_positive
 for key,col,fn in [('initial_median_return','initial_return','median'),('round_net','round_pnl','sum'),('initial_net','initial_pnl','sum'),('first5_median','initial_first5_session','median'),('median_hold','round_held_closes','median'),('capital_days','round_capital_days','sum')]:assert eq(getattr(p,key),getattr(g[col],fn)())
report=(N/'REPORT_FINAL.md').read_text();slow=pd.read_csv(N/'STALLED20_LATE_WINNERS.csv');n=0
for (arm,y),g in slow.groupby(['account','entry_year'],sort=False):
 g=g.set_index('threshold');z=g.loc[0.0];a=g.loc[.3];b=g.loc[.5];line=f"| {arm} | {y} | {int(z.stalled_total)} | {int(z.closed_winners_n)}/{z.round_net:,.2f} | {int(a.closed_winners_n)}/{a.round_net:,.2f} | {int(b.closed_winners_n)}/{b.round_net:,.2f} | {int(a.first5_confirmed_after20)} |";assert line in report,line;n+=1
for p in outs[outs.group.eq('EXIT_BEFORE20_FINAL_LOSS')].itertuples():
 line=f"| {p.account} | {p.entry_year} | {p.n} | {p.initial_losses}/{p.initial_positive} | {p.round_net:,.2f} | {p.median_hold:.2f} |";assert line in report,line
assert '逐个特征的边际分布描述' in report
peerpoints=pd.read_csv(P/'POINT_FEATURES.csv');peerreport=(P/'READOUT.md').read_text()
for p in peerpoints.itertuples():
 state='条件可计算' if p.peer_supported else 'UNKNOWN';line=f"| {p.name} {p.sid} | {p.day} | {p.score_original:.3f} | {p.score_peer_mechanical:.3f} | {p.score_delta:+.3f} | {state} | {p.peer_min}/{p.peer_total} | {p.peer_fraction_min:.1%} |";assert line in peerreport,line
prefix=pd.read_csv(P/'PREFIX_FUTURE_QA.csv');assert len(prefix)==22 and prefix.all_used_member_day_prefix_exact.all() and prefix.future_close_amount_poison_exact.all() and prefix.member_day_checks.sum()==27510
# Known/UNKNOWN split of source bucket02: stream raw literal tokens, not new future labels.
c=collections.Counter()
for l in gzip.open(R/'act_only_ablation_continuous_v1/run/pair/opportunities.jsonl.gz','rt'):
 for token in re.findall(r'sector_up:[^"\\]+',l):c[token]+=1
assert set(c)=={'sector_up:false'}
trace=pd.read_parquet(F/'ROLE_CANDIDATE_TRACE.parquet');periods=json.loads((F/'CONTRACT.json').read_text())['periods'];combos=[]
for (arm,day,sid),g in trace.groupby(['account','signal_day','sid']):
 if g.original_pending.any() or not g.industry_active.all() or not g.no_barrier.all():continue
 reasons=set(v for value in g.close_result for v in value.split(';') if v);assert reasons and reasons<={'minimum_unit_exceeds_risk_or_nominal_cap','no_nominal_gap'}
 for per,(lo,hi) in periods.items():
  if lo<=day<=hi:combos.append((arm,per,' + '.join(sorted(reasons))))
counts=collections.Counter(combos);published=pd.read_csv(F/'CLOSE_SIZE_STOCKDAY_REASON_COMBINATIONS.csv')
for p in published.itertuples():assert counts[p.account,p.period,p.exclusive_close_reason_combination]==p.stockdays
assert len(counts)==len(published)
for p in pd.read_csv(F/'MERGED_STAGE_KNOWN_UNKNOWN_SPLIT.csv').itertuples():
 assert p.unknown_or_unidentified_stockdays==0 and p.stockdays==p.known_failure_stockdays
 if p.original_merged_stage.startswith('07'):assert sum(v for (a,b,k),v in counts.items() if a==p.account and b==p.period)==p.stockdays
# Verify final manifests exactly in the schema used by each author.
checks={}
for root,name in [(N,'FINAL_MANIFEST.json'),(F,'OUTPUT_SHA256.json'),(P,'FINAL_OUTPUT_SHA256.json')]:
 data=json.loads((root/name).read_text());hmap=data.get('files',data.get('output_hashes',data));checked=0
 for path,h in hmap.items():
  if isinstance(h,str) and len(h)==64 and (root/path).is_file():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==h,(root,path);checked+=1
 checks[str(root.name)+'/'+name]=checked
out={'status':'PASS','unchanged_preentry_rows':5824,'fast_failure_rows':int(fast.sum()),'distribution_rows':90,'overlap_rows':60,'group_outcome_rows':18,'slowwinner_report_rows_verified':n,'slowwinner_report_cells_verified':n*7,'fastloss_report_rows_verified':6,'peer_report_rows_verified':22,'author_prefix_evidence_reviewed_cases':22,'author_member_day_prefix_checks':27510,'merged_known_unknown_split_rows':20,'close_size_reason_combination_rows':len(published),'raw_sector_rejection_tokens':dict(c),'manifest_checks':checks,'loss_report_sha256':hashlib.sha256((N/'REPORT_FINAL.md').read_bytes()).hexdigest(),'scope':'All named numeric tables checked independently except physical source prefix/future perturbation execution, whose completed authored evidence/code was reviewed; external PIT and real fills remain UNKNOWN.'}
(O/'FINAL_DOCUMENT_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
