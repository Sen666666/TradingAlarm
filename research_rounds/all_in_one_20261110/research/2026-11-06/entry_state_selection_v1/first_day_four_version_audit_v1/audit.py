from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;U=R/'unified_probe_account_contract_v1';N=U/'first_day_check_v2';B=R/'account_comparison_continuous_v1/no_loss_add_v1/run_1200000/pair';M=R/'m3_ab_shared_probe_v1/known_evidence_union_diagnostic_v1/economic_run_2022_once';hs={}
def read(p,gz=False):
 p=Path(p);hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.load(gzip.open(p,'rt')) if gz else json.loads(p.read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str))
a=read(N/'pair/PVR.json.gz',True);old=read(B/'PVR.json.gz',True);status=read(U/'STATUS.json');ad=read(N/'ADMISSION_EVENTS.json');dec=next(x for x in a['decisions'] if x['at'].startswith('2022-01-04'));names={'002246.SZ':'北化股份','000999.SZ':'华润三九','002603.SZ':'以岭药业','601933.SH':'永辉超市'};closes={'002246.SZ':D('10.11'),'000999.SZ':D('36.68'),'002603.SZ':D('19.55'),'601933.SH':D('4.29')};ranks={};p=N/'pair/rank-policy.jsonl.gz';hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
with gzip.open(p,'rt') as f:
 for line in f:
  x=json.loads(line)
  if x['day']=='2022-01-04' and x['sid'] in names:ranks[x['sid']]=x
rows=[];original=[]
for t in a['trades']:
 sid=t['security_id'];x=next(x for x in ad if x['sid']==sid);cost=D(t['gross_cny'])+D(t['fees_cny']);r=ranks[sid];rows.append(dict(sid=sid,name=names[sid],signal_day='2022-01-04',entry_day='2022-01-05',role=x['role'],pool=x['pool'],qty=t['shares'],proxy_buy=t['price'],gross=t['gross_cny'],buy_fee=t['fees_cny'],buy_cash=str(cost),PVR=r['PVR'],candidate_ordinal=r['final_slot']+1,candidate_total=294,H1_original_rank=r['original_H1_rank'],signal_floor_raw=x['floor'],fee_inclusive_plan_risk=x['fee_inclusive_risk'],probe_nominal_risk_after=x['probe_after'][1],Jan5_raw_close=str(closes[sid]),Jan5_mark_after_buy_fee=str(D(t['shares'])*closes[sid]-cost),new_round_realized_result='NOT_RUN_AFTER_FIRST_DAY'))
 bu=next(v for v in old['trades'] if v['security_id']==sid and v['side']=='buy');lid=bu['layer'];sells=[(v,part) for v in old['trades'] if v['side']=='sell' for part in v.get('parts',[]) if part['layer']==lid];net=sum((D(part['net_cash']) for v,part in sells),D(0))-D(bu['gross_cny'])-D(bu['fees_cny']);original.append(dict(sid=sid,name=names[sid],old_buy=bu,old_sells=[dict(trade=v,part=part) for v,part in sells],old_first_layer_cash_net=str(net),old_first_layer_return=str(net/(D(bu['gross_cny'])+D(bu['fees_cny']))),warning='Old baseline account reference only; not the new unified-probe account future outcome'))
pd.DataFrame(rows).to_csv(O/'UNIFIED_JAN5_FOUR.csv',index=False);save('OLD_BASELINE_FOUR_REFERENCE.json',original)
gross=sum(D(x['gross']) for x in rows);fees=sum(D(x['buy_fee']) for x in rows);assert gross==D('30584.284500') and fees==D('22.7128260351500');save('AMOUNT_RECONCILIATION.json',dict(gross=str(gross),buy_fees=str(fees),cash=str(gross+fees),first_day_NAV=a['ending_NAV'],future_result=None,annual_return=None,annual_max_drawdown=None,source_status=status))
archives=read(M/'ARCHIVES.json');rr=read(M/'ROUND_REPORT.json');jj=read(M/'EXACT_TRADE_JOURNAL.json');mrows=[]
for r in rr:
 if not str(r.get('entry_day','')).startswith('2022-01-06'):continue
 rid=r['round_id'];x=archives[rid];tr=[v for v in jj if v['round_id']==rid];cash=sum((D(w['cash_delta']) for v in tr for w in v['report_only_allocations'].values()),D(0));assert cash==D(r['whole_round_NET80']);mrows.append(dict(sid=r['sid'],name=x['name'],signal_day='2022-01-05',entry_day='2022-01-06',event=x['event_type'],industry=x['industry'],N=x['sector_N'],K=x['sector_K'],n=x['sector_M3_n'],diffusion=x['sector_delta3'],PVR=x['PVR_score'],industry_feasible_rank=x['original_feasible_rank'],first_qty=x['entry_q'],first_proxy_price=x['entry_price'],net=r['whole_round_NET80'],return_fraction=r['conditional_return_on_actual_buy_cash'],status=r['status'],actual_trades=tr))
assert len(mrows)==4;save('M3_JAN6_DIFFERENT_FOUR.json',mrows)
text='''# 两套“首日4只”的版本与现金核对

## 用户所问52只缩为4只：统一probe首日工程版

确切来源 unified_probe_account_contract_v1，implementation SHA 755547e59cce871762523167bf21006033260291d6f0e613876d5c063aa5bc02。
仅运行2022年1月4日信号与1月5日执行/收盘。STATUS明确 full_window_run=false、active_account_run=false、full_window_paused_for_sector_breadth_contract=true。它没有接入成员M3广度，不是已经完成2022全年验证的完整新策略。

货款30,584.284500元 + 买费22.71282603515元 = 实际现金支出30,606.99732603515元。30,584.28与30,606.9973是货款和含费支出的区别，不是账不平。

|股票|数量|代理买价|含费支出|原PVR|294候选顺位|原保护价|1/5收盘账面盈亏*|
|---|---:|---:|---:|---:|---:|---:|---:|
'''
for x in rows:text+=f"|{x['name']} {x['sid']}|{x['qty']}|{float(x['proxy_buy']):.6f}|{float(x['buy_cash']):.2f}|{x['PVR']:.3f}|{x['candidate_ordinal']}|{float(x['signal_floor_raw']):.4f}|{float(x['Jan5_mark_after_buy_fee']):+.2f}|\n"
text+='''
*市值减实际买入现金，已含买费、尚未扣假设卖费，未平仓，不能叫最终盈利。首日NAV 1,198,447.002674元，较120万元−0.129416%。这不是全年收益或全年最大回撤。

## 当时选入合同

原Q检查市场可买、I/E0就绪且有效、股票/行业身份与H1可用、市值大于100亿元、行业E0等。CORE要原当天i_buy；MOBILE要存续I资格与真实fresh CP。PVR只排序，不替代资格；实际trade中的pvr字段仍是旧H1，不可拿它当原PVR。

原PVR：r=ln(C/Cprev)，s=max(1e−8,1.4826×严格前63绝对收益中位)，B=严格前21金额中位；u=tanh(r/s)，b=tanh(ln(A/B))，e=u(1+0.5|u|b)；E为最近21个e的0.9衰减归一加权，分数=50+50tanh(2E)。未知原槽保留，同股CORE先于MOBILE。

所有空仓首入都改走probe，首仓名义不超过决策NAV2%，含买卖费/滑点的计划保护风险不超过0.25%，共享probe名义风险不超过当时预算NAV0.5%，其他原现金/行业限制保留。名义保护风险不是最大亏损保证。

北化、三九、以岭当日I_buy=true、G=4，CORE按原I保护线入场。永辉I_buy=true、G=2、fresh CP=true；它的CORE也被probe_risk拒绝，但MOBILE使用更近的max(I,CP)保护线，100股才可放进余量。

前三股把probe名义风险占到5979.0765元，约6000元风险池只剩20.9元；永辉100股新增名义风险约20.0004元，入后5999.07694元。永辉在294候选中第115，并非评分前4。这4只是原顺序和共享风险余量的结果，不能称已选出最好的4只。

原行业E0/CP授权不等于“多数成员右侧”。按已有研究广度，北化行业M3过、两只中药M3过，永辉零售行业为UNKNOWN；这只是诊断，因为该工程版没有使用M3硬门。

## 四股旧账户后续，仅作参考

以下取本工程版明示baseline no_loss_add_v1/run_1200000/pair/PVR.json.gz的实际模拟现金，均不是新统一probe账户的后续结果。

|股票|旧买入|旧卖出|旧首层费后净额|旧首层回报|
|---|---|---|---:|---:|
'''
for x in original:
 bu=x['old_buy'];sell=x['old_sells'][-1]['trade'];text+=f"|{x['name']}|{bu['at'][:10]}，{bu['shares']}股，{bu['price']}元|{sell['at'][:10]}，{sell['price']}元|{float(x['old_first_layer_cash_net']):+.2f}|{float(x['old_first_layer_return'])*100:+.2f}%|\n"
text+='''
前三股旧首次买入日/数量/价格与新首日相同，但后续资金、持仓、晋升、追加路径可能改变，所以仍不能移植。永辉旧账1月5日没有买；旧首笔是1月14日5200股，新版1月5日只有100股，差异尤其明显。不能把旧永辉亏损当新100股亏损。

能判断：这4笔符合已审的首日工程合同，资金确实只投约2.55%，不再首日投近90%；不能判断：筛选质量、后续胜率或全年收益已改善。资金约束改变本身不是新选股预测能力。

## 不要混入另一套M3的4只

最新M3 A+B共享诊断真正首买是1月6日（1月5日信号），不是1月5日。它的4只是新希望1000、天康600、创维数字800、平潭100，已有闭合整轮分别−2016.91、−846.00、+25.66、−28.67元。1胜3亏，但新希望含一次ADD，首层−1384.40元，整轮不能冒充首层。

这4个M3首日事件均为A行业出生：新希望/天康所在农产品加工n=4,N=7,K=6；创维黑色家电n=3,N=5,K=5；平潭种植业n=3,N=5,K=5。它们不是统一probe版上述4股。完整数字和原逐笔现金在M3_JAN6_DIFFERENT_FOUR.json。

最新M3已保存路径到5月19日OPEN的600595持仓责任UNKNOWN，且原收尾失败保留；本报告不报任何全年收益/最大回撤。年度补齐与审查由另一独立任务协调，未重复运行。

## 审计边界与文件

没有新运行账户、改公式、借旧股利润拼接新结果。原日线OPEN均为条件模拟代理，未证明现实涨停队列可成交，静态股票池非PIT。

UNIFIED_JAN5_FOUR.csv；AMOUNT_RECONCILIATION.json；OLD_BASELINE_FOUR_REFERENCE.json；M3_JAN6_DIFFERENT_FOUR.json；SOURCE_HASHES.json；OUTPUT_SEAL.json。
'''
(O/'READOUT.md').write_text(text);save('SOURCE_HASHES.json',hs);assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hs.items());save('OUTPUT_SEAL.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SEAL.json'});print(O/'READOUT.md');print(hashlib.sha256((O/'OUTPUT_SEAL.json').read_bytes()).hexdigest())
