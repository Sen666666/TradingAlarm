"""Offline current-snapshot cap join. Never downloads or executes a strategy.

Input quotes: actual collector snapshot {rows:[{symbol,raw_fields,observations}]},
or probe-compatible JSON list of {request, records, observed_at} batches,
or {results:[...]} / {records:[...], observed_at}. Exact native identity is mandatory.
FX input: {snapshot_date:'2026-10-22', rates:[{currency:'HKD', rate_to_cny:...,
effective_date:'2026-10-22', observed_at:'...', source:'...', source_sha256:'...'}]}.
Rates mean CNY per ONE unit of source currency. CNY identity needs no FX source.
An older documented FX rate is retained as an estimate. For stale FX, an explicit
rate_to_cny_min/max and bounds_basis can classify securities away from the threshold;
without bounds the size decision stays unknown. No uncertainty band is invented.
Writes new directory only; no implicit overwrite and no filling missing quotes.
"""
from pathlib import Path
import argparse, csv, json, hashlib, math
from collections import Counter, defaultdict
from datetime import datetime

HERE = Path(__file__).resolve().parent

def read_csv(path):
    with path.open() as f:return list(csv.DictReader(f))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def positive(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0
def truth(v):return str(v).strip().lower() in ('true','1','yes')

def quote_batches(obj, inherited=None):
    inherited=inherited or {}
    if isinstance(obj,list):
        for item in obj:yield from quote_batches(item,inherited)
    elif isinstance(obj,dict):
        context={**inherited,**{k:obj[k] for k in ('observed_at','request','body_sha256') if k in obj}}
        if 'rows' in obj:
            for row in obj['rows']:
                if not isinstance(row.get('symbol'),str):raise ValueError('Collector row missing native symbol')
                raw=row.get('raw_fields',{})
                for kind,keys in [('202',('2942','1771976','3475914','3541450')),('200',('10','55'))]:
                    fields={k:raw[k] for k in keys if k in raw}
                    if not fields:continue
                    observation=row.get('observations',{}).get(kind,{})
                    if not observation.get('returned_symbol_matched'):
                        if any(v is not None for v in fields.values()):
                            raise ValueError('Nonempty quote fields without confirmed returned native identity')
                        continue
                    yield {'5':row['symbol'],**fields}, {
                        'observed_at':observation.get('observed_at',''),
                        'body_sha256':observation.get('response_sha256',''),
                        'request':{'id':int(kind),'market':row.get('market'),'code':row.get('code')},
                        'as_of_date_label':row.get('as_of_date_label')}
        elif 'records' in obj:
            for record in obj['records']:yield record,context
        elif 'results' in obj:
            yield from quote_batches(obj['results'],context)
        elif '5' in obj:
            yield obj,context
        else:raise ValueError('Unsupported quote JSON shape; explicit records or native key 5 required')
    else:raise ValueError('Unsupported quote value')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--master',type=Path,default=HERE/'current-ah-security-master.resolved.csv')
    ap.add_argument('--ah-links',type=Path,default=HERE/'current-ah-company-links.csv')
    ap.add_argument('--quotes',type=Path,nargs='+',required=True)
    ap.add_argument('--quote-observed-at',default='',help='Explicit fallback observation time when input batch omits it; never inferred from mtime')
    ap.add_argument('--fx',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--snapshot-date',default='2026-10-22')
    args=ap.parse_args()
    if args.snapshot_date!='2026-10-22':raise ValueError('Frozen research snapshot is 2026-10-22')
    if args.output.exists():raise ValueError('Output already exists; choose a new directory to preserve prior evidence')
    rows=read_csv(args.master)
    native={r['ths_symbol']:r for r in rows}
    symbols={r['symbol']:r for r in rows}
    if len(native)!=len(rows) or len(symbols)!=len(rows) or '' in native:
        raise ValueError('Master contains missing/duplicate native or normalized symbol')
    caps=defaultdict(list);quotes=defaultdict(list);input_manifest=[];order=0
    for path in args.quotes:
        source_hash=sha(path)
        input_manifest.append({'path':str(path.resolve()),'sha256':source_hash})
        for record,context in quote_batches(json.loads(path.read_text())):
            order+=1
            sym=record.get('5')
            if not isinstance(sym,str):raise ValueError('Quote lacks exact native symbol 5')
            stamp=context.get('observed_at') or args.quote_observed_at
            if stamp:datetime.fromisoformat(stamp.replace('Z','+00:00'))
            evidence={'record':record,'observed_at':stamp,'source_file':str(path.resolve()),
                      'source_sha256':source_hash,'response_sha256':context.get('body_sha256',''),
                      'request':context.get('request',{}),'input_order':order}
            if '3541450' in record:caps[sym].append(evidence)
            if '10' in record:quotes[sym].append(evidence)
    def newest(items):
        # Explicit chronological observation where available; stable input order otherwise.
        return max(items,key=lambda x:(datetime.fromisoformat(x['observed_at'].replace('Z','+00:00')).timestamp()
                                      if x['observed_at'] else float('-inf'),x['input_order'])) if items else None
    cap_by_native={s:newest(v) for s,v in caps.items()}
    price_by_native={s:newest(v) for s,v in quotes.items()}
    fx={'CNY':{'currency':'CNY','rate_to_cny':1,'effective_date':args.snapshot_date,
               'observed_at':'','source':'CNY identity','source_sha256':''}}
    if args.fx:
        fx_obj=json.loads(args.fx.read_text())
        if fx_obj.get('snapshot_date')!=args.snapshot_date:raise ValueError('FX snapshot mismatch')
        for entry in fx_obj['rates']:
            c=entry['currency']
            if c=='RMB':c='CNY'
            if c in fx:raise ValueError('Duplicate/overridden FX currency')
            if not positive(entry.get('rate_to_cny')) or not entry.get('effective_date') or entry['effective_date']>args.snapshot_date:
                raise ValueError('FX must be positive CNY per unit, with a source date no later than the snapshot')
            if not all(entry.get(k) for k in ('source','observed_at','source_sha256')):
                raise ValueError('FX source, source hash and observation time are required')
            fx[c]={**entry,'currency':c}
        input_manifest.append({'path':str(args.fx.resolve()),'sha256':sha(args.fx)})
    ah_by_h={r['h_symbol']:r['a_symbol'] for r in read_csv(args.ah_links)
             if r.get('current_pair_status')=='both_current'}
    if any(a not in symbols or h not in symbols for h,a in ah_by_h.items()):
        raise ValueError('Current AH pair has absent master endpoint')
    records=[]
    for row in rows:
        sym=row['symbol'];n=row['ths_symbol'];r=dict(row)
        cap=cap_by_native.get(n);price=price_by_native.get(n)
        raw=cap['record'].get('3541450') if cap else None
        company_sym=ah_by_h.get(sym,sym)
        source_row=symbols[company_sym];source_native=source_row['ths_symbol']
        company_cap=cap_by_native.get(source_native)
        company_raw=company_cap['record'].get('3541450') if company_cap else None
        currency='CNY' if source_row['exchange']!='HK' else source_row['currency']
        if currency=='RMB':currency='CNY'
        rate=fx.get(currency)
        cap_status=('missing_supplier_ZSZ' if not company_cap else
                    'invalid_supplier_ZSZ' if not positive(company_raw) else
                    'missing_quote_observed_at' if not company_cap['observed_at'] else
                    'missing_currency_rate' if not rate else 'available' if rate['effective_date']==args.snapshot_date else 'available_stale_fx_estimate')
        cny=company_raw*rate['rate_to_cny'] if cap_status.startswith('available') else None
        lower=upper=None
        if cny is None:size='unknown'
        elif cap_status=='available':
            lower=upper=cny
            size='pass' if cny>10_000_000_000 else 'fail'
        else:
            lo,hi=rate.get('rate_to_cny_min'),rate.get('rate_to_cny_max')
            if positive(lo) and positive(hi) and lo<=rate['rate_to_cny']<=hi and rate.get('bounds_basis'):
                lower,upper=company_raw*lo,company_raw*hi
                size='pass' if lower>10_000_000_000 else 'fail' if upper<=10_000_000_000 else 'unknown'
            else:size='unknown'
        south='not_required_A' if row['exchange']!='HK' else ('pass' if truth(row.get('southbound_sse_eligible')) else 'fail')
        industry='pass' if row.get('industry_index_symbol') else 'unknown'
        security='review' if row.get('ordinary_share_review')=='name_mentions_PREF_requires_type_review' else 'pass'
        states=[size,south,industry,security]
        eligible='fail' if 'fail' in states else 'unknown' if 'unknown' in states or 'review' in states else 'pass'
        r.update(supplier_zsz_local=raw if raw is not None else '',supplier_zsz_currency=row['currency'],
                 supplier_zsz_observed_at=cap['observed_at'] if cap else '',
                 supplier_zsz_source_file=cap['source_file'] if cap else '',supplier_zsz_source_sha256=cap['source_sha256'] if cap else '',
                 supplier_zsz_response_sha256=cap['response_sha256'] if cap else '',
                 supplier_ltsz_diagnostic=cap['record'].get('3475914','') if cap else '',
                 quote_price_diagnostic=price['record'].get('10','') if price else '',
                 quote_price_observed_at=price['observed_at'] if price else '',
                 company_cap_source_symbol=company_sym,company_cap_source_native=source_native,
                 company_cap_rule='current_A_ZSZ_for_both_AH' if company_sym!=sym else 'supplier_ZSZ_own_listing',
                 company_cap_raw=company_raw if company_raw is not None else '',company_cap_currency=currency,
                 company_cap_source_file=company_cap['source_file'] if company_cap else '',
                 company_cap_source_sha256=company_cap['source_sha256'] if company_cap else '',
                 company_cap_observed_at=company_cap['observed_at'] if company_cap else '',
                 company_cap_fx_to_cny=rate['rate_to_cny'] if rate else '',company_cap_fx_source=rate['source'] if rate else '',
                 company_cap_fx_source_sha256=rate.get('source_sha256','') if rate else '',
                 company_cap_fx_effective_date=rate['effective_date'] if rate else '',
                 company_cap_fx_observed_at=rate['observed_at'] if rate else '',
                 company_market_cap_cny=cny if cny is not None else '',company_market_cap_status=cap_status,
                 company_market_cap_cny_lower=lower if lower is not None else '',company_market_cap_cny_upper=upper if upper is not None else '',
                 fx_bounds_basis=rate.get('bounds_basis','') if rate else '',
                 fx_break_even_to_cny=10_000_000_000/company_raw if positive(company_raw) else '',
                 fx_percent_change_to_threshold=(10_000_000_000/company_raw/rate['rate_to_cny']-1)*100 if positive(company_raw) and rate else '',
                 size_filter_status=size,southbound_filter_status=south,industry_filter_status=industry,
                 security_type_filter_status=security,strategy_snapshot_filter_status=eligible,
                 strategy_snapshot_filter_definition='current company cap strictly > CNY10bn; HK current SSE southbound; known same-source industry bridge; type review clear')
        records.append(r)
    args.output.mkdir(parents=True)
    fields=list(dict.fromkeys(k for r in records for k in r))
    for filename,subset in [('current-snapshot-selection.csv',records),('strategy-snapshot-pool.csv',[r for r in records if r['strategy_snapshot_filter_status']=='pass'])]:
        with (args.output/filename).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(subset)
    summary={'snapshot_date':args.snapshot_date,'threshold_cny':10_000_000_000,'comparison':'strictly greater than',
             'raw_master_rows':len(rows),'output_rows':len(records),'raw_pool_not_filtered':len(rows)==len(records),
             'size_filter':dict(Counter(r['size_filter_status'] for r in records)),
             'cap_status':dict(Counter(r['company_market_cap_status'] for r in records)),
             'strategy_snapshot_filter':dict(Counter(r['strategy_snapshot_filter_status'] for r in records)),
             'available_supplier_zsz':sum(positive(r['supplier_zsz_local']) for r in records),
             'current_AH_pairs':len(ah_by_h),'unmatched_native_quote_symbols':sorted(set(caps)-set(native)),
             'multiple_ZSZ_observations':{s:len(v) for s,v in caps.items() if len(v)>1},
             'inputs':input_manifest+[{'path':str(args.master.resolve()),'sha256':sha(args.master)},
                                       {'path':str(args.ah_links.resolve()),'sha256':sha(args.ah_links)}],
             'quotes_only_no_account_runs':True,'industry_history_availability_not_certified_by_this_join':True,
             'selection_status':'snapshot metadata eligibility only; requires subsequent data coverage and strategy protocol checks',
             'output_sha256':{p.name:sha(p) for p in args.output.glob('*.csv')}}
    (args.output/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('inputs','output_sha256','multiple_ZSZ_observations')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
