"""Small dated-rule adapter for the fixed first10 study; no facts are invented.

The frozen manifest supplies verified versions or explicitly approved proxies.
An unqualified current lot/venue snapshot is never a historical rule version.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime
from typing import Mapping
from sector_account import QuantityRule


class RuleUnavailable(ValueError):
    """Missing or unapproved evidence; callers retain an unknown status."""


def day(value):
    if isinstance(value,datetime):return value.date()
    return value if isinstance(value,date) else date.fromisoformat(value)


@dataclass(frozen=True)
class ResolvedQuantity:
    quantity: QuantityRule
    source_id: str
    basis: str
    status: str
    valid_from: date
    valid_to: date | None
    proxy_id: str | None = None


def version_on(versions,on_date,approved_proxy_ids=()):
    target=day(on_date);ranges=[]
    for row in versions:
        lo=day(row['from']);hi=day(row['to']) if row.get('to') else None
        if hi is not None and hi<=lo:raise ValueError('Invalid version interval')
        if not row.get('source_id'):raise RuleUnavailable('Rule has no source identity')
        ranges.append((lo,hi,row))
    ranges.sort(key=lambda x:x[0])
    for left,right in zip(ranges,ranges[1:]):
        if left[1] is None or left[1]>right[0]:raise ValueError('Overlapping rule versions')
    matches=[r for lo,hi,r in ranges if lo<=target and (hi is None or target<hi)]
    if not matches:raise RuleUnavailable('No rule version for this historical date')
    row=matches[0];basis=row.get('basis')
    if basis=='official_rule':
        if row.get('verification_status')!='verified':raise RuleUnavailable('Official rule not marked verified')
    elif basis=='explicit_research_proxy':
        if not row.get('proxy_id') or row['proxy_id'] not in approved_proxy_ids:
            raise RuleUnavailable('Research proxy was not frozen/approved')
    else:raise RuleUnavailable('Unknown rule evidence basis')
    return row


def quantity_version(manifest:Mapping,sid:str,on_date,approved_proxy_ids=()):
    row=version_on(manifest.get('quantity_versions',{}).get(sid,()),on_date,approved_proxy_ids)
    rule=QuantityRule(**row['rule'])
    return ResolvedQuantity(rule,row['source_id'],row['basis'],
        'verified_rule' if row['basis']=='official_rule' else 'explicit_proxy',
        day(row['from']),day(row['to']) if row.get('to') else None,row.get('proxy_id'))


def market_identity_on(manifest:Mapping,sid:str,on_date,approved_proxy_ids=()):
    """Historical venue is separate from today's fixed pool membership.

    A current .BJ suffix cannot create a BSE interval over earlier NEEQ history.
    venue_not_before is a source-backed global floor, not a per-stock IPO date.
    """
    row=version_on(manifest.get('venue_versions',{}).get(sid,()),on_date,approved_proxy_ids)
    venue=row.get('venue')
    if venue not in ('SSE_MAIN','SSE_STAR','SZSE_MAIN','SZSE_CHINEXT','BSE','HKEX_MAIN','HKEX_GEM','NEEQ'):
        raise RuleUnavailable('Unknown trading venue identity')
    floor=manifest.get('venue_not_before',{}).get(venue)
    if floor:
        if not floor.get('source_id'):raise RuleUnavailable('Venue opening floor lacks evidence')
        if day(on_date)<day(floor['from']):raise RuleUnavailable('Venue was not open yet')
    if venue=='NEEQ':raise RuleUnavailable('NEEQ observations are outside A/H exchange execution')
    return dict(venue=venue,source_id=row['source_id'],basis=row['basis'],proxy_id=row.get('proxy_id'),
                status='verified_rule' if row['basis']=='official_rule' else 'explicit_proxy')


def sellable_at(fill_at:datetime,session_opens,lag_sessions:int):
    """Inventory timing only; cash settlement uses its separately frozen policy."""
    if fill_at.tzinfo is None or fill_at.utcoffset() is None:raise ValueError('Aware execution time required')
    if type(lag_sessions) is not int or lag_sessions<0:raise ValueError('Nonnegative explicit session lag required')
    opens=list(session_opens)
    if any(x.tzinfo is None or x.utcoffset() is None for x in opens):raise ValueError('Aware session opens required')
    if opens!=sorted(set(opens)):raise ValueError('Unique increasing sessions required')
    local_dates=[x.astimezone(fill_at.tzinfo).date() for x in opens]
    if len(local_dates)!=len(set(local_dates)):raise ValueError('Multiple opens for one exchange session')
    if fill_at.date() not in local_dates:raise RuleUnavailable('Execution date is not in supplied calendar')
    if lag_sessions==0:return fill_at
    later=[x for x in opens if x.astimezone(fill_at.tzinfo).date()>fill_at.date()]
    if len(later)<lag_sessions:raise RuleUnavailable('Calendar lacks required future sessions')
    return later[lag_sessions-1]


def a_sellable_at(fill_at:datetime,exchange_session_opens):
    """For an already admitted ordinary A-share fill, prevent same-day resale."""
    return sellable_at(fill_at,exchange_session_opens,1)
