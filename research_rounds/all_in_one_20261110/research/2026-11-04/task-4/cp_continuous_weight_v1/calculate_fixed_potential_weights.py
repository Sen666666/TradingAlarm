"""Only frozen scalar diagnostic weights; no stateful grants/orders/accounts."""
from pathlib import Path
import json,math,csv,hashlib
P=Path(__file__).resolve().parent;sources={};rows=[]
def read(p):sources[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def F(q):return max(q,0)+math.log1p(math.exp(-abs(q)))
for r in read(P/'yingxin/JAN19_25_Q_AND_ANCHOR_DECOMPOSITION.json'):
 if r['day']<'2022-01-20':continue
 rows.append({'name':'盈新','sid':r['sid'],'date':r['day'],'raw_close':r['close_raw'],'Q_s':r['Q_s'],'Q_l':r['Q_l'],'Q_l_previous':r['Q_yesterday_l'],'Q_l_today_old_anchor':r['Q_old_anchor_at_today_l'],'raw_delta_Q_l':r['delta_Q_raw_l'],'comparable_delta_Q_l':r['delta_Q_comparable_old_anchor_l'],'rebase_delta_Q_l':r['Q_rebase_component_l'],'original_CP_receipt':r['original_CP_receipt'],'original_E0_event':r['original_E0_event']})
for r in read(P/'hytera/SEP23_OCT21_CONTINUOUS_Q_AND_DECOMPOSITION.json'):
 if r['date']<'2024-09-24':continue
 rows.append({'name':'海能达','sid':r['sid'],'date':r['date'],'raw_close':r['raw_close'],'Q_s':r['Q_s'],'Q_l':r['Q_l'],'Q_l_previous':r['Q_l_yesterday'],'Q_l_today_old_anchor':r['Q_l_today_old_anchor_and_sigma'],'raw_delta_Q_l':r['raw_dQ_l'],'comparable_delta_Q_l':r['market_dQ_l'],'rebase_delta_Q_l':r['rebase_dQ_l'],'original_CP_receipt':r['original_CP_receipt'],'original_E0_event':r['original_E0_event']})
for r in rows:
 df=F(r['Q_l_today_old_anchor'])-F(r['Q_l_previous']);r['softplus_current_raw_Q']=F(r['Q_l']);r['softplus_today_old_anchor']=F(r['Q_l_today_old_anchor']);r['comparable_delta_softplus']=df;r['potential_weight_not_grant']=-math.expm1(-max(0,df));r['no_long_Q_ge1_gate']=True;r['not_stateful_risk_or_actual_trade']=True
(P/'ALL_DAILY_FIXED_POTENTIAL_WEIGHTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with(P/'ALL_DAILY_FIXED_POTENTIAL_WEIGHTS.csv').open('w',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
sources[str((P/'FIXED_WEIGHT_COUNTERFACTUAL_FORMULA.txt').resolve())]=hashlib.sha256((P/'FIXED_WEIGHT_COUNTERFACTUAL_FORMULA.txt').read_bytes()).hexdigest();(P/'WEIGHT_SCALAR_SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['name'],r['date'],f"Qs={r['Q_s']:.4f}",f"Ql={r['Q_l']:.4f}",f"dQmarket={r['comparable_delta_Q_l']:+.4f}",f"dQrebase={r['rebase_delta_Q_l']:+.4f}",f"wpot={r['potential_weight_not_grant']:.4f}")
