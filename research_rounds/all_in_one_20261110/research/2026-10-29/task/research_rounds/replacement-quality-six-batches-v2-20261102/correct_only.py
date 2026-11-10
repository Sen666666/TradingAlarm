"""Analysis errata only; reuse all validated price labels without recomputation."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
JAN=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-difference-readonly-20261102')
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if (O/'BUY_FEE_ERRATA.json').exists():
  target=read(O/'BUY_FEE_ERRATA.json');rr=read(O/'ALL_ROWS.json')
  total=sum(D(z['realized_trade_PNL']) for r in rr if r['arm']=='2022-C10' and r['side']=='D' for z in r['actual_account_outcomes'])
  assert total==D(target['correct_net']);print('ALREADY_CORRECTED_NO_SECOND_FEE_DEDUCTION',total);return
 rows=read(O/'ALL_ROWS.json');before={ (r['case'],r['side'],r['sid']):r['labels'] for r in rows};costs={z['layer']:z for z in read(JAN/'ALL_LAYERS.json')['C10']};fee=D(0);old=D(0);new=D(0);parts=[]
 for r in rows:
  for u in r['actual_units']:
   if 'price_gain_before_sell_after_buyfees' in u:u['mark_price_gain_before_sell_excluding_buyfees']=u.pop('price_gain_before_sell_after_buyfees')
  if r['arm']=='2022-C10' and r['side']=='D':
   for z in r['actual_account_outcomes']:
    q=z['shares'];c=costs[z['layer']];f=D(c['buy_fee'])*q/c['buy_qty'];old+=D(z['realized_trade_PNL']);fee+=f
    z['realized_trade_PNL']=str(D(z['realized_trade_PNL'])-f);z['allocated_buy_fee']=str(f);new+=D(z['realized_trade_PNL']);parts.append(dict(sid=r['sid'],layer=z['layer'],shares=q,allocated_buy_fee=str(f)))
 assert new==D('-14440.25979803318888888888889')
 assert all(r['labels']==before[r['case'],r['side'],r['sid']] for r in rows)
 save(O/'ALL_ROWS.json',rows)
 for p in (O/'cases').glob('*.json'):
  x=read(p);x['rows']=[r for r in rows if r['case']==x['summary']['certificate']];save(p,x)
 report=(O/'REPORT.txt').read_text();report=report.replace('21市场日为主、5日为辅；终点不逐股顺延。','D+21为起始后21市场交易日（含起始共22个收盘观察），D+5相应为6个收盘观察；终点不逐股顺延。')
 report=report.replace('中际300股实际层净−1582.09，而同起点21日价格+71.30%；','中际144层Aug14买300、Aug18筹资卖，层净−1582.09；截至Aug29未再入，全股含July旧层净+3840.91，二者不得混用。同起点D+21价格+71.30%；')
 report+='\n独审后V2口径勘误：Jan旧D已实现原漏分摊买费156.66917010元，−14283.59062793改为−14440.25979803元。标记市值价差字段改名mark_price_gain_before_sell_excluding_buyfees；未称已扣买费。全部130个价格标签/风险分母/新层贡献不变。V1原件完整保留。\n'
 (O/'REPORT.txt').write_text(report)
 save(O/'BUY_FEE_ERRATA.json',dict(old=str(old),allocated_buy_fee_omitted=str(fee),correct_net=str(new),parts=parts,financial_events=0,labels_recomputed=0,all_130_labels_exact=True,new_layer_PNL_unchanged=True,
  old_v1_manifest_sha256=sha(O.parent/'replacement-quality-six-batches-v1-20261102/DELIVERABLE_MANIFEST.json')))
 print('CORRECTED Jan D',str(old),'minus fee',str(fee),'=',str(new),'130 labels reused',flush=True)
if __name__=='__main__':main()
