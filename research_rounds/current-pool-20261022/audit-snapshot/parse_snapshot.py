"""Offline snapshot extraction. Does not modify source files or call the network."""
from pathlib import Path
import csv, json, configparser, hashlib
from collections import Counter, defaultdict
from openpyxl import load_workbook

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
RAW = OUT / 'raw'

def read_ini(path):
    c = configparser.ConfigParser(interpolation=None, strict=False)
    c.optionxform = str
    c.read_string((RAW / path).read_text(encoding='gb18030'))
    return c

def write_csv(name, rows, fields=None):
    fields = fields or list(rows[0])
    with (OUT / name).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = json.loads((OUT / 'source-manifest.initial.json').read_text())
observed = manifest['observed_at']
tree = read_ini('BlockUpdate/block_tree.ini')
industry = read_ini('BlockUpdate/block_industry.ini')
hk_industry = read_ini('BlockUpdate/block_hk_industry.ini')
hk = read_ini('BlockUpdate/block_hk.ini')
links = read_ini('StockLink/stocklink.ini')
children = {k: [a for a, flag in tree[v].items() if flag]
            for section in tree.sections() for k, v in tree[section].items()
            if v.startswith('@') and v in tree}

def descendants(k, seen=None):
    seen = set() if seen is None else seen
    if k in seen:
        return set()
    seen.add(k)
    result = {k}
    for child in children.get(k, []):
        result |= descendants(child, seen)
    return result

indices = {k: v.split(':')[-1] for k, v in links['stock_48_X_K'].items()
           if k.startswith('881')}
index_members = {idx: descendants(block) for idx, block in indices.items()}
with (OUT / 'current-stock-master.csv').open() as f:
    a_rows = list(csv.DictReader(f))
for r in a_rows:
    matches = [idx for idx, leaves in index_members.items() if r['industry_leaf_code'] in leaves]
    r['industry_match_count'] = len(matches)
    r['industry_index_symbol'] = 'URFI' + matches[0] if len(matches) == 1 else ''
    r['industry_block_code'] = indices[matches[0]] if len(matches) == 1 else ''
    r['industry_name'] = industry['BLOCK_NAME_MAP_TABLE'].get(r['industry_block_code'], '')
    r['industry_mapping_basis'] = 'StockLink index-to-block; only nonempty block_tree edges; leaf membership in block_industry'
write_csv('current-stock-master.industry-resolved.csv', a_rows)
write_csv('a-industry-index-bridge.csv', [
    {'index_symbol': 'URFI'+idx, 'block_code': block,
     'industry_name': industry['BLOCK_NAME_MAP_TABLE'].get(block,''),
     'current_member_count': sum(r['industry_index_symbol']=='URFI'+idx for r in a_rows),
     'version': industry['ConfigInfo']['ConfigVer'], 'observed_at': observed}
    for idx, block in indices.items()])

ah = []
for sec, exchange in [('stock_16_A_H','SH'), ('stock_32_A_H','SZ')]:
    for code, dest in links[sec].items():
        h_code = dest.split(':')[1]
        ah.append({'a_symbol': code+'.'+exchange, 'h_symbol': h_code[2:].zfill(5)+'.HK',
                   'a_code':code, 'h_ths_code':h_code,
                   'link_source_section':sec, 'link_raw':dest,
                   'reverse_raw':links['Stock_176_H_A'].get(h_code,''),
                   'source_version':links['ConfigInfo']['ConfigVer'], 'observed_at':observed,
                   'company_cap_rule':'Use current A listing supplier ZSZ in CNY for both listings; never add A/H ZSZ'})
write_csv('current-ah-company-links.csv', ah)

# Current southbound eligibility is the already downloaded official current table,
# not reconstructed event history. Keep the original column identifying its former use.
sb_path = ROOT.parent / 'sector-stock-20261021/coverage/sse-chain-v1/current-list.csv'
with sb_path.open() as f:
    sb_rows = list(csv.DictReader(f))
sb_stock = {r['code']: r for r in sb_rows if r['security_type_raw']=='股票'}
write_csv('current-southbound-sse-stocks.csv', list(sb_stock.values()))

native = defaultdict(set)
hk_leaf = defaultdict(list)
for source in [hk, hk_industry]:
    for block, value in source['BLOCK_STOCK_CONTEXT'].items():
        for item in value.split(','):
            if not item: continue
            market, code = item.split(':')
            unsigned = int(market) % 256
            if unsigned in (177,178): native[code].add('UHKM' if unsigned==177 else 'UHKG')
            if source is hk_industry:
                hk_leaf[code].append(block)
hk_roots = [k for k,v in tree['@1004'].items() if v]
hk_root_desc = {k:descendants(k) for k in hk_roots}
hk_index_by_block = {v.split(':')[-1]:k for k,v in links['Stock_88_X_K'].items()
                     if v.split(':')[-1] in hk_roots}
write_csv('hk-industry-index-bridge.csv',[
    {'industry_block_code':k,'industry_name':hk_industry['BLOCK_NAME_MAP_TABLE'].get(k,''),
     'index_code':hk_index_by_block.get(k,''),'stocklink_section':'Stock_88_X_K',
     'index_big_market':'88','base_market_str':'UFII','retrieval_status':'not requested; historical availability unverified',
     'source_version':links['ConfigInfo']['ConfigVer'],'observed_at':observed}
    for k in hk_roots])
hk_ind_rows = []
for code, leaves in hk_leaf.items():
    matches = [k for k, ds in hk_root_desc.items() if any(x in ds for x in leaves)]
    hk_ind_rows.append({'symbol': code[2:].zfill(5)+'.HK', 'ths_code':code,
                       'leaf_codes':';'.join(leaves),
                       'leaf_names':';'.join(hk_industry['BLOCK_NAME_MAP_TABLE'].get(x,'') for x in leaves),
                       'industry_block_codes':';'.join(matches),
                       'industry_names':';'.join(hk_industry['BLOCK_NAME_MAP_TABLE'].get(x,'') for x in matches),
                       'industry_index_code':hk_index_by_block.get(matches[0],'') if len(matches)==1 else '',
                       'industry_index_market_source':'Stock_88_X_K; BigMarket88 base UFII; data retrieval unverified',
                       'industry_index_symbol':'',
                       'industry_index_bridge_status':'Direct THS StockLink index-code-to-block exists; not the 12 Hang Seng indices; history not verified',
                       'source_version':hk_industry['ConfigInfo']['ConfigVer'],
                       'observed_at':observed,
                       'freshness':'Visible in client today; provider content version July 2026'})
write_csv('hk-current-industry-members.csv', hk_ind_rows)
hk_ind_by_symbol = {r['symbol']:r for r in hk_ind_rows}

xlsx = ROOT / 'hkex-current-list-01/ListOfSecurities.xlsx'
receipt = json.loads(xlsx.with_name('receipt.json').read_text())[1]
sheet = load_workbook(xlsx, read_only=True, data_only=True).active
declared_dimensions = [sheet.max_row, sheet.max_column]
sheet.reset_dimensions()  # Source XML dimension says A1:R8, actual rows are much longer.
matrix = list(sheet.iter_rows(values_only=True))
headers = matrix[2]
all_rows = [dict(zip(headers,row), source_sheet_row=n) for n,row in enumerate(matrix[3:],4) if row[0]]
write_csv('hkex-all-securities-extracted.csv', all_rows)
equity = [r for r in all_rows if r['Category']=='Equity']
rmb_to_primary = {r['RMB Counter']:r['Stock Code'] for r in equity if r['RMB Counter']}
equity_by_code = {r['Stock Code']:r for r in equity}
dual = []
for rmb, primary in rmb_to_primary.items():
    a,b = equity_by_code[primary],equity_by_code[rmb]
    dual.append({'primary_symbol':primary+'.HK','rmb_symbol':rmb+'.HK',
                 'primary_currency':a['Trading Currency'],'rmb_currency':b['Trading Currency'],
                 'same_isin':a['ISIN']==b['ISIN'],'isin':a['ISIN'],
                 'source_primary_row':a['source_sheet_row'],'source_rmb_row':b['source_sheet_row'],
                 'source_version':matrix[1][0],'observed_at':receipt['observed_at']})
write_csv('hk-dual-counter-links.csv',dual)
ahead_codes = {item.split(':')[1] for item in hk['BLOCK_STOCK_CONTEXT'].get('CABE','').split(',') if item}
h_rows = []
ah_h = {r['h_symbol']:r['a_symbol'] for r in ah}
for r in equity:
    code = r['Stock Code']
    if code in rmb_to_primary: continue  # Same ISIN and explicit source counter relation, preserved above.
    ths_code = 'HK'+code.lstrip('0').zfill(4)
    markets = native.get(ths_code,set())
    subtype = r['Sub-Category']
    if subtype=='Equity Securities (Main Board)':
        market, basis = 'UHKM', 'HKEX explicit Main Board; client177=UHKM'
    elif subtype=='Equity Securities (GEM)':
        market, basis = 'UHKG', 'HKEX explicit GEM; client178=UHKG'
    elif len(markets)==1:
        market, basis = next(iter(markets)), 'Explicit current client block membership native market'
    else:
        market, basis = '', 'No unambiguous native market in available client blocks'
    sym = code+'.HK'
    ind = hk_ind_by_symbol.get(sym,{})
    row = {'symbol':sym,'current_symbol':sym,'ths_symbol':market+ths_code if market else '',
           'ths_market':market,'code':code,'ths_code':ths_code,'exchange':'HK',
           'security_type':'HK_equity','security_subtype':subtype,'name':r['Name of Securities'],
           'currency':r['Trading Currency'],'board_lot':int(str(r['Board Lot']).replace(',','')),
           'isin':str(r['ISIN'] or '').strip(),'rmb_counter':r['RMB Counter'] or '',
           'native_market_basis':basis,'native_cache_markets':';'.join(sorted(markets)),
           'source_file':str(xlsx),'source_sha256':receipt['sha256'],
           'source_version':matrix[1][0],'source_sheet':'ListOfSecurities','source_sheet_row':r['source_sheet_row'],
           'observed_at':receipt['observed_at'],'snapshot_date':'2026-10-22',
           'version_caveat':'Observed Oct22 night; provider label Oct23; do not assert official effective Oct22 roster',
           'client_upcoming_flag':ths_code in ahead_codes,
           'southbound_sse_eligible':code in sb_stock,'southbound_sse_source_date':'2026-10-22',
           'industry_leaf_code':ind.get('leaf_codes',''),'industry_leaf_name':ind.get('leaf_names',''),
           'industry_block_code':ind.get('industry_block_codes',''),'industry_name':ind.get('industry_names',''),
           'industry_version':ind.get('source_version',''),'industry_index_symbol':'',
           'company_a_symbol':ah_h.get(sym,''),'company_market_cap_cny':'',
           'company_market_cap_status':'pending_current_supplier_quote_and_currency_conversion',
           'ordinary_share_review':('name_mentions_PREF_requires_type_review' if 'PREF' in r['Name of Securities']
                                    else 'special_equity_subtype_preserved' if subtype not in ('Equity Securities (Main Board)','Equity Securities (GEM)')
                                    else 'HKEX_equity_main_or_GEM')}
    h_rows.append(row)
a_symbols = {r['symbol'] for r in a_rows}
h_symbols = {r['symbol'] for r in h_rows}
for link in ah:
    link['a_in_current_master'] = link['a_symbol'] in a_symbols
    link['h_in_current_master'] = link['h_symbol'] in h_symbols
    link['current_pair_status'] = ('both_current' if link['a_in_current_master'] and link['h_in_current_master']
                                   else 'one_or_both_absent_from_current_master_do_not_apply_AH_cap_rule')
write_csv('current-ah-company-links.csv', ah)
for r in h_rows:
    r['company_a_link_candidate'] = r['company_a_symbol']
    if r['company_a_symbol'] not in a_symbols:
        r['company_a_symbol'] = ''
write_csv('current-hk-equity-master.csv', h_rows)
combined_fields = list(dict.fromkeys(k for r in a_rows+h_rows for k in r))
write_csv('current-ah-security-master.csv', a_rows+h_rows, combined_fields)
write_csv('hk-non-equity-classification.csv', [r for r in all_rows if r['Category']!='Equity'])

sb_compare = {}
for key in ['D2D9','D31D','DA04','DA12']:
    raw_codes = [x.split(':')[1] for x in hk['BLOCK_STOCK_CONTEXT'].get(key,'').split(',') if x]
    cs = {(x[2:] if x.startswith('HK') else x).zfill(5) for x in raw_codes}
    sb_compare[key] = {'name':hk['BLOCK_NAME_MAP_TABLE'].get(key,''), 'count':len(cs),
                       'only_client':sorted(cs-set(sb_stock)), 'only_sse_stock':sorted(set(sb_stock)-cs)}
verification = {
    'snapshot_date':'2026-10-22', 'network_requests_by_this_script':0,
    'a_raw_pool_unchanged':len(a_rows)==5576,
    'a_industry_unique':sum(r['industry_match_count']==1 for r in a_rows),
    'a_industry_missing':[r['symbol'] for r in a_rows if r['industry_match_count']==0],
    'a_industry_ambiguous':[r['symbol'] for r in a_rows if r['industry_match_count']>1],
    'a_industry_rule':'Ignore empty tree values; retain nonempty explicit child links',
    'ah_pairs':len(ah),'ah_both_current_pairs':sum(r['current_pair_status']=='both_current' for r in ah),
    'ah_incomplete_current_pairs':[r for r in ah if r['current_pair_status']!='both_current'],
    'hkex_declared_dimensions':declared_dimensions,'hkex_actual_rows':len(matrix),
    'hkex_rows':len(all_rows),'hkex_version':matrix[1][0],'hkex_observed_at':receipt['observed_at'],
    'hkex_equity_rows':len(equity),'hkex_primary_equity_rows':len(h_rows),
    'hkex_dual_counters':len(dual),'hkex_dual_same_isin_all':all(r['same_isin'] for r in dual),
    'hk_primary_native_market':dict(Counter(r['ths_market'] for r in h_rows)),
    'hk_native_unknown':[r['symbol'] for r in h_rows if not r['ths_market']],
    'hk_primary_currency':dict(Counter(r['currency'] for r in h_rows)),
    'hk_primary_subtype':dict(Counter(r['security_subtype'] for r in h_rows)),
    'hk_client_upcoming_in_official':[r['symbol'] for r in h_rows if r['client_upcoming_flag']],
    'hk_primary_missing_industry':sum(not r['industry_leaf_code'] for r in h_rows),
    'southbound_sse_stocks':len(sb_stock),'southbound_client_comparison':sb_compare,
    'artifacts':{p.name:sha(p) for p in OUT.glob('*.csv')}
}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in verification.items() if k not in ('artifacts','southbound_client_comparison')},ensure_ascii=False,indent=2))
