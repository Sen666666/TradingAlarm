"""Limited source/calendar audit of already written ratios; no signal/account code."""
from pathlib import Path
import json,hashlib,pandas as pd
OUT=Path(__file__).resolve().parent
DETAIL=json.loads((OUT/'SOURCE_AND_CASE_DETAILS.json').read_text())
ROWS=json.loads((OUT/'ALL_ORIGINAL_CP_RS.json').read_text())
ROOT=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data')
MP=ROOT/'ths-index-history-20261018'
IP=ROOT/'ths-index-history-9603-20261018'
BRIDGE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/a-industry-index-bridge.csv')
META=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
MEM=Path('/Users/bytedance/repos/my-quant/data/processed/security_memberships/security_memberships.parquet')
sha=json.loads((OUT/'SOURCE_SHA256.json').read_text())
def readjson(p):
 sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
m=pd.read_csv(MP/'canonical/USHI1B0300.csv',parse_dates=['date']).set_index('date');mi=m.index
mp=readjson(MP/'protocol.json');mn=readjson(MP/'server-names.json');mc=readjson(MP/'checkpoints/USHI1B0300.json')
ip=readjson(IP/'protocol.json');inn=readjson(IP/'server-names.json')
a=[]
for sid,d in DETAIL.items():
 gid=d['case']['industry'];p=Path(d['industry_manifest_entry']['refs']['CP1_input']);ind=pd.read_parquet(p)
 rawp=Path(d['original_bundle_industry_series']['raw']['path']);raw=pd.read_parquet(rawp)
 for r in [x for x in ROWS if x['sid']==sid]:
  t=pd.Timestamp(r['date']);h=r['horizon_industry_observations'];t0=pd.Timestamp(r['start_date']);mt0=mi[mi.get_loc(t)-h] if t in mi and mi.get_loc(t)>=h else None
  ii=ind.index[(ind.index>=t0)&(ind.index<=t)];mm=mi[(mi>=t0)&(mi<=t)]
  a.append({'sid':sid,'date':r['date'],'horizon':h,'industry_t_minus_h':r['start_date'],'HS300_t_minus_h':None if mt0 is None else mt0.strftime('%Y-%m-%d'),'endpoints_equal_HS300_calendar':bool(mt0==t0),'entire_interval_calendar_equal':ii.equals(mm),'industry_only_dates':[x.strftime('%Y-%m-%d') for x in ii.difference(mm)],'HS300_only_dates':[x.strftime('%Y-%m-%d') for x in mm.difference(ii)],'industry_endpoints_original_observed_price_eligible':all(bool(raw.at[x,'observed_bar']) and bool(raw.at[x,'price_eligible']) and not bool(raw.at[x,'source_invalid']) and not bool(raw.at[x,'synthetic_event_bar']) for x in [t0,t])})
 inv={'original_stock_mapping_metadata':readjson(META)[sid],'industry_server_identity':[{'received_at':q['received_at'],'name':q['names'][gid],'query_id':q['query']['id'],'market':q['query']['market']} for q in inn['URFI'] if gid in q['names']],'industry_original_raw_source_paths':list(map(str,raw.source_path.unique())),'industry_original_CP_input_equals_saved_raw_all_history_max_abs_diff':float((ind['close']-raw['close'].reindex(ind.index)).abs().max()),'industry_protocol_symbol_record':[x for x in ip['symbols'] if x['symbol']==gid],'industry_request':ip['request'],'industry_price_basis':'saved original raw unadjusted index points; not total return; index methodology/launch/PIT compositions not certified in project metadata','stock_price_basis':'original CP continuous theoretical-ex-price coordinate; not labeled total return. All requested windows have constant original factor, so endpoint CP log returns exactly equal original raw-price log returns up to floating roundoff.'}
 (OUT/(sid+'_SOURCE_IDENTITY.json')).write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n')
b=pd.read_csv(BRIDGE);b=b[b.index_symbol.isin(['URFI881153','URFI881129'])];sha[str(BRIDGE)]=hashlib.sha256(BRIDGE.read_bytes()).hexdigest();b.to_json(OUT/'CURRENT_ONLY_INDUSTRY_BRIDGE_ROWS.json',orient='records',force_ascii=False,indent=2)
d=pd.read_parquet(MEM);d=d[d.symbol.isin(DETAIL)];sha[str(MEM)]=hashlib.sha256(MEM.read_bytes()).hexdigest();d.to_json(OUT/'EXISTING_SW_MEMBERSHIP_TARGET_ROWS_NOT_USED.json',orient='records',force_ascii=False,date_format='iso',indent=2)
(OUT/'CALENDAR_ALIGNMENT_AUDIT.json').write_text(json.dumps({'rows':len(a),'all_t_minus_h_endpoints_equal_HS300':all(x['endpoints_equal_HS300_calendar'] for x in a),'all_interval_calendars_equal_HS300':all(x['entire_interval_calendar_equal'] for x in a),'all_industry_endpoints_original_eligible':all(x['industry_endpoints_original_observed_price_eligible'] for x in a),'rows_detail':a},ensure_ascii=False,indent=2)+'\n')
market={'fixed_benchmark_not_selected_by_result':'USHI1B0300','server_name':mn['USHI']['names']['USHI1B0300'],'server_name_received_at':mn['USHI']['received_at'],'protocol_symbol_record':[x for x in mp['symbols'] if x['symbol']=='USHI1B0300'],'request':mp['request'],'checkpoint':{k:mc[k] for k in ['symbol','status','rows','first','last','canonical','canonical_sha256','completed_at']},'canonical_current_hash_matches_checkpoint':sha[str(MP/'canonical/USHI1B0300.csv')]==mc['canonical_sha256'],'PIT_caveat':'2026 download of historical price index; source is not a 2022/2024 archived contemporaneous feed. Protocol publication metadata explicitly unverified. No constituent history reconstruction used.'}
(OUT/'FIXED_HS300_SOURCE_IDENTITY.json').write_text(json.dumps(market,ensure_ascii=False,indent=2)+'\n')
sha[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(OUT/'SOURCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
print('calendar rows',len(a),'all end dates',all(x['endpoints_equal_HS300_calendar'] for x in a),'all intervals',all(x['entire_interval_calendar_equal'] for x in a),'market sha matches',market['canonical_current_hash_matches_checkpoint'])
print('max CPraw RS delta',max(abs(x['RS_stock_cp_minus_industry']-x['RS_stock_raw_minus_industry']) for x in ROWS))
print('missing',sum(bool(x['missing_reasons']) for x in ROWS),'constantfactor',all(x['stock_factor_constant_all_observed_interval'] for x in ROWS))
