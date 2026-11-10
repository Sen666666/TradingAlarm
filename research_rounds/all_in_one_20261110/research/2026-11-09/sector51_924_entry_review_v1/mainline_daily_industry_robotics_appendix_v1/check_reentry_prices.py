from pathlib import Path
import json,csv,hashlib,math
import pandas as pd
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=R/'mainline_daily_industry_robotics_appendix_v1';OLD=R/'mainline_daily_industry_evidence_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rd(p):return json.loads(Path(p).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def bt(x):return int(x) if isinstance(x,(bool,np.bool_)) else -1
def finite(x):
 try:return x is not None and math.isfinite(float(x))
 except:return False
def lin(r):
 v=[r.get(k) for k in ['source_kind','source_path','segment_id']]
 return tuple(str(x) for x in v) if all(pd.notna(x) and str(x).strip().lower() not in ('','none','null','nan','na','unknown') for x in v) else None
def px(r):
 if not all(bt(r.get(k))==1 for k in ['observed_bar','price_eligible','volume_eligible']) or not all(bt(r.get(k))==0 for k in ['source_invalid','synthetic_event_bar']):return None
 if not all(finite(r.get(k)) and r[k]>0 for k in ['raw_open','adjustment_factor']) or lin(r) is None:return None
 return float(r.raw_open)*float(r.adjustment_factor)
mp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in rd(mp)}
final=rd(O/'WAIT_TICKET_AT_RECOVERY.json');alive=[x for x in final if x['eligible_for_industry_plus_original_price_state_reexamination']]
life=rd(O/'WAIT_TICKET_LIFECYCLE.json');hashes=rd(O/'WAIT_SOURCE_HASHES.json');hashes[str(mp)]=sha(mp)
out=[]
for x in alive:
 sid=x['sid'];m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));assert sha(p)==m['source_sha256'][p];hashes[p]=sha(p)
 z=pd.read_parquet(p);a=z.loc['2024-12-05'] if pd.Timestamp('2024-12-05') in z.index else pd.Series(dtype=object);b=z.loc['2024-12-11'] if pd.Timestamp('2024-12-11') in z.index else pd.Series(dtype=object)
 p0=px(a);p1=px(b);same=lin(a) is not None and lin(a)==lin(b)
 floor=next(y['I_floor'] for y in life if y['sid']==sid and y['day']=='2024-12-10' and y['phase']=='CLOSE')
 out.append(dict(round_id=x['round_id'],sid=sid,name=x['name'],original_OPEN='2024-12-05',industry_only_earliest_recheck_OPEN='2024-12-11',
  original_raw_open=float(a.raw_open) if p0 is not None else None,original_adjustment_factor=float(a.adjustment_factor) if p0 is not None else None,original_adjusted_OPEN=p0,
  recheck_raw_open=float(b.raw_open) if p1 is not None else None,recheck_adjustment_factor=float(b.adjustment_factor) if p1 is not None else None,recheck_adjusted_OPEN=p1,
  source_lineage_same=same,price_status='KNOWN_COMPARABLE' if p0 is not None and p1 is not None and same else 'UNKNOWN_OR_SOURCE_CHANGED',
  adjusted_OPEN_change_pct=100*(p1/p0-1) if p0 is not None and p1 is not None and same else None,
  I_floor_at_1210_CLOSE=floor,recheck_OPEN_above_known_I=(p1>floor) if p1 is not None and floor is not None else None,
  unknown_or_missing_quote=(p0 is None or p1 is None),not_fee_slippage_adjusted=True,no_execution_or_portfolio_return_claim=True))
assert len(out)==8
save('WAIT_REENTRY_OPEN_PRICE_COMPARISON',out);save('WAIT_SOURCE_HASHES',hashes)
lines=['# 机器人仍活8票：等待后的同口径OPEN价格','',
'只比较原12/5 OPEN与行业G恢复后最早可重审12/11 OPEN的已保存raw_open×adjustment_factor。不是原实际含滑点成交价，不含费用、容量、最小量和可执行性，不是候选收益。两个已于12/6 stock=false取消的原票不放入可重审组。','',
'| 股票 | 12/5调整OPEN | 12/11调整OPEN | 等待后价差 | 报价/源状态 | 12/11 OPEN高于12/10原I线 |',
'|---|---:|---:|---:|---|---|']
for x in out:lines.append(f"| {x['name']} / {x['sid']} | {x['original_adjusted_OPEN']:.6f} | {x['recheck_adjusted_OPEN']:.6f} | {x['adjusted_OPEN_change_pct']:+.2f}% | {x['price_status']} | {x['recheck_OPEN_above_known_I']} |")
lines+=['','全部8票两日OPEN报价可读且同源，未知或无可用报价0；也都高于已核12/10原只上调I线。这里仍不证明12/11可以成交，事件/票身份完整引擎、现金、经济量、dated lot、容量和其他所在基准门槛均未重放。','',
'这明确保留等待追价的代价：不能只称12/5挡住10票、12/10放回8票，就把原损失当免费避免。']
(O/'WAIT_REENTRY_PRICE_READOUT.md').write_text('\n'.join(lines))
p=O/'READOUT.md';p.write_text(p.read_text()+'\n\n## 9. 等待追价补充\n\n仍活8票的原12/5 OPEN与12/11可重审OPEN同尺度价差见WAIT_REENTRY_PRICE_READOUT.md；全部两日报价同源可知，但不代表已认证成交或候选收益。\n')
old=rd(O/'ORIGINAL_OUTPUT_SEAL.json');assert old==rd(OLD/'OUTPUT_SEAL.json') and all(sha(OLD/n)==h for n,h in old.items())
save('OUTPUT_SEAL',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'})
print(json.dumps(out,ensure_ascii=False))
