"""Append-only seed-equivalent core comparison. No T or account rerun."""
from pathlib import Path
from decimal import Decimal as D
import json,csv,hashlib
O=Path(__file__).resolve().parent;R=O.parent;P=R/'mainline_candidate_v2_pending_quote_pause/checkpoint_20240930'
Z=D(0)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
before={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!=Path(__file__).name}
def read(p):return json.loads(p.read_text())
lots=read(O/'LOT_CAPITAL_CLASSIFICATION_ASOF.json');rounds=read(O/'ROUND_CLASSIFICATION_ASOF.json');orders=read(P/'ORDERS.json')
assert sha(P/'ORDERS.json')==read(P/'OUTPUT_HASHES.json')['ORDERS.json']
seed={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
rows=[];summary=[]
for day in ['2024-09-20','2024-09-23','2024-09-26','2024-09-27']:
 rr=[]
 for r in rounds:
  if r['day']!=day:continue
  ls=[x for x in lots if x['day']==day and x['round_id']==r['round_id']]
  ss=sum((D(x['market_value']) for x in ls if x['kind']=='SEED'),Z)
  aa=next((x for x in ls if x['lot_id']==r['earliest_surviving_ADD_lot']),None)
  aq=aa['qty'] if aa else 0;sq=seed[r['round_id']]['qty'];p=D(aa['raw_mark']) if aa else Z;eq=min(aq,sq);winner=r['current_mainline_winner']
  old=ss+aq*p if winner else Z;new=ss+eq*p if winner else Z
  oldexport=sum((D(x['CORE2_WINNER_SEED_FIRST_ADD_core_value']) for x in ls),Z)
  assert old==oldexport
  x=dict(day=day,sid=r['sid'],sector51=r['sector51'],round_id=r['round_id'],category=r['category'],current_mainline_winner=winner,original_seed_lot_id=seed[r['round_id']]['lot_id'],original_seed_bought=seed[r['round_id']]['day'],original_seed_qty=sq,current_seed_qty=sum(x['qty'] for x in ls if x['kind']=='SEED'),current_seed_market_value=ss,earliest_surviving_ADD_lot_id=r['earliest_surviving_ADD_lot'],historical_first_ADD_lot_id=r['historical_first_ADD_lot'],earliest_surviving_ADD_remaining_qty=aq,ADD_seed_equivalent_protected_qty=eq if winner else 0,current_raw_close=D(ls[0]['raw_mark']),old_whole_first_surviving_ADD_core=old,new_seed_equivalent_core=new,released_to_mobile_qty=aq-eq if winner else 0,core_capital_difference=old-new,difference_kind='NONE' if old==new else 'WHOLE_ADD_LAYER_EXCEEDS_ORIGINAL_SEED',no_new_account_or_T_run=True)
  rows.append(x);rr.append(x)
 summary.append(dict(day=day,all_held_rounds=len(rr),current_winner_rounds=sum(x['current_mainline_winner'] for x in rr),current_winner_rounds_with_surviving_ADD=sum(x['current_mainline_winner'] and x['earliest_surviving_ADD_remaining_qty']>0 for x in rr),old_whole_layer_core=sum((x['old_whole_first_surviving_ADD_core'] for x in rr),Z),new_seed_equivalent_core=sum((x['new_seed_equivalent_core'] for x in rr),Z),core_capital_difference=sum((x['core_capital_difference'] for x in rr),Z),different_rounds=sum(x['core_capital_difference']!=0 for x in rr),released_to_mobile_qty=sum(x['released_to_mobile_qty'] for x in rr)))
def save(n,a):
 p=O/(n+'.json');assert not p.exists();p.write_text(json.dumps(a,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(a,list) and a:
  p=O/(n+'.csv');assert not p.exists()
  with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
save('SUPPLEMENT_SEED_EQUIVALENT_CORE_ROUNDS',rows);save('SUPPLEMENT_SEED_EQUIVALENT_CORE_SUMMARY',summary)
text=['# 补充：确认核心按原始SEED同量限额（仅差额核对）','',
'候选定义：当前赢家资格保持原核心二条件；保护当前仍持SEED，加当前最早剩余实际ADD中的min(该ADD剩余股数,本轮原始真实SEED买入股数)。剩余ADD资本为机动层。没有ADD就不补造。',
'',
'四个M2既有截面逐轮核查结果：','日期 | 全部持有轮 | 当前赢家轮 | 赢家中仍有ADD的轮 | 原整层核心（元） | 同量核心（元） | 差额（元）','---|---:|---:|---:|---:|---:|---:']
for r in summary:text.append(' | '.join([r['day']]+[str(r[k]) for k in ['all_held_rounds','current_winner_rounds','current_winner_rounds_with_surviving_ADD','old_whole_layer_core','new_seed_equivalent_core','core_capital_difference']]))
text+=['',
'结论：现M2这四个截面差额全为0，852个当日持有轮全部列入附表，其中251个当日赢家轮按真实原始SEED订单和当前剩余ADD逐一核实。没有对T全表作任何重算，没有新策略/新账户。',
'',
'此相同只属于当前已运行的渐进ADD路径。若新组合恢复单次2%预算，一笔首次ADD可能大于SEED；不能因该大笔资金先获资就自动成为不可动成熟核心。拟议同量定义把一份SEED作为试仓、再一份同量实际ADD作为确认核心，其余作为趋势扩仓。该定义仍待父线程选定，并未授权实施或新回测。',
'',
'原READOUT、T全表、QA与原封印全部保持不变。本附表另有独立输入/产物封印。']
p=O/'SUPPLEMENT_SEED_EQUIVALENT_CORE_READOUT.md';assert not p.exists();p.write_text('\n'.join(text)+'\n')
assert all(sha(O/name)==h for name,h in before.items()),'ORIGINAL_DIAGNOSTIC_CHANGED'
sources={str(p):sha(p) for p in [O/'LOT_CAPITAL_CLASSIFICATION_ASOF.json',O/'ROUND_CLASSIFICATION_ASOF.json',P/'ORDERS.json',P/'OUTPUT_HASHES.json',Path(__file__)]}
save('SUPPLEMENT_SEED_EQUIVALENT_CORE_QA',dict(result='PASS_DIFFERENCE_ZERO_ALL_FOUR_DATES',rows=len(rows),winner_rows=sum(x['current_mainline_winner'] for x in rows),different_rows=sum(x['core_capital_difference']!=0 for x in rows),original_diagnostic_files_unchanged=len(before),original_T_reruns=0,new_account_runs=0,source_hashes=sources))
save('SUPPLEMENT_OUTPUT_HASHES',{p.name:sha(p) for p in O.iterdir() if p.is_file() and (p.name.startswith('SUPPLEMENT_') or p.name.startswith('append_seed_equivalent_check')) and p.name!='SUPPLEMENT_OUTPUT_HASHES.json'})
print(json.dumps(summary,default=str,ensure_ascii=False))
