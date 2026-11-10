"""Publish already verified two-window evidence. No account or indicator work."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,shutil,inspect
import runner as R
O=R.O;W=R.W;IO=R.IO
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(x):return D(str(x))
def f(x):return f'{n(x):.2f}'

def main():
    results=[read(O/'analysis'/w/'COMPARISON.json') for w in ('2022','2025_26')]
    assert all(read(O/'runs'/w/'VERIFICATION.json')['passed'] and read(O/'analysis'/w/'COMPLETION.json')['passed'] for w in ('2022','2025_26'))
    for name in ('AUDIT_REPORT.txt','16TESTS.json','CORE_PRIORITY.json'):
        source=Path('/tmp/migration-native-independent.mTO77c')/name
        if source.exists():
            target=O/'independent-native-audit'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);assert sha(source)==sha(target)
    IO.write_json(O/'COMPARISON.json',results)
    lines=['原单遍＋迁池/新准入解耦（SD）｜固定两窗结果，待独立金融审计',
        'SC=已审原Bdiag（无账户3%准入门）；SD只移除route/request的迁池成功依赖。两窗各100万新起点。',
        '原signals/H1/数量/费用/ACT/预算/退出/日线执行均保留；无C1/R1/新stage/两遍。原SC账只读，未重跑。','',
        '时期 | SC收益/DD | SD收益/DD | 平均曝险SC→SD | 费用SC→SD']
    for r in results:
        s,t=r['SC'],r['SD']
        lines.append(f"{r['window']} | {f(s['return_pct'])}%/{f(s['global_DD']['percent'])}% | {f(t['return_pct'])}%/{f(t['global_DD']['percent'])}% | {f(s['mean_exposure_pct'])}%→{f(t['mean_exposure_pct'])}% | {f(s['fees'])}→{f(t['fees'])}元")
    lines+=['','结论：弱窗少亏，强窗少赚且DD更大，没有一致改善；目前不晋升为默认策略。未据结果改规则或续跑。','',
        '真实干预与资金竞争（“接纳”是原生预留，另列实际成交）：']
    for r in results:
        w=r['window'];s,t=r['SC'],r['SD'];c=r['funded_changes'];p=r['new_permission']
        lines.append(f"{w}: 接纳{s['admissions']}→{t['admissions']}，实际有fill订单{s['actual_filled_orders']}→{t['actual_filled_orders']}，零fill预留{s['zero_fill_reservations']}→{t['zero_fill_reservations']}；买/卖fill {s['buy_fills']}/{s['sell_fills']}→{t['buy_fills']}/{t['sell_fills']}。")
        lines.append(f"实际获资股{c['all_stocks']['SC']}→{c['all_stocks']['SD']}（新增{c['all_stocks']['gained']}、失去{c['all_stocks']['lost']}）；行业attempt {c['all_attempts']['SC']}→{c['all_attempts']['SD']}（新{c['all_attempts']['gained']}、失{c['all_attempts']['lost']}）。")
        lines.append(f"当次迁池本会失败仍新confirmed预留{p['admissions']}、成交凭据{p['filled_canonical_receipts']}，该批层净贡献{f(p['native_fill_contribution']['net'])}元；这是实际获准cohort，不是总政策因果收益。原因{p['by_original_migration_failure']}。")
        cov=t['opportunity_coverage'];lines.append(f"全市场合格freshCP1机会{cov['all_qualified_market_receipts']}张，confirmed实际获资{s['opportunity_coverage']['confirmed_mobile_filled_receipts']}→{cov['confirmed_mobile_filled_receipts']}；末收盘{cov['last_close_authorizations_next_open_outside_window']}张次开盘在窗外，单列右边界；ACT暂停机会未删分母。")
    lines+=['','贡献按真实层现金+已确认分红+剩余库存重估，全部加总核同NAV（元）：',
        '时期/政策 | 已全平正 | 已全平负 | 未平净 | 已全平肥尾 | 未平肥尾']
    for r in results:
        for ref in ('SC','SD'):
            c=r[ref]['contributions'];lines.append(f"{r['window']}/{ref} | {f(c['closed_positive'])} | {f(c['closed_negative'])} | {f(n(c['open_positive'])+n(c['open_negative']))} | {f(c['closed_tail'])} | {f(c['open_tail'])}")
    lines+=['肥尾沿旧每层净贡献/实买成本≥30%的描述口径；相关层不是独立胜率。未平贡献尚未兑现。',
        '2022新增权限层亏1.27万，但全户少亏3.52万；强窗新增权限层赚2.49万，但全户少赚7.83万。不能用该批层替代全政策评估。',
        '强窗长飞光纤贡献45590.63→1186.84、德福科技43134.46→10377.45元，两者差额约−7.72万。旧版12/19及4/22重入/新层尚未平，SD在原资源约束下未获资。不是新增买入层本身都亏。',
        '长飞12/19实际拒因probe_risk+sector_capital+sector_risk；德福4/22为pool_capital+probe_risk（两路拒因并集，不声称每项独占）。',
        '原前10赢家、全部逐股金额差分桥、新/失获资名单及前10正贡献/确定性最差3股完整路径均已保存；不据未来结果改名单。','',
        '旧probe等待（首个收盘仍probe且自身attempt已confirmed/expanded的真实层，非全部probe的均值）：']
    for r in results:
        for ref in ('SC','SD'):
            q=r[ref]['waits'];lines.append(f"{r['window']}/{ref}: {q['layers']}层；{q['statuses']}；后来观察迁入者等待median/max={q['observed_migration_lag_median']}/{q['observed_migration_lag_max']}观察；旧/失效attempt probe平均占资{f(q['old_or_inactive_probe_mean_capital'])}元。")
    lines+=['强窗SD已观察迁池max43对SC30，旧/失效probe平均占资3.72万对2.40万；新准入并不消除旧池占用。',
        '等待按收盘快照计，attempt先结束是竞争终点；只有仍有效等待至窗末者标右删失，不能用已迁入子集概括全体。',
        '资源拒绝按opening×股票×角色计且有共存原因；独占由旧probe造成的全部拒绝数未知，没有额外放松约束反事实。','',
        '固定三强行情复盘（SC→SD，峰值为实际行业市值/NAV，含被动涨价）：']
    cases=read(O/'analysis/2025_26/THREE_FIXED_CASES.json')
    for sector in dict.fromkeys(c['sector'] for c in cases):
        x,y=[c for c in cases if c['sector']==sector]
        lines.append(f"{x['industry']}: 首买{(x['first_actual_buy'] or {}).get('at','无')}→{(y['first_actual_buy'] or {}).get('at','无')}；新买{f(x['buy_cash'])}→{f(y['buy_cash'])}元；峰值{f(x['actual_peak_weight'][1])}%({x['actual_peak_weight'][0]})→{f(y['actual_peak_weight'][1])}%({y['actual_peak_weight'][0]})。")
    lines+=['中际旭创、新易盛在本强窗两策略均未实际获资；未使用白名单或整手例外。','',
        '工程与边界：两条完整SD，各242收盘，共2924笔真实fill、6次实际split；484日交易流/NAV、股数、费用和pool占用桥通过，8季度身份检查点通过。',
        '物理前缀到2022/1/10、2025/7/7，两侧落盘并真实重启；前缀随后接续为同一新臂。只有2个额外短物理截断技术视图，未重跑SC/C1/两遍/2023。',
        '原1709/90当前snapshot非PIT，原缺行/IPO/映射及权息时点代理保留；日线H/L/volume有效性和同开盘卖款复用仍是代理。',
        '现金桥取实际journal cashflows；库存估值继承原mark，并用同源原收盘复核，不是外部独立估值认证。',
        '两窗均已消费研究样本，normal结果不等于独立留出、执行压力或实盘认证。当前停止经济运行，等待独立审计。']
    IO.write_bytes(O/'RESULTS.txt',('\n'.join(lines)+'\n').encode())
    # Explicit saved traces for the two largest strong-window delta constituents.
    trace=rows(O/'runs/2025_26/pair/SD-route.jsonl.gz')
    chosen=[x for x in trace if (x['sid']=='601869.SH' and x['at'][:10]=='2025-12-19') or (x['sid']=='301511.SZ' and x['at'][:10]=='2026-04-22')]
    IO.write_json(O/'TWO_LARGE_WINNER_DIFFERENCES.json',dict(scope='post-hoc descriptive saved path, not future selection',SD_actual_route_records=chosen))
    first=[]
    for win in ('2022','2025_26'):
        old=W/('2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031')/'runs/B_diag/pair'
        new=O/'runs'/win/'pair';left=rows(old/'funding.jsonl.gz');right=rows(new/'funding.jsonl.gz')
        ix=next((i for i,(a,b) in enumerate(zip(left,right)) if a!=b),min(len(left),len(right)))
        first.append(dict(window=win,funding_sequence_first_difference_index=ix,SC=left[ix] if ix<len(left) else None,SD=right[ix] if ix<len(right) else None))
    IO.write_json(O/'FIRST_FUNDING_DIFFERENCES.json',first)
    timings={w:read(O/'runs'/w/'TIMING.json') for w in ('2022','2025_26')}
    IO.write_json(O/'READINESS_FOR_INDEPENDENT_AUDIT.json',dict(ready=True,independent_financial_audit_pending=True,
        frozen_native_adapter_sha=R.EXPECTED,new_complete_SD_paths=2,original_SC_paths_replayed=0,
        extra_short_physical_SD_views=2,C1=False,two_pass=False,R1=False,new_stage=False,new2023=False,
        daily_rows_verified=484,quarter_identity_checkpoints=8,actual_fill_records=2924,actual_splits=6,
        timings=timings,results='COMPARISON.json',source='runner.py wraps only read-only route/daily diagnostics and outputs; frozen native adapter unchanged',
        unknowns=['exclusive causal attribution of all old-probe blocks','future realization of terminal open contributions','PIT universe and live execution'],
        verdict='mixed two-window tradeoff; no default-strategy promotion or automatic next run'))
    text=inspect.getsource(R.Runner)+'\n'+inspect.getsource(R.migration_view)
    IO.write_bytes(O/'KEY_LOGGING_AND_OUTPUT_FUNCTIONS.txt',text.encode())
    audit_guide='''Independent review: run native/test_logging tests via unittest imports without __main__, directing output to /tmp.
Do not overwrite LOGGING_GATE.json: its exact generation-time bytes (including runtime) are in both run source freezes.
No economic replay is needed for financial review. Read the saved SC/SD books, 5 native flows, SD route/wait logs,
quarter checkpoints/provenance and analysis bridges. Native adapter SHA must remain 879579695da6b8b28fb9d411400836eea6f375dc1698b51b0502621ffd714b30.
Snapshot physical-prefix comparison excludes only immutable future input lookups, retains every native account field.
Attempt-wait statuses were clarified during saved-book analysis: ended attempts are competing endpoints, not right-censored active attempts.
No account/source/decision changes were made for that classification. All final results use the final analysis source.
'''
    IO.write_bytes(O/'AUDIT_GUIDE.txt',audit_guide.encode())
    files=[p for p in O.rglob('*') if p.is_file() and p.name!='ARTIFACT_SHA256.json' and '__pycache__' not in p.parts]
    IO.write_json(O/'ARTIFACT_SHA256.json',{str(p.relative_to(O)):sha(p) for p in sorted(files)})
    print('PUBLISHED2_SD',len(files),'files',sha(Path(R.__file__)),flush=True)

if __name__=='__main__':main()
