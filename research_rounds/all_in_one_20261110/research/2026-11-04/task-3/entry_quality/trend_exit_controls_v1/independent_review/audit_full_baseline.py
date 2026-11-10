"""Full original book equality and independent trade/dividend wealth bridge."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D,getcontext
import json,gzip,hashlib
getcontext().prec=65
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');S={};C=Counter();Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);S[str(p)]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
refs={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair','strong':B/'pvr_pool_feasibility/runs/2025_26/pair'};results={}
for window,original in refs.items():
 out=P/'runs/BASELINE'/window;assert read(out/'DONE.json')['completed'];meta=read(out/'RUN_METADATA.json');assert meta['fresh_cash']==1000000 and meta['no_checkpoint_import'] and not meta['yearly_reset'];assert meta['tool_manifest_sha256'] is None
 for p,h in meta['source_freeze'].items():assert sha(p)==h;C['current_frozen_source_SHA']+=1
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');gold=read(original/'B.json.gz');gd=read(original/'daily.jsonl.gz');assert book==gold and daily==gd;C['whole_book_field_identity']+=len(book);C['whole_daily_identity']+=len(daily)
 assert len(daily)==(726 if window=='2022_2024' else 242)
 cash_events=[(t['at'],(D(t['gross_cny'])-D(t['fees_cny'])) if t['side']=='sell' else -D(t['gross_cny'])-D(t['fees_cny'])) for t in book['trades']];div_events=[(a['receivable']['ex_at'],D(a['receivable']['net_local'])) for a in book['audit'] if a['kind']=='dividend_accrual'];events=sorted(cash_events+div_events);i=0;economic=Z;peak=D(1000000);maxdd=Z
 for d in daily:
  while i<len(events) and events[i][0]<=d['at']:economic+=events[i][1];i+=1
  expect=D(1000000)+economic+D(d['inventory']);assert abs(expect-D(d['nav']))<D('1e-8'),(window,d['at'],expect,d['nav']);assert D(d['available'])>=0;C['daily_independent_trade_AR_inventory_NAV']+=1
  peak=max(peak,D(d['nav']));maxdd=min(maxdd,D(d['nav'])/peak-1)
  assert abs(sum((D(x['cash'])+D(x['dividend']) for x in book['layers']),Z)+D(daily[-1]['inventory'])-(D(book['ending_NAV'])-D(1000000)))<D('1e-8')
 fees=sum((D(t['fees_cny']) for t in book['trades']),Z);assert abs(fees-D(daily[-1]['fees_cny']))<D('1e-8');assert book['ending_NAV']==daily[-1]['nav'] and book['ending_cash']==daily[-1]['available'];C['final_layer_cash_AR_inventory_bridge']+=1
 fills={a['receipt']['receipt_id']:a for a in book['audit'] if a['kind']=='fill'};requests={a['event_id']:a for a in book['audit'] if a['kind']=='exit_request'}
 for t in book['trades']:
  f=fills[t['receipt_id']];assert t['at'][11:19]=='09:30:00';assert D(t['fees_cny'])==sum((D(v) for v in f['fee_components'].values()),Z);assert D(t['gross_cny'])==D(f['receipt']['gross_cny']);C['all_fill_fee_and_OPEN_identity']+=1
  if t['side']=='sell':assert requests[f['order_id']]['at']<t['at'];C['actual_sell_order_clock']+=1
 results[window]=dict(daily=len(daily),trades=len(book['trades']),all_book_fields_exact=list(book),initial_cash=1000000,ending_NAV=book['ending_NAV'],net_wealth_change=str(D(book['ending_NAV'])-D(1000000)),total_fees=str(fees),minimum_daily_available=str(min(D(d['available']) for d in daily)),max_CLOSE_drawdown=str(maxdd),original_reference=str(original))
out=dict(status='PASS_FULL_BASELINE',results=results,checks=dict(C),source_sha256=S,limits=['All726/242 original native daily rows and complete books are exactly equal, including trades, audit, decisions, budget and final cash.','Independent economic bridge counts recognized dividend AR as wealth, not settled cash. Native inventory valuation reuses the original held-price/source audit, established here by exact whole-path equality.','No alternative-account result is covered by this receipt.'],new_accounts=0)
(O/'FULL_BASELINE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
