"""Fixed 55-day breakout vs frozen MA entry, identical trend exits and risk rules."""
import hashlib
import json
from pathlib import Path
from campaign_engine import run_campaign
from hk_extension import load_extended
from trend_tail_audit import summarize

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/campaign-entry-transfer'
CONTROL = ROOT / 'results/campaign-low-atr-v1'


def main():
    OUT.mkdir(exist_ok=True)
    engine_hash = hashlib.sha256((ROOT / 'campaign_engine.py').read_bytes()).hexdigest()
    assert engine_hash == (CONTROL / 'engine-sha256.txt').read_text().strip()
    protocol = dict(
        hypothesis='Prior55day high breakout may reduce ordinary losses versus MA200 plus positive126day momentum, while preserving rare trends.',
        fixed='Same low_ATR ranking, trend exit, pyramiding, risk0.5%, portfolio guards, universe and dates as frozen control.',
        cases='A/HK/mixed breakout, base and double costs. All cases reported. No window search.',
        costs='base15bps plus HK FX10bps; stress30bps plus HK FX20bps. Minimum commissions unchanged.',
        evaluation='Net ordinary remainder excluding ex-post best10% campaigns, tail profits, open marked inventory, drawdown; not maximize CAGR.',
        limitations='Previously explored history and selected surviving ETFs; exploratory mechanism test, not holdout or individual-stock proof. Top10 grouping ex-post only.',
        engine_sha256=engine_hash)
    target = OUT / 'protocol.json'
    if target.exists():
        assert json.loads(target.read_text()) == protocol
    target.write_text(json.dumps(protocol, indent=2))
    assets, _ = load_extended()
    records = []
    for market in ['A', 'HK', 'mixed']:
        chosen = {n:a for n,a in assets.items() if market == 'mixed' or a['currency'] == ('CNY' if market == 'A' else 'HKD')}
        for stress in [False, True]:
            name = market + ('-breakout-cost2' if stress else '-breakout')
            m, p, o, c, s = run_campaign(chosen, entry='breakout', exit_mode='trend',
                pyramid=True, ranking='low_atr', cost_bps=30 if stress else 15, fx_bps=20 if stress else 10)
            m.update(case=name, market=market, entry='breakout', double_cost=stress)
            records.append(m)
            p.to_csv(OUT / (name + '-path.csv'))
            (OUT / (name + '-orders.json')).write_text(json.dumps(o))
            (OUT / (name + '-campaigns.json')).write_text(json.dumps(dict(closed=c, open=s)))
            (OUT / 'results.json').write_text(json.dumps(records, indent=2))
            a = summarize(c)
            print(name, json.dumps(dict(total_return=m['total_return'], drawdown=m['max_drawdown'],
                closed=len(c), opened=len(s), win_rate=a['win_rate'], payoff=a['payoff_ratio'],
                tail=a['top10_pnl'], ordinary=a['ordinary_pnl'])), flush=True)
    (OUT / 'engine-sha256.txt').write_text(engine_hash)


if __name__ == '__main__':
    main()
