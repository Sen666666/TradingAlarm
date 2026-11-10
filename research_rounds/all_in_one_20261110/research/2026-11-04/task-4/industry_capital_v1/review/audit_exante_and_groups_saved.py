"""Frozen point/strata joins and every saved outcome group, no indicator/account replay."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import gzip,json,hashlib,time
R=Path(__file__).resolve().parent;I=R.parent;F=I/'features';Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt')as h:
  for s in h:yield json.loads(s)
def dec(x):return D(str(x))
t0=time.monotonic();pts={(x['window'],x['sid'],x['signal_day']):x for x in rows(F/'POINT_FEATURES.jsonl.gz')};feats={x['key']:x for x in rows(F/'EXANTE_EVENT_FEATURES.jsonl.gz')};assert len(pts)==16131 and len(feats)==8335
cnt=Counter();cov=Counter();pairs=0
for x in feats.values():
 assert x['exante_only']and not x['future_labels_read'];c=x['candidate'];assert c==pts[x['window'],x['sid'],x['signal_day']];olds=x['old_stocks'];assert len(olds)==x['old_stock_count'];assert len({p['sid']for p in olds})==len(olds)
 for o in olds:
  p=pts[x['window'],o['sid'],x['signal_day']];assert all(o[k]==v for k,v in p.items());pairs+=1
  if o['OPEN_capital_weight']is not None:assert dec(o['OPEN_capital_weight'])==dec(o['S0_shares'])*dec(o['raw_OPEN'])
 wk=bool(olds)and all(o['OPEN_capital_weight']is not None for o in olds);pk=bool(olds)and all(o['PVR_score']is not None for o in olds);total=sum((dec(o['OPEN_capital_weight'])for o in olds),Z)if wk else None
 assert wk==x['old_OPEN_weights_known']and pk==x['old_PVR_all_known']and(total==dec(x['old_total_OPEN_capital'])if total is not None else x['old_total_OPEN_capital']is None)
 mean=sum((dec(o['OPEN_capital_weight'])*dec(o['PVR_score'])for o in olds),Z)/total if wk and pk and total>0 else None;gap=dec(c['PVR_score'])-mean if c['PVR_score']is not None and mean is not None else None
 assert(mean==dec(x['old_PVR_mean_OPEN_weighted'])if mean is not None else x['old_PVR_mean_OPEN_weighted']is None);tag='no_old_inventory'if not olds else'unknown'if gap is None else'gap_ge15'if gap>=15 else'gap_0_to15'if gap>=0 else'gap_negative';assert tag==x['PVR_gap_stratum']
 known=bool(olds)and all(o['COR_weak']is not None for o in olds);weak=sum(o['COR_weak']is True for o in olds);wt='no_old_inventory'if not olds else'unknown'if not known else'none_weak'if not weak else'all_weak'if weak==len(olds)else'mixed_weak';assert weak==x['old_COR_weak_count']and wt==x['old_COR_weak_stratum'];cnt[x['window']+'|PVR|'+tag]+=1;cnt[x['window']+'|COR|'+wt]+=1;cov['new_ok']+=c['COR_new_ok']is True;cov['new_known']+=c['COR_new_known'];cov['new_any_oldweak']+=c['COR_new_ok']is True and weak>0;cov['new_all_oldweak']+=c['COR_new_ok']is True and wt=='all_weak'
s=read(F/'SUMMARY.json');assert s['counts']==dict(cnt)and len(s['prefix_checks'])==15 and all(p['exact']for p in s['prefix_checks']);assert s['no_future_labels_read']and not s['parameters_fitted'];assert cov['new_known']==8329 and cov['new_ok']==2124 and cov['new_any_oldweak']==22 and cov['new_all_oldweak']==6
joined=list(rows(I/'MATCHED_WITH_EXANTE.jsonl.gz'));assert len(joined)==8335 and len({x['key']for x in joined})==8335
original={x['key']:x for x in rows(I/'MATCHED_HOLDINGS.jsonl.gz')}
for x in joined:
 assert x['exante']==feats[x['key']];assert all(x[k]==v for k,v in original[x['key']].items())
 d=x['OPEN'];period=(d[:4]if d<'2024-09-24'else'2024_after924')if x['window']=='long'else('2026H1'if d>='2026-01-01'else'2025H2');assert x['period']==period

def dist(v):
 v=sorted(map(dec,v));n=len(v);return dict(n=n,mean=sum(v,Z)/n if n else None,median=(v[n//2]if n%2 else(v[n//2-1]+v[n//2])/2)if n else None,p10=v[int((n-1)*.1)]if n else None,p90=v[int((n-1)*.9)]if n else None,minimum=v[0]if n else None,maximum=v[-1]if n else None)
def equal(a,b):
 if a is None:return b is None
 return dec(a)==dec(b)
def check_file(name,data,fn):
 global ng
 groups=defaultdict(list)
 for x in data:groups[fn(x)].append(x)
 saved=read(I/name);assert len(saved)==len(groups)
 for z in saved:
  key=tuple(z['group'])if isinstance(z['group'],list)else z['group'];a=groups[key];known=[x for x in a if x['matched_status']=='known_conditional_match'];assert z['events']==len(a)and z['matched']==len(known);assert Counter(z['quadrants'])==Counter(x['quadrant']for x in known);assert Counter(z['unmatched'])==Counter(x['matched_status']for x in a if x['matched_status']!='known_conditional_match')
  fields=[('new_net_return_pct',[x['new_net_return_pct']for x in known]),('old_net_return_pct',[x['old_all']['old_net_return_from_current_gross_mark_pct']for x in known]),('equal_cash_gap',[x['equal_cash_gap']for x in known]),('required_relief_scenario_gap',[x['release_adjusted_conditional_gap']for x in known if x.get('release_adjusted_conditional_gap')is not None])]
  for k,v in fields:
   e=dist(v);assert z[k]['n']==e['n']
   for metric in e:
    if metric!='n':assert equal(z[k][metric],e[metric]),(name,key,k,metric,z[k][metric],e[metric])
  assert z['required_relief_scenario_gap_positive']==sum(dec(x['release_adjusted_conditional_gap'])>0 for x in known if x.get('release_adjusted_conditional_gap')is not None);assert z['matched_not_ruled_out_by_capital_bound']==sum(bool(x.get('not_ruled_out_by_capital_bound'))for x in known)
 ng+=len(saved)
pure=[x for x in joined if x['classification']in ['sector_capital_only','both_sector_only']];ng=0
checks=[('FOUR_QUADRANT_BY_WINDOW.json',joined,lambda r:r['window']),('FOUR_QUADRANT_BY_OPEN_COHORT.json',joined,lambda r:(r['window'],r['period'])),('FOUR_QUADRANT_PURE_INDUSTRY.json',pure,lambda r:(r['window'],r['classification'])),('SEMICONDUCTOR_FOUR_QUADRANTS.json',[r for r in joined if r['semiconductor126']],lambda r:(r['window'],r['period'])),('EXANTE_PVR_gap_OUTCOMES.json',joined,lambda r:(r['window'],r['exante']['PVR_gap_stratum'])),('EXANTE_old_COR_weak_OUTCOMES.json',joined,lambda r:(r['window'],r['exante']['old_COR_weak_stratum'])),('EXANTE_candidate_COR_new_and_any_old_weak_OUTCOMES.json',joined,lambda r:(r['window'],'yes'if r['exante']['candidate']['COR_new_ok']is True and r['exante']['old_COR_weak_count']>0 else'no_or_unknown')),('EXANTE_original_lock_OUTCOMES.json',joined,lambda r:(r['window'],'prior_exit_lock'if r['exante']['old_prior_CLOSE_exit_lock_stock_count']else'no_prior_stock_exit_lock')),('EXANTE_capital_bound_OUTCOMES.json',joined,lambda r:(r['window'],'not_ruled_out'if r.get('not_ruled_out_by_capital_bound')else'ruled_out_or_unknown'))]
for name,data,fn in checks:check_file(name,data,fn)
wins=[x for x in pure if x['matched_status']=='known_conditional_match'and x['quadrant']=='new_profit_old_loss'];saved=read(I/'PURE_INDUSTRY_NEW_PROFIT_OLD_LOSS_ALL.json');assert {x['key']for x in wins}=={x['key']for x in saved}and len(wins)==15
res={'passed':True,'scope':'Static causal feature-source review plus complete saved point/strata joins, all fixed outcome groups and distributions. No new indicator calculation, model fit, mark, ledger or policy.','events':8335,'points':16131,'old_stock_event_pairs':pairs,'frozen_thresholds':['PVR candidate-minus-weighted-old gap>=15,0..15,<0,unknown','Original COR pure evidence projection, not full RS-gap10/age/weekly/portfolio strategy.','No future labels/files read by build_exante_features; only CLOSE facts/scores/raw amount and currentOPEN capital weights.'],'producer_physical_prefixes_checked_as_saved':15,'new_COR_known':cov['new_known'],'new_COR_ok':cov['new_ok'],'new_COR_and_any_oldweak':cov['new_any_oldweak'],'new_COR_and_all_oldweak':cov['new_all_oldweak'],'summary_files_checked':len(checks),'complete_summary_groups_and_all_statistics_exact':ng,'pure_industry_events':len(pure),'pure_industry_known':sum(x['matched_status']=='known_conditional_match'for x in pure),'pure_new_profit_old_loss':len(wins),'pure_new_profit_old_loss_not_capital_excluded':sum(bool(x.get('not_ruled_out_by_capital_bound'))for x in wins),'pure_new_profit_old_loss_old_weak_counts':dict(Counter(x['exante']['old_COR_weak_count']for x in wins)),'pure15_old_weak_strata':dict(Counter(x['exante']['old_COR_weak_stratum']for x in wins)),'pure15_PVR_gap_ge15':sum(x['exante']['PVR_gap_stratum']=='gap_ge15'for x in wins),'pure15_PVR_gap_ge15_and_not_capital_excluded':sum(x['exante']['PVR_gap_stratum']=='gap_ge15'and x.get('not_ruled_out_by_capital_bound',False)for x in wins),'limits':['COR indicator numeric values and15prefix outputs are existing producer calculations; this review did not rerun full indicators.','Only descriptive development strata, not train/test/OOS or a new profitable rotation rule.','OPEN entry cohort is not calendar-period portfolio wealth; year2024 subgroup before924 is partial-year, not full2024.','Whole-basket weak vs any individualweak are distinct; unknown retained.','Capital-bound survivors still may fail cash/risk/locks/FIFO/stock/real execution and do not establish net portfolio gains.'],'new_reviewer_accounts':0,'new_reviewer_marks':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),F/'build_exante_features.py',F/'EXANTE_EVENT_FEATURES.jsonl.gz',F/'POINT_FEATURES.jsonl.gz',F/'SUMMARY.json',I/'EXANTE_DIAGNOSTIC_STRATA.txt',I/'summarize_opportunity_cost.py',I/'MATCHED_WITH_EXANTE.jsonl.gz']},'seconds':time.monotonic()-t0}
(R/'EXANTE_AND_OUTCOME_GROUPS_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k not in ['source_sha256','limits','frozen_thresholds']},indent=2))
