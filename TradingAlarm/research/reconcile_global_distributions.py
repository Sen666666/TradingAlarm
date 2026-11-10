"""Keep issuer settlement evidence separate from frozen vendor signal inputs."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
from build_stock_features import ROOT


def parse_ishares(path):
    s=Path(path).read_text()
    # Issuer's unrelated disclaimers contain unescaped ampersands. Parse only
    # the complete distribution worksheet, without lossy XML recovery.
    begin='<ss:Worksheet ss:Name="Distributions">';end='</ss:Worksheet>'
    s=s[s.index(begin):];s=s[:s.index(end)+len(end)]
    root=ET.fromstring('<root xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'+s+'</root>')
    ns={'s':'urn:schemas-microsoft-com:office:spreadsheet'}
    rows=[[d.text for d in r.findall('s:Cell/s:Data',ns)] for r in root.findall('.//s:Row',ns)]
    assert rows[0][:4]==['Record Date','Ex-Date','Payable Date','Total Distribution']
    out=[]
    for r in rows[1:]:
        assert len(r)==8
        ex,pay=pd.Timestamp(r[1]),pd.Timestamp(r[2]);amount=float(r[3])
        assert pay>=ex and amount>=0
        components_available=all(x not in ('--', None, '') for x in r[4:])
        if components_available:
            assert abs(amount-sum(float(x) for x in r[4:]))<1e-6
        out.append(dict(ex_date=str(ex.date()),pay_date=str(pay.date()),amount=amount,record_date=str(pd.Timestamp(r[0]).date()),components_verified=components_available))
    assert len({r['ex_date'] for r in out})==len(out)
    return out


def parse_ssga(path, symbol):
    frame=pd.read_excel(path,sheet_name='dividend');frame.columns=frame.columns.str.strip()
    frame=frame[frame.TICKER.str.strip().eq(symbol)]
    assert len(frame)>0
    out=[]
    for _,r in frame.iterrows():
        ex,pay=pd.Timestamp(r['EX-DATE']),pd.Timestamp(r['PAYABLE DATE'])
        assert pay>=ex and pd.notna(r['DIVIDEND ($)'])
        capital=[r['SHORT TERM CAPITAL GAIN ($)'],r['LONG TERM CAPITAL GAIN ($)']]
        # Blank capital-gain cells represent no additional listed payment;
        # retain the source components so the assumption is reviewable.
        amount=float(r['DIVIDEND ($)'])+sum(float(v) for v in capital if pd.notna(v))
        out.append(dict(ex_date=str(ex.date()),pay_date=str(pay.date()),amount=amount,
                        record_date=str(pd.Timestamp(r['RECORD DATE']).date()),
                        capital_gain_components=[None if pd.isna(v) else float(v) for v in capital]))
    assert len({r['ex_date'] for r in out})==len(out)
    return out


def main():
    folder=ROOT/'data/global-transfer';summaries=[]
    for symbol in ('IEF','EFA','SPY'):
        path=folder/('SSGA-distributions.xlsx' if symbol=='SPY' else f'{symbol}-issuer-download.xls')
        if not path.exists():continue
        issuer=parse_ssga(path,symbol) if symbol=='SPY' else parse_ishares(path);bydate={r['ex_date']:r for r in issuer}
        vendor=json.loads((folder/f'{symbol}-distributions.json').read_text())
        merged=[];missing=[]
        for v in vendor:
            if v['ex_date'] not in bydate:missing.append(v['ex_date']);continue
            i=bydate[v['ex_date']]
            merged.append(dict(**i,symbol=symbol,vendor_amount=v['amount'],amount_difference=i['amount']-v['amount'],settlement_verified=i['pay_date']>=i['record_date'],source_file=path.name))
        extra=[r for r in issuer if '2006-01-01'<=r['ex_date']<='2025-12-31' and r['ex_date'] not in {v['ex_date'] for v in vendor}]
        (folder/f'{symbol}-issuer-distributions.json').write_text(json.dumps(merged,indent=2))
        summaries.append(dict(symbol=symbol,vendor_events=len(vendor),matched=len(merged),missing_dates=missing,issuer_only_events=extra,
            max_absolute_amount_difference=max(abs(r['amount_difference']) for r in merged),
            max_payment_delay_days=max((pd.Timestamp(r['pay_date'])-pd.Timestamp(r['ex_date'])).days for r in merged),
            invalid_chronology=[r['ex_date'] for r in merged if not r['settlement_verified']],
            differences_beyond_vendor_rounding=[r['ex_date'] for r in merged if abs(r['amount_difference'])>0.000501],
            usable=not missing and not extra and all(r['settlement_verified'] for r in merged),
            usable_execution_2007plus=not missing and not extra and all(r['settlement_verified'] for r in merged if r['ex_date']>='2007-01-01')))
    out=dict(records=summaries,note='Issuer gross distributions; withholding tax and broker settlement are not verified. Frozen vendor inputs/results remain unchanged. Use precise issuer amounts only in a separately versioned account run.')
    (ROOT/'results/global-transfer-freeze/settlement-reconciliation.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
