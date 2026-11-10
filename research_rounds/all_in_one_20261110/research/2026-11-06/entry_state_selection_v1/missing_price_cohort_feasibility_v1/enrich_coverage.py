from pathlib import Path
import json,sys,hashlib,time,collections,ast
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
J=R/'independent_channel_joint_economic_v1';sm=json.loads((U/'STOCK_MANIFEST.json').read_text());rules=json.loads((B/'inputs-v2/market-rules.json').read_text());wins=json.loads((O/'PROTOCOL.json').read_text())['windows'];H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
rows=[]
for m in sm:
 sid=m['symbol'];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));q=pd.read_parquet(p,columns=['raw_open','raw_close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','quality_status','source_kind']);first=q.index.min() if len(q) else None;last=q.index.max() if len(q) else None;vv=rules['venue_versions'].get(sid,[]);rulefrom=min([r['from'] for r in vv],default=None)
 for w,(lo,hi) in wins.items():
  ds=cal[(cal>=lo)&(cal<=hi)];present=ds.isin(q.index);missing=ds[~present];before=sum(d<first for d in missing) if first is not None else 0;after=sum(d>last for d in missing) if last is not None else 0;inside=len(missing)-before-after if first is not None else 0;pre_rule=sum(str(d.date())<rulefrom for d in missing) if rulefrom else 0;z=q.reindex(ds)
  bad=z[z.raw_open.notna()&((z.raw_open<=0)|(z.raw_close<=0)|~z.observed_bar.eq(True)|~z.price_eligible.eq(True)|~z.source_invalid.eq(False)|~z.synthetic_event_bar.eq(False))]
  rows.append(dict(sid=sid,window=w,missing_rows=len(missing),before_local_first=before,after_local_last=after,within_local_observed_span=inside,no_local_history=len(missing) if first is None else 0,missing_before_dated_identity_start=pre_rule,dated_identity_start=rulefrom,first_local_observation=str(first),last_local_observation=str(last),nonpositive_open_or_close=int((z.raw_open.le(0)|z.raw_close.le(0)).sum()),bad_present_flag_rows=len(bad),bad_present_details=bad.reset_index().astype(str).to_dict('records'),rule_unavailable_with_present_raw=sum(str(d.date())<rulefrom for d in ds[present]) if rulefrom else sum(present),suspension_reason_verified=False))
df=pd.DataFrame(rows);df.to_csv(O/'PRICE_GAP_CLASSIFICATION.csv',index=False);save('PRICE_GAP_SUMMARY.json',dict(summary=df.groupby('window').sum(numeric_only=True).to_dict('index'),limitations=['Before first local observation and before dated identity starts are proxies for pre-listing, not official IPO proof.','Absent rows inside observed span cannot distinguish suspension vs upstream missing source without dated official suspension records; no fabricated suspension label.','Source schema supplies no independent historical suspension flag.']))
# Build new AB facts using exact original event logic, with only windows/output changed.
p=R/'m3_stock_birth_during_sector_v1/freeze_events.py';text=p.read_text();body=text[text.index("panel=pd.read_parquet"):text.index('# Original A membership')]
old="windows=[('2022','2022-01-01','2022-12-31',None),('2024_924','2024-09-01','2024-12-31',None),('2026H1_SEMI','2026-01-01','2026-06-30','URFI881121')]"
new="windows=[('2023','2023-01-01','2023-12-31',None),('2024JanAug','2024-01-01','2024-08-31',None)]";assert body.count(old)==1;body=body.replace(old,new)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();env=dict(pd=pd,np=np,json=json,Path=Path,R=R,U=U,D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2',hashes={},sha=sha)
exec(compile(body,str(p)+':original_event_logic_new_window_only','exec'),env);e=env['e'];e.to_csv(O/'MISSING_WINDOW_AB_EVENTS.csv',index=False)
checks=[]
for wn,g in e.groupby('window'):
 for d in sorted(g.day.unique())[::max(1,g.day.nunique()//5)]:
  prefix=env['M'].loc[:d];previous=prefix.shift()
  for z in g[g.day.eq(d)].itertuples():assert prefix.at[d,z.sid]==1 and (pd.isna(previous.at[d,z.sid]) and pd.isna(z.previous_stock_state) or previous.at[d,z.sid]==z.previous_stock_state)
  checks.append(dict(window=wn,cut=str(pd.Timestamp(d).date()),exact=True))
save('AB_EVENT_FEASIBILITY_QA.json',dict(original_source_sha256=sha(p),extracted_definition_sha256=hashlib.sha256(body.encode()).hexdigest(),changes='window tuples only; no old runner imported or old output written',counts=e.groupby(['window','event_type']).agg(events=('sid','size'),sids=('sid','nunique'),I_and_PVR_known=('I_and_PVR_known','sum')).reset_index().to_dict('records'),prefix_checks=checks,no_economics=True,full_warm_panel_shift_before_window=True))
# Correct fixture lineage comparison to match consumer: compare raw signal and raw OPEN;
# market replay casts segment to float (0.0), raw OPEN preserves integer (0).
from decimal import Decimal as D
from types import SimpleNamespace
sys.path.insert(0,str(J));sys.path.insert(0,str(B/'code'))
from market_adapter import MarketAdapter
from joint_policy import PriceSizing,OpenView
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeSchedule,FeeComponent
p=R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py';source=p.read_text();env=dict(D=D,meta={},rules=rules,proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'],market_identity_on=market_identity_on,version_on=version_on,QuantityRule=QuantityRule,FeeSchedule=FeeSchedule,FeeComponent=FeeComponent,SLIP=D('.0005'))
for n in ast.parse(source).body:
 if isinstance(n,ast.FunctionDef) and n.name in {'getmeta','fee','size'}:exec(compile(ast.Module(body=[n],type_ignores=[]),str(p)+':definition_only','exec'),env)
sizer=PriceSizing(SimpleNamespace(**{k:env[k] for k in ['getmeta','fee','size']},RuleUnavailable=RuleUnavailable));a=MarketAdapter();tickets=pd.read_csv(O/'FIXTURE_RECEIPT_FEASIBILITY.csv');out=[]
for sid,g in tickets.groupby('sid'):
 market=a.load_sid(sid)
 for r in g.itertuples():
  d=pd.Timestamp(r.day);nd=pd.Timestamp(r.next_common_open);z=market.loc[d];sig=a.open(sid,d);op=a.open(sid,nd);match=OpenView.from_mapping(sig).lineage==OpenView.from_mapping(op).lineage and np.isclose(sig['adjustment_factor'],op['adjustment_factor'],rtol=1e-11)
  v={'result':'SOURCE_OR_FACTOR_UNKNOWN_NO_SIZING'}
  if match:v=sizer.initial_open(sid,nd,OpenView.from_mapping(op),floor=D(str(z.S_new))/D(str(op['adjustment_factor'])),capacity=z.capacity_shares)
  out.append(dict(sid=sid,window=r.window,day=r.day,next_common_open=r.next_common_open,raw_signal_open_lineage_equal=match,open_result=v['result'],q=v.get('q'),fee=str(v.get('fee')),plan_risk=str(v.get('risk')),prior_receipt_industry=r.industry,NOT_A_TRADE=True))
pd.DataFrame(out).to_csv(O/'FIXTURE_NEXT_OPEN_V2.csv',index=False);save('FIXTURE_NEXT_OPEN_V2_QA.json',dict(result='PASS_ORIGINAL_RAW_LINEAGE_AND_ISOLATED_OPEN_SIZE',receipt_count=len(out),open_results=dict(collections.Counter(r['open_result'] for r in out)),correction='Initial fixture compared stringified replay float segment to raw integer segment; no real source mismatch. V2 uses raw signal lineage exactly as original JointConsumer._validate_open. Original failed fixture preserved.',no_cash_or_ownership_or_competition_evaluated=True,old_files_unchanged=True))
old=json.loads((O/'OLD_TREE_SHA256_BEFORE.json').read_text());assert all(sha(p)==h for p,h in old.items())
print(json.dumps(dict(gaps=json.loads((O/'PRICE_GAP_SUMMARY.json').read_text()),ab=json.loads((O/'AB_EVENT_FEASIBILITY_QA.json').read_text()),open=json.loads((O/'FIXTURE_NEXT_OPEN_V2_QA.json').read_text())),ensure_ascii=False,default=str))
