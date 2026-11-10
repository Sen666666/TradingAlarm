"""Offline, self-contained report. No strategy calculation or account writes."""
import html
import pandas as pd
from g1util import *

def main():
    out=HERE/'report';out.mkdir(exist_ok=False);cases=read(HERE/'cases.json');summary=pd.read_csv(HERE/'summary.csv',float_precision='round_trip');payload={}
    for c in cases:
        d=pd.read_parquet(HERE/'inputs'/f"{c['symbol']}.parquet").loc[c['start']:c['end']];g=pd.read_parquet(HERE/'grading'/f"{c['symbol']}.parquet").loc[d.index];e=pd.read_parquet(HERE/'replay'/f"{c['symbol']}-evidence.parquet").loc[d.index];accounts={}
        for scenario in SCENARIOS:
            accounts[scenario]={}
            for policy in POLICIES:
                key='__'.join([c['id'],policy,scenario]);p=HERE/'accounts'/key;l=pd.read_parquet(p/'ledger.parquet');t=pd.read_csv(p/'trades.csv',float_precision='round_trip');s=pd.read_parquet(HERE/'prepared'/c['id']/f'{policy}.parquet');stat=summary.loc[summary.key.eq(key)].iloc[0].to_dict()
                accounts[scenario][policy]=dict(nav=l.nav.tolist(),dd=(l.drawdown*100).tolist(),held=l.held.tolist(),floor=s.floor.tolist(),target=s.target.tolist(),buy_event=s.buy_event.tolist() if 'buy_event' in s else s.target.tolist(),trades=t.to_dict('records'),stats=stat)
        payload[c['id']]=dict(case=c,dates=[str(x.date()) for x in d.index],close=d.close.tolist(),volume_ratio=e.strength_activity.tolist(),score=g.score.tolist(),proposal=(g.proposal*25).tolist(),grade=g.grade.tolist(),label=g.display.tolist(),phase=g.phase.tolist(),z5=g.z5.tolist(),z21=g.z21.tolist(),S21=e.strength_S21.tolist(),S63=e.strength_S63.tolist(),fresh=g.fresh_up.tolist(),evidence=g.up_reasons.tolist(),reason=g.reason.tolist(),transition=g.transition.tolist(),blocked=g.promotion_blocked.tolist(),accounts=accounts)
    data=dict(cases=payload,summary=summary.to_dict('records'),analysis=read(HERE/'analysis/summary.json'),audit=read(HERE/'accounting-audit.json'),freeze=read(HERE/'freeze.json')['recorded_at'])
    template=(HERE/'code/report_template.html').read_text();template=template.replace('__PAYLOAD__',json.dumps(clean(data),ensure_ascii=False,allow_nan=False).replace('</','<\/')).replace('__PROTOCOL__',html.escape((HERE/'PROTOCOL.md').read_text()))
    (out/'index.html').write_text(template)
    write(out/'build.json',dict(recorded_at=now(),self_contained=True,external_resources=0,bytes=(out/'index.html').stat().st_size,source=str(Path(__file__).relative_to(ROOT)),sha256=sha(out/'index.html')))
    print(read(out/'build.json'),flush=True)

if __name__=='__main__':main()
