from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
j=lambda n:json.loads((O/n).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=pd.read_csv(O/'PRICE_ROUND_PATH_ATTRIBUTION.csv',float_precision='round_trip');r['window_label']=r.window_label.astype(str);st=pd.read_csv(O/'STOCK_ATTRIBUTION.csv',float_precision='round_trip');st['window']=st.window.astype(str)
# Complete top-N / remainder complements instead of presenting overlapping top-N sets as partitions.
conc={}
for w,g in r.groupby('window_label'):
 for ranking in ['net','loss_amount']:
  for n in [10,20]:
   stocks=st[st.window==w].sort_values(ranking,ascending=ranking=='net').head(n).sid;parts=[]
   for label,x in [('TOP',g[g.sid.isin(stocks)]),('REMAINDER',g[~g.sid.isin(stocks)])]:
    p=x.net_pnl;parts.append(dict(part=label,n=len(x),stocks=x.sid.nunique(),profit_rounds=int((p>0).sum()),loss_rounds=int((p<0).sum()),net=float(p.sum()),profit_amount=float(p[p>0].sum()),loss_amount=float(-p[p<0].sum()),probe_trade=float(x.probe_trade.sum()),add_trade=float(x.add_trade.sum()),net80_income=float(x.net80_income.sum())))
   assert sum(x['n'] for x in parts)==len(g) and abs(sum(x['net'] for x in parts)-g.net_pnl.sum())<1e-7
   conc[f'{w}__{ranking}__TOP{n}']=parts
save('CONCENTRATION_COMPLETE_PARTITIONS.json',conc)
qa=j('FINAL_QA.json');qa['complete_concentration_partitions_checked']=len(conc);qa['parent_independent_aggregation_review']=dict(source='Parent native review message received 2026-11-08, not a second full fee/price calculation',round_ids_unique=2862,round_day_keys_unique=115079,next_open_strictly_after_close=True,settled_qty_equals_held_minus_today_buys=True,settled_flag_consistent=True,saved_gate_equals_reconstructed_net_all_rows=True,daily_aggregates_match_final_round_table=True,scope='Independently read original gate and exported daily/round files; verified aggregation and timing fields, not an independent recomputation of all 115079 price/fee valuations.')
qa['completed_utc']=datetime.now(timezone.utc).isoformat();save('FINAL_QA.json',qa)
rd=O/'READOUT.md';s=rd.read_text();s=s.replace('2022的主要损失不是已经赚到大段利润后全部回吐，而是大量回合没有正收盘净权益，或虽一度为正、仍未达到自身初始计划风险1R。','按固定1R尺度，2022亏损金额的91.07%来自从未正收盘或最大正净权益仍不足1R的回合；已经≥1R后最终亏损占8.93%。不能因此说其余回合没有利润空间，或把后验分类当作失败原因的因果证明。')
needle='## 5. ADD前后与重复试错\n';s=s.replace(needle,needle+'\n原ADD合同要求严格正净利润，并不要求先达到1R。因此ADD前未到1R不是违规，也不能据此认定新增1R加仓门会改善。1R仅是本次后验固定描述尺度。\n')
s=s.replace('2022发生ADD的891轮中，', '2022账本总额拆分为PROBE交易净额−1,003,380.64、ADD交易净额−233,948.59、已确认NET80 +49,871.57元，主要净损失仍在初层。\n\n2022发生ADD的891轮中，')
s=s.replace('及三个只读研究脚本','及只读研究脚本');s=s.replace('- STOCK_ATTRIBUTION.csv：全部个股集中度，可回溯全部回合。','- STOCK_ATTRIBUTION.csv、CONCENTRATION_COMPLETE_PARTITIONS.json：全部个股、固定top10/top20及互斥剩余项，逐表完整守恒。')
s=s.replace('- 复用了原保存账本、gate及既有日期费用纯函数，','- 父任务另独立复核了2862唯一回合、115079唯一round/day、T+1库存字段、next_open时序、保存gate及全部每日峰值聚合；该复核不冒称再次重算全部价格费用。\n- 复用了原保存账本、gate及既有日期费用纯函数，')
rd.write_text(s)
# Keep original protocol and all original inputs byte-identical.
H={**j('SOURCE_HASHES_STAGE1.json'),**j('SOURCE_HASHES_STAGE2.json')};assert all(sha(path)==h for path,h in H.items())
save('OUTPUT_HASHES.json',{x.name:sha(x) for x in sorted(O.iterdir()) if x.is_file() and x.name!='OUTPUT_HASHES.json'})
print('COMPLETE',qa['source_hashes_checked'],'source hashes;',qa['exhaustive_partitions_checked']+qa['complete_concentration_partitions_checked'],'complete partitions')
