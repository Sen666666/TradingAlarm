"""Single-position shadow protection paths; no cash, fills, costs or new returns."""
from ph_common import *
import math
from datetime import datetime
import phase_policy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SHADOW = O / 'shadow'
COLORS = {'E0': '#a56e16', 'F': '#2878a5', 'PH': '#9a3d95'}
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def stamp(day, hour='15:00:00'):
    return pd.Timestamp(str(day)[:10] + ' ' + hour, tz='Asia/Shanghai').isoformat()


def run_case(case, inputs):
    sector, sid = case['group'], case['symbol']
    sources = {
        'market': PREPS[sector] / 'signals' / f'{sid}.parquet',
        'facts': PREPS[sector] / 'facts' / f'{sid}.parquet',
        'strict': STRICT[sector] / f'{sid}.parquet',
        'F': FAST[sector] / f'{sid}.parquet',
        'E0_events': O / 'events' / sector / f'{sid}.parquet',
        'old_account': SA / sector / 'AMT/accounts-v2/S__S0_base.json',
        'old_campaigns': SA / sector / 'AMT/analysis/campaigns.csv',
    }
    inputs.update({str(p): sha(p) for p in sources.values()})
    bars, facts, strict, fast, event = [pd.read_parquet(sources[k]) for k in ['market', 'facts', 'strict', 'F', 'E0_events']]
    bars = bars.reindex(facts.index)
    account = read(sources['old_account'])
    campaigns = pd.read_csv(sources['old_campaigns'], usecols=['account', 'symbol', 'entry_at'])
    matches = campaigns[(campaigns.account == 'S__S0_base') & (campaigns.symbol == sid)
                        & (campaigns.entry_at.str[:10] >= case['start'])
                        & (campaigns.entry_at.str[:10] <= case['end'])].sort_values('entry_at')
    if len(matches):
        entry_at = matches.iloc[0].entry_at
        contract = [r for r in account['audit_log'] if r['kind'] == 'entry_contract'
                    and r['sid'] == sid and r['at'] < entry_at][-1]
        decision_day = pd.Timestamp(contract['at'][:10])
        entry_support = float(contract['floor_signal'])
        anchor_kind = 'old_S_AMT1_base_first_actual_entry_in_window'
    else:
        f = facts.loc[case['start']:case['end']]
        eligible = f.i_buy.astype(bool) & strict.strict_target.reindex(f.index).astype(bool)
        assert eligible.any(), (sid, 'fixed window has no eligible hypothetical anchor')
        decision_day = eligible[eligible].index[0]
        j = facts.index.get_loc(decision_day)
        assert j + 1 < len(facts)
        entry_at = stamp(facts.index[j + 1], '09:30:00')
        entry_support = float(facts.loc[decision_day, 'i_floor'])
        anchor_kind = 'hypothetical_next_observed_open_after_first_I_and_S_AMT1'
    entry_day = pd.Timestamp(entry_at[:10])
    assert pd.Timestamp(case['start']) <= entry_day <= pd.Timestamp(case['end'])
    assert math.isfinite(entry_support) and entry_support > 0
    assert float(bars.loc[entry_day, 'open']) > entry_support, (sid, 'shadow opening anchor below initial support')
    entry_segment = facts.loc[entry_day, 'segment_id']
    states = {p: dict(phase='TRIAL', P=entry_support, L_star=None, E_entry=entry_support, entry_at=entry_at)
              for p in ['F', 'PH']}
    e0_floor = entry_support
    finished = {p: False for p in COLORS}
    traces = []
    for day, row in facts.loc[entry_day:case['end']].iterrows():
        if all(finished.values()):
            break
        assert row.segment_id == entry_segment, (sid, day, 'undefined source crossing')
        j = facts.index.get_loc(day)
        er, fr = event.loc[day], fast.loc[day]
        obs = dict(at=stamp(day, '15:10:00'), close=float(row.close), E=float(row.i_floor) if pd.notna(row.i_floor) else None,
                   E_prev=float(facts.iloc[j - 1].i_floor) if pd.notna(facts.iloc[j - 1].i_floor) else None, E_up=bool(er['event'] == 1),
                   pivot=float(er['pivot']) if pd.notna(er['pivot']) else None,
                   pivot_at=stamp(er.pivot_date) if pd.notna(er.pivot_date) else None,
                   F_up=bool(fr['event'] == 1),
                   F_pivot=float(fr['pivot']) if pd.notna(fr['pivot']) else None,
                   F_pivot_at=stamp(fr.pivot_date) if pd.notna(fr.pivot_date) else None,
                   risk_on=True, original_up=bool(row.i_target), exit_pending=False)
        for policy in COLORS:
            if finished[policy]:
                continue
            before = e0_floor if policy == 'E0' else states[policy]['P']
            if policy == 'E0':
                reason = 'E0' if not obs['original_up'] else 'protection' if phase_policy.compare(row.close, before) <= 0 else None
                after = before if reason else phase_policy.higher(before, obs['E'])
                diag = dict(phase_before='E0', phase_after='EXIT_PENDING' if reason else 'E0',
                            P_before=before, P_after=after, exit_required=bool(reason), exit_reason=reason,
                            handoff=False, F_eligible=False, F_applied=False)
                e0_floor = after
            else:
                result = phase_policy.step(states[policy], obs, policy)
                states[policy] = result['state']
                diag = result['diagnostic']
                assert phase_policy.compare(diag['P_after'], before) >= 0
                if diag['handoff']:
                    assert not diag['F_applied']
                    assert diag['P_after'] == phase_policy.higher(before, obs['E'])
                if diag['phase_before'] in ('BRIDGE', 'TREND'):
                    assert not diag['F_applied']
            finished[policy] = diag['exit_required']
            traces.append(dict(diag, date=str(day.date()), policy=policy, obs=obs.copy()))
    summary = dict(**case, anchor_kind=anchor_kind, decision_day=str(decision_day.date()),
                   entry_at=entry_at, E_entry=entry_support, opening_price=float(bars.loc[entry_day, 'open']), policies={})
    for p in COLORS:
        rr = [r for r in traces if r['policy'] == p]
        summary['policies'][p] = {
            'last_close': rr[-1]['date'], 'exit_close': rr[-1]['date'] if rr[-1]['exit_required'] else None,
            'exit_reason': rr[-1]['exit_reason'], 'last_phase': rr[-1]['phase_after'],
            'handoffs': [dict(date=r['date'], phase=r['phase_after'], P_before=r['P_before'],
                              P_after=r['P_after'], E=r['obs']['E'], same_day_F_up=r['obs']['F_up'],
                              same_day_F_pivot=r['obs']['F_pivot'], F_applied=r['F_applied']) for r in rr if r['handoff']],
            'F_applied_count': sum(r['F_applied'] for r in rr),
            'exit_before_handoff': bool(p == 'PH' and rr[-1]['exit_required'] and not any(r['handoff'] for r in rr)),
            'bridge_observations': sum(r['phase_after'] == 'BRIDGE' for r in rr),
            'trend_observations': sum(r['phase_after'] == 'TREND' for r in rr),
        }
    save(SHADOW / f'{sector}-{sid}-trace.json', traces)
    return summary, bars.loc[case['start']:case['end']], traces


def plot(cases, path):
    fig, axs = plt.subplots(3, 3, figsize=(18, 9), gridspec_kw={'height_ratios': [4, 1.3, .8]})
    for j, (c, bars, traces) in enumerate(cases):
        ax, av, ap = axs[:, j]
        ax.plot(bars.index, bars.close, c='#4b535a', lw=1, label='收盘')
        ax.fill_between(bars.index, bars.low, bars.high, color='#bfc8d0', alpha=.35)
        entry = pd.Timestamp(c['entry_at'][:10])
        ax.axvline(entry, c='#555', ls=':', lw=.8)
        for p, color in COLORS.items():
            rr = [r for r in traces if r['policy'] == p]
            ts = pd.to_datetime([r['date'] for r in rr])
            ax.plot(ts, [r['P_after'] for r in rr], color=color, ls='--' if p == 'F' else '-',
                    lw=1.4 if p == 'PH' else 1, drawstyle='steps-post', label=p + '下一观察保护')
            for r in rr:
                if r['handoff']:
                    ax.scatter(pd.Timestamp(r['date']), r['P_after'], marker='*', c=color, s=80, zorder=6)
                    ax.annotate(r['phase_after'], (pd.Timestamp(r['date']), r['P_after']), fontsize=6, xytext=(3, 8), textcoords='offset points')
                if r['exit_required']:
                    ax.scatter(pd.Timestamp(r['date']), r['obs']['close'], marker='x', c=color, s=45, zorder=7)
            if p == 'PH':
                code = {'TRIAL': 1, 'BRIDGE': 2, 'TREND': 3, 'EXIT_PENDING': 0}
                ap.step(ts, [code[r['phase_after']] for r in rr], where='post', color=color, lw=1.5)
        label = '旧账户真实入场锚' if c['anchor_kind'].startswith('old_') else '假设入场锚'
        ax.set_title(f"{c['name']} {c['symbol']}\n{label} {str(entry.date())}", fontsize=10)
        ax.legend(fontsize=6, loc='best')
        av.bar(bars.index, bars.amount / 1e8, color=np.where(bars.close.diff() >= 0, '#b66c62', '#4c9387'), width=1.5)
        av.set_ylabel('实际金额/亿元', fontsize=8)
        ap.set_yticks([0, 1, 2, 3], ['EXIT', 'TRIAL', 'BRIDGE', 'TREND'], fontsize=6)
        ap.set_ylim(-.2, 3.2)
        for a in [ax, av, ap]:
            a.set_xlim(bars.index[0], bars.index[-1]); a.grid(alpha=.15)
            a.tick_params(axis='x', rotation=20, labelsize=7)
    fig.suptitle('PH1固定窗影子轨迹：单一观察锚，ACT始终开启；星号=交接，叉号=退出判定\n不分配资金、不模拟新成交/收益；同日新保护仅供之后使用', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .93)); fig.savefig(path, dpi=120); plt.close(fig)


def main():
    assert read(O / 'raw-review.json')['reviewed'] and read(O / 'event-validation.json')['passed']
    SHADOW.mkdir(exist_ok=False)
    inputs = {str(p): sha(p) for p in [Path(__file__), O / 'code/phase_policy.py', O / 'RULES.txt', SA / 'raw/cases.json']}
    cases = [run_case(case, inputs) for case in read(SA / 'raw/cases.json')['cases']]
    images = []
    for i in range(4):
        path = SHADOW / f'overview-{i + 1}.png'; plot(cases[i * 3:(i + 1) * 3], path); images.append(str(path))
    assert all(sha(p) == h for p, h in inputs.items()), 'input_changed'
    save(SHADOW / 'summary.json', {
        'cases': [c[0] for c in cases], 'images': images, 'input_sha256': inputs,
        'anchor_rule': 'first actual entry inside each fixed window in PRIOR S-AMT1 base account; otherwise first original I AND S-AMT1 close in window followed by next observed opening date, explicitly hypothetical',
        'risk_on': True, 'ACT_note': 'Always on only to isolate position protection. This deliberately does not reuse or simulate any account pause schedule.',
        'no_allocation_or_trade_execution': True, 'returns_computed': False,
        'one_shadow_cycle_per_window': True, 'new_policy_cannot_reopen_after_exit': True,
        'phase_clock': 'Original closing-pivot dates stamped at 15:00 Asia/Shanghai exactly as the frozen PH1 study contract; actual opening anchors at 09:30.',
        'sizing_note': 'Neither A nor R sizing is evaluated; only protection-state paths at a common anchor.',
        'cases_with_mature_handoff': sum(bool(c[0]['policies']['PH']['handoffs']) for c in cases),
        'cases_exiting_before_handoff': sum(c[0]['policies']['PH']['exit_before_handoff'] for c in cases),
        'guard_checks': ['No protection reduction', 'M-before-F excludes new F on handoff close', 'No F updates in BRIDGE/TREND', 'Exit is absorbing per shadow cycle', 'No source-segment crossing'],
        'reviewed': False,
    })
    print(json.dumps({'cases': len(cases), 'mature': sum(bool(c[0]['policies']['PH']['handoffs']) for c in cases), 'images': images}, ensure_ascii=False))


if __name__ == '__main__':
    main()
