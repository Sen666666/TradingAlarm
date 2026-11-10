"""Summarize saved evidence. Risk-lock snapshot is NOT assumed to be the exit line."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,hashlib,math
P=Path(__file__).resolve().parent;R=P.parent/'g-s-C-month-continuation-20261102';Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def save(n,x):
 p=P/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(x,default=str,ensure_ascii=False,sort_keys=True,indent=2)+'\n');t.replace(p)
def money(v):return f'{D(v):,.2f}'
def main():
 co=read(P/'ALL_FRESH_CP1_COHORT.json');eng=read(P/'ENGINEERING_DAILY.json');ct=read(P/'DAILY_RESOURCE_CONTEXT.json');pr=read(P/'ALL_PROTECTION_EVENTS.json');summ={};bysec={};accepted={};lines=['工程机械全流程只读归因：先给已证首阻','',
 'Jul1—21两档均有17张去重fresh CP1且原Q通过，涉及11只工程机械股票；全部进入C投影但Q=0，原trace均含account_risk6界限。不是算法到Jul22才发现。',
 'Jul1长龄液压C-mobile=0，但独立T/core实际预留300；Jul2 OHLC全42.46，原reject_flat_day代理不准成交，实际零fill。此为准入和执行两层，也不是“早买必赚”的反事实。',
 'Jul8徐工/三一/恒立已合格，C计划全0；Jul21六个合格候选仍全0；Jul22行业升至真实C队首后才授予大Q。Jul23实际C10买五只、毛49.1141万，C20买三只、毛29.7455万；计划不冒充成交。',
 '截至此证据，首段主要阻挡是原行业优先序下的联合资源竞争，另有一笔core准入后执行阻挡；不能归成没有信号。account_risk6是已存可共存界限，不擅称全部独占，也不推放宽即可盈利。','']
 for arm,rr in co.items():
  q=[r for r in rr if r['stock_Q'] is True];req=[r for r in q if r['C_trace'] is not None];pos=[r for r in req if r['C_Q']>0];zero=[r for r in req if not r['C_Q']];engq=[r for r in eng[arm] if r['fresh_CP1'] and r['stock_Q'] is True];sec=defaultdict(Counter)
  for r in rr:
   c=sec[r['sector']];c['fresh']+=1;c['Q_pass']+=r['stock_Q'] is True;c['Q_unknown']+=r['stock_Q'] is None;c[r['stage_class']]+=1;c['actual_C_reserved']+=bool(r['C_actual_reserved_orders']);c['actual_C_filled']+=any(o['filled_qty'] for o in r['C_actual_reserved_orders'])
  bysec[arm]={k:dict(v) for k,v in sec.items()};summary=dict(market_stock_days=1709*23,fresh_CP1=len(rr),Q_pass=len(q),C_requested=len(req),C_positive_plan=len(pos),C_zero_plan=len(zero),C_zero_plan_with_account_risk_bound=sum(any('account_risk6' in k for k in r['C_trace'].get('blockers_or_necessary_bounds',{})) for r in zero),actual_C_reserved_receipts=sum(bool(r['C_actual_reserved_orders']) for r in pos),actual_C_filled_receipts=sum(any(o['filled_qty'] for o in r['C_actual_reserved_orders']) for r in pos),stage_counts=dict(Counter(r['stage_class'] for r in q)),engineering_qualified_fresh=len(engq),engineering_stage_counts=dict(Counter(r['stage_class'] for r in engq)))
  summ[arm]=summary;lines.append(arm+' 全行业分母 '+str(summary))
  lines.append('该分母为股票×决策日×canonical receipt，重复股票/行业相关，不是独立样本或策略胜率。Jul31次开仍待执行，单列终点删失；同股core成交不当成C-mobile凭据兑现。')
  lines.append('工程机械每日行业H1全90名次 / 实际C队列 / 原持仓风险 / 参考风险上限(未扣新费) / 可用现金：')
  for c in ct[arm]:
   lines.append(f"{c['day']} H1={c['industry_H1']} ranks={c['industry_rank_all90_1based']}/{c['industry_C_queue_1based']}, permit/support/mature={c['industry_F1']['permit']}/{c['industry_F1']['support']}/{c['industry_F1']['mature']}, risk={money(c['old_risk'])}/{money(c['account_risk_reference_before_new_fees'])}, cash={money(c['available'])}")
  # OPEN owns the accepted pre-CLOSE protective line; risk-lock h may predate ratchet.
  needed={e['duty']['requested_at'][:10] for z in pr[arm] for e in z['exit_evidence'] if 'CP1_old_line_exit' in e['duty']['reasons']};op={}
  for day in sorted(needed):
   p=R/'runs'/arm/(day+'-OPEN.json');assert p.exists(),str(p);x=read(p)['account'];op[day]=dict(layers={z['id']:z for z in x['layers']},factors=x['market_factors'],sha256=hashlib.sha256(p.read_bytes()).hexdigest())
  evs=[]
  for z in pr[arm]:
   for e in z['exit_evidence']:
    if 'CP1_old_line_exit' not in e['duty']['reasons']:continue
    day=e['duty']['requested_at'][:10];a=op[day];old=a['layers'][z['layer']];floor=D(old['floor'])/D(a['factors'][z['sid']]);bar=next((v for v in eng[arm] if v['day']==day and v['sid']==z['sid']),None);close=D(str(bar['source_facts']['raw_close'])) if bar else None
    if close is not None:assert close<=floor,(z['sid'],day,close,floor)
    evs.append(dict(layer=z['layer'],sid=z['sid'],sector=z['sector'],opened=z['opened'],request=e['duty']['requested_at'],earliest=e['duty']['earliest_at'],initial_price=z['entry_price'],initial_floor=z['initial_floor_raw'],initial_distance=z['initial_distance_fraction'],source_scale=z['source_CP1'].get('original_scale') if z['source_CP1'] else None,accepted_line_before_trigger_CLOSE=floor,trigger_close=close,original_risk_lock_snapshot_is_NOT_line=e['prior_known_line_snapshot'],actual_sales=e['actual_sale_parts'],source_OPEN_sha256=a['sha256']))
  accepted[arm]=evs;lines.append('全行业实际CP1退出责任层数 '+str(len(evs))+'；初始保护距离中位数 '+str(sorted(float(v['initial_distance']) for v in evs)[len(evs)//2] if evs else None)+'（纯描述，不搜索阈值）。')
 lines+=['','保护链重点（C10；两档线/时钟相同、数量不同）：']
 for e in accepted['2025_26-C10']:
  if e['sid'] not in ('000425.SZ','000528.SZ','688425.SH'):continue
  lines.append(str({k:e[k] for k in ('sid','opened','initial_price','initial_floor','initial_distance','source_scale','request','earliest','accepted_line_before_trigger_CLOSE','trigger_close','actual_sales')}))
 lines+=['风险锁h是冻结风险基准，可能早于最后一次CP1抬线；不能把h.floor错当退出线。已用触发日原OPEN持仓线、当日CLOSE及原订单记录交叉核。',
 '徐工/柳工首次保护距离约9.64%/9.39%，并非紧贴成本的微小线；买前Jul22 G1=4，Jul23买后CLOSE才变−3/原E0负事件，不能倒用当日收盘冷却为买前已知。I仍有效，23/24收盘尚在线上，25才真穿线，28原下一市场开盘卖；这是规则选择，不是漏执行退出。',
 '铁建首次初始距离约8.19%；Jul24收盘新CP1将实际线抬至约7.4596，Jul25收盘6.57已大幅穿线，Jul28实卖6.61669。即便名义线接近成本也不保证能在该线成交；收盘触发/下一开盘和跳空损失不可抹除。',
 '铁建Jul25 E0_down_reset、Jul28 lower_anchor；Jul29新receipt在SEEK中的真实新局部推进产生，raw close6.75仍低于此前7.72，原I有效、G1暖2；不是重用旧receipt，但也不是已收复旧高。新候选线6.52117，Jul30买6.6033（距离1.24%），同CLOSE6.51穿线，Jul31卖6.426785。',
 '低波动尺度约0.75%确实沿用，但不能把首次大跌亏损简单归为“保护太近”：初买开盘跳高放大到8%以上距离，且后续抬线被大跌跨过；再入1.24%近线的代价需与全部同类退出/恢复比较。',
 '', '最多两个源头假设与下一最小事件验收（仅建议，未执行）：',
 'H1：行业相对H1×大目标优先/联合资源使早期合格股拿不到立足量，急涨后队首才集中。检验应固定Jul8/21/22真实规划快照：保持全部资格/限额，核原前排预留对替代一手是否确实构成直接竞争；只作局部合法性，不能累加或推收益。长龄的一字零fill为执行负控；IT服务实际盈利旧仓不能事后叫弱仓。若不可替代主要来自固定保护风险/原最小单位，而非排序，则否定单纯排序解释。',
 'H2：持续I/行业支持被用于新资金，而局部CP1重置后新推进与保护退出不是同一尺度的趋势证明。用原公式的同前缀“持续赢家/暴涨后回落/跌后真恢复”事件链，检验source reset/新receipt、实际线生效钟、入场风险和次开执行；同价路径不同账户成交必须产生相同市场凭据。必须同时纳入全部行业“急冷但未穿线随后盈利”的负控，不能先启用G1急跌全卖或禁止重入。',
 '', '剩余未知：这里的old_risk和top10 owners是整批前真实快照；未保存的逐候选精确影子前缀不猜补，trace计数不是机会数。未做放松上限/换名单/新政策账户或新收益回放。82行业上涨仅作环境描述，不是策略可赚全部的基准。',
 '完整字段见ENGINEERING_DAILY（14股×23日×两档，I/E0/G1/CP1/PVR/结构/真实资格、目标、实际预留/成交）、DAILY_RESOURCE_CONTEXT（90/队列名次、支持/permit、资金风险/旧持仓）、ALL_FRESH_CP1_COHORT（全行业原母体）、ALL_PROTECTION_EVENTS与PROTECTION_ACCEPTED_LINES。']
 save('COHORT_SUMMARY.json',summ);save('COHORT_BY_SECTOR.json',bysec);save('PROTECTION_ACCEPTED_LINES.json',accepted);(P/'REPORT.txt').write_text('\n'.join(lines)+'\n');save('READONLY_CHECKS.json',dict(passed=True,account_events=0,new_indicators=0,all_engineering_CP_exits_crossed_actual_accepted_line=True,original_risk_lock_not_used_as_actual_stop=True))
 print('READ_ONLY_REPORT_READY',summ)
if __name__=='__main__':main()
