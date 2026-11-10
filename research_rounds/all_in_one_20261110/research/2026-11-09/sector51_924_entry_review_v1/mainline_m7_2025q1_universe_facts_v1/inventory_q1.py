"""Frozen full-universe Q1 source scan only; no engine or historical execution."""
import json,pathlib,csv,hashlib,collections
from decimal import Decimal as D
import pandas as pd
O=pathlib.Path(__file__).resolve().parent;R=O.parent;B=R/'mainline_m7_long_horizon_sealed_v2/once_20260630';V6=R/'mainline_m7_cash_batch_design_v6/once_20260630';A=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions');E=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1');hashes={};drift=[]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def track(p,expected=None):
 p=str(p);hashes[p]=sha(p)
 if expected and hashes[p]!=expected:drift.append(p)
 return hashes[p]
def read(p):track(p);return json.loads(pathlib.Path(p).read_text())
expected=read(B/'SOURCE_HASHES.json');cp=R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv';track(cp,expected[str(cp)]);ids={r['symbol'] for r in csv.DictReader(cp.open()) if r['eligible']=='True'};mp=next(p for p in expected if p.endswith('/STOCK_MANIFEST.json'));manifest={m['symbol']:m for m in read(mp)};ad={(r['sid'],r['ex_date']) for r in read(V6/'EVENT_ADMISSION.json')};rows=[];coverage=[]
for sid in sorted(ids):
 ap=A/(sid+'.json');obj=read(ap);assert hashes[str(ap)]==expected[str(ap)];actions=collections.defaultdict(list)
 for n,e in enumerate(obj['events'],1):
  if '2025-01-01'<=e['effective_date']<='2025-03-31':actions[e['effective_date']].append(dict(ordinal=n,event=e))
 m=manifest[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));track(sp,expected[sp]);z=pd.read_parquet(sp,columns=['adjustment_factor','raw_close','source_kind','source_path','segment_id','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']).sort_index();f=z.adjustment_factor;changes=z[(f/f.shift()-1).abs()>1e-11];dates=set(actions)|{str(t.date()) for t in changes.index if '2025-01-01'<=str(t.date())<='2025-03-31'}
 for dt in sorted(dates):
  acts=actions[dt];prev=z[z.index<pd.Timestamp(dt)].iloc[-1];cur=z.loc[pd.Timestamp(dt)] if pd.Timestamp(dt) in z.index else None;pure=len(acts)==1 and D(acts[0]['event']['cash_per_old_share'])>0 and D(acts[0]['event']['split_ratio'])==1 and acts[0]['event'].get('classification')=='ordinary_cash_and_pro_rata_bonus';ds=D(acts[0]['event']['cash_per_old_share']) if pure else None;fo=D(str(prev.adjustment_factor));fn=D(str(cur.adjustment_factor)) if cur is not None else None;pc=D(str(prev.raw_close));res=fo*pc/(pc-ds)/fn-1 if pure and fn and pc>ds else None
  def valid(r):return r is not None and all(pd.notna(r[k]) and r[k] in [True,1] for k in ['observed_bar','price_eligible','volume_eligible']) and all(pd.notna(r[k]) and r[k] in [False,0] for k in ['source_invalid','synthetic_event_bar'])
  origin=lambda r:[str(r[k]) for k in ['source_kind','source_path','segment_id']]
  rows.append(dict(sid=sid,ex_date=dt,actions=acts,pure_cash=pure,factor_changed=fn is not None and abs(fn/fo-1)>D('1e-11'),v6_admitted=(sid,dt) in ad,local_action_path=str(ap),local_action_sha256=hashes[str(ap)],signal_path=sp,signal_sha256=hashes[sp],factor_old=str(fo),factor_new=str(fn),previous_observation=str(prev.name.date()),previous_raw_close=str(pc),source_bridge_residual=str(res) if res is not None else None,source_bridge_pass=res is not None and abs(res)<D('1e-11'),previous_valid=bool(valid(prev)),current_valid=bool(valid(cur)),origin_before=origin(prev),origin_after=origin(cur) if cur is not None else None,same_lineage=cur is not None and origin(prev)==origin(cur)))
 coverage.append(dict(sid=sid,signal_last=str(z.index.max().date())))
rows.sort(key=lambda r:(r['ex_date'],r['sid']));needed={r['sid'] for r in rows if r['pure_cash'] and not r['v6_admitted']};rawpaths=set(E.glob('cash*/raw/*.json'))|set(R.glob('**/raw/*.json'))|set(R.glob('**/RAW*/*.json'))|set(R.glob('**/NOV_DEC_RAW_COMPLETION/*.json'));cache=collections.defaultdict(list)
for p in sorted(rawpaths):
 if p.stem not in needed:continue
 obj=read(p)
 if isinstance(obj,dict) and obj.get('endpoint')=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139':cache[obj.get('sid',p.stem)].append(dict(path=str(p),sha256=hashes[str(p)],records=obj.get('raw',{}).get('records',[])))
for r in rows:
 if not r['pure_cash'] or r['v6_admitted']:continue
 r['cached_response_paths']=[x['path'] for x in cache[r['sid']]];r['cached_exact_rows']=[dict(path=x['path'],sha256=x['sha256'],record=v) for x in cache[r['sid']] for v in x['records'] if v.get('F020D')==r['ex_date']]
new=[r for r in rows if r['pure_cash'] and not r['v6_admitted']];summary=dict(eligible_count=len(ids),source_boundary_dates=len(rows),explicit_action_dates=sum(bool(r['actions']) for r in rows),purecash_dates=sum(r['pure_cash'] for r in rows),complex_action_dates=sum(bool(r['actions']) and not r['pure_cash'] for r in rows),factor_only_dates=sum(not r['actions'] for r in rows),factor_change_dates=sum(r['factor_changed'] for r in rows),purecash_v6_admitted=sum(r['pure_cash'] and r['v6_admitted'] for r in rows),purecash_additional=len(new),additional_with_cached_exact_rows=sum(bool(r['cached_exact_rows']) for r in new),additional_with_cached_response_but_no_exact_rows=sum(bool(r['cached_response_paths']) and not r['cached_exact_rows'] for r in new),missing_cached_response_sid_count=len({r['sid'] for r in new if not r['cached_response_paths']}),purecash_source_bridge_failures=[dict(sid=r['sid'],date=r['ex_date']) for r in rows if r['pure_cash'] and not r['source_bridge_pass']],complex_events=[dict(sid=r['sid'],ex_date=r['ex_date'],actions=r['actions']) for r in rows if not r['pure_cash']],source_hash_mismatches=drift,history_run=False,new_admissions=0)
assert not drift
payload=dict(summary=summary,events=rows,additional_purecash=new,coverage=coverage,source_hashes=hashes)
(O/'Q1_UNIVERSE_INVENTORY.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(O/'Q1_INVENTORY_READOUT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
