"""Normalize explicit implemented THS-style distribution rows; never invent pay dates."""
import re
from datetime import date


def parse_ths_rights(symbol, row):
    """Parse observed id211/471 text, rejecting unmodeled rights subscriptions."""
    text=row['471']
    match=re.fullmatch(r'(\d{4}-\d{2}-\d{2})\(每十股\s+(.+)\)\$',text)
    if not match:raise ValueError('unsupported rights record')
    effective=date.fromisoformat(match[1])
    if effective.strftime('%Y%m%d')!=str(row['1']):raise ValueError('rights dates disagree')
    tokens=re.findall(r'(转增|送股|送|红利)(\d+(?:\.\d+)?)(股|元)',match[2])
    tokens=[('送股' if k=='送' else k,a,u) for k,a,u in tokens]
    remainder=re.sub(r'(转增|送股|送|红利)\d+(?:\.\d+)?(?:股|元)','',match[2]).strip()
    if remainder or not tokens or len({x[0] for x in tokens})!=len(tokens):raise ValueError('unmodeled rights component')
    values={}
    for kind,amount,unit in tokens:
        if unit!=('元' if kind=='红利' else '股'):raise ValueError('incorrect rights units')
        values[kind]=float(amount)/10
    return dict(symbol=symbol,effective_date=str(effective),gross_cash_per_old_share=values.get('红利',0.),
                bonus_shares_per_old_share=values.get('送股',0.),capitalization_shares_per_old_share=values.get('转增',0.),
                pay_date=None,new_share_tradable_date=None,announcement_date=None,
                source='THS id211 datatype1,471',ledger_ready=False)


def normalize_distribution(row):
    if row.get('status') != '实施方案':
        return None
    text=row['plan'].replace(' ','')
    # Deliberately reject nonstandard plans rather than silently lose a share event.
    match=re.fullmatch(r'10(?:送(?P<bonus>\d+(?:\.\d+)?)股?)?(?:转(?:增)?(?P<split>\d+(?:\.\d+)?)股?)?(?:派(?P<cash>\d+(?:\.\d+)?)元?)?(?:\(含税\))?',text)
    if not match or not any(match.groupdict().values()):
        raise ValueError('unsupported distribution plan')
    announcement=date.fromisoformat(row['announcement_date'])
    record=date.fromisoformat(row['record_date']);ex=date.fromisoformat(row['ex_date'])
    if not announcement<=record<ex:
        raise ValueError('invalid announcement/record/ex-date sequence')
    cash=float(match['cash'] or 0)/10
    bonus=float(match['bonus'] or 0)/10
    split=float(match['split'] or 0)/10
    pay=row.get('pay_date')
    listing=row.get('new_share_tradable_date')
    if pay and date.fromisoformat(pay)<ex:raise ValueError('pay date before ex-date')
    if listing and date.fromisoformat(listing)<ex:raise ValueError('new-share date before ex-date')
    return dict(symbol=row['symbol'],announcement_date=str(announcement),record_date=str(record),ex_date=str(ex),
                gross_cash_per_old_share=cash,bonus_shares_per_old_share=bonus,capitalization_shares_per_old_share=split,
                pay_date=pay,new_share_tradable_date=listing,source=row['source'],
                ledger_ready=(cash==0 or bool(pay)) and (bonus+split==0 or bool(listing)),
                tax_treatment='unmodeled; gross dividend only')
