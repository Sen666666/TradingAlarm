"""Inventory HK annotations without pretending all events are cash dividends."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def classify(e):
    if e.get('hgcgContent') or e.get('ggContent'):return 'share_action_requires_review'
    text=e.get('FHcontent','')
    if '实物分派' in text:return 'in_kind_distribution_requires_asset_ledger'
    if '认购' in text or '优先' in text:return 'subscription_right_requires_review'
    if re.fullmatch(r'(?:末期息|中期息|末期股息每股)([0-9.]+)港元;?',text):return 'cash_dividend_candidate'
    if text:return 'unparsed_distribution'
    if e.get('HGcontent','').startswith('回购'):return 'issuer_buyback_not_holder_cashflow'
    if e.get('HGcontent'):return 'unparsed_holder_annotation'
    return 'empty'

def main():
    d=json.loads((ROOT/'data/hk-stock-raw/hk00700.json').read_text());items=[];counts={}
    for row in d['rows']:
        for e in row[6:]:
            if not isinstance(e,dict):continue
            kind=classify(e);counts[kind]=counts.get(kind,0)+1
            if kind not in ('empty','issuer_buyback_not_holder_cashflow'):items.append(dict(date=row[0],kind=kind,vendor_event=e,verified_for_ledger=False))
    conflicts=[dict(date='2022-01-20',kind='in_kind_delivery_date',vendor_paixiri='2022-01-21',issuer_dispatch_date='2022-03-25',source='https://static.www.tencent.com/uploads/2023/04/06/214dce4c5312264800b20cfab64861ba.pdf',consequence='Do not release JD shares or cash on vendor date; dispatch date itself is not broker credited/tradable confirmation'),dict(date='2023-01-05',kind='in_kind_delivery_date',vendor_paixiri='2023-01-06',issuer_expected_dispatch='2023-03-24',source='https://static.www.tencent.com/uploads/2022/11/16/b92d6f78a14cbcc512c2b48f0942dd9f.pdf',consequence='Do not treat early-January vendor date as March share delivery'),dict(date='2014-05-16',kind='dividend_share_basis',vendor_amount=1.2,split_previous_day=5,proposed_post_split_amount=.24,source='https://static.www.tencent.com/storage/uploads/2019/11/09/fc317816961029ec11d0bed7b4c0965e.pdf',consequence='Require explicit post-split distribution confirmation;do not multiply1.2 by post-split shares')]
    report=dict(symbol='HK00700',rows=len(d['rows']),counts=counts,events=items,source_conflicts=conflicts,account_ready=False,limitation='Event list is provider coverage,not proof of completeness;buybacks do not automatically create a personal shareholder cashflow')
    (ROOT/'results/stock-data-audit/hk-pilot-actions.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(counts)
if __name__=='__main__':main()
