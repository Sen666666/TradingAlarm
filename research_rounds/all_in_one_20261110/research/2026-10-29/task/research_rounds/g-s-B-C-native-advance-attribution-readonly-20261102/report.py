"""Render existing attribution files only; do not solve or delete targets."""
from pathlib import Path
import json
from datetime import date
from decimal import Decimal as D
O=Path(__file__).resolve().parent
read=lambda n:json.loads((O/n).read_text())
def when(x):return x['confirmed_date'] if x else '本context无推进'
def main():
    summary=read('SUMMARY.json');receivers=read('RECEIVING_INDUSTRIES.json');sellers=read('DONOR_INDUSTRIES.json');market=read('MAY7_MARKET_DIRECTIONS.json');demands=read('RECEIVING_DEMANDS.json')
    lines=['B/C接收与供资行业的原生推进归因（只读，0金融事件）',
        '主结果：Jan6/Jul3四份已保存B/C投影，28个正增量请求、15个政策×接收行业行，接收行业当天price_advance全部为0。不是市场没有推进：Jan6建筑材料/公路铁路运输、Jul3能源金属/风电设备有原生推进。',
        '每个正增量前缀都有新增影子D。表内金额是保存Q×保存mark、不含费的拟买资本，不是成交或收益；不得把删除该量直接当节约损失。全部28行及receipt/context/source在RECEIVING_DEMANDS。',
        '', '日期/政策 | 接收行业 | 拟买原价资本元 | 当前context起点 | 当前context最近推进 | 当前S成熟/用途']
    for r in receivers:
        ctxdate=date.fromordinal(int(r['current_context'].split('|')[-2])).isoformat() if r['current_context'] else '无'
        # Several stocks in a sector may share the same use; preserve the actual bound use list.
        uses=sorted({d['use'] for d in demands if d['day']==r['day'] and d['policy']==r['policy'] and d['sector']==r['sector']})
        lines.append(f"{r['day']} {r['policy']} | {r['industry']} | {D(r['new_mark_capital']):,.2f} | {ctxdate} | {when(r['last_current_context_advance'])} | {r['mature']} / {','.join(uses)}")
    lines+=['', '拟供资侧']
    for k,s in summary.items():
        for pol,a in s.items():lines.append(f"{k} {pol}：{a['donor_industries']}个拟供资行业，其中{a['same_day_advance_donor_industries']}个当天仍推进；保存净卖款{D(a['saved_net_sell']):,.2f}元。")
    for r in sellers:
        if r['has_current_context_advance_today']:lines.append(f"当天推进仍被卖：{r['day']} {r['policy']} {r['industry']}，{','.join(r['names'])}，拟卖原价市值{D(r['sold_mark']):,.2f}元。")
    lines+=['其余供资行业没有当天的新推进，但所选层均沿保存输入I/原实际线/持有支持判断为可留存的mobile；配置供资不是原保护失败。行业S是否仍有效与股票是否可借G正常持有分列在DONOR_INDUSTRIES，不能把无新推进或S已结束统一叫垃圾旧仓。',
        '不把某卖出行业净款独占配给某新股票。逐需求只记录原前缀D增加/回填；最终供资金额按原完整D核同，避免重叠累加。',
        '', '原S成熟与一次迁移是不同语义',
        '原policy.py:40–56：break_started/repair_restored建context；该context内price_advance令mature=True，后续无推进不会因此撤销成熟；价格失败/源切换结束context才清除。permit弱/恢复不是按股票receipt重新产生推进。普通上下文中推进先发生、permit后恢复，成熟仍可延续；ACT事故的授权另受严格cutoff/seq及context身份检查。',
        '原policy.py:67–87：ACT恢复可用新的price_advance解锁该行业S；原allowed检查support/permit/mature与用途解锁，没有“这次推进已用于配置迁移”的消费闸门。policy.consumed是股票凭据消费，不是行业推进消费。一个原推进可一直支持成熟资格，并不表示账户有一张未花的预算券。',
        '因此若研究“一推进只迁移一次”，需把行业事件(source,context,event_id)的迁移使用与成熟资格分开；原账无法回填其已用/未用。不能因没有字段就认定历史推进仍未使用，也不能因已作成熟授权就自动认定迁移次数耗尽。',
        '半导体May7是当前context第一次推进：同一事件在原规则使S成熟。若允许它同时支持首次行业迁移，是把资格与一次行业批次用途分开，并非两份资金；若成熟即算耗掉唯一迁移机会，则必须等再下一推进，是额外延迟，不能暗含。一次应按行业完整批次去重，而非每只股票/每张CP1都重新获得一次迁移。以上是待定语义，不在本轮实现。',
        '', '若按“当天新推进”作标签，会允许/延迟什么',
        'Jan6：B的软件/黑色家电/中药/传媒，C的中药/黑色家电，新增配置腾挪均无当天推进支持；最近推进分别1/4或更早。Jul3：B/C全部接收方向同样没有当天推进；汽车服务及其他/软件/专用/通用在当前行业context甚至尚无后续推进，但有原G许可，不能把这部分说成非法S。',
        '这会拦本批新增机会性D，不等于28笔买量全部变0：已有真实现金可能支持较小量，前排未卖后的整账也会改变，当前未重算，合法缩量未知。若只是一次未用历史推进可等fresh使用，则Jan6的1/4推进、Jul3的6/24/6/30/7/1推进是否还有迁移机会均UNKNOWN。原G广泛部署与替换有效旧仓是否同受此门，是另一个必须明示的范围，不能顺便把G快启改成等行业推进。',
        '延期不等于保存当天股票receipt到下一推进。原fresh/deadline不变；之后还需新的合法股票机会、当前P/ACT与真实资源。原保护/ACT/支持失效退出义务不受此门撤销，也不假释放现金。',
        '', '2026-05-07：仅市场方向，不是G/S账户']
    for r in market:
        if not (r['frozen_expansion_list_count'] or r['price_advance_today'] or r['industry']=='能源金属'):continue
        lines.append(f"{r['industry']}：当天推进={r['price_advance_today']}，context起点{r['market_context_started']}，首次推进{r['context_first_advance']}，最近{r['last_current_context_advance']}；原扩张列表{r['frozen_expansion_list_count']}股。")
    allowed=sum(r['frozen_expansion_list_count'] for r in market if r['price_advance_today']);delayed=sum(r['frozen_expansion_list_count'] for r in market if not r['price_advance_today'])
    lines +=[f"原61股中{allowed}股方向伴随当天推进（化学品9/元件14/半导体21/消费电子10）；另{delayed}股方向无当天推进（通信6/电池1）。其他电子当天首次推进但无fresh列表机会；能源金属前日5/6推进、当天无推进也无fresh机会。推进/机会必须同时分别核，不由排名或推进单独造订单。", 
        'May7市场context起点可核，但没有本G/S账户context/ACT或迁移消费账，不编造政策context ID、不预设54股都能买。未做门控后重排、容量求解或收益推演。',
        '', '收口',
        '支持：当前激进腾挪主要不是接收行业当日新推进触发，而是既有许可+fresh个股CP1+排序/目标与资源联立；这使事件去重成为可反驳的小差分问题。否定：没有新行业推进就没有任何新股票证据、旧被卖股必然已弱、删除迁移即可省下相应亏损。未知：门控能否减少错换而不伤害行情响应；同日门和一次未用事件门不可混称。本轮不选择/实现门控、不改变B/C结果、不跑收益。']
    (O/'REPORT.txt').write_text('\n'.join(lines)+'\n')
    print('REPORT_READY',len(demands),'demands',len(receivers),'receiving industry rows',flush=True)

if __name__=='__main__':main()
