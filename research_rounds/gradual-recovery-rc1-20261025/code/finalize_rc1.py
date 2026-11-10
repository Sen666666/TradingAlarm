"""Post-result presentation and explicit failure details; no rule changes."""
from common_rc1 import *
import pandas as pd
from plot_rc1 import plot
def main():
 verify();out=HERE/'report';(out/'details').mkdir(exist_ok=False)
 cases=[dict(id='gold_down_Mar_Jul2026',symbol='AU0',start='2026-03-01',end='2026-07-31'),dict(id='cpo_recovery_Jun2025',symbol='300308.SZ',start='2025-05-01',end='2025-08-01'),dict(id='cambricon_false_recovery_Aug2024',symbol='688256.SH',start='2024-08-01',end='2024-10-15'),dict(id='maotai_false_recovery_Aug2026',symbol='600519.SH',start='2026-07-20',end='2026-10-22')]
 for c in cases:
  z=pd.read_parquet(HERE/'analysis'/f"{c['symbol']}-trace.parquet");plot(c['symbol'],z,c,out/'details'/f"{c['id']}.png")
 write(out/'detail-manifest.json',dict(posthoc_illustration_not_new_test_samples=True,cases=cases))
 ev=pd.read_parquet(HERE/'analysis/local-receipts.parquet');a=ev.loc[ev.date.ge('2023-01-01')&ev.added_buy_event];assert len(a)==31
 full=pd.read_csv(HERE/'results-v1/summary.csv');u=pd.read_csv(HERE/'analysis/uniform2023-summary.csv');outcomes=dict(recent_added_events=len(a),below_pre_high=int(a.below_pre_high.sum()),negative21=int(a.ret21.lt(0).sum()),broken_anchor21=int(a.anchor_broken21.eq(True).sum()),either_failure21=int((a.ret21.lt(0)|a.anchor_broken21.eq(True)).sum()),recent_old_starts=int(u.original_ix_starts.sum()),recent_new_starts=int(u.rc1_ix_starts.sum()),recent_extra_days=int(u.extra_qualified_days.sum()),old_slow_blocked=int(u.old_slow_blocked_cold_days.sum()),restored_slow_blocked=int(u.restored_slow_blocked_days.sum()))
 write(out/'key-results.json',outcomes)
 table=u[['name','original_ix_starts','rc1_ix_starts','extra_qualified_days','warm_promotions_below_high','old_slow_blocked_cold_days','restored_slow_blocked_days']].rename(columns={'name':'标的','original_ix_starts':'原IX启动','rc1_ix_starts':'RC1版启动','extra_qualified_days':'新增资格日','warm_promotions_below_high':'前高以下升暖','old_slow_blocked_cold_days':'原慢推进冷态滞留日','restored_slow_blocked_days':'其中恢复至暖日'})
 findings=f'''<div class="box"><h2>本轮裁决：新收据成立，整体反弹问题仍在</h2><p>全来源2442张局部推进收据中1422张低于前结构高点，927张发生在明确下降背景。下降背景的新通道没有单独升暖；但原IX通道保持，因此沪金2026-04-08、06-15仍由原通道获得暖/参与资格。这两次并未被RC1消除。</p><p>统一2023年以来：新增31个买入资格事件，30个在前高以下；其中后21有效观察下跌{outcomes['negative21']}个，重新跌破锚点{outcomes['broken_anchor21']}个。这些是事后价格路径，不是交易胜率或账户收益。原启动{outcomes['recent_old_starts']}段、RC1版{outcomes['recent_new_starts']}段，新增{outcomes['recent_extra_days']}个资格日；提前与合并会改变段数。</p><p>原先189个“慢推进但卡在冷区”的同标的股票日，只恢复25个。改善有限，不能称冷态粘滞已经解决；RC1作为证据原型保留，不晋升为已验证交易改良。</p><div class="scroll">{table.to_html(index=False,border=0)}</div><p class="muted">各行2023年至自身末日；黄金ETF止于10月16，沪金/半导体止于10月23，股票止于10月22，不补缺。</p></div>'''
 details='''<div class="box"><h2>重点正反例（结果后展示）</h2><p>中际2025-06-04由RC1在前高以下恢复，原IX次日也恢复，主要改善是提前一天；不能把其后大涨都归给RC1。寒武纪2024-08-19和茅台2026-08-10则是背景仍偏上时新增的失败恢复，表明长期背景也会滞后。</p>'''
 titles=['黄金2026年3—7月：旧通道仍参与两次反弹','中际2025年6月：前高以下提前恢复','寒武纪2024年8月：新增恢复后再破锚','茅台2026年8月：旧上行背景未及时排除失败恢复']
 for c,title in zip(cases,titles):details+=f'<details><summary>{title}</summary><a href="details/{c["id"]}.png"><img loading="lazy" src="details/{c["id"]}.png" alt="{title}"></a></details>'
 details+='</div>'
 p=out/'index.html';s=p.read_text();marker='<div class="box"><h2>同批黄金、半导体和股票对照</h2>';assert marker in s and '本轮裁决' not in s;s=s.replace(marker,findings+details+marker);s=s.replace('<option value="added">','<option value="added" selected>').replace('let limit=100','let limit=20').replace('limit=100;draw()','limit=20;draw()');p.write_text(s)
 print(outcomes,flush=True)
if __name__=='__main__':main()
