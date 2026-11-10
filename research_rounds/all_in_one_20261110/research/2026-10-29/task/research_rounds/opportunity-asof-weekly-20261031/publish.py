"""Report the fixed phase0 result, with all weeks retained in source tables."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def f(x):return 'N/A' if x is None else f'{x:.2f}'
def write_csv(name,rs):
 with (O/name).open('w') as h:
  w=csv.DictWriter(h,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def main():
 text=['21观察成熟机会质量：固定周度as-of检验｜2026-10-31',
       '结论：没有跨时期、跨事件/首候选版本稳定的正向延续性。按冻结停止条件，不用这个代理建立资金扩张/缩减开关，也不反向变成抄底开关，不调整平滑、成熟窗口或horizon追结果。0账户回放、0交易规则变更。',
       '', '口径',
       't固定为每自然周最后一个真正市场交易日收盘。known仅该周真实第21个同源有效观察终点已到且<=t的候选收益，以成熟日先日内等权再日等权；不使用known MFE/MAE。停牌/缺行不按理论21市场日提前成熟。future是紧接下一自然周授权的全部候选，先入组再标可评价/缺失；按授权日日等权。future21收益及+30%收盘MFE仅事后评价。汇总对各完整未来周再等权，不按密集receipt数扩大权重。',
       '全事件版保留继承attempt；首候选版仅attempt真实起点在窗内的stock×attempt第一张合格候选，不要求attempt已经结束。继承attempt首张历史未知，排除分母明确，不冒称窗内首为历史首。known均值正/精确零/负/unknown分开，unknown不并负。',
       '候选源只覆盖原冻结授权窗：2022和2025-07-01至2026-06-30。未补窗前机会，因此起初unknown有左截断成分，不能把它认作真实历史上毫无成熟证据。已冻结future价格尾足21观察，本轮future标签缺失0，不把窗外授权扩进来。',
       '', '主表：known状态与下一自然周候选21收益（百分数）',
       '窗口/版本 | known正/负/零/unknown检查点 | 完整future正/负/unknown周数 | known正后均值/中位 | known负后均值/中位 | 正后/负后future右尾%']
 allsummary=[];strata=[];concentration=[]
 for win in ['2022','2025_26']:
  s=read(O/win/'SUMMARY.json');rs=read(O/win/'WEEKLY.json');d=read(O/win/'DENOMINATORS.json');allsummary+=s
  for version in ['all_events','first_new_attempt']:
   gs={x['known_group']:x for x in s if x['variant']==version and x['market_asof_group']=='all'};p,n,z,u=[gs[k] for k in ['positive','negative','zero','unknown']]
   text.append(f"{win}/{version} | {p['total_checkpoints']}/{n['total_checkpoints']}/{z['total_checkpoints']}/{u['total_checkpoints']} | {p['complete_future_weeks']}/{n['complete_future_weeks']}/{u['complete_future_weeks']} | {f(p['future_return_mean_week_equal'])}/{f(p['future_return_median_week'])} | {f(n['future_return_mean_week_equal'])}/{f(n['future_return_median_week'])} | {f(p['future_tail_daily_then_week_equal']*100)}/{f(n['future_tail_daily_then_week_equal']*100)}")
   rr=[r for r in rs if r['variant']==version]
   for kg in ['positive','negative','zero','unknown']:
    aa=[r for r in rr if r['known_group']==kg];nn=[r['known']['events'] for r in aa];is_=[r['known']['top3_industry_event_share'] for r in aa if r['known']['top3_industry_event_share'] is not None];sm=[r['known']['max_stock_event_share'] for r in aa if r['known']['max_stock_event_share'] is not None]
    concentration.append(dict(window=win,variant=version,known_group=kg,weeks=len(aa),known_events_min=min(nn) if nn else None,known_events_median=float(np.median(nn)) if nn else None,known_events_max=max(nn) if nn else None,known_top3_sector_event_share_median=float(np.median(is_)) if is_ else None,known_max_stock_event_share_median=float(np.median(sm)) if sm else None,top3_weeks_absolute_future_mean_share=gs[kg]['top3_weeks_absolute_mean_share']))
   for mg in ['positive','negative']:
    both={x['known_group']:x for x in s if x['variant']==version and x['market_asof_group']==mg};p,n=both['positive'],both['negative'];strata.append(dict(window=win,variant=version,asof_market_R21=mg,known_positive_complete_weeks=p['complete_future_weeks'],known_negative_complete_weeks=n['complete_future_weeks'],future_mean_after_positive=p['future_return_mean_week_equal'],future_mean_after_negative=n['future_return_mean_week_equal'],difference_positive_minus_negative=p['future_return_mean_week_equal']-n['future_return_mean_week_equal'] if p['complete_future_weeks'] and n['complete_future_weeks'] else None))
 text+=['2022两个版本正known后的未来均值都更差；2025—26全事件版也更差，但仅新attempt首候选版反为较好，负known仅7个完整future周。不呈现可复用的稳定同向延续。不能选择后者的正结果救代理，更不据此改成逆向开关。',
        '正样本全事件版负known后future均值13.82%、中位8.84%、正收益周90.91%；不是只一个极端周，但11周中前三周占绝对周均值总量60.63%，相邻21观察价格窗口又重叠，不构成11个独立试验。首候选版负known仅7周、前三周占68.33%，更须保留稀疏限制。',
        '', '当前市场上下文（全部只用t及以前）',
        '原固定1709/90域市场价格时钟：行业内股票log收益等权，再行业等权累积。它不是全A指数，也没有新增/重算基准。上下文为截至t的21市场观察收益和当前自然周收益；future市场不进入known状态。',
        '同截至t市场21正/负分层后，全事件版仍没有正向known延续：',
        '窗口 | 当前market21符号 | 正known/负known完整周 | 下一周候选21均值：正known后 / 负known后']
 for x in strata:
  if x['variant']=='all_events':text.append(f"{x['window']} | {x['asof_market_R21']} | {x['known_positive_complete_weeks']}/{x['known_negative_complete_weeks']} | {f(x['future_mean_after_positive'])} / {f(x['future_mean_after_negative'])}")
 text+=['known与同期市场方向本来有关联，但上述粗分层也没有恢复全事件版同向关系。此为描述性分层，不是完整市场收益归因或因果控制；各格周数有限。全部首候选版分层同时保存在MARKET_ASOF_STRATA.csv，不选择有利格。',
        '', '实际Bdiag上下文：原策略，不是代理资金算法',
        '2022首次有成熟样本的检查点2/11：known236事件/215股/52行业，成熟日等权-5.86%；原账曝险65.16%，该自然周新买含费37.7625万元，其中confirmed mobile33.6343万元。',
        '2025—26首次有成熟样本的检查点8/1：known271事件/256股/57行业，+7.54%；原账曝险63.22%，周新买含费17.8360万元，其中confirmed mobile13.8269万元。',
        '每个检查点的实际NAV/曝险/ACT/本周所有新买与confirmed-mobile新买金额完整保留。它们属于冻结原Bdiag，并未按known状态调整过，不能将其收益包装成本代理表现。',
        '', '时点、边界和分母',
        '2022共50个真实检查点（1/7至12/30）；2025—26共51个（7/4至6/26）。无市场交易周没有t；2026/6/30是周中，真正周末市场日7/3在窗外，不建立6/30假t。6/26下一自然周含窗外7/1—3，保留窗内94个全事件候选但标future_week_truncated，不入主比较；2022末后的下一周同样截断。没有扩大授权窗口。',
        '无下周市场交易、下周无合格候选、known缺成熟值、截断、future标签缺失各自分开；所有周逐行留存。',
        '2022首候选版：原10580事件中894为继承attempt候选，继承窗内首504个历史首次未知；纳入3098个真正窗内新attempt首候选，排除同新attempt后续6588个。正样本原19358中继承8536、继承首1455；纳入3546个新attempt首候选，排除新attempt后续7276个。全事件不因继承排除。',
        '', '工程核验和限制',
        '202个checkpoint×版本行独立复算成熟日/授权日日等权均值，原源hash均不变；延后真实21观察终点的样本不可提前成熟；篡改尚未成熟未来收益不改变known；unknown与精确零分开；中途窗口与原市场as-of前缀验证通过。known输出没有MFE/MAE字段。',
        '主聚合1.58秒；核验和导出秒级。没有运行账户、重算信号或构建交易引擎，没有新费用/仓位阈值。当前无数据/权限/连接阻塞。',
        '全部价格标签不含费用、实际保护退出或成交可得性，不能称策略胜率或已经验证的动态资金算法。当前snapshot非PIT、历史已消费、前向窗口/股票/行业相关；日线收盘as-of并非真实发布时点/开盘可执行认证。',
        '交付：各窗WEEKLY.csv/json全周透明表；SUMMARY.json及COMPACT_SUMMARY.csv含正负零unknown、可评价周及排除原因；MARKET_ASOF_STRATA.csv、CONCENTRATION.csv、CALENDAR_BOUNDARIES/DENOMINATORS.json、VERIFICATION.json、FREEZE.json。此分支收口，不继续扫描平滑窗口或将代理接入资金扩张。']
 (O/'READOUT.txt').write_text('\n'.join(text)+'\n');compact=[{k:v for k,v in r.items() if k!='future_status_counts'} for r in allsummary if r['market_asof_group']=='all'];write_csv('COMPACT_SUMMARY.csv',compact);write_csv('MARKET_ASOF_STRATA.csv',strata);write_csv('CONCENTRATION.csv',concentration)
 manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and p.name!='FINAL_EVIDENCE.json'}
 (O/'FINAL_EVIDENCE.json').write_text(json.dumps(dict(readonly=True,new_account_paths=0,decision='no_stable_positive_continuation_do_not_build_gate',outputs_SHA256=manifest),ensure_ascii=False,indent=2)+'\n')
 print('READOUT_SHA256',manifest['READOUT.txt'],'artifacts',len(manifest))
if __name__=='__main__':main()
