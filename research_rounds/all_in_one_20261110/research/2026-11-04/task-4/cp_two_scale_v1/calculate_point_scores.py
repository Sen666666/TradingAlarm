"""Fixed mathematical scores only; no new signal sequence or account."""
from pathlib import Path
import json,math,csv,hashlib
p=Path(__file__).resolve().parent;root=[];sources={}
def read(q):
 q=Path(q);sources[str(q.resolve())]=hashlib.sha256(q.read_bytes()).hexdigest();return json.loads(q.read_text())
for r in read(p/'yingxin/TWO_SCALE_FOUR_CLOSES.json'):
 root.append({'sid':r['sid'],'name':'盈新','date':r['day'],'raw_close':r['close_raw'],'short_pivot_day':r['low_pivot_day'],'short_confirm_day':r['low_confirm_at'][:10],'short_anchor_raw':r['low_pivot_raw_in_today_units'],'long_pivot_day':r['high_pivot_day'],'long_confirm_day':r['high_confirm_at'][:10],'long_anchor_raw':r['high_pivot_raw_in_today_units'],**{k:r[k]for k in ['A_s','L_s','ER_s','DD_s','A_l','L_l','ER_l','DD_l','sigma_s','sigma_l']}})
for r in read(p/'hytera/ALL43_CONFIRMED_E0_TWO_SCALE_PATHS.json'):
 if r['date']not in ['2024-09-24','2024-09-30','2024-10-18']:continue
 s,l=r['short'],r['long'];ss=s['anchor'];ll=l['anchor']
 root.append({'sid':r['sid'],'name':'海能达','date':r['date'],'raw_close':r['raw_close'],'short_pivot_day':ss['pivot_day'],'short_confirm_day':ss['confirm_day'],'short_anchor_raw':s['pivot_a_div_current_factor'],'long_pivot_day':ll['pivot_day'],'long_confirm_day':ll['confirm_day'],'long_anchor_raw':l['pivot_a_div_current_factor'],**{k+'_'+axis:v[k]for axis,v in [('s',s),('l',l)]for k in ['A','L','ER','DD']},'sigma_s':ss['sigma_CP_z_at_confirm'],'sigma_l':ll['sigma_CP_z_at_confirm']})
for r in root:
 for axis in ['s','l']:
  a,e,sg=r['A_'+axis],r['ER_'+axis],r['sigma_'+axis];g=a*abs(e)if e is not None else None;q=g/(math.sqrt(5)*sg)if g is not None and sg else None;r['G_'+axis]=g;r['threshold_'+axis]=math.sqrt(5)*sg;r['Q_'+axis]=q
 r['pointwise_hypothesis_class_not_new_signal']='LONG_SUPPORTED'if r['Q_s']>=1 and r['Q_l']>=1 else'PRICE_RECLAIMED_PROBE_ONLY'if r['Q_s']>=1 and r['A_l']>0 else'SHORT_PROBE_ONLY'if r['Q_s']>=1 else'NO_SHORT_SUPPORT'
 r['not_a_new_permission_event_or_account']=True
(p/'POINTWISE_TWO_SCALE_SCORES.json').write_text(json.dumps(root,ensure_ascii=False,indent=2)+'\n')
with(p/'POINTWISE_TWO_SCALE_SCORES.csv').open('w',newline='')as f:w=csv.DictWriter(f,fieldnames=list(root[0]));w.writeheader();w.writerows(root)
sources[str((p/'FROZEN_TWO_SCALE_PERMISSION_HYPOTHESIS.txt').resolve())]=hashlib.sha256((p/'FROZEN_TWO_SCALE_PERMISSION_HYPOTHESIS.txt').read_bytes()).hexdigest();(p/'POINT_SCORES_SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
for r in root:print(json.dumps({k:r[k]for k in ['name','date','raw_close','G_s','Q_s','G_l','Q_l','pointwise_hypothesis_class_not_new_signal']},ensure_ascii=False))
