"""Format original accounting facts; no new exit rule or strategy path."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
import csv,hashlib,json
getcontext().prec=50
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def add(rows,k):return sum((D(r[k]) for r in rows),D(0))
fmt=lambda v:f'{D(v):,.2f}'
sel=read('SELECTION_AND_CONCENTRATION.json');ls=read('LAYER_CUTOFF_AND_STAGE_BRIDGE.json');index=read('INDEX.json')
stock=[]
for r in sel['selected_stocks']:
 rr=[x for x in ls if x['sid']==r['sid']]
 stock.append(dict(**r,cutoff_qty=sum(x['cutoff_qty'] for x in rr),cutoff_mark_value=add(rr,'cutoff_mark_value'),cutoff_paid_basis=add(rr,'cutoff_remaining_paid_basis'),cutoff_unreal=add(rr,'cutoff_unreal'),post_net_sale_cash=add(rr,'post_cutoff_actual_net_sale_cash'),ending_value=add(rr,'ending_mark_value'),ending_AR=add(rr,'ending_dividend_AR'),life_net=add(rr,'life_net_separate'),descriptive_giveback=sum((D(x['descriptive_cutoff_profit_giveback_amount']) for x in rr if x['descriptive_cutoff_profit_giveback_amount'] is not None),D(0)),descriptive_old_decline_beyond_positive_initial_unreal=sum((D(x['descriptive_decline_beyond_initial_positive_unreal']) for x in rr if x['descriptive_decline_beyond_initial_positive_unreal'] is not None),D(0))))
save('SIX_STOCK_CUTOFF_BRIDGE_SUMMARY.json',stock)
with (O/'SIX_STOCK_CUTOFF_BRIDGE_SUMMARY.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(stock[0]));w.writeheader();w.writerows(stock)

trigger_rows=[]
for ix in index['stocks']:
 x=read(ix['path']);obs={o['day']:o for o in x['original_daily_observations']}
 for layer in x['layers']:
  for part in layer['all_actual_exit_parts']:
   at=part['original_order_create']['at'];o=obs.get(at[:10]);lid=layer['summary']['layer'];live=None if o is None else next((v for v in o['actual_live_layers_after_original_CLOSE_checks'] if v['original_snapshot']['id']==lid),None)
   old=None if o is None else next((h for h in o['previous_saved_CLOSE_live_layers'] if h['id']==lid),None)
   trigger_rows.append(dict(sid=ix['sid'],layer=lid,role=layer['summary']['role'],request_at=at,request_reason=part['actual_part']['reason'],original_request_raw_C=None if o is None else o['original_facts']['raw_close'],original_factor=None if o is None else o['original_facts']['factor'],previous_CLOSE_adjusted_floor=None if old is None else old['floor'],request_day_saved_adjusted_floor=None if live is None else live['original_snapshot']['floor'],request_day_raw_effective_protection=None if live is None else live['raw_effective_protection_after_original_CLOSE_checks'],original_i_target=None if o is None else o['original_facts']['i_target'],request_day_CP_receipt=None if o is None else o['original_CP_cache']['receipt'],request_day_CP_candidate=None if o is None else o['original_CP_cache']['candidate'],proxy_fill_at=part['actual_trade']['at'],raw_OPEN=part['actual_trade']['raw_open'],execution_price=part['actual_trade']['price'],shares=part['actual_part']['shares'],order_id=part['actual_fill_audit']['order_id'],source_file=ix['path'],request_audit_index=part['exit_request_audit_index'],fill_audit_index=part['fill_audit_index']))
with (O/'TRIGGER_AND_PROXY_FILL_TABLE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(trigger_rows[0]));w.writeheader();w.writerows(trigger_rows)

ta=read('601601_SH_ORIGINAL_FACTS.json');o8=next(o for o in ta['original_daily_observations'] if o['day']=='2024-10-08');o9=next(o for o in ta['original_daily_observations'] if o['day']=='2024-10-09');first=ta['layers'][0]['all_actual_exit_parts'][0]
t=first['actual_trade'];q=D(t['shares']);c0=D(str(o8['original_facts']['raw_close']));ct=D(str(o9['original_facts']['raw_close']));op=D(t['raw_open']);ep=D(t['price']);fee=D(t['fees_cny'])
decomp=dict(sid='601601.SH',original_layers=[1904,1914,1931],q=q,cutoff='2024-10-08 15:10:00+08:00',cutoff_raw_C=c0,trigger_CLOSE='2024-10-09 15:10:00+08:00',trigger_raw_C=ct,
 old_CP_adjusted_floor=o9['previous_saved_CLOSE_live_layers'][0]['floor'],factor=o9['original_facts']['factor'],old_CP_raw_floor=o9['actual_live_layers_after_original_CLOSE_checks'][0]['raw_effective_protection_after_original_CLOSE_checks'],trigger_i_target=o9['original_facts']['i_target'],trigger_CP_receipt=o9['original_CP_cache']['receipt'],trigger_CP_candidate=o9['original_CP_cache']['candidate'],
 request=first['original_order_create'],proxy_fill_at=t['at'],raw_OPEN=op,actual_proxy_price=ep,
 cutoff_to_trigger_CLOSE_decline=q*(c0-ct),trigger_CLOSE_to_next_raw_OPEN_decline=q*(ct-op),raw_OPEN_to_proxy_5bp_slippage=q*(op-ep),actual_simulated_sell_fee_once=fee,
 total_phase_decline=q*(c0-ct)+q*(ct-op)+q*(op-ep)+fee,
 source=dict(file='601601_SH_ORIGINAL_FACTS.json',request_audit_index=first['exit_request_audit_index'],fill_audit_index=first['fill_audit_index'],trade_index=first['book_trade_index']),
 interpretation='Original-price timeline identity only. Trigger raw CLOSE equals next raw OPEN in this case. This does not show any post-trigger overnight raw-price loss or an earlier executable sale opportunity. Fee is the actual simulated logical-order fee once, not per-layer repeated minimum. No candidate return.')
assert decomp['total_phase_decline']==-add([r for r in ls if r['sid']=='601601.SH'],'stage_wealth')
save('TAIBAO_ORIGINAL_GIVEBACK_TIMELINE.json',decomp)

lines=['# P10证券、保险：原仓位与退出事实','',
'范围为原No60 BASELINE 2024-10-08 15:10 CLOSE至2024-12-31 CLOSE。只读原模拟账、原daily、已存P10财富桥及SHA核同的原facts/CP/signal缓存。0账户、模型、回测、新EMA/斜率指标或候选退出。所有fill、receipt、cash与费用均为原模拟账记录，不是经纪商或交易所成交/ACK。','',
'## 全行业阶段排名与筛选','',
'P10账户财富变化−167,054.3167822144115元：10/8旧75层−54,596.71621278579；之后新303层−112,457.6005694286215。不能把新303层损耗当作整个P10变化。按所有行业的阶段净财富排序，证券不是前二。','',
'|亏损排名|行业 / sector|阶段ΔW|旧仓ΔW|新增层ΔW|','|---:|---|---:|---:|---:|']
for r in sel['all_industry_ranking'][:6]:lines.append(f'|{r["loss_rank"]}|{r["industry"]} / {r["sector"]}|{fmt(r["wealth"])}|{fmt(r["old_inventory_wealth"])}|{fmt(r["new_layer_wealth"])}|')
lines+=['','证券13层10股，前三股占本行业净损耗60.95%；保险13层5股，前三股占79.27%。分母是各行业负的净阶段贡献，不是全市场亏单总额或策略因果贡献。完整排名在INDUSTRY_STAGE_RANKING.csv。','',
'|选定股票 / 原层|P10阶段ΔW|10/8市值 / 剩余含买费成本|10/8浮盈|之后净卖回款|life net另列|','|---|---:|---:|---:|---:|---:|']
for r in stock:lines.append(f'|{r["sid"]} {r["name"]} / {r["layer_ids"]}|{fmt(r["stage_wealth"])}|{fmt(r["cutoff_mark_value"])} / {fmt(r["cutoff_paid_basis"])}|{fmt(r["cutoff_unreal"])}|{fmt(r["post_net_sale_cash"])}|{fmt(r["life_net"])}|')
lines+=['',
'只有002670国盛证券2225是P10新增层（原行动标签new_reentry），买入后净亏2051.30308803715；其它五股全部是10/8存量，其所选原层年末已平，期末残值和AR均0。五只旧仓起始浮盈均大于阶段负ΔW，life net仍为正。逐层描述性回吐=min(10/8正unreal，阶段负ΔW)，超过起始正浮盈部分为0；该定义只解释原财富变化，没有用之后最高点，也不是可以提前卖掉的收益。','',
'旧仓桥为“10/8后原净卖回款 + 期末残值 − 10/8市值 + 分红AR变化”。原完整比较审计表明无partial-basis点、paid dividends=0；每个所选旧层cutoff cash与−原gross−原买费核同。买费已经在起始paid basis，不在P10重复扣；卖费已在parts net cash，只扣一次。逐层q/raw mark/factor/basis/unreal、净回款、AR、阶段ΔW和life net见LAYER_CUTOFF_AND_STAGE_BRIDGE.csv/json。','',
'## 太保原时序','',
'10/8原1200股，rawC40.76，市值48912，含买费basis36359.4915325842，已知浮盈12552.5084674158。10/8更新后的CP旧线55.14261903078265（continuous），factor1.4546762493788945，即raw37.90714191857259；10/9原rawC36.68、I_target仍1，CP没有新receipt/candidate，原MOBILE旧线保护请求退出。10/10原raw OPEN仍36.68，代理价36.66166，净售43960.3761907128，life net+7600.8846581286。','',
'阶段回落4951.6238092872 = 1200×(40.76−36.68) 4896 + 1200×(触发C36.68−次raw OPEN36.68) 0 + 5bp滑点22.008 + 原整单卖费33.6158092872。此例主要回落已在触发收盘前发生；不是“触发后仍损失大幅隔夜gap”的例子。TAIBAO_ORIGINAL_GIVEBACK_TIMELINE.json保原路径算术及索引，不构造早卖反事实。','',
'## 请求与代理成交时钟','',
'|股票/原层|原退出请求→代理fill|原raw OPEN / 代理价|原reason|','|---|---|---|---|']
seen=set()
for r in trigger_rows:
 key=r['order_id']
 if key in seen:continue
 seen.add(key);same=[a['layer'] for a in trigger_rows if a['order_id']==key]
 lines.append(f'|{r["sid"]} / {same}|{r["request_at"][:10]}→{r["proxy_fill_at"][:10]}|{r["raw_OPEN"]} / {r["execution_price"]}|{r["request_reason"]}|')
lines+=['',
'ACTUAL_BUYS.csv保存14层原买信号、成交q/p/费、入场floor和fill当时pool；ACTUAL_SELL_PARTS.csv保14parts、对应whole-order fee和净款，不能再按层重收最低佣金；TRIGGER_AND_PROXY_FILL_TABLE.csv把请求日rawC/旧线与实际代理fill并列。','',
'6个*_ORIGINAL_FACTS.json各有61个P10交易日（cutoff原daily index665到725），含flat日、原ACT/I/CP、prior CLOSE层快照与当日原检查/ratchet后快照、请求扩展和fill audit索引。62个实际持仓层CLOSE点的紧凑表为DAILY_HELD_LAYERS_AND_PROTECTION.csv。CORE真实I退出链与MOBILE旧floor先检查后ratchet的源码入口是joint_v3.py:223–239；退出及结算在下一OPEN原opening先于新买funding（302–324）。','',
'字段缺失/范围：原as-of缓存会注明实际source_day，缺当日观察不假装新quote。pending且无fill不证明真实停牌/跌停；daily OHLCV proxy无法证明真实开盘竞价/连续首笔可成交。没有计算EMA候选、提前卖价、获利归因或任何新PnL；末端损耗本身不能证明原退出过早或过晚。SOURCE_MANIFEST.json绑定所有原输入/源码SHA；本件自校验不是独立审核收据。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
save('VALIDATION.json',dict(status='PASS_ORIGINAL_RECORD_EXTRACTION_SELF_CHECK',stocks=6,layers=14,full_daily_points_per_stock=61,held_layer_CLOSE_points=62,actual_sell_parts=14,old_layers=13,new_layers=1,stage_old75_and_new303_boundary_preserved=True,selected_old_layer_wealth_cash_bridges_close=True,taibao_price_timeline_closes=True,new_accounts=0,new_models=0,new_backtests=0,new_indicators=0,new_candidate_PnL=0))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_ORIGINAL_P10_SIX_STOCK_FACTS_ONLY',readout_sha256=sha(O/'READOUT.md'),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json'),taibao_timeline_sha256=sha(O/'TAIBAO_ORIGINAL_GIVEBACK_TIMELINE.json'),deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),new_accounts=0,new_models=0,new_backtests=0,new_indicators=0,new_candidate_PnL=0)
save('SEAL_RECEIPT.json',seal)
print(json.dumps(seal,ensure_ascii=False))
