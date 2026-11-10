"""Readable local report from frozen results; no economic computation."""
from pathlib import Path
import csv, html

HERE = Path(__file__).resolve().parents[1]
LABEL = {'SEMI': '半导体', 'COMM': '通信', 'DRUG': '创新药', 'BANK': '银行'}

def read(name):
    with (HERE / name).open() as h:
        return list(csv.DictReader(h))

def table(head, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>'+html.escape(x)+'</th>' for x in head) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'

def main():
    target = HERE / 'report'
    target.mkdir(exist_ok=False)
    s = read('analysis-v1/summary.csv')
    cov = read('review-v1/risk-coverage.csv')
    cases = read('review-v1/posthoc-cases.csv')
    def find(group, policy, stress='base'):
        return next(r for r in s if r['group']==group and r['policy']==policy and r['scenario']==stress)
    def rd(r):
        return f"{float(r['net_return']):+.2%} / {float(r['max_drawdown']):.2%}"
    body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LER-01：A股局部入场与全部试错成本</title><style>body{font:17px/1.75 system-ui,sans-serif;color:#233548;max-width:1180px;margin:35px auto;padding:0 22px}h1{line-height:1.35}h2{margin-top:38px}a{color:#1f638a}img{width:100%;height:auto;border:1px solid #e5e9ec}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:11px;text-align:right;border-bottom:1px solid #d9e1e7;white-space:nowrap}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}.outcome{padding:18px 23px;background:#f1f5f7;border-left:5px solid #356780}.muted{color:#5b6b78;font-size:15px}</style><h1>A股局部入场、局部失效与再次入场</h1><p class="outcome"><b>一轮完成，不晋升默认。</b>低胜率可以盈利；当前候选尚未稳定优于原I。只有通信的尾部净利润能独立覆盖全部亏损交易。四池所有情景回撤均超过20%。</p><p>先12原始量价窗 → 一个冻结候选 → 12候选轨迹 → 技术准入 → 28资金路径 → 8实际结构复查。4旧基础控制，24新增经济；经济运行一次，结果后规则改动0。</p><p><a href="../CONCLUSION.md">完整结论</a> · <a href="../RULES.md">冻结公式</a> · <a href="../TRADE_REVIEW.md">实际成交复查</a> · <a href="../analysis-v1/summary.csv">全部数据CSV</a> · <a href="../analysis-v1/accounting.json">独立核账</a> · <a href="../technical/prefix-receipt-v1.json">真实截断复算</a></p><h2>新买点和趋势持有</h2><p>原E0有效背景中，局部休整后收盘突破昨日高点，价格位移获得成交量信用确认，形成新入场凭据。实际买入绑定固定局部低位；E0支持提高后自然接管。卖完后，新凭据可再次入场，无固定重试上限、固定倍数止盈。</p><p class="muted">日线收盘确认，下一可成交开盘执行，保留T+1、跳空与未成交限制。局部位不保证实际只亏1R，也不保证距离狭窄。</p><h2>基础结果：累计净收益 / 最大回撤</h2>'''
    body += table(['固定池','原I','新入场＋结构持有LH','完整局部LER','LER胜率'], [[LABEL[g],rd(find(g,'I')),rd(find(g,'LH')),rd(find(g,'LER')),f"{float(find(g,'LER')['win_rate']):.2%}"] for g in LABEL])
    body += '<p>半导体的收益损失大部分已发生在更换入场时；通信局部退出/再入进一步降低收益。创新药和银行相对LH有所改善，均未解决回撤。差额包含资金占位与后续参与路径，不能当成相同交易的纯止损收益。</p><img alt="四池完整净值，I、LH与LER对照" src="../review-v1/nav-base.png"><h2>尾部能否独立支付全部亏损</h2><p>闭合净回报≥30%仅为统计边界。金额单位万元，费用已计入每笔净损益。</p>'
    body += table(['固定池','尾部净利润','全部亏损交易净亏损','覆盖倍数','普通闭合净损益','开放持仓损益'], [[LABEL[g],f"{float(r['tail_net_profit'])/1e4:.2f}",f"{float(r['all_losing_trades_net_loss'])/1e4:.2f}",f"{float(r['tail_to_all_loss']):.2f}",f"{float(r['ordinary_closed_net'])/1e4:+.2f}",f"{float(r['open_net'])/1e4:+.2f}"] for g in LABEL for r in cov if r['group']==g and r['scenario']=='base'])
    body += '<p>半导体胜率22.22%仍盈利，但尾部独立覆盖还差约2.33万元，由普通盈利补上；创新药和银行更依赖普通盈利。867个获得资金的因果结构中，47个多次尝试，最多3次；所有失败均保留。不能只统计最终成功的尝试。</p><h2>执行压力：累计净收益 / 最大回撤</h2>'
    body += table(['固定池','基础','双成本','额外延迟一个可成交开盘'],[[LABEL[g],rd(find(g,'LER')),rd(find(g,'LER','cost2')),rd(find(g,'LER','delay1'))] for g in LABEL])
    body += '<p>创新药延迟后转亏，银行延迟后的微利依赖开放权益。延迟组均有真实成交，不存在零交易假优势。</p><h2>完整结构内的实际正反例</h2><p class="muted">每池按最大尾部贡献/最差净损益事后选例，仅解释结果，不改规则。图中蓝三角实际买入、叉号实际卖出；每个结构的全部尝试都保留。</p>'
    for r in cases:
        role = '尾部例' if r['case'].endswith('tail') else '亏损例'
        body += f"<h3>{LABEL[r['group']]} · {html.escape(r['name'])} · {role}</h3><p>{r['attempts']}次尝试，结构净损益{float(r['net_pnl'])/1e4:+.2f}万元。</p><img loading='lazy' alt='{html.escape(r['name'])}全部实际尝试与量价图' src='../review-v1/{r['case']}.png'>"
    body += '<h2>经济前的原始量价与候选轨迹</h2><p>固定日期、事前63观察收益排名选取强/中/弱，不按旧买点或未来收益选图。信号草图不是实际资金成交。</p>'
    for folder,label in [('raw','原始量价'),('model-charts-v1','候选轨迹')]:
        for n in [1,2]:
            body += f"<h3>{label} {n}</h3><img loading='lazy' alt='{label}第{n}组' src='../{folder}/contact-{n}.png'>"
    body += '<h2>核验与适用边界</h2><p>39,200经济日账独立重建净值差0元；四条旧I基础完整日志与逐日净值精确复现；14真实截断路径10,178日账/决策一致，局部收据从截断证据重算。另有744独立公式、12真实量价前缀和3合成前缀。技术失败原样保留。</p><p class="muted">四固定池共256股，每户100万元，2021-01-04—2026-10-16。当前存续、分类、市值快照和已见开发历史，非历史时点全市场或样本外。日线成交代理不等于实盘成交；无新行情下载、无实盘。继续保留原I和本候选全部证据，不自动调参或扩展账户。</p></html>'
    (target/'index.html').write_text(body)
    print(target/'index.html')

if __name__ == '__main__':
    main()
