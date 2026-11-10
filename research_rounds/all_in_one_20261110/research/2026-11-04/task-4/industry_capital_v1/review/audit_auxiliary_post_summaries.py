"""All remaining descriptive post-join groups, no indicators, prices or accounts."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from datetime import date
import gzip,json,hashlib,time
R=Path(__file__).resolve().parent;I=R.parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt')as h:
  for s in h:yield json.loads(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dist(v,short=True):
 a=sorted(D(str(x))for x in v);n=len(a);return dict(n=n,mean=sum(a,Z)/n if n else None,median=(a[n//2]if n%2 else(a[n//2-1]+a[n//2])/2)if n else None,p10=a[int((n-1)*.1)]if n else None,p90=a[int((n-1)*.9)]if n else None,min=a[0]if n else None,max=a[-1]if n else None)
def eq(a,b):
 if b is None:return a is None
 return D(str(a))==b if isinstance(b,D)else a==b
t0=time.monotonic();a=list(rows(I/'MATCHED_WITH_EXANTE.jsonl.gz'));assert len(a)==8335
quotes={r['key']:r['original_OPEN_contract_preview']for r in rows(I/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz')if r['is_first_sector_reject_in_original_source_I_epoch']};batches=[];co=defaultdict(Counter);values=defaultdict(lambda:defaultdict(list))
for r in a:
 k=r['window'],r['period'];co[k]['first_events']+=1;co[k][r['new']['status']]+=1;q=quotes[r['key']];values[k]['minimum_buy_cash'].append(q['dated_minimum_cash']);values[k]['frozen_preview_max_gross'].append(q['OPEN_preview_max_gross']);n=r['new']
 if n['known_net']:
  values[k]['candidate_net_return_pct'].append(n['net_return_pct']);values[k]['candidate_net_PnL_at_minimum_unit'].append(n['net_liquidation_profit']);values[k]['holding_calendar_days'].append((date.fromisoformat(n['horizon_CLOSE_day'])-date.fromisoformat(n['OPEN'])).days)
 b=r.get('same_batch_filled_alternatives',{})
 if b.get('status')=='actual_committed_new_fills_Tplus1_not_rotation_donors'and n['known_net']:
  nr=D(n['net_return_pct']);orr=D(b['net_return_from_actual_buy_cash_pct']);qu='zero_boundary'if nr==0 or orr==0 else('new_profit'if nr>0 else'new_loss')+'_'+('old_profit'if orr>0 else'old_loss');batches.append(dict(key=r['key'],window=r['window'],OPEN_cohort=r['period'],new_net_return_pct=nr,committed_net_return_pct=orr,quadrant=qu,can_sell_committed_at_that_OPEN=False))
saved=read(I/'CANDIDATE_NET_AND_AMOUNT_DISTRIBUTIONS.json');assert len(saved)==len(co)
for z in saved:
 k=z['window'],z['OPEN_cohort'];assert z['counts']==dict(co[k])
 for name,v in values[k].items():
  d=dist(v);assert all(eq(z['distributions'][name][metric],value)for metric,value in d.items())
sb=read(I/'SAME_BATCH_ACTUAL_FILL_COMPARISON.json');assert len(sb)==len(batches)
for s,b in zip(sb,batches):assert all(eq(s[k],v)for k,v in b.items())
for x in read(I/'SAME_BATCH_SUMMARY.json'):
 b=[r for r in batches if r['window']==x['window']];assert x['events']==len(b)and Counter(x['quadrants'])==Counter(r['quadrant']for r in b)
 for name,field in [('candidate_return','new_net_return_pct'),('committed_return','committed_net_return_pct')]:assert all(eq(x[name][k],v)for k,v in dist([r[field]for r in b]).items())
pure=[r for r in a if r['matched_status']=='known_conditional_match'and r['classification']in ['sector_capital_only','both_sector_only']];examplekeys=[]
for quad in ['new_profit_old_profit','new_profit_old_loss','new_loss_old_profit','new_loss_old_loss']:
 v=[r for r in pure if r['quadrant']==quad and r.get('not_ruled_out_by_capital_bound')and r.get('release_adjusted_conditional_gap')is not None];v.sort(key=lambda r:D(r['release_adjusted_conditional_gap']))
 if v:examplekeys.extend([v[0]['key'],v[-1]['key']]if len(v)>1 else[v[0]['key']])
examples=read(I/'BALANCED_EXAMPLES.json');assert [x['key']for x in examples]==examplekeys and all('Posthoc'in x['display_selection']for x in examples)
res={'passed':True,'scope':'Candidate amount/return/holding-day distributions, same-batch comparison tables and all summary groups plus posthoc display-example selection. No new path/mark or parameter.','mother_events':8335,'candidate_cohort_distribution_groups':len(co),'same_batch_records':len(batches),'same_batch_counts':dict(Counter(x['window']for x in batches)),'all_saved_auxiliary_group_counts_and_distributions_exact':True,'balanced_posthoc_examples':len(examples),'same_batch_cashflow_source_limit':'Comparison-table groups/returns match saved actual-commitment baselines. This audit did not recalculate each auxiliary original buy-layer terminal mark; main old S0 baskets were fully checked separately.','display_examples_are_signals':False,'entry_cohort_not_portfolio_period_wealth':True,'new_reviewer_accounts':0,'new_reviewer_prices':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),I/'CANDIDATE_NET_AND_AMOUNT_DISTRIBUTIONS.json',I/'SAME_BATCH_ACTUAL_FILL_COMPARISON.json',I/'SAME_BATCH_SUMMARY.json',I/'BALANCED_EXAMPLES.json',I/'summarize_opportunity_cost.py']},'seconds':time.monotonic()-t0}
(R/'AUXILIARY_POST_SUMMARY_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k!='source_sha256'},indent=2))
