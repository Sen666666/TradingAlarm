"""Completed native labels: saved financial/merge identities and raw-fact exit clock.
No Account/Runner/Provider, market marks or new financial path is constructed.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from datetime import datetime
import gzip,hashlib,json,time,bisect
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;I=R.parent;P=I/'labels_new';W=I.parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lines(p):
 with gzip.open(p,'rb')as h:return list(h)
t0=time.monotonic();done=read(P/'FULL_LABEL_COMPLETE.json');freeze=read(P/'CONTINUATION_SOURCE_FREEZE.json');assert done['passed']and done['source_freeze_sha256']==sha(P/'CONTINUATION_SOURCE_FREEZE.json')
for path,s in freeze['source_sha256'].items():assert sha(path)==s
final=P/'FIRST_REJECT_SHADOW_LABELS.jsonl.gz';assert sha(final)==done['output_sha256'];raw=lines(final);old=lines(P/'FIRST_REJECT_SHADOW_LABELS.partial.jsonl.gz');assert len(raw)==8335 and len(old)==3879 and raw[:3879]==old
row=[json.loads(x)for x in raw];by={x['key']:x for x in row};assert len(by)==8335
mother={x['key']:x for x in map(json.loads,lines(I/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz'))if x['is_first_sector_reject_in_original_source_I_epoch']};assert list(by)==list(mother)and len(mother)==8335
for j in range(4):
 d=P/'remaining_shards'/f'worker{j}';comp=read(d/'COMPLETE.json');tim=read(d/'TIMING.json');assert comp['passed']and tim['failure']is None and not tim['timed_out']and tim['seconds']<=90
 f=d/'LABELS.jsonl.gz';assert sha(f)==comp['output_sha256'];assert all(rawline==raw[list(by).index(json.loads(rawline)['key'])]for rawline in lines(f))
assert done['additional_compute_seconds']<=360 and done['single_asset_shadow_paths']==8335 and done['label_attempts']==8336
statuses=Counter(x['status']for x in row);assert statuses==Counter(closed=8058,censored_open=253,entry_nonfill=24);assert Counter(x['window']for x in row)==Counter(long=5264,strong=3071)
partial=Counter();flags=Counter();bysid=defaultdict(list)
for x in row:
 e=mother[x['key']];assert x['sid']==e['sid']and x['window']==e['window']and x['source_I_epoch']==e['original_intent']['epoch'];assert x['failure_tags']==e['failure_tags']
 if x['status']=='entry_nonfill':assert not x['known_net']and x['filled_shares']==0 and D(x['entry_cash_actual'])==0;continue
 assert x['known_net']and not x['unknown_reason'];qty=int(x['filled_shares']);request=int(x['requested_shadow_shares']);assert request==e['original_OPEN_contract_preview']['dated_minimum_shares']and 0<qty<=request
 assert x['entry_partial']==(qty<request);partial['entry_partial']+=x['entry_partial'];partial['unspent_seed_positive']+=D(x['initial_seed_cash'])>D(x['entry_cash_actual'])
 b={k:D(v)for k,v in x['cash_or_receivables_balance'].items()};nav=b['available']+b['order_reserved']+b['settlement_locked']-b['payable']+b['sale_receivable']+b['dividend_receivable']+b['inventory'];assert nav==b['nav']==D(x['native_nav'])==D(x['terminal_NAV'])
 seed=D(x['initial_seed_cash']);cn=D(x['entry_cash_actual']);pnl=nav-seed;drag=D(x['terminal_liquidation_drag']);net=pnl-drag;assert pnl==D(x['net_pnl_original_ledger'])==D(x['gross_native_profit'])and net==D(x['net_liquidation_profit'])
 assert D(x['terminal_net_liquidation_estimate'])==nav-drag and D(x['wealth_from_invested_Cn_excluding_unspent_seed'])==cn+pnl and D(x['wealth_from_invested_Cn_net_liquidation'])==cn+net
 assert D(x['net_return_pct'])==net/cn*100 and D(x['actual_shadow_fees'])==b['fees_cny']and seed>=cn>0
 remaining=int(x['terminal_qty']);assert remaining==x['remaining_shares']and x['terminal_censored']==(remaining>0)
 if x['status']=='closed':assert remaining==0 and drag==0 and x['full_exit_at'][:10]==x['horizon_CLOSE_day']and datetime.fromisoformat(x['full_exit_at']).date()>datetime.fromisoformat(x['exit_proposal_at']).date()
 else:
  assert remaining>0 and x['full_exit_at']is None
  mark=D(x['terminal_mark']);px=mark*(D(1)-D('.0005'));assert b['inventory']==remaining*mark and drag==remaining*(mark-px)+D(x['estimated_terminal_sale_fee'])
 for k in ['CA_events','fractional_action_proxy_count']:flags[k]+=x[k]
 flags['derived_terminal_marks']+=bool(x['terminal_mark_derived']);flags['recognized_dividend_positive']+=D(x['dividend_net_recognized'])>0
 bysid[x['sid']].append(x)
# Independently derive all first exit-proposal days from immutable original I/source and ACT facts.
envs={}
for w in ['long','strong']:
 ds=list(map(json.loads,lines(W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair/daily.jsonl.gz')));envs[w]=([x['at'][:10]for x in ds],np.asarray([x['on']for x in ds],dtype=bool));assert envs[w][0]==sorted(envs[w][0])
sm={x['symbol']:x for x in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};clock=Counter();fact_hashes={}
for sid,xs in bysid.items():
 fp=Path(sm[sid]['refs']['facts']);actual=sha(fp);assert actual==sm[sid]['output_sha256'][str(fp)];fact_hashes[str(fp)]=actual;f=pd.read_parquet(fp,columns=['segment_id','i_target']);s=f.segment_id.to_numpy(float);it=f.i_target.to_numpy(float);cache={}
 for x in xs:
  source=x['source_I_epoch'][0];w=x['window'];key=w,source
  if key not in cache:
   days,on=envs[w];pos=f.index.searchsorted(pd.DatetimeIndex(days),side='right')-1;valid=pos>=0;seg=s[np.maximum(pos,0)];target=it[np.maximum(pos,0)];bad=(~valid)|(~np.isfinite(seg))|(seg!=source)|(~np.isfinite(target))|(target!=1)|(~on);cache[key]=[days[j]for j in np.flatnonzero(bad)]
  bad=cache[key];j=bisect.bisect_left(bad,x['OPEN']);stop=bad[j]if j<len(bad)else None;proposal=x['exit_proposal_at'][:10]if x['exit_proposal_at']else None;assert proposal==stop,(x['key'],proposal,stop)
  st=f.index.searchsorted(pd.Timestamp(x['signal_day']),side='left');en=f.index.searchsorted(pd.Timestamp(x['horizon_CLOSE_day']),side='right');assert en>st and np.isfinite(s[st:en]).all()and(s[st:en]==source).all()
  assert x['horizon_CLOSE_day']<=envs[w][0][-1]
  if x['status']=='censored_open':assert x['horizon_CLOSE_day']==envs[w][0][-1]
  if stop:assert datetime.fromisoformat(x['exit_proposal_at']).time().isoformat()=='15:10:00'
  clock[x['exit_reason']or'no_exit_proposal_by_terminal']+=1
res={'passed':True,'scope':'Complete saved8335 merge/source/financial identities and independently derived original I/ACT/source first-stop dates. No ledger or market rerun.','output_sha256':sha(final),'source_freeze_sha256':sha(P/'CONTINUATION_SOURCE_FREEZE.json'),'events':8335,'windows':dict(Counter(x['window']for x in row)),'statuses':dict(statuses),'original3879_bytes_exact':True,'worker_new4456_raw_rows_exact':True,'all_saved_financial_equations_exact':True,'all8311_filled_paths_first_stop_and_fact_source_continuity_exact':True,'fact_files_checked':len(fact_hashes),'exit_reason_counts':dict(clock),'partial_and_seed_flags':dict(partial),'CA_and_terminal_flags':dict(flags),'label_compute_seconds_original':done['original_compute_seconds'],'label_compute_seconds_additional_sum':done['additional_compute_seconds'],'total_label_compute_seconds':done['total_label_compute_seconds'],'single_asset_shadow_paths_full_labels':8335,'single_asset_calibration_paths_separate':5,'all_constructed_single_asset_paths_including_calibration':8340,'full_label_attempts':8336,'new_portfolio_policy_accounts':0,'limitations':['253 remaining positions use estimated terminal net liquidation, not actual sells;24 nonfills stay without net label.','No shared cash/risk/pool feasibility or donor action has been simulated. Fixed original ACT is a local environment assumption.','Native CA/dividend-net-factor/fractional-share/execution proxies inherited; exact saved equations do not independently reconstruct each8311 raw CA/fill event.','Event units overlap and money/profits cannot sum as a new portfolio return.'],'reviewer_new_ledger_paths':0,'reviewer_new_market_marks':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),final,P/'FULL_LABEL_COMPLETE.json',P/'CONTINUATION_SOURCE_FREEZE.json',P/'native_single_asset.py']},'independent_fact_sha256':fact_hashes,'seconds':time.monotonic()-t0}
(R/'COMPLETED_SINGLE_ASSET_LABELS_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k not in ['source_sha256','independent_fact_sha256','limitations']},indent=2))
