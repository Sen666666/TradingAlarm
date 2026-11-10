"""Publish source map and preparation status, never economic results."""
from pathlib import Path
from datetime import datetime,timezone
import json,csv,html,hashlib

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    report=HERE/'report';report.mkdir(exist_ok=False)
    mapping=[
        ('01:16','EMA9/21/50/150','保留原参数；日线图已计算','EMA种子/预热/来源段重置已记录'),
        ('02:40','典型多头排列，也做均线缠绕','图检已完成，经济规则待审','缠绕0.5ADR、EMA50五日不降为研究约定'),
        ('02:40','回到9/21EMA，叠加AVWAP/前高低/缺口','分钟支撑过程未验证','AVWAP锚固定，不前后挪锚选未来贴合'),
        ('04:03','1/5/15分钟越前K高点即触发，急跌急拉','缺历史分钟OHLC，未实现成交','两根K线/0.25ADR速度条件待审'),
        ('04:33','通常整理1—2周以上，贴9EMA收窄，偏好inside day','inside day已作事实诊断','10日/1ADR位移/2ADR箱体/0.7收窄/0.25贴线待审'),
        ('04:53','越昨日高点入，不等箱顶','未用日线收盘信号替换','盘中执行必须有分钟证据'),
        ('05:12','开盘首根1或5分钟区间高点','缺历史分钟，未实现','不开盘回填前高成交'),
        ('06:21','当日/触发或前K低点；ADR一半且最多5%，通常3%','原锚顺序与宽度意图保留，未交易','拟固定min(ADR20/2,3%)；不用触发分钟最终低点'),
        ('06:52','每笔风险约0.5%，倒算仓位','提出固定预算与共享资金约束','0.5%名义风险，30%单股/六槽/90%需审阅'),
        ('07:19','至少3R甚至5R且小时图远离均线，首批约15%','未模拟部分卖出','拟5R+小时9EMA偏离1ADR，15%初始数量一次'),
        ('07:42','两三天后9EMA高于成本，常移保本','规则待审','拟满两交易日，9EMA高于成本生效'),
        ('07:42','余仓挂9EMA下某根K低点跟随','规则待审','拟最近一根低于9EMA的日K低点减一tick，只上调'),
        ('07:42','高于日线9EMA15%—20%再卖，大涨后巨量再卖','规则待审','拟20%、3倍20日成交额中位数，各一次'),
        ('07:42/11:08','环境影响卖出数量；观察指数9/21EMA','A股指数数据和规则尚未准入','拟沪深300/中证1000，修复前两笔及40日延续份额约定'),
        ('本次用户要求','保留E0持有与不使用E0的卖出对比','草案A/B已分开','A接E0持有；B不加E0闸或出口'),
        ('A股执行适配','新买当日不能卖出','执行合同已列明，未产生订单','触及止损后等待可卖，全部超损计账')]
    with (HERE/'source/rule-map.csv').open('x') as f:
        w=csv.writer(f);w.writerow(['video_time','source_rule','current_status','research_convention_or_gap']);w.writerows(mapping)
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>视频EMA规则重研究｜日线准备与待审约定</title><style>body{font:17px/1.75 system-ui,sans-serif;color:#233548;max-width:1220px;margin:34px auto;padding:0 22px}h1{line-height:1.4}h2{margin-top:38px}a{color:#1f638a}img{width:100%;height:auto;border:1px solid #e1e6eb}.status{background:#fff4dc;border-left:5px solid #b48529;padding:18px 22px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #dfe5ea;min-width:130px}.muted{color:#5c6f7c;font-size:15px}</style><h1>按视频均线、回调与突破规则重新研究</h1><p class="status"><b>日线图检已完成；资金回测未准入，新增账户0。</b><br>缺覆盖历史区间的1分钟OHLCV与成交额；视频裁量的量化草案需先审阅。没有用日线收盘信号代替分钟买点，也没有用旧LER结果充当本轮收益。</p><p><a href="../RULES_FOR_REVIEW.md">完整待审规则VEMA-Q1</a> · <a href="../DATA_AND_EXECUTION.md">分钟缺口与T+1执行</a> · <a href="../EMA_REVIEW.md">12窗图检记录</a> · <a href="../source/video-transcript.txt">视频逐字稿</a> · <a href="../technical/daily-checks.json">日线与截断核验</a></p><h2>拟比较的两组</h2><p>A：相同视频入场/初始止损/风险定仓，后续交给E0结构持有。<br>B：相同视频入场/初始止损/风险定仓，后续按视频保本、9EMA跟随与分批卖出，不使用E0。<br>两组初始条件相同，卖出后资金占位和再次参与自然分化，不能把账户差额都称逐笔纯退出效应。</p><h2>原文与研究约定逐项对应</h2><p>20日ADR、10日整理、贴线/收窄比例、5R首批、巨量倍率和环境数字都不是视频已给定的唯一值；它们已单列待审，不因收益好坏修改。</p><div class="scroll"><table><thead><tr><th>出处</th><th>视频内容</th><th>本轮状态</th><th>约定或缺口</th></tr></thead><tbody>'''
    for row in mapping:body+='<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>'
    body+='</tbody></table></div><h2>真实数据缺口</h2><p>已查市场快照1143条证券，只有17条含2026-10-16分时序列，共3205个采样价格点，全部没有分钟OHLC。另盘点1544个历史研究Parquet的10类schema，未发现可用于本轮的历史1分钟数据集。此结论只针对已核查的本地资料，不表示外部服务一定无法提供。</p><p>没有分钟资料，无法验证局部快速反转、触发前低点、小时图偏离及买入后止损顺序，更不能计算全部试错由大赢家覆盖的实际比例。</p><h2>T+1适配</h2><p>当日新买不能即时止损。实际买入后确认触及止损须记受限退出请求，等下一可卖时点；跳空、跌停、停牌和费用全部入账。名义0.5%不是实际亏损上限。分钟OHLC内仍有顺序歧义时需保守合同及影响报告。</p><h2>先看原始量价，再看EMA</h2><p class="muted">固定沿用12个事前原始图窗，避免按本轮表现换案例。历史已看，只是开发图检。EMA9/21/50/150因果计算；黑三角是inside day，不是买点。未自行生成AVWAP锚或分钟信号。</p>'
    for group in ['SEMI','COMM','DRUG','BANK']:
        label={'SEMI':'半导体','COMM':'通信','DRUG':'创新药','BANK':'银行'}[group]
        body+=f'<h2>{label}：强／中／弱三窗</h2>'
        for role,name in [('strong','强'),('middle','中'),('weak','弱')]:
            body+=f'<h3>{label} · 锚前{name}组</h3><p>原始OHLCV</p><img loading="lazy" alt="{group}_{role}原始量价" src="../raw/{group}_{role}.png"><p>EMA叠图与单日振幅；不是交易信号</p><img loading="lazy" alt="{group}_{role}EMA诊断" src="../ema/{group}_{role}.png">'
    body+='<h2>完成与未完成</h2><p>完成：源规则清单、A股T+1合同、12原始窗及12EMA叠图、256股日线事实、62,884独立EMA行核验、12真实截断日线前缀；旧LER518证据及E0/R/R1登记30文件哈希不变。</p><p>未完成：用户审阅量化约定、分钟/指数环境数据准入、实际入场与卖出实现、有限资金对比、全部试错与尾部覆盖核算。没有资金收益或晋升结论。</p></html>'
    (report/'index.html').write_text(body)
    rules=HERE/'RULES_FOR_REVIEW.md'
    state=dict(recorded_at=datetime.now(timezone.utc).isoformat(),status='awaiting_minute_data_and_rule_review',
        user_allows_explicit_discretion_quantification=True,user_requires_rules_shown_before_economics=True,
        rules_review_confirmed=False,rules_draft='RULES_FOR_REVIEW.md',rules_draft_sha256=sha(rules),
        economic_admission=False,new_economic_accounts=0,planned_max_economic_paths=24,
        raw_windows_reviewed=12,ema_windows_reviewed=12,verified_historical_minute_dataset=None,
        local_report='http://127.0.0.1:8799/report/',daily_checks='technical/daily-checks.json',
        major_unfulfilled=['Minute execution and T+1 research','Two holding policies financial comparison','All trial costs versus tail-winner coverage'])
    with (HERE/'RUN_STATE.json').open('x') as f:json.dump(state,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(state,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
