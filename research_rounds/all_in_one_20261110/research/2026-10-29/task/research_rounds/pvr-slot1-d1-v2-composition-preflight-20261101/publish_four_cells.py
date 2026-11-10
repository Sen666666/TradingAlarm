"""Saved-data quarter money bridges, compact interpretation and audit index."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import collections,gzip,json,hashlib
import analyze_four_cells as F
O,OUT,ROOT,J=F.O,F.OUT,F.ROOT,F.J
Z=D(0)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):
    with gzip.open(path,'rt') as f:return [json.loads(x) for x in f]
def save(path,x):F.IO.write_json(path,J.W.canon(x))
def n(x):return D(str(x))

def main():
    result=read(OUT/'FOUR_CELL_COMPARISON.json');money={};bridges={}
    for ref,root in F.SPECS.items():
        with gzip.open(root/'pair/B.json.gz','rt') as f:b=json.load(f)
        ds=rows(root/'pair/daily.jsonl.gz');balances=rows(root/'pair/balances.jsonl.gz')
        quarters=collections.defaultdict(list)
        for r in ds:quarters[str(F.J.pd.Timestamp(F.day(r['at'])).to_period('Q'))].append(r)
        previous=dict(real=Z,unreal=Z,div=Z,nav=D(1000000));parts=[]
        for q,days in quarters.items():
            d=days[-1];cut=d['at'];cost=collections.defaultdict(lambda:Z);gross=collections.defaultdict(lambda:Z);flow=Z
            for t in b['trades']:
                if t['at']>cut:continue
                if t['side']=='buy':
                    cost[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny']);gross[t['layer']]+=n(t['gross_cny'])
                    flow-=n(t['gross_cny'])+n(t['fees_cny'])
                else:flow+=n(t['gross_cny'])-n(t['fees_cny'])
            # Original live close snapshot contains that close's ACTUAL unit
            # costs after only splits already occurred. No terminal basis is
            # carried backwards across future corporate actions.
            basis=sum((D(l['qty'])*n(l['unit_cost'])*cost[l['id']]/gross[l['id']]
                       for l in d['layers']),Z)
            real=flow+basis;unreal=n(d['inventory'])-basis;div=Z
            for a in b['audit']:
                if a['kind']!='dividend_accrual':continue
                rec=a['receivable']
                assert rec['currency']=='CNY' and 'ex_at' in rec
                if rec['ex_at']<=cut:div+=n(rec['net_local'])
            residual=D(1000000)+real+unreal+div-n(d['nav'])
            assert abs(residual)<D('.00000001'),(ref,q,residual)
            writeoffs=result['cells'][ref]['actual_realized_unrealized_dividends']['nontrade_writeoff_rows']
            nontrade=sum((n(x['nontrade_realized_cost_writeoff']) for x in writeoffs if x['known_at']<=cut),Z)
            prior_nontrade=parts[-1]['cumulative']['nontrade_fractional_writeoff'] if parts else Z
            changes=dict(strict_actual_closed_trade_realized_change=(real-nontrade)-(previous['real']-prior_nontrade),
                nontrade_fractional_writeoff_change=nontrade-prior_nontrade,
                unrealized_PnL_change=unreal-previous['unreal'],recognized_dividends=div-previous['div'])
            assert abs(sum(changes.values(),Z)-(n(d['nav'])-previous['nav']))<D('.00000001')
            parts.append(dict(quarter=q,start_NAV=previous['nav'],end_NAV=n(d['nav']),
                wealth_change=n(d['nav'])-previous['nav'],quarter_changes=changes,
                cumulative=dict(realized_including_nontrade_writeoffs=real,
                    strict_actual_closed_trade_realized=real-nontrade,nontrade_fractional_writeoff=nontrade,
                    unrealized_PnL=unreal,recognized_dividends=div),
                terminal_quarter_dividend_AR=d['dividend_receivable'],remaining_allocated_buy_cost=basis,
                residual=residual,asof_basis='that quarter original day-close live-layer unit_cost/qty snapshot plus trades already happened',
                dividend_clock='explicit native dividend_accrual.receivable.ex_at; no generic nested timestamp search'))
            previous=dict(real=real,unreal=unreal,div=div,nav=n(d['nav']))
        expected=result['cells'][ref]['actual_realized_unrealized_dividends']
        assert abs(previous['real']-n(expected['realized_including_nontrade_writeoffs']))<D('.00000001')
        assert abs(previous['unreal']-n(expected['unrealized_net_mark_minus_allocated_buy_cost']))<D('.00000001')
        money[ref]=parts
        grouped=collections.defaultdict(list)
        for b0 in balances:grouped[str(F.J.pd.Timestamp(F.day(b0['at'])).to_period('Q'))].append(b0)
        fields=('independent_NAV_difference','budget_NAV_difference','spendable_difference',
            'reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference')
        bridges[ref]={q:dict(days=len(rs),max_abs_difference={k:max(abs(n(x[k])) for x in rs) for k in fields},
            max_abs_pool_occupancy_difference=max(abs(n(v)) for x in rs for v in x['pool_occupancy_difference'].values())) for q,rs in grouped.items()}
        bridges[ref]['full_window']=dict(days=len(balances),all_original_independent_cashflow_NAV_differences_zero=
            all(n(x['independent_NAV_difference'])==0 for x in balances),
            max_abs_difference={k:max(abs(n(x[k])) for x in balances) for k in fields})
    save(OUT/'QUARTER_REALIZED_UNREALIZED_DIVIDEND_WEALTH_BRIDGES.json',money)
    save(OUT/'QUARTER_AND_FULL_LEDGER_BRIDGES.json',bridges)
    cells=result['cells'];sc_seg_start=D('1254017.3510707366560');sc_end=D('1510396.4054562225250')
    status=read(ROOT/'EXECUTION_STATUS.json')
    completion=dict(scope='one SC own April1 -> June30 continuation',
        recorded_start=read(ROOT/'ACTUAL_START.json'),execution_status=status,
        completion_status_file_publication_UTC_from_filesystem=datetime.fromtimestamp((ROOT/'EXECUTION_STATUS.json').stat().st_mtime,timezone.utc).isoformat(),
        note='controller did not record a separate completion wall timestamp; publication evidence is labeled rather than backfilled',
        source_authorization_sha256=sha(ROOT/'FULL_RUN_AUTHORIZATION.json'),
        terminal_checkpoint_sha256=sha(ROOT/'checkpoint.pkl'),terminal_provenance_sha256=sha(ROOT/'checkpoint.provenance.json'),
        new59_session_return_pct=(sc_end/sc_seg_start-1)*100,
        full_Q2_return_pct=cells['SC_D1']['quarters'][-1]['return_pct'],
        full_Q2_includes_already_verified_April1=True,new_financial_paths=1)
    save(ROOT/'ACTUAL_COMPLETION_EVIDENCE.json',completion)
    real_adv=n(cells['PVR_D1']['actual_realized_unrealized_dividends']['strict_actual_closed_trade_realized'])-n(cells['SC_D1']['actual_realized_unrealized_dividends']['strict_actual_closed_trade_realized'])
    un_adv=n(cells['PVR_D1']['actual_realized_unrealized_dividends']['unrealized_net_mark_minus_allocated_buy_cost'])-n(cells['SC_D1']['actual_realized_unrealized_dividends']['unrealized_net_mark_minus_allocated_buy_cost'])
    lines=['SC/PVR × normal/D1，固定2025-07-01—2026-06-30完整四格；新SC接续完成待独审。',
      '本轮仅新增SC自身4/1close之后59交易日；旧183日日志(182旧日+4/1)逐项append-only。无其他金融路径，3个已核参考只读复用。',
      '', '格子 | 收益% | 最大DD% | 平均真实持仓% | 费用元 | 已平负贡献元 | 实际未实现净利元']
    for ref,m in cells.items():
        lines.append(f"{ref} | {n(m['return_pct']):.4f} | {n(m['global_DD']['percent']):.4f} | {n(m['mean_exposure_pct']):.4f} | {n(m['fees']):.2f} | {n(m['contributions']['closed_negative']):.2f} | {n(m['actual_realized_unrealized_dividends']['unrealized_net_mark_minus_allocated_buy_cost']):.2f}")
    lines += ['', '季度收益(全Q2含已经核过的4/1；不是把59日重归一掩盖旧净值)：']
    for ref,m in cells.items():lines.append(ref+': '+', '.join(q['quarter']+' '+f"{n(q['return_pct']):.4f}%" for q in m['quarters']))
    lines += ['',f"SC新增59日从1254017.3510707366560到1510396.4054562225250，区间{completion['new59_session_return_pct']:.6f}%；完整Q2 {n(cells['SC_D1']['quarters'][-1]['return_pct']):.6f}%，原1m以来51.039641%。输入39.84秒，剩余路径/导出56.07秒，总106.98秒。",
      '', '主要全流程取舍：',
      '1. SC D1相对normal收益-0.4954个百分点、DD13.1795→11.6623%；PVR D1相对normal收益-31.2123个百分点、DD9.0593→8.8186%。不能说一天延迟普遍伤害一样，也不能以D1仍盈利宣称实盘稳健。',
      f"2. PVR相对SC收益差normal +43.3616pp、D1 +12.6447pp，交互差-30.7169pp。D1下PVR纯实际卖出交易净利仅比SC多{real_adv:.8f}元；原286.36926元是含零股核销的已实现损益差，SC未平688257第727层核销0.40股成本损失27.86997322元，已单列；实际未实现多{un_adv:.8f}元。差额主要仍未兑现。原严格诊断门失败记录不改，这是单独获准探索试验，不是策略晋升。",
      '3. 预留/成交/零fill：SC normal926/902/24；SC D1 1197/748/449(含2期末待买)；PVR normal997/970/27；PVR D1 1481/960/521(含4期末待买)。D1平均待买本金占NAV分别3.6656%/4.3051%，资源仍被诚实占用。零fill不都等于信号失败或已终止。所有格ACT暂停0。',
      '4. 真实首次/追加/全清后重入层：SC normal480/232/190→D1 416/171/161；PVR normal576/245/149→D1 626/186/148。SC D1新增98股/失去162股；PVR D1新增184/失去134，不能只报净数；市场价格信号不变，后续core-first/池容量/旧单重验与退出现金释放会改变账户机会。',
      '5. 主线峰值权重SC normal/SC D1/PVR normal/PVR D1：军工Q4 11.66/9.61/14.18/11.74%；油气Q1 .154/.032/2.107/1.287%；严格半导体H1 4.57/4.66/7.54/5.81%。能源Q3 SC有小仓/PVR两格0。电子化学品全窗8.17/5.91/23.64/14.82%，不可合并成半导体抓住了。市值峰值包含被动涨价，不代表新买越过原行业上限。中际/新易四格均未参加，具体验证路径仍在各格fixed文件。',
      '6. SC D1贡献增加的正控制国际复材+48195、通鼎+14888，损失的机会长飞-44807、鼎泰-31496；PVR D1嘉美+43410但中船-99571、京蓝-64408、唯特偶-54489。是保存路径的账务差，不是逐股独立因果或可交换资金的反事实收益。',
      '', '季度财务桥用当季原close快照的真实unit_cost/qty及已发生交易、显式dividend_accrual.ex_at；不把终点复权成本/未来line倒填以前季度。closed层贡献与实际realized/unrealized明确分开，股息应收不是自由现金。完整精确金额见FOUR_CELL_COMPARISON/QUARTER_REALIZED_UNREALIZED_DIVIDEND_WEALTH_BRIDGES。',
      '新SC核242日cash/share/equity/fee/pool桥、1322笔fill(新增238)、4个实际持股送转(3split+1split_fraction_floor_proxy)、3旧D1季度身份+新June身份，无回填旧provenance。曾仅分析器漏fractional audit kind而在6/11报股数差，原账/镜像未错；失败/source保存，3个分析回归通过，没有重跑经济路径。',
      '', '支持：排序信息的实际价值与排队/整手/预算/角色优先有重大交互，normal优势不能直接迁移到延迟执行。否定“SC近似稳健即可证明PVR路径同样稳健”及“终值增加都已兑现”。未知：未平肥尾后续是否兑现、弱市压力表现、逐笔独占资源因果。四格均已消费窗口、snapshot非PIT、日线H/L/volume代理不能认证开盘盘口可得性；不自动改预算/阈值/排序或启新路径。']
    (OUT/'READOUT.txt').write_text('\n'.join(lines)+'\n')
    audit=dict(ready_for_independent_audit=True,new_SC_financial_path_only=True,
        parent_April1_checkpoint_sha256=read(ROOT/'FROZEN_RUN_METADATA.json')['parent_sha256'],
        terminal_checkpoint_sha256=sha(ROOT/'checkpoint.pkl'),source_controller_sha256=sha(O/'run_SC_D1_Q2.py'),
        composition_sha256=sha(O/'composition.py'),source_analysis_sha256=sha(O/'analyze_four_cells.py'),
        source_publish_sha256=sha(__file__),authorization_sha256=sha(ROOT/'FULL_RUN_AUTHORIZATION.json'),
        source_binding_exact_before_execution=True,old183_days_no_replay=True,
        verification=read(OUT/'SC_CONTINUATION_VERIFICATION.json'),
        corporate_action_report_regression=read(OUT/'CORPORATE_ACTION_SCHEMA_GATE.json'),
        financial_execution_status=status,four_cell_report=str(OUT/'READOUT.txt'),
        quarter_money_bridges=str(OUT/'QUARTER_REALIZED_UNREALIZED_DIVIDEND_WEALTH_BRIDGES.json'),
        analysis_failure_history=str(OUT/'analysis-split-schema-errata-v1'),
        independent_prior_evidence=str(ROOT/'independent-evidence'),new_policy_or_additional_path=False)
    save(ROOT/'AUDIT_READINESS.json',audit)
    paths=[x for x in ROOT.glob('*.json') if x.name!='ARTIFACT_SHA256.json']+list(OUT.glob('*.json'))+[OUT/'READOUT.txt',O/'run_SC_D1_Q2.py',O/'analyze_four_cells.py',Path(__file__)]
    save(ROOT/'ARTIFACT_SHA256.json',{str(p):sha(p) for p in paths})
    print('FOUR_CELL_AUDIT_READY',ROOT/'AUDIT_READINESS.json',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as ex:F.save(Path('failure/PUBLISH_ERROR.json'),dict(type=type(ex).__name__,reason=str(ex),economic_replays=0));raise
