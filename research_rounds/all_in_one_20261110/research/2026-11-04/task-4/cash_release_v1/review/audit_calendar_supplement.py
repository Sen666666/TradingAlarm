"""Independent calendar arithmetic and saved F1 unknown-label joins only."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,json,statistics,hashlib,time
import pandas as pd
O=Path(__file__).resolve().parent;C=O.parent;T=C.parent.parent/'task'
F=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
ROOTS={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair','strong':T/'pvr_pool_feasibility/runs/2025_26/pair'}
def read(p):return json.loads(Path(p).read_text())
def gz(p):
 with gzip.open(p,'rt')as f:return list(map(json.loads,f))
def table(p):
 f=pd.read_parquet(p,columns=['permit_next_open','unknown']);assert not f.permit_next_open.isna().any()
 return {str(d)[:10]:(bool(r.permit_next_open),tuple(r.unknown))for d,r in f.iterrows()}
def main():
 started=time.monotonic();globalf=table(F/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet')
 cat=read(F/'industry-coverage/run-v1/NODE_CATALOGUE.json');industries={n['sector']:table(n['daily_result_path'])for n in cat if n['domain']=='NATIVE1709'}
 rows=read(C/'ALL_MARKET_OPEN_LIQUIDITY_STOCKS.json');actual={(r['window'],r['OPEN']):r for r in rows};assert len(actual)==966
 groups=defaultdict(list);peryear={};counts=Counter()
 for w,root in ROOTS.items():
  dd=gz(root/'daily.jsonl.gz');dd=sorted(dd,key=lambda r:r['at']);dates=[r['at'][:10]for r in dd]
  with gzip.open(root/'B.json.gz','rt')as f:b=json.load(f)
  dec={r['at'][:10]:r for r in b['decisions']};buy=defaultdict(lambda:D(0));sell=defaultdict(lambda:D(0));bf=defaultdict(lambda:D(0));sf=defaultdict(lambda:D(0))
  for t in b['trades']:
   d=t['at'][:10]
   if t['side']=='buy':buy[d]+=D(t['gross_cny'])+D(t['fees_cny']);bf[d]+=D(t['fees_cny'])
   else:sell[d]+=D(t['gross_cny'])-D(t['fees_cny']);sf[d]+=D(t['fees_cny'])
  attempts=Counter(r['at'][:10]for r in gz(root/'funding.jsonl.gz')if'09:30:00'in r['at'])
  assert not attempts[dates[0]]and buy[dates[0]]==sell[dates[0]]==0
  for prev,eod in zip(dd,dd[1:]):
   d=eod['at'][:10];sd=prev['at'][:10];r=actual.pop((w,d));a=D(eod['available'])+buy[d];nav=D(dec[sd]['nav']);R=nav*D('.1')
   assert r['signal_day']==sd and r['ACT_on']==dec[sd]['on']
   for k,v in [('S0_available',a),('decision_NAV',nav),('original_extra10_buffer',R),('maximum_discussable_release_cash',min(a,R)),('actual_protection_sale_net',sell[d]),('actual_original_buy_cash',buy[d]),('original_buy_fees',bf[d]),('original_sell_fees',sf[d])]:assert D(r[k])==v,(w,d,k)
   assert r['has_original_OPEN_attempts']==bool(attempts[d])and r['original_OPEN_role_events']==attempts[d]
   assert r['S0_cash_pct_decisionNAV']==float(a/nav*100)
   assert r['maximum_discussable_release_pct_decisionNAV']==float(min(a,R)/nav*100)
   assert r['original_final_cash_pct_same_CLOSE_NAV']==float(D(eod['available'])/D(eod['nav'])*100)
   g=globalf.get(sd);assert r['F1_global_permit']==(g[0]if g else None)and r['F1_global_input_unknown']==(g is None or bool(g[1]))
   groups[w,d[:4]].append(r);counts[w]+=1
 assert not actual and counts=={'long':725,'strong':241}
 summaries={(r['window'],r['year']):r for r in read(C/'ALL_MARKET_OPEN_LIQUIDITY_SUMMARY.json')}
 for key,rs in groups.items():
  want=summaries[key];assert want['market_OPEN_days']==len(rs)
  assert want['with_original_attempts']==sum(r['has_original_OPEN_attempts']for r in rs)
  assert want['ACT_on_days']==sum(r['ACT_on']for r in rs)
  assert want['F1_global_unknown_days']==sum(r['F1_global_input_unknown']for r in rs)
  assert want['S0_cash_pct']['median']==statistics.median(r['S0_cash_pct_decisionNAV']for r in rs)
  assert want['S0_cash_pct']['mean']==statistics.mean(r['S0_cash_pct_decisionNAV']for r in rs)
  assert want['original_cash_below_extra10_days']==sum(D(r['S0_available'])<D(r['original_extra10_buffer'])for r in rs)
  peryear['|'.join(key)]={k:want[k]for k in ['market_OPEN_days','with_original_attempts','ACT_on_days','original_cash_below_extra10_days']}
 got=defaultdict(Counter);stocksets=defaultdict(set)
 for r in gz(C/'ALL_ORIGINAL_CASH_REJECTS.jsonl.gz'):
  g=globalf.get(r['signal_day']);i=industries[r['sector']].get(r['signal_day']);gu=g is None or bool(g[1]);iu=i is None or bool(i[1]);u=gu or iu
  assert r['F1_global_permit']==(g[0]if g else None)and r['F1_industry_permit']==(i[0]if i else None)
  joint=g[0]and i[0]if g is not None and i is not None else None
  assert r['F1_joint_permit']==joint
  for role in [r['role'],'all']:
   k=r['window'],r['OPEN'][:4],role;a=got[k];a['role_events']+=1;a['mature_release_criterion']+=r['original_permission_eligible'];a['F1_global_input_unknown']+=gu;a['F1_industry_input_unknown']+=iu;a['F1_any_input_unknown']+=u;a['F1_known_both_permit']+=not u and joint is True;a['F1_known_joint_cold']+=not u and joint is False;a['mature_and_F1_unknown']+=r['original_permission_eligible']and u;stocksets[k].add((r['OPEN'],r['sid']))
 for r in read(C/'F1_UNKNOWN_PRESERVATION_STRATA.json'):
  k=r['window'],r['year'],r['role'];assert r['unique_stock_OPENs']==len(stocksets[k])
  for field,v in got[k].items():assert r[field]==v,(k,field)
  assert r['role_events']==r['F1_any_input_unknown']+r['F1_known_both_permit']+r['F1_known_joint_cold']
 result=dict(status='PASS_COMPLETE_OPEN_AND_F1_UNKNOWN_SUPPLEMENT',complete_original_OPENs=966,excluded_seed_CLOSEs=2,per_window=dict(counts),per_year=peryear,full_cash_reject_F1_joins=132742,F1_unknown_role_events={w:sum(v['F1_any_input_unknown']for k,v in got.items()if k[0]==w and k[2]=='all')for w in ROOTS},unknown_not_counted_as_known_cold=True,no_new_financial_events=True,seconds=time.monotonic()-started)
 (O/'CALENDAR_AND_F1_UNKNOWN_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
