"""Frozen breakout/no-add rules on gold and bond fund proxies, without relabeling."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from campaign_engine import run_campaign
from hk_extension import load_extended
from trend_tail_audit import summarize

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/campaign-asset-transfer'


def main():
    OUT.mkdir(exist_ok=True)
    assets,_=load_extended()
    groups={'gold':['USHJ518880'],'bonds':['USHJ511010'],
        'gold_bonds':['USHJ518880','USHJ511010'],
        'equity':[n for n,a in assets.items() if a['kind']=='equity'], 'all':sorted(assets)}
    protocol=dict(groups=groups,rule='Unchanged55daybreakout entry,initial4ATR stop plus two closes belowMA200 exit,noadds,lowATRpriority.',
        capacity='Alleligible names;unchanged0.5%entryrisk,4%aggregatestoprisk,gross90%,single35%,sector45%,HK50%,drawdownguards.',
        cases='Eachgroup base,doublecost,oneextraexecutionday;all15cases.',
        data='ExistingTencentraw andEastmoneyfundactioncache. Explicitkind eligibility,not mislabeling bonds/gold as equities. Data quality audit saved.',
        limitations='ETFproxies,not direct gold/bond holdings,futures,or property. Reused2018+prices;execution2022+;no untouchedholdout. Dividend table completeness not certified against full issuer archive. Same fixed fees may be conservative for bond ETFs.',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    file=OUT/'protocol.json'
    if file.exists():assert json.loads(file.read_text())==protocol
    file.write_text(json.dumps(protocol,indent=2))
    audit=[]
    for n in groups['gold_bonds']:
        a=assets[n];raw=a['raw'];code=n[4:]
        assert raw.index.is_unique and raw.index.is_monotonic_increasing
        assert (raw[['open','high','low','close']]>0).all().all()
        bad=(raw.high<raw[['open','close','low']].max(axis=1))|(raw.low>raw[['open','close','high']].min(axis=1))
        audit.append(dict(symbol=n,kind=a['kind'],rows=len(raw),first=str(raw.index[0].date()),last=str(raw.index[-1].date()),ohlc_inconsistent_rows=int(bad.sum()),zero_volume=int((raw.volume==0).sum()),lot=a['lot'],volume_multiplier=a['volume_multiplier'],dividends=a['dividends'],splits=a['splits'],sha256={str(f.name):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/f'data/tencent-sh{code}-raw.json',ROOT/f'data/eastmoney-fhsp-{code}.html']}))
        assert not bad.any(), 'Malformed OHLC must be investigated before running'
    (OUT/'data-audit.json').write_text(json.dumps(audit,indent=2))
    records=[]
    for group,names in groups.items():
        for scenario in ['base','cost2','delay1']:
            case=group+'-'+scenario;chosen={n:assets[n] for n in names};decisions=[]
            m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),eligible_kinds=('equity','defensive'),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,extra_delay=1 if scenario=='delay1' else 0,decision_audit=decisions)
            if group=='equity' and scenario in ['base','cost2']:
                ref=ROOT/'results/campaign-capacity-audit';key='mixed-full'+('-cost2' if scenario=='cost2' else '')
                pd.testing.assert_frame_equal(p,pd.read_csv(ref/(key+'-path.csv'),index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-12)
                assert o==json.loads((ref/(key+'-orders.json')).read_text())
            for e in decisions:
                if e['event']=='sizing' and e['units']>0:assert e['planned_risk_before']+e['planned_risk_added']<=e['planned_risk_limit']+1e-6
            stats=summarize(c)
            m.update(case=case,group=group,scenario=scenario,closed_pnl=sum(x['pnl'] for x in c),ordinary_pnl=stats.get('ordinary_pnl'),tail_pnl=stats.get('top10_pnl'))
            records.append(m);p.to_csv(OUT/(case+'-path.csv'));(OUT/(case+'-orders.json')).write_text(json.dumps(o));(OUT/(case+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)));(OUT/'results.json').write_text(json.dumps(records,indent=2))
            print(case,{k:m[k] for k in ['total_return','max_drawdown','closed_campaigns','open_campaigns','closed_pnl']},flush=True)


if __name__=='__main__':main()
