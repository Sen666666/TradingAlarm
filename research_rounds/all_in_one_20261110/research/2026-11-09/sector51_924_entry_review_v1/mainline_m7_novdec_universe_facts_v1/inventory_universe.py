import json,pathlib,csv,hashlib,collections
from decimal import Decimal as D
R=pathlib.Path(__file__).resolve().parent.parent;O=pathlib.Path(__file__).resolve().parent;V5=R/'mainline_m7_cash_batch_design_v5';B=R/'mainline_m7_long_horizon_sealed_v2/once_20260630';hashes={}
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):hashes[str(p)]=sha(p);return json.loads(pathlib.Path(p).read_text())
expected=read(B/'SOURCE_HASHES.json');cp=R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv';hashes[str(cp)]=sha(cp);assert hashes[str(cp)]==expected[str(cp)];cl=list(csv.DictReader(cp.open()));ids={r['symbol'] for r in cl if r['eligible']=='True'};basead={(r['sid'],r['ex_date']) for r in read(B/'EVENT_ADMISSION.json')};v5ad={(r['sid'],r['ex_date']) for r in read(V5/'once_20260630/EVENT_ADMISSION.json')};A=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions');rows=[]
for sid in sorted(ids):
 p=A/(sid+'.json');obj=read(p);assert hashes[str(p)]==expected[str(p)]
 for n,e in enumerate(obj['events'],1):
  dt=e['effective_date']
  if '2024-11-01'<=dt<='2024-12-31':rows.append(dict(sid=sid,ex_date=dt,event_id=f'{sid}|LOCAL_DISTRIBUTION_{n:03d}',local_action_ordinal=n,action=e,local_action_path=str(p),local_action_sha256=hashes[str(p)],pure_cash=D(e['cash_per_old_share'])>0 and D(e['split_ratio'])==1 and e.get('classification')=='ordinary_cash_and_pro_rata_bonus',baseline_admitted=(sid,dt) in basead,v5_admitted=(sid,dt) in v5ad))
rows.sort(key=lambda r:(r['ex_date'],r['sid']));new=[r for r in rows if r['pure_cash'] and not r['v5_admitted']];keys={(r['sid'],r['ex_date']) for r in new};E=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1');sources=list(E.glob('cash*/raw/*.json'))+list(V5.glob('NOV_DEC_RAW_COMPLETION/*.json'))+list(R.glob('**/raw/*.json'));rawmatch=collections.defaultdict(list)
for p in sorted(set(sources)):
 if p.stem not in {s for s,d in keys}:continue
 obj=read(p)
 if not isinstance(obj,dict) or 'cninfo' not in obj.get('endpoint',''):continue
 for rec in obj.get('raw',{}).get('records',[]):
  key=(obj.get('sid',p.stem),rec.get('F020D'))
  if key in keys:rawmatch[key].append(dict(path=str(p),sha256=hashes[str(p)],endpoint=obj['endpoint'],record=rec))
for r in new:r['existing_official_rows']=rawmatch[(r['sid'],r['ex_date'])]
summary=dict(scope='FULL_FROZEN_ELIGIBLE_UNIVERSE_EXPLICIT_ACTION_INVENTORY_NOV_DEC2024',eligible_symbols=len(ids),all_classification_symbols=len(cl),action_dates=len(rows),purecash_dates=sum(r['pure_cash'] for r in rows),complex_dates=sum(not r['pure_cash'] for r in rows),purecash_original_admitted=sum(r['pure_cash'] and r['baseline_admitted'] for r in rows),purecash_v5_admitted=sum(r['pure_cash'] and r['v5_admitted'] for r in rows),additional_purecash_to_review=len(new),additional_with_existing_official_rows=sum(bool(r['existing_official_rows']) for r in new),additional_missing_existing_official_rows=sum(not r['existing_official_rows'] for r in new),historical_run=False,new_admission=False,limitation='Explicit action inventory, not standalone factor-only anomaly inventory or future portfolio forecast.')
(O/'UNIVERSE_NOV_DEC_INVENTORY.json').write_text(json.dumps(dict(summary=summary,events=rows,additional_purecash=new,source_hashes=hashes),ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,indent=2));print('missing',[(r['sid'],r['ex_date']) for r in new if not r['existing_official_rows']])
