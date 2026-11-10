import json,sys,hashlib,csv
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import pandas as pd
sys.dont_write_bytecode=True
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');OUT=Path(__file__).parent
CODE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code');sys.path.insert(0,str(CODE))
from sector_account import FeeComponent,FeeSchedule
from market_rules import market_identity_on,version_on
hashes={}
def read(p):
 p=Path(p);hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
rules=read(CODE.parent/'inputs-v2/market-rules.json'); econ=read(CODE.parent/'inputs-v2/economic-protocol.json')
proxies=[]
# Fee schedules are the same frozen versions used by the engine. All explicit proxies in frozen manifest remain labelled proxies.
for arr in list(rules['venue_versions'].values())+list(rules['fee_versions'].values()):
 proxies += [x['proxy_id'] for x in arr if x.get('proxy_id')]
def fee(s,dt,q,p):
 if not q:return D(0)
 venue=market_identity_on(rules,s,dt,proxies)['venue'];v=version_on(rules['fee_versions'][venue],dt,proxies)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**c) for c in v['components']))
 return sum(fs.incremental('sell',D(q)*p,{}, {},1,shares=q,par_value=D(str(rules['security_metadata'][s]['par_value']))).values(),D(0))
for p in [CODE/'market_rules.py',CODE/'sector_account.py',R/'joint51_candidate_v9_facts/engine.py',R/'mainline_candidate_v3_core_reference/engine.py',R/'mainline_candidate_v8_false_mainline_retirement/engine.py']:
 hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
manifest={x['symbol']:x for x in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
cache={}
def bars(s):
 if s not in cache:
  p=Path(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet')));h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==manifest[s]['source_sha256'][str(p)];hashes[str(p)]=h;cache[s]=pd.read_parquet(p)
 return cache[s]
CASES=['000158.SZ','002261.SZ','002049.SZ','002865.SZ','002506.SZ','603806.SH','688223.SH']
paths={'M7_1031':R/'mainline_m7_downturn_cash_batch_v6/once_20241031','M7_1106':R/'mainline_m7_long_horizon_sealed_v2/once_20260630','M8_1031':R/'mainline_candidate_v8_false_mainline_retirement_run_v1/once_20241031'}
result={};all_daily=[];all_round=[];all_floor=[];timing=[]
for label,p in paths.items():
 cap=read(p/'CAPITAL_LOTS.json');hold=read(p/'HOLDINGS.json');orders=read(p/'ORDERS.json');ats=read(p/'ATTEMPTS.json');equity=read(p/'EQUITY_EVENTS.json');read(p/'DAY_LEDGER.json');read(p/'SECTOR_DAILY.json')
 end=max(x['day'] for x in cap);orders=[o for o in orders if o['day']<=end];ag={a['id']:a for a in ats};og=defaultdict(list);eg=defaultdict(list);hg=defaultdict(list);cg=defaultdict(list)
 for o in orders:og[o['round_id']].append(o)
 for e in equity:
  if e.get('round_id') and e['event']=='ACCRUE_NET80':eg[e['round_id']].append(e)
 for h in hold:hg[h['round_id'],h['day']].append(h)
 for c in cap:cg[c['round_id'],c['day']].append(c)
 daily=defaultdict(list);maxerr=D(0)
 for (rid,day),lots in sorted(cg.items()):
  c=lots[0];s=c['sid'];hs=hg[rid,day];q=sum(l['qty'] for l in hs);raw=D(c['raw_mark']);net=D(c['round_net']);assert all(D(l['round_net'])==net for l in lots)
  cash=sum((D(o['cash_delta']) for o in og[rid] if o['day']<=day),D(0));div=sum((D(e['receivable_delta']) for e in eg[rid] if e['day']<=day),D(0));base=cash+div;liq=q*raw*D('.9995')-fee(s,day,q,raw*D('.9995'));err=net-(base+liq);maxerr=max(maxerr,abs(err));assert abs(err)<D('.000001'),(label,rid,day,err)
  groups=defaultdict(int);floor_lot=[]
  for h in hs:
   fl=D(h['protection_signal'])/D(h['factor']);groups[fl]+=h['qty'];px=fl*D('.9995');floor_lot.append(h['qty']*px-fee(s,day,h['qty'],px))
   all_floor.append(dict(run=label,round_id=rid,day=day,sid=s,lot_id=h['lot_id'],kind=h['kind'],qty=h['qty'],raw_close=raw,adjustment_factor=h['factor'],protection_signal=h['protection_signal'],protection_raw=fl,cp_id=h['cp_id'],locked_exit=h['locked_exit']))
  grouped=sum((qf*fl*D('.9995')-fee(s,day,qf,fl*D('.9995')) for fl,qf in groups.items()),D(0))
  row=dict(run=label,round_id=rid,sid=s,day=day,qty=q,raw_close=raw,net=net,cumulative_cashflow=cash,dividend_accrued=div,floor_proxy_grouped=base+grouped,floor_proxy_per_lot=base+sum(floor_lot,D(0)),floor_raw_min=min(groups),floor_raw_max=max(groups),sector_state=c['sector_state'],M=c['M'],stock_state=c['stock_state'],expansion_qty=sum(l['qty'] for l in lots if l.get('capital_role')=='EXPANSION'))
  row['triple_bad']=c['sector_state']==0 and c['M']==0 and c['stock_state']==0 and net<=0
  daily[rid].append(row);all_daily.append(row)
 rounds=[]
 for rid,ds in daily.items():
  a=ag[rid];s=a['sid'];peak=max(ds,key=lambda d:d['net']);last=ds[-1];final=a['final_qty'];endnet=D(a['marked_net_pnl']) if final==0 else last['net'];marked=D(a['marked_net_pnl']);trough=min((d for d in ds if d['day']>=peak['day']),key=lambda d:d['net']);min_after=min(trough['net'],endnet)
  row=dict(run=label,round_id=rid,sid=s,name=next((o['name'] for o in og[rid]),s),seed_day=a['seed_day'],peak_day=peak['day'],peak_net=peak['net'],peak_raw_close=peak['raw_close'],peak_qty=peak['qty'],peak_floor_net=peak['floor_proxy_grouped'],last_close_day=last['day'],exit_day=a.get('exit_day'),exit_reason=a['exit'],final_qty=final,final_net=endnet,attempt_marked_net=marked,giveback=peak['net']-endnet,giveback_pct=(peak['net']-endnet)/peak['net']*100 if peak['net']>0 else None,minimum_net_after_peak=min_after,max_giveback=peak['net']-min_after,last_floor_net=last['floor_proxy_grouped'],last_raw_close=last['raw_close'],last_floor_raw_min=last['floor_raw_min'],last_floor_raw_max=last['floor_raw_max'],positive_peak_preserved_at_peak_floor=peak['floor_proxy_grouped']>0)
  rounds.append(row);all_round.append(row)
  if s in CASES or (label=='M7_1031' and s=='300085.SZ'):
   bb=bars(s)
   for i,d in enumerate(ds):
    if '2024-10-08'<=d['day']<='2024-10-14':
     ix=bb.index.get_loc(pd.Timestamp(d['day']));n=bb.iloc[ix+1];nd=str(bb.index[ix+1].date());nopen=D(str(n.raw_open));valid=bool(n.observed_bar and n.price_eligible and not n.source_invalid and not n.synthetic_event_bar)
     t=dict(d);t.update(next_day=nd,next_raw_open=nopen,next_open_vs_close_pct=(nopen/d['raw_close']-1)*100,next_quote_valid=valid,two_consecutive_bad=(i>0 and d['triple_bad'] and ds[i-1]['triple_bad']),next_open_fixed_inventory_net=d['cumulative_cashflow']+d['dividend_accrued']+d['qty']*nopen*D('.9995')-fee(s,nd,d['qty'],nopen*D('.9995')))
     timing.append(t)
 rounds.sort(key=lambda x:x['peak_net'],reverse=True)
 result[label]=dict(certified_through=end,total_rounds_with_close=len(rounds),cashflow_reconciliation_max_error=maxerr,top20=rounds[:20],cases=[x for x in rounds if x['sid'] in CASES],all_rounds_ranked=rounds)
result['caveats']=['MFE仅指实际持仓路径有持仓收盘日的最高round_net，不含盘中高点，也不含卖出后虚构持仓。未持到收盘的轮次不会进入此排名。','round_net=累计订单现金流+已计提净80%现金股息+存量股数×原始收盘×(1-0.0005)-继承费用；全部轮日独立重算校验。','期末零股数采用实际现金流+股息 realized marked_net_pnl；期末仍持仓采用最后认证收盘 round_net，另列不扣假设卖出成本的 ATTEMPTS.marked_net_pnl。','I/CP保护信号为复权坐标；raw_floor=protection_signal/factor。floor_proxy是假定每层以当前已知 floor×(1-slip)卖出的静态压力测试，并非可成交价或止损保证。不同层保护触发不同日期，未来factor/股息/持仓均可能变化。按相同floor合单费用和逐lot费用同时列出。','次OPEN固定库存净值只描述隔夜价格暴露，不代表M9订单，不重新分配资金，不模拟退出；需要行情有效、权益未变等才能用于对照。','M7_1106文件虽名once_20260630，认证仅到2024-11-06；未引用11/7不完整交易。M9不在本诊断中运行或调参。','退出后没有CAPITAL_LOTS，无法用这些文件观察原轮次第二个坏收盘；只能列已有实际持仓快照，不补造M9状态。']
result['hashes']=hashes
(OUT/'DIAGNOSTIC.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
for name,rows in [('ROUND_RANKING',all_round),('ROUND_DAILY',all_daily),('LOT_PROTECTIONS',all_floor),('OCTOBER_DETECTION',timing)]:
 with (OUT/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({k:{'top10':v['top20'][:10],'cases':v['cases'],'reconciliation':v['cashflow_reconciliation_max_error']} for k,v in result.items() if k in paths},ensure_ascii=False,default=str))
