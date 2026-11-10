"""Transcribed public third-party payment dates; explicitly not issuer-verified."""
import json
from build_stock_features import ROOT
TABLE='''
2025 1222:1224 0924:0926 0626:0630 0325:0327
2024 1223:1226 0927:1001 0628:0702 0322:0327
2023 1221:1227 0928:1003 0629:0705 0324:0329
2022 1222:1228 0923:0928 0623:0628 0323:0328
2021 1227:1230 0924:0929 0624:0629 0325:0330
2020 1224:1230 0925:0930 0625:0630 0310:0313
2019 1218:1223 0924:0927 0627:0702 0328:0402
2018 1213:1218 0924:0927 0618:0621 0326:0329
2017 1221:1227 0922:0927 0623:0629 0322:0328
2016 1222:1229 0913:0919 0621:0627 0321:0328
2015 1223:1230 0923:0929 0626:0702 0325:0331
2014 1222:1229 0924:0930 0624:0630 0325:0331
2013 1224:1231 0923:0927 0624:0628 0322:0328
2012 1224:1231 0924:0928 0625:0629 0326:0330
2011 1223:1230 0923:0929 0624:0630 0325:0331
2010 1227:1231 0924:0930 0624:0630 0325:0331
2009 1224:1231 0924:0930 0624:0630 0325:0331
2008 1224:1231 0924:0930 0624:0630 0325:0331
2007 1220:1227 0924:0928 0625:0629 0326:0330
2006 1222:1229 0925:0929 0626:0630 0320:0329
'''

def main():
    dates={}
    for line in TABLE.strip().splitlines():
        year,*pairs=line.split()
        for pair in pairs:
            ex,pay=pair.split(':');dates[f'{year}-{ex[:2]}-{ex[2:]}']=f'{year}-{pay[:2]}-{pay[2:]}'
    folder=ROOT/'data/global-transfer';vendor=json.loads((folder/'VNQ-distributions.json').read_text())
    assert set(dates)=={r['ex_date'] for r in vendor}
    rows=[dict(r,pay_date=dates[r['ex_date']],settlement_verified=False,
               settlement_scenario=True,payment_source='https://dividendhistory.org/payout/VNQ/',
               amount_source='VNQ-yahoo.json') for r in vendor]
    assert all(r['pay_date']>=r['ex_date'] for r in rows)
    (folder/'VNQ-provisional-distributions.json').write_text(json.dumps(rows,indent=2))
    meta=dict(source='https://dividendhistory.org/payout/VNQ/',accessed='2026-10-18',events=len(rows),
              method='Payment dates transcribed from browser-readable public table; direct HTTP snapshot returned bot challenge and is NOT supporting evidence. Amounts retained from frozen vendor source, not third-party table (historical amounts can exclude capital return).',
              limitation='Not independently verified issuer history. Use only explicit provisional settlement scenario; test +10 observed-session payment delay. No tax or guaranteed broker-credit claim.')
    (folder/'VNQ-provisional-source.json').write_text(json.dumps(meta,indent=2));print(len(rows))

if __name__=='__main__':main()
