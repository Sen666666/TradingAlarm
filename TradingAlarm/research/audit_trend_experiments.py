"""Deduplicate comparable recent accounts, verify repeats, audit goal evidence."""
import json,hashlib,html
from pathlib import Path
import pandas as pd
from strength_account_review import drawup
ROOT=Path('results');OUT=ROOT/'trend-research-audit'
SOURCES=['trend-strength-ah-transfer','strength-volume-units','strength-multiscale-structure','strength-anchored','strength-path-efficiency','strength-swing-structure','strength-developing-swing','strength-envelope-swing']
def main():
    seen={};duplicates=0;records=0;rows=[];hashes={}
    for source in SOURCES:
        folder=ROOT/source;results=json.loads((folder/'results.json').read_text());validation=json.loads((folder/'validation.json').read_text());assert validation['new_ledgers']==len(results)
        hashes[source]=hashlib.sha256((folder/'results.json').read_bytes()).hexdigest()
        episodepath=folder/'episode-attribution.json';episodes={x['case']:x for x in json.loads(episodepath.read_text())['results']} if episodepath.exists() else {}
        for r in results:
            records+=1;case=r['case'];path=pd.read_parquet(folder/(case+'-path.parquet'));orders=json.loads((folder/(case+'-orders.json')).read_text())
            assert r['allocation']=='equal_capital' and r['cadence']=='daily'
            if case in seen:
                oldpath,oldorders,oldrow=seen[case]
                pd.testing.assert_frame_equal(oldpath,path,check_exact=True);assert oldorders==orders;assert oldrow['total_return']==r['total_return'];duplicates+=1;continue
            seen[case]=(path,orders,r);e=episodes.get(case)
            row={k:r[k] for k in ['case','group','strategy','scenario','total_return','max_drawdown','average_cash_weight','fees','year2026']};row.update(drawup(path.nav));row['source']=source
            if e:row['episode_economics']={k:e[k] for k in ['closed_count','closed_win_rate','average_win','average_loss','ordinary_all_bottom90','parent_closed_with_remaining_claims']}
            rows.append(row)
    strategies=sorted(set(r['strategy'] for r in rows));summary=[]
    for s in strategies:
        subset=[r for r in rows if r['strategy']==s];assert len(subset)==6
        b={r['group']:r for r in subset if r['scenario']=='base'};stress={g:min(r['total_return'] for r in subset if r['group']==g) for g in b}
        summary.append(dict(strategy=s,etf_base=b['etf17']['total_return'],hk_base=b['hk7']['total_return'],etf_worst=stress['etf17'],hk_worst=stress['hk7'],worst_drawdown=min(r['max_drawdown'] for r in subset),best_hindsight_drawup=max(r['max_hindsight_drawup'] for r in subset),all_cases_positive=all(r['total_return']>0 for r in subset),all_cases_mdd_under20=all(r['max_drawdown']>=-.2 for r in subset)))
    report=dict(source_records=records,duplicate_records_verified=duplicates,unique_accounts=len(rows),unique_strategies=len(strategies),sources_sha256=hashes,strategies=summary,accounts=rows,limits='Recentcomparablefamiliesonly,nottotalresearchtrialcount. Sixscenariosperstrategycorrelated,notsixindependenttests. Maxhindsightdrawupisupperbounddiagnostic,nottradablecycle. 2026andselectednamesaredevelopment. Worstcaseamongbase/cost2/delay1,notallpossiblestresses. HKbottom90isa retrospectivePNLdecomposition,nottradefilter.')
    transfer=[]
    for folder,name in [('trend-strength-transfer485','linear_geometry_price_volume'),('strength-anchored-transfer485','anchored_neutral_price_volume')]:
        values=json.loads((ROOT/folder/'sleeve-report.json').read_text())['rows']
        x=next(x for x in values if x['strategy']==name and x['allocation']=='equal_capital' and x['scenario']=='base' and x['cutoff']=='2026-10-16' and x['terminal']=='last_mark' and x['cost']==15)
        transfer.append({'strategy':name,'synthetic_A485_return':x['equal_initial_sleeve_return'],'source':folder,'scope':'2024-2026 isolated fractional adjusted-price sleeves, not comparable raw-share account returns'})
    report['broader_transfer']=transfer
    report['any_account_hindsight_drawup80']=any(x['max_hindsight_drawup']>=.8 for x in rows)
    report['largest_hindsight_drawup']=max(x['max_hindsight_drawup'] for x in rows)
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    def pct(x):return f'{x:+.2%}'
    body=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [s['strategy'],pct(s['etf_base']),pct(s['hk_base']),pct(s['etf_worst']),pct(s['hk_worst']),pct(s['worst_drawdown']),pct(s['best_hindsight_drawup'])])+'</tr>' for s in summary)
    doc='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>趋势研究统一复核</title><style>body{font-family:system-ui,sans-serif;max-width:1400px;margin:32px auto;padding:0 24px;color:#182b44}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #ddd;padding:9px;text-align:right}td:first-child,th:first-child{text-align:left}th{background:#eef2f7;position:sticky;top:0}.note{background:#f4f6fa;padding:18px;line-height:1.7}</style><h1>趋势交易研究：近期实验统一复核</h1><p>2022—2026-10-16；17 只 ETF 与 7 只港股；同一现金／持仓账户引擎，计入成本。</p>'''
    doc+=f'<p>{records} 条已保存结果，经逐路径、逐订单核对去除 {duplicates} 条重复对照，剩余 {len(rows)} 个账户场景、{len(strategies)} 个策略定义。它们不是独立试验。</p>'
    doc+='<div class="note">目前没有可采用策略。事后最大上涨区间用于检查路径中是否曾出现目标幅度，不能当作可实现收益。最差场景仅指基础、成本加倍、延迟一日三者中的最差，不能代表所有风险。此表不按盈利排名挑选市场或版本。</div><table><thead><tr><th>策略定义</th><th>ETF 累计</th><th>港股累计</th><th>ETF 最差场景</th><th>港股最差场景</th><th>最差回撤</th><th>最大事后上涨区间</th></tr></thead><tbody>'+body+'</tbody></table>'
    doc+='<h2>已反复出现的问题</h2><ul><li>局部速度强不等于持续趋势；降低交易频率可能同时漏掉早期大涨。</li><li>更快退出也会更快误入反弹；更严格确认又会错失趋势初段。</li><li>少量港股上的改善未稳定迁移至 485 只 A 股；不能分市场选择最好版本。</li><li>2026 年案例已经用于反复诊断，属于开发数据，不能再宣称独立验证。</li></ul><p>后续算法必须同时报告：普通交易损耗、大盈利贡献、成本与延迟敏感性、2026 逐段强度和实际交易、跨样本迁移。低胜率本身不是优势。</p></html>'
    extra='<h2>跨样本复核</h2><p>全部114条账户路径，事后最大上涨区间上限为43.20%，没有达到80%。这不是可交易择时收益。两类在ETF/港股六场景中仍为正的定义，A股485样本迁移结果如下：</p><ul>'+''.join('<li>'+html.escape(x['strategy'])+'：'+pct(x['synthetic_A485_return'])+'</li>' for x in transfer)+'</ul><p>A股这里是2024—2026年独立分配资金的简化模拟，不能与上表现金与持仓逐笔记账的回测口径直接比较；作用是检验迁移方向，结果不支持采用。</p>'
    doc=doc.replace('</html>',extra+'</html>')
    (OUT/'review.html').write_text(doc)
    print({k:report[k] for k in ['source_records','duplicate_records_verified','unique_accounts','unique_strategies']})
    for s in summary:print(s)
if __name__=='__main__':main()
