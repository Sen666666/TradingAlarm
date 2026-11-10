"""Match vendor ex-dates to issuer filing payment facts; do not infer missing years."""
import json
from build_stock_features import ROOT

SOURCES={
 'early':'https://www.sec.gov/Archives/edgar/data/1383148/000119312508099710/ds1.htm',
 '2008':'https://www.sec.gov/Archives/edgar/data/1328239/000119312510000195/dposasr.htm',
 '2019':'https://www.sec.gov/Archives/edgar/data/1328237/000156459020007544/dbc-10k_20191231.htm',
 '2022':'https://www.sec.gov/Archives/edgar/data/1328237/000156459023002358/dbc-10k_20221231.htm',
 '2023':'https://www.sec.gov/Archives/edgar/data/1328237/000095017024019059/dbc-20231231.htm',
 '2025':'https://www.sec.gov/Archives/edgar/data/1328237/000119312526083563/dbc-20251231.htm'}
# Manually transcribed numeric facts from DBC-specific tables/paragraphs.
# Ex-date is vendor evidence, not inferred from record date or settlement rules.
FACTS=[
 ('2006-12-18','2006-12-20','2006-12-29',.61,'early'),
 ('2007-12-17','2007-12-19','2007-12-28',.76,'early'),
 ('2008-12-15','2008-12-17','2008-12-30',.34,'2008'),
 ('2018-12-24','2018-12-26','2018-12-31',.18853,'2019'),
 ('2019-12-23','2019-12-24','2019-12-31',.25383,'2019'),
 ('2022-12-19','2022-12-20','2022-12-23',.14467,'2022'),
 ('2023-12-18','2023-12-19','2023-12-22',1.08926,'2023'),
 ('2024-12-23','2024-12-23','2024-12-27',1.11582,'2025'),
 ('2025-12-22','2025-12-22','2025-12-26',.74424,'2025')]


def main():
    folder=ROOT/'data/global-transfer'
    vendor=json.loads((folder/'DBC-distributions.json').read_text())
    bydate={r['ex_date']:r for r in vendor}
    assert set(bydate)=={r[0] for r in FACTS}
    rows=[]
    for ex,record,pay,amount,source in FACTS:
        assert ex<=record<=pay
        delta=amount-bydate[ex]['amount'];assert abs(delta)<=.000501
        rows.append(dict(symbol='DBC',ex_date=ex,record_date=record,pay_date=pay,amount=amount,
                         vendor_amount=bydate[ex]['amount'],amount_difference=delta,
                         settlement_verified=True,source=SOURCES[source],
                         ex_date_source='DBC-yahoo.json',amount_record_pay_source='issuer regulatory filing',
                         source_accessed='2026-10-18'))
    (folder/'DBC-issuer-distributions.json').write_text(json.dumps(rows,indent=2))
    result=dict(matched_vendor_events=len(rows),verified_payment_events=len(rows),
        complete_against_vendor=True,independent_all_years_completeness=False,
        scope='All 9 vendor-listed events matched to issuer amount/record/payment facts. Does not prove no omitted events in all intervening years. Gross shareholder distributions; no investor-specific taxation modeled.',
        sources=SOURCES)
    (ROOT/'results/global-transfer-freeze/DBC-settlement-reconciliation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
