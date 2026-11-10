"""Descriptive fixed-share comparator to actual M7 October8 holdings. Not an alpha input."""
import json,hashlib,argparse
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;ap=argparse.ArgumentParser();ap.add_argument('run');args=ap.parse_args();P=R/args.run/'once_20241031';A='2024-10-08';Z=D(0)
read=lambda p:json.loads(Path(p).read_text());ll=read(P/'DAY_LEDGER.json');a=next(r for r in ll if r['day']==A);end=ll[-1]['day'];out=O/(args.run+'__'+end);old={}
for h in read(P/'HOLDINGS.json'):
 if h['day']==A:old[h['sid']]=old.get(h['sid'],0)+h['qty']
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');m={r['symbol']:r for r in read(M)};sources=[Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1/cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json'),R/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json',R/'joint51_candidate_v9_facts/ADDITIONAL_REVIEWED_EVENTS.json',R/'retained_20241010_cash_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20241010_TWO_V1.json']
manifest=P.parent/'REVIEWED_BATCH_MANIFEST.json'
if manifest.exists():
 for entry in read(manifest)['adapters']:
  sp=Path(entry['path']);assert hashlib.sha256(sp.read_bytes()).hexdigest()==entry['sha256'];sources.append(sp)
events={(e['sid'],e['ex_date']):e for p in sources for e in read(p)};hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+[M]};bars={}
for s in old:
 p=Path(next(p for p in m[s]['source_sha256'] if p.endswith('/signal.parquet')));h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m[s]['source_sha256'][str(p)];hashes[str(p)]=h;bars[s]=pd.read_parquet(p)
rows=[];claims={};peak=D(a['NAV']);dd=Z
for l in ll:
 ds=l['day']
 if ds<=A:continue
 market=Z
 for s,q in old.items():
  z=bars[s];r=z.loc[pd.Timestamp(ds)];prev=z[z.index<pd.Timestamp(ds)].iloc[-1]
  assert r.observed_bar and r.price_eligible and not r.source_invalid and not r.synthetic_event_bar, ('Comparator lacks verified available mark',s,ds)
  assert tuple(str(r[c]) for c in ['source_kind','source_path','segment_id'])==tuple(str(prev[c]) for c in ['source_kind','source_path','segment_id'])
  changed=abs(D(str(r.adjustment_factor))/D(str(prev.adjustment_factor))-1)>D('1e-11');ev=events.get((s,ds))
  if changed:
   assert ev is not None,('Missing reviewed comparator factor event',s,ds)
   fo=D(str(prev.adjustment_factor));fn=D(str(r.adjustment_factor));pc=D(str(prev.raw_close));assert abs(fo*pc/(pc-D(ev['d_source']))/fn-1)<D('1e-11')
  if ev and ev['record_date']>=A:claims[(s,ds)]=(q*D(ev['d_cash'])*D('.8'),ev['pay_date'])
  market+=q*D(str(r.raw_close))
 cash=D(a['cash'])+sum((v for v,pay in claims.values() if pay<=ds),Z);recv=D(a['receivable'])+sum((v for v,pay in claims.values() if pay>ds),Z);nav=cash+recv+market;peak=max(peak,nav);dd=min(dd,nav/peak-1)
 rows.append(dict(day=ds,passive_NAV=str(nav),passive_return_since1008_pct=str(100*(nav/D(a['NAV'])-1)),passive_max_close_drawdown_since1008_pct=str(dd*100),passive_cash=str(cash),passive_receivable=str(recv),actual_NAV=l['NAV'],actual_minus_passive_NAV=str(D(l['NAV'])-nav)))
res=dict(result='PASS',anchor=A,through=end,fixed_stocks=len(old),fixed_quantities=old,rows=rows,source_hashes=hashes,caveats=['No trading after actual October8 close; not a retuned strategy or funded reallocation experiment.','Uses same net80 entitlement proxy and source-coordinate cash factor bridges.','No transaction costs after anchor for passive case; actual NAV includes actual modeled costs.','Stops if quotes unavailable or an unreviewed held corporate action appears; no improvised stale valuation.'])
(out/'PASSIVE_1008_ANCHOR_COMPARATOR.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False))
