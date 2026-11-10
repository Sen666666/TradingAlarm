"""Final bounded-horizon readout and immutable-output verification; no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,hashlib,sys
import pandas as pd
O=Path(__file__).resolve().parent;R=O/'facts_v9';S=R/'full_20241031_once';rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
summary=rd(R/'COMPARISON_SUMMARY.json');last=summary['last_difference'];assert last['day']=='2024-10-25';gate=rd(O/'gateoff_validation_facts_v9/BASELINE_EXACT_VALIDATION.json');assert gate['result']=='PASS' and gate['through']=='2024-10-25'
lineages=rd(R/'BARRED_SEED_PATH_LINEAGES.json');nofills=rd(S/'NO_FILLS.json');assert len(nofills)==4 and all(x['side']=='BUY_SEED' for x in nofills);assert len(lineages)==4 and all(x['scenario_blocked_same_seed'] for x in lineages);assert all(x['baseline_add_count']==0 for x in lineages)
decomp=rd(R/'DAILY_PATH_ACCOUNTING_DECOMPOSITION.json')[-1];ro=rd(R/'FREEZE.json');base=Path(ro['source_facts'])/'full_20241031_once'
held=[x for x in rd(S/'HOLDINGS.json') if x['day']=='2024-10-25' and x['sid']=='300277.SZ'];assert sum(x['qty'] for x in held)==100
m=next(x for x in rd(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')) if x['symbol']=='300277.SZ');src=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(src)==m['source_sha256'][str(src)];z=pd.read_parquet(src);assert z.loc['2024-10-28':'2024-10-31'].empty;nextrow=str(z[z.index>pd.Timestamp('2024-10-25')].index.min().date())
gap=dict(planned_end='2024-10-31',certified_through='2024-10-25',first_uncertified_day='2024-10-28',sid='300277.SZ',scenario_held_qty=100,scenario_last_holdings=held,missing_rows=['2024-10-28','2024-10-29','2024-10-30','2024-10-31'],next_source_row=nextrow,source=str(src),source_sha256=sha(src),reason='Frozen signal source has no rows for an actual held security. This report does not infer a suspension solely from missing rows.',no_old_price_carry=True,no_virtual_open=True,no_silent_inventory_deletion=True,partial_orders=rd(S/'UNCERTIFIED_DAY.json')['partial_orders'],planned_horizon_directory_name_is_not_completion_claim=True)
assert not gap['partial_orders']
for name,obj in [('INTENDED_HORIZON_NOT_COMPLETED',gap)]:
 p=R/(name+'.json');assert not p.exists();p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
# Verify every frozen source, plus all prior and current exported output manifests.
protected={};versions=[]
for v in sorted(O.glob('facts_v[0-9]*'))+sorted(O.glob('gateoff_validation_facts_v[0-9]*')):
 f=rd(v/'FREEZE.json')
 for p,h in {**f['source_hashes'],**f['scenario_hashes']}.items():
  if p in protected:assert protected[p]==h,('INCONSISTENT_FROZEN_HASH',p)
  protected[p]=h
 version=dict(path=str(v),source_facts=f['source_facts'],through=rd(v/'RUN_STATUS.json')['certified_through'],output_manifests=[])
 for out in sorted(v.glob('*/OUTPUT_HASHES.json')):
  hashes=rd(out)
  for n,h in hashes.items():
   if n!='OUTPUT_HASHES.json':assert sha(out.parent/n)==h,('OUTPUT_DRIFT',out.parent/n)
  version['output_manifests'].append(dict(path=str(out),sha256=sha(out),verified_files=len(hashes)))
 versions.append(version)
assert all(sha(p)==h for p,h in protected.items()),'FROZEN_SOURCE_DRIFT'
checks=rd(R/'PRIOR_PREFIX_REPLAY_QA.json');assert checks['result']=='PASS' and checks['through']=='2024-10-24'
source_evidence={str(p):sha(p) for p in [Path(__file__),R/'COMPARISON_SUMMARY.json',R/'DAILY_PATH_ACCOUNTING_DECOMPOSITION.json',R/'BARRED_SEED_PATH_LINEAGES.json',R/'INTENDED_HORIZON_NOT_COMPLETED.json',O/'gateoff_validation_facts_v9/BASELINE_EXACT_VALIDATION.json']}
seal=dict(result='PASS',scope='Bounded execution-stress research through 2024-10-25; planned 10/31 horizon not completed.',frozen_source_files_verified=len(protected),versions=versions,source_evidence=source_evidence,execution_source_unchanged_since_v4=True,no_original_baseline_artifact_modified_by_this_research=True)
lines=['# 一字bar成交敏感性对照：最终可核账至2024-10-25','', '**计划终点10/31未完成。** 主线与压力账均因实际持仓300277在10/28缺整行行情而停止，不能把目录名full_20241031_once理解为已完成10/31。没有沿用旧价、虚构OPEN或删去持仓。','', '## 共同33日结果',f'- 压力NAV：{D(last["scenario_NAV"]):,.2f}元；同事实基线NAV：{D(last["baseline_NAV"]):,.2f}元；压力减基线：{D(last["difference_NAV"]):+,.2f}元。',f'- 压力现金：{D(last["scenario_cash"]):,.2f}元；应收0；市值：{D(last["scenario_market_value"]):,.2f}元；净清算NAV：{D(last["scenario_net_liquidation_NAV"]):,.2f}元。',f'- 压力持仓{last["scenario_stocks"]}只、{last["scenario_shares"]}股、仓位{D(last["scenario_weight_pct"]):.4f}%；基线{last["baseline_stocks"]}只、{last["baseline_shares"]}股、{D(last["baseline_weight_pct"]):.4f}%。','- 两账均有1852笔实际订单，但交易内容并不相同。累计38项按日期/股票/方向汇总的交易路径差异，最新20只股票的累计损益存在差异。','', '## 四笔SEED无成交及完整路径']
for x in lineages:
 nf=next(n for n in nofills if n['sid']==x['sid'] and n['day']==x['seed_day']);a=x['baseline_attempt'];lines.append(f'- {x["seed_day"]} {x["sid"]} {x["name"]}：100股，raw同价{nf["raw_open"]}元，原批次预留{D(nf["reserved_cost"]):,.2f}元。基线对应轮截至10/25标记损益{D(a["marked_net_pnl"]):+,.2f}元，实际ADD次数0，退出日{a.get("exit_day","尚未退出")}。')
lines += ['- 压力中四张失败种子票均到期，未产生该轮持仓。截至可核截止日，四个对应基线轮没有直接派生ADD；不能据此推断10/25之后也没有。',f'- 被挡四股票的完整会计路径差额为{D(decomp["blocked_seed_symbol_pnl_difference"]):+,.2f}元，其他股票路径差额为{D(decomp["other_symbol_pnl_difference"]):+,.2f}元，两者合计为全户NAV差额。此为股票会计分组，不是独立因果归因。','- 原海能达轮10/14退出、收益381.73元已纳入完整路径；没有把这一数字直接当成全户反事实扣除。','', '## 不变规则和执行边界','- 1692成员、50有效行业和一份共享现金；M3/A/B/CP/I、2%/4%资本槽、费用、T+1、排序和资本规则全部保持原冻结合同。','- 每次复制的是压力路径当时真实状态，只计算该OPEN原始意图与数量上限，不借用基线未来持仓。先冻结完整原意图和买单预留，再事后应用全天raw O=H=L=C不成交。失败买单的预留直到整批结束才释放，不能分给同批后排。','- 失败SEED到期无持仓；失败ADD不消费CP，后续只能依原规则再计划；失败SELL保留lot并锁定退出，不能虚构卖出现金。历史四笔失败均为SEED；ADD/SELL失败语义由独立合成案例覆盖。','- raw OPEN ±5bp保持为成本代理，即使越过当日H/L也不能当作真实可成交价格证明。','', '## 9月24日后的实时不可知问题','- 9/24后市场快速普涨的速度、范围、持续行业与逐笔成交可达性，当时都不可知道。日线完整H/L/C到收盘才确定，所以本场景不能作为开盘交易信号、alpha、排序或同批资金重分配依据。','- 未重建历史ST、正式涨跌停价、竞价排队和对手盘；一字bar不等于真实必不能成交。该场景是条件成交可达性压力研究，不是实时排队模型，也不是收益下界。当前成员与行业分类并非PIT，也非完整历史A股。','', '## 验证与数据边界','- 冻结核心合同与执行源从v4起未改；先行12项合成测试通过，另有独立47项对抗案例。每次事实更新都以新目录保留旧版，并精确重放旧12家族。','- 最新v9已精确重放压力账至10/24的12家族。关闭gate后，33日九个原账输出家族与主线逐行精确一致，仅剥离候选的三个新增注释字段。','- 上述测试不认证真实交易所成交，也不补造10/28至10/31行情。独立逐笔核账/因果审计结论应以independent_oneprice_audit_v1对应版本报告为准。','', '## 文件索引','- facts_v9/full_20241031_once：可核至10/25的订单、候选、CP、账户日账、持仓、权益、50行业日账、尝试、期末待单、OPEN意图、预留及无成交。','- facts_v9/checkpoint_20241022和CHECKPOINT_20241022_COMPARISON：明确的10/22中间账。','- facts_v9/DAILY_BASELINE_DIFFERENCES、DAILY_SECTOR_DIFFERENCES、DAILY_SYMBOL_PATH_DIFFERENCES：每日账户、行业和逐股差额。','- facts_v9/ALL_OPEN_REJECTIONS、ALL_TRADE_PATH_DIFFERENCES、BARRED_SEED_PATH_LINEAGES：全部拒单、38项交易路径差异及被挡种子的后续路径。','- facts_v9/INTENDED_HORIZON_NOT_COMPLETED.json：300277缺行证据、原持仓和未完成期限。','- gateoff_validation_facts_v9/BASELINE_EXACT_VALIDATION.json：最终共同33日的基线精确复现。','- 各版FREEZE、OUTPUT_HASHES、PRIOR_PREFIX_REPLAY_QA及FINAL_BOUNDED_RESEARCH_SEAL保留来源与完整性验证。']
report=O/'FINAL_RESEARCH_READOUT_ZH.md';assert not report.exists();report.write_text('\n'.join(lines)+'\n');seal['final_readout_sha256']=sha(report);p=O/'FINAL_BOUNDED_RESEARCH_SEAL.json';assert not p.exists();p.write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(result='PASS',protected_sources=len(protected),versions=len(versions),through=last['day'],final_NAV=last['scenario_NAV'],NAV_difference=last['difference_NAV'],readout=str(report)),ensure_ascii=False))
