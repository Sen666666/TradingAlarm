"""Read frozen output and sealed local parquet only. No strategy imports/replay/network."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,sys
sys.dont_write_bytecode=True
import pandas as pd
import audit_saved_outputs as au
O=Path(__file__).resolve().parent;R=O.parent;Z=D(0);CLOSE='2024-10-23';OPEN='2024-10-24';SID='000158.SZ';RID='000158.SZ|2|2024-09-23'
read=au.read;sha=au.sha;near=au.near;sm=au.sm
paths={'M7':R/'mainline_m7_cash_batch_design_v6/once_20260630','V11':R/'mainline_candidate_v11_structural_maturity_entry_execution_fix_v2/once_20250120'}
seal=read(O/'FINAL_AUDIT_SEAL.json')
for n,h in seal['files'].items():assert sha(O/n)==h,('audit_changed',n)
sources=read(paths['V11']/'SOURCE_HASHES.json');mp=next(p for p in sources if p.endswith('/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'));m=next(x for x in read(mp) if x['symbol']==SID)
rawpath=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));cppath=m['refs']['CP1']
for p in [mp,rawpath,cppath]:assert sha(p)==sources[p]
raw=pd.read_parquet(rawpath);cp=pd.read_parquet(cppath)
for d in [CLOSE,OPEN]:assert raw.at[pd.Timestamp(d),'symbol']==SID
rawclose=D(str(raw.at[pd.Timestamp(CLOSE),'raw_close']));rawopen=D(str(raw.at[pd.Timestamp(OPEN),'raw_open']));cf=D(str(raw.at[pd.Timestamp(CLOSE),'adjustment_factor']));of=D(str(raw.at[pd.Timestamp(OPEN),'adjustment_factor']))
prices=dict(raw_close=rawclose,close_factor=cf,adjusted_close=rawclose*cf,raw_open=rawopen,open_factor=of,adjusted_open=rawopen*of,raw_path=rawpath,raw_sha256=sources[rawpath],cp_path=cppath,cp_sha256=sources[cppath])
rules=read(au.RULES);proxies=read(au.PROTOCOL)['approved_proxy_ids']
def group(rs,bysector=False):
 g={}
 for r in rs:
  if r['q']<=0:continue
  k=(r['allocation_phase'],r['kind'],r['event_id'].split('|')[0] if bysector else 'ALL')
  if k not in g:g[k]=dict(allocation_phase=k[0],kind=k[1],sector51=k[2],count=0,cost=Z,sids=[])
  g[k]['count']+=1;g[k]['cost']+=D(r['cost']);g[k]['sids'].append(r['sid'])
 return list(g.values())
out=dict(verdict='PASS_SAVED_FUNDING_PATH',scope='Observed development window. Frozen 10/23 CLOSE plan and actual 10/24 OPEN only. No strategy replay or changes; no per-yuan receiver attribution.',prices=prices,accounts={})
for label,path in paths.items():
 names=['ORDERS','HOLDINGS','CAPITAL_LOTS','CP_EVENTS','TRANSFERS','REFERENCE_DAILY','SECTOR_DAILY','EQUITY_EVENTS','FUNDING_REQUESTS']
 outputhash=read(path/'OUTPUT_HASHES.json')
 for n in names:assert sha(path/(n+'.json'))==outputhash[n+'.json']
 a={n:read(path/(n+'.json')) for n in names};lots=[x for x in a['CAPITAL_LOTS'] if x['day']==CLOSE and x['round_id']==RID];holds=[x for x in a['HOLDINGS'] if x['day']==CLOSE and x['round_id']==RID]
 assert len(lots)==len(holds)==4
 marked=sum((D(x['cash_delta']) for x in a['ORDERS'] if x['round_id']==RID and x['day']<=CLOSE),Z)+sm(holds,'market_value')+sum((D(x['receivable_delta']) for x in a['EQUITY_EVENTS'] if x.get('round_id')==RID and x['day']<=CLOSE and D(x.get('receivable_delta','0'))>0),Z)
 qty=sum(x['qty'] for x in holds);liq=marked-qty*rawclose*D('.0005')-au.fee_calc(rules,proxies,SID,CLOSE,qty,rawclose*D('.9995'),'sell')
 for l in lots:near(liq,l['round_net'],'whole_round_net');assert l['M']==0 and l['stock_state']==0 and l['sector_state']==1 and l['current_winner']=='False' and l['confirmed_history'] is True
 checks=[]
 for h in holds:
  if h['kind']!='ADD':continue
  e=next(x for x in a['CP_EVENTS'] if x.get('cp_id')==h['cp_id'] and x['event']=='CREATED_AFTER_SEED');floor=D(e['candidate']);bar=cp.loc[pd.Timestamp(e['day'])]
  assert bool(bar['receipt']) and D(str(bar['candidate']))==floor
  effective=D(h['protection_signal']);assert rawclose*cf>effective and rawopen*of>effective and effective>=floor
  margins=[]
  for t,z in raw.loc[e['day']:OPEN].iterrows():
   day=t.strftime('%Y-%m-%d');factor=D(str(z['adjustment_factor']))
   if day>e['day']:margins.append(D(str(z['raw_open']))*factor-floor)
   if day<=CLOSE:margins.append(D(str(z['raw_close']))*factor-floor)
  assert min(margins)>0
  checks.append(dict(lot_id=h['lot_id'],qty=h['qty'],original_cp_id=h['cp_id'],original_cp_CLOSE=e['day'],original_cp_floor=floor,effective_protection_floor=effective,effective_floor_unbroken_at_decision_close=True,effective_floor_unbroken_at_execution_open=True,original_floor_min_verified_open_close_margin=min(margins),intraday_lows_not_an_execution_rule=True))
 trans=a['TRANSFERS'];close=next(x for x in trans if x['day']==CLOSE and x['event']=='DEMAND_PLAN');op=next(x for x in trans if x['day']==OPEN and x['event']=='TRANSFER_CASH');fund=next(x for x in trans if x['day']==OPEN and x['event']=='RECEIVER_FUNDING')
 refs=[x for x in a['REFERENCE_DAILY'] if x['day']==CLOSE];plans=[x for x in trans if x['day']==CLOSE and x.get('sid')==SID];execs=[x for x in trans if x['day']==OPEN and x.get('sid')==SID]
 sales=[x for x in a['ORDERS'] if x['day']==OPEN and x['sid']==SID and x['side'].startswith('SELL')]
 buys=[x for x in a['ORDERS'] if x['day']==OPEN and x['side'].startswith('BUY')];donors=[x for x in a['ORDERS'] if x['day']==OPEN and x.get('transfer_rank')]
 positive=[r for r in op['receivers'] if r['q']>0];assert len(positive)==len(buys)
 for rr in positive:
  oo=[x for x in buys if x['sid']==rr['sid'] and x['side']=='BUY_'+rr['kind']];assert len(oo)==1 and oo[0]['qty']==rr['q'];near(-D(oo[0]['cash_delta']),rr['cost'],'actual_receiver_cost')
 near(-sm(buys,'cash_delta'),op['M_desired_cost'],'all_actual_buys');near(sm(donors,'cash_delta'),op['net_cash_released'],'all_actual_donors');near(sum((D(x['cost']) for x in close['receivers']),Z),close['M_desired_cost'],'close_selected_cost')
 near(sum((D(x['cost']) for x in positive if x['allocation_phase']!='EVENT'),Z),fund['M_actual_buy_cost'],'non_event_actual_buy_cost')
 acc=dict(source_output_hashes={n+'.json':outputhash[n+'.json'] for n in names},stock_sector_state=next(x for x in a['SECTOR_DAILY'] if x['day']==CLOSE and x['sector51']=='软件与IT服务'),round_marked_net=marked,round_net_liquidation=liq,lot_classification=lots,CP_floor_checks=checks,Changshan_plans=plans,Changshan_executions=execs,Changshan_actual_sales=sales,Changshan_net_released=sm(sales,'cash_delta'),Changshan_qty_sold=sum(x['qty'] for x in sales),independent_D=sum((D(x['D']) for x in refs),Z),independent_D_by_sector=[dict(sector51=x['sector51'],D=x['D']) for x in refs if D(x['D'])>0],reference_header={k:refs[0][k] for k in ['budget_before_event','event_reserve_total','budget','stress','outside_fixed','expansion_budget','unallocated_expansion_budget']},close_plan=close,open_cash=op,open_funding=fund,close_receivers=group(close['receivers']),open_receivers=group(op['receivers']),open_receivers_by_sector=group(op['receivers'],True),actual_buy_orders=buys,actual_donor_orders=donors,ADD_funding_rechecks=[x for x in a['FUNDING_REQUESTS'] if x['day']==OPEN and x['event']=='ADD'],planned_donor_lots=close['planned_donors'],actual_donor_orders_count=len(donors))
 out['accounts'][label]=acc
b=out['accounts']['M7'];v=out['accounts']['V11'];assert b['Changshan_qty_sold']==1900 and v['Changshan_qty_sold']==0
out['V11_minus_M7']=dict(independent_D=v['independent_D']-b['independent_D'],close_selected_cost=D(v['close_plan']['M_desired_cost'])-D(b['close_plan']['M_desired_cost']),close_gap=D(v['close_plan']['initial_gap'])-D(b['close_plan']['initial_gap']),open_actual_buy_cost=D(v['open_cash']['M_desired_cost'])-D(b['open_cash']['M_desired_cost']),open_gap=D(v['open_cash']['initial_gap'])-D(b['open_cash']['initial_gap']),open_actual_donor_net=D(v['open_cash']['net_cash_released'])-D(b['open_cash']['net_cash_released']))
out['conclusion']='Same original donor policy. V11 Changshan ADD remained eligible NON_MAINLINE_EXPANSION; no direct protection was added. Fewer/different new MATURE SEED requests reduced aggregate financing demand and Changshan was absent from the selected donor plan. Differences include prior actual allocations; one-day counterfactual causality and per-yuan matching are not claimed.'
au.save('CHANGSHAN_1024_FUNDING_APPENDIX',out)
lines=['# 常山北明10/24资金路径附录','', '## 结论','', '原M7卖出的是仍盈利、CP保护未破的历史确认ADD层，但当晚M=0，旧规则将其作为NON_MAINLINE_EXPANSION融资。V11没有改变这项资格，也没有直接保护赢家；少/不同的新MATURE票改变了融资需要与被选中的donor队列。以下只复核已提交订单，不作逐元去向配对或单日反事实模拟。','', '## 10/23收盘已知事实','',f'- 两版stock=0、sector=1、M=0；软件行业Q=1、S=0、F=0、E=0.27461460298863405。历史已确认，但规则current_winner=False，因为当前M不是1。不能把后来10/24收盘状态倒灌到本次开盘决策。',f'- 原M7整轮清算净利{b["round_net_liquidation"]:,.2f}元；V11为{v["round_net_liquidation"]:,.2f}元，均已从实际订单和持仓独立重算。',f'- 原M7有SEED700股固定，ADD分别900、1500、100股可供资；V11 SEED700股固定，ADD900、1500、1000股同样可供资。两版均无未知/退出锁定。','', '## 原CP及融资成交','']
for x in b['CP_floor_checks']:lines.append(f'- lot {x["lot_id"].split("|")[-1]}：原CP {x["original_cp_CLOSE"]}，floor {x["original_cp_floor"]}，10/23有效保护已上移至{x["effective_protection_floor"]}；直到10/24 OPEN的原CP后续OPEN/CLOSE均未破。')
lines += [f'- 10/23 raw CLOSE={rawclose}、复权CLOSE={rawclose*cf}；10/24 raw OPEN={rawopen}、复权OPEN={rawopen*of}，都高于有效floor。只检查规则使用的OPEN/CLOSE，不声称盘中最低价保护。', '- M7 donor rank67计划900股、实际卖900；rank74计划1500、实际卖1000后缺口归零；rank76计划100、实际0（RECEIVER_GAP_ZERO）。',f'- 实际卖价21.998995，净供资合计{b["Changshan_net_released"]:,.8f}元。V11该日无常山donor计划和卖单。','', '## 整体需求及现金','', '| 项目 | M7 | V11 |','|---|---:|---:|']
metrics=[('独立需求D',b['independent_D'],v['independent_D']),('CLOSE已选receivers总cost',D(b['close_plan']['M_desired_cost']),D(v['close_plan']['M_desired_cost'])),('CLOSE融资缺口',D(b['close_plan']['initial_gap']),D(v['close_plan']['initial_gap'])),('CLOSE计划donor层数',b['planned_donor_lots'],v['planned_donor_lots']),('OPEN实际买款含EVENT',D(b['open_cash']['M_desired_cost']),D(v['open_cash']['M_desired_cost'])),('OPEN融资缺口',D(b['open_cash']['initial_gap']),D(v['open_cash']['initial_gap'])),('OPEN实际donor净供资',D(b['open_cash']['net_cash_released']),D(v['open_cash']['net_cash_released'])),('OPEN买后现金',D(b['open_funding']['cash_after_all_buys']),D(v['open_funding']['cash_after_all_buys']))]
for name,x,y in metrics:lines.append(f'| {name} | {x:,.2f} | {y:,.2f} |')
lines += ['', 'D是独立需求、非已选成交买款。CLOSE估算与OPEN重检也不混用。M_actual_buy_cost在RECEIVER_FUNDING中排除EVENT，本表另列实际全部买款。','', '## receiver实际用途','']
for label in ['M7','V11']:
 a=out['accounts'][label];lines.append(f'### {label}')
 for g in a['open_receivers']:lines.append(f'- {g["allocation_phase"]} {g["kind"]}：{g["count"]}笔，实际买款{g["cost"]:,.2f}元。')
 for g in a['open_receivers_by_sector']:
  if g['allocation_phase']=='MATURE' and g['kind']=='SEED':lines.append(f'  - {g["sector51"]}：{g["count"]}笔，{g["cost"]:,.2f}元。')
lines += ['', '- CLOSE两版都计划3个ADD：金刚光伏300093、同有科技300302、神州泰岳300002。OPEN最终只成交金刚光伏1200股，买款27,020.63426535元；另两笔重检未成交原因见JSON的ADD_funding_rechecks。EVENT均8笔、买款70,026.45934450135元。', '- 因而该OPEN实际买款差273,492.585915278034元全部落在新MATURE SEED集合和数量变化，而非当日ADD或EVENT变化。融资净供资少263,565.25331756262元，不能把差额全部指给常山，也不能说常山卖款专门买了某一只票。', '- 常山最后净利差包含先前ADD数量、此前融资及之后退出的全部路径，不能把整段约2.50万元优势全归给10/24没卖1900股。三只贡献股合计优势大于账户优势，其他真实路径抵消了相当部分。','', '## 来源及限制','', '- 精确逐lot、原CP、原始source哈希、CLOSE/OPEN receivers全名单、实际买卖订单及行业汇总见同名JSON。', '- 源和结果均只读，未改引擎或基线、未加载Data、未跑策略、未联网。全部已观察开发窗，非OOS/PIT/实盘证明。']
(O/'CHANGSHAN_1024_FUNDING_APPENDIX.md').write_text('\n'.join(lines)+'\n')
seal['files']={p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['FINAL_AUDIT_SEAL.json','AUDIT_SEAL.json']}
(O/'FINAL_AUDIT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(verdict=out['verdict'],delta=out['V11_minus_M7'],receivers={k:a['open_receivers'] for k,a in out['accounts'].items()},source_raw=rawpath),ensure_ascii=False,default=str))
