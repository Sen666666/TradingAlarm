from pathlib import Path
from decimal import Decimal as D
import json,csv,re,hashlib,datetime,pandas as pd
O=Path(__file__).resolve().parent;B=O.parent
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
MP=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=json.loads((O/'SOURCE_SEAL.json').read_text());assert all(sha(Path(p))==h for p,h in seal['sources'].items())
manifest={m['symbol']:m for m in json.loads(MP.read_text())};sources={**seal['sources'],str(MP):sha(MP)}
config={'300456.SZ':('1225131539','0.37',None,'2026-04-20'),'300661.SZ':('1225188355','0.2',None,'2026-04-24'),'300373.SZ':('1225257415','0.5',None,'2026-04-29'),'688403.SH':('1225304657','0.05',None,'2026-05-14'),'600206.SH':('1225346618','0.096',None,'2026-06-03'),'300613.SZ':('1225330669','0.08','0.0792388','2026-05-26'),'688798.SH':('1225307803','0.43',None,'2026-05-15'),'603290.SH':('1225357870','0.508',None,'2026-06-09'),'301611.SZ':('1225332905','0.1',None,'2026-05-27'),'688432.SH':('1225373237','0.055','0.0548','2026-06-17')}
rows=[];adapters=[];notices=[]
for t in seal['targets']:
 sid=t['sid'];rawp=O/'raw'/(sid+'.json');rawb=rawp.with_suffix('.response');blob=json.loads(rawp.read_text());assert sha(rawb)==blob['raw_response_sha256'];api=json.loads(rawb.read_text(),parse_float=D)
 hits=[r for r in api['records'] if r['F020D']==t['day']];assert len(hits)==1;r=hits[0]
 dc=D(str(r['F012N']))/10;aid,dcnotice,dr,sig=config[sid];assert dc==D(dcnotice)
 assert re.fullmatch(r'10派([0-9.]+)元\(含税\)',r['F007V']) and r['F010N'] in (None,0) and r['F011N'] in (None,0)
 ann,rec,ex,pay=[r[k] for k in ['F006D','F018D','F020D','F023D']];assert ann<=rec<ex<=pay
 pdf=O/'notice_pdf'/(sid+'_'+aid+'.pdf');txt=pdf.with_suffix('.txt');meta=json.loads(pdf.with_suffix('.json').read_text());compact=re.sub(r'\s+','',txt.read_text())
 assert '证券代码：'+sid[:6] in compact and sha(pdf)==meta['sha256'] and '年度权益分派实施公告' in compact
 for dt in [rec,ex,pay,sig]:
  y,m,d=map(int,dt.split('-'));assert any(z in compact for z in [dt,f'{y}/{m}/{d}',f'{y}年{m}月{d}日',f'{y}年{m:02}月{d:02}日']), (sid,dt)
 assert dcnotice in compact or str(dc*10) in compact
 if dr:assert dr in compact
 ap=AS/'inputs-v1/actions'/(sid+'.json');a=json.loads(ap.read_text());assert a['series_id']==sid
 matches=[(i,e) for i,e in enumerate(a['events']) if e['effective_date']==ex];assert len(matches)==1;i,e=matches[0];ds=D(e['cash_per_old_share']);assert D(e['split_ratio'])==1 and ds==dc and abs(ds-D(t['d_source']))<=D('1e-16')
 sp=Path(next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet')));assert sha(sp)==manifest[sid]['source_sha256'][str(sp)]
 f=pd.read_parquet(sp).sort_index();pday=f.index[f.index<pd.Timestamp(ex)][-1];prev=f.loc[pday];assert abs(D(str(prev.raw_close))-D(t['previous_close']))<=D('1e-12');assert str(pday.date())==rec
 residual=abs(D(t['factor_old'])*D(t['previous_close'])/(D(t['previous_close'])-ds)/D(t['factor_new'])-1);assert residual<=D('1e-11')
 n={'sid':sid,'announcement_id':aid,'notice_url':meta['url'],'pdf_path':str(pdf),'pdf_sha256':sha(pdf),'text_path':str(txt),'text_sha256':sha(txt),'signature_date':sig,'publication_path_date':meta['metadata']['adjunctUrl'].split('/')[1],'record_date':rec,'ex_date':ex,'pay_date':pay,'d_cash':str(dc),'d_ref':dr,'code_gross_A_share_RMB_dates_context_verified':True,'d_ref_scope':'Explicit stock ex-reference deduction only; bond adjustment auxiliary notices excluded','archived_PIT':False}
 notices.append(n)
 if sid=='300373.SZ':n['market_note']='A-share pay date May 8; GDR onward payout May 15 excluded.'
 if sid in ['300661.SZ','300613.SZ']:n['notice_caveat']='Application-period start year contains apparent issuer typo; not used as record/ex/pay date.'
 fact={**t,'source_csv_d_source':t['d_source'],'d_source':str(ds),'d_cash':str(dc),'d_ref':dr,'api_F012N_per10_exact':str(r['F012N']),'api_terms':r['F007V'],'announcement_date':ann,'record_date':rec,'ex_date':ex,'pay_date':pay,'previous_day':str(pday.date()),'company_fact_resolution':'API_AND_MAIN_IMPLEMENTATION_NOTICE_MATCH','fact_path':str(rawp),'fact_sha256':sha(rawp),'response_path':str(rawb),'response_sha256':sha(rawb),'notice_url':meta['url'],'production_admitted':False,'source_coordinate_residual':str(residual)}
 rows.append(fact)
 evidence={str(p):sha(p) for p in [rawp,rawb,pdf,txt,pdf.with_suffix('.json'),pdf.with_suffix('.pdf.meta.json'),ap,sp]};sources.update(evidence)
 eid=sid+'|LOCAL_DISTRIBUTION_'+str(i+1).zfill(3)
 adapters.append({'sid':sid,'economic_event_id':eid,'economic_event_id_candidate':eid,'event_type':'PURE_CASH','record_date':rec,'ex_date':ex,'pay_date':pay,'d_source':str(ds),'source_csv_d_source':t['d_source'],'d_cash':str(dc),'d_ref':dr,'factor_old':t['factor_old'],'factor_new':t['factor_new'],'previous_close':t['previous_close'],'previous_day':str(pday.date()),'source_coordinate_residual':str(residual),'local_action_ordinal':i+1,'local_action_path':str(ap),'local_action_sha256':sha(ap),'source_fact_path':str(rawp),'source_fact_sha256':sha(rawp),'notice':n,'evidence_sources':evidence,'evidence_version':hashlib.sha256(json.dumps({'fact':fact,'sources':evidence},sort_keys=True).encode()).hexdigest(),'coordinate_scope_candidate':'FROZEN_SOURCE_TRANSLATION_ONLY','entitlement_scope_candidate':'OWN_REGISTER_Q_NET80_NOT_ACTUAL_TAX','coordinate_verified_for_production':False,'entitlement_verified_for_production':False,'production_admitted':False,'runtime_gate':'BLOCKED_PENDING_INDEPENDENT_FACT_REVIEW_AND_TECHNICAL_TESTS'})
assert len(adapters)==10 and len({r['economic_event_id'] for r in adapters})==10
save(O/'EVENT_ADAPTER_CANDIDATES.json',adapters);save(O/'NOTICE_ADJUDICATIONS.json',notices);save(O/'ADJUDICATED_EVENT_FACTS.json',rows)
with (O/'ADJUDICATED_EVENT_FACTS.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for p in O.rglob('*'):
 if p.is_file() and p.suffix in ('.response','.pdf','.txt'):sources[str(p)]=sha(p)
assert all(sha(Path(p))==h for p,h in seal['sources'].items())
save(O/'SOURCE_HASHES.json',sources)
save(O/'SUMMARY.json',{'events':10,'main_notices_verified':10,'downloaded_notices':12,'auxiliary_bond_notices_excluded':2,'d_cash_equals_exact_local_action':10,'d_ref_differs_from_cash':2,'all_record_previous_observation':True,'all_pay_ex':True,'production_admitted':0,'backtest_runs':0,'source_hashes_unchanged':True,'current_historical_not_PIT':True,'actual_tax_verified':False})
save(O/'LOCAL_PARSER_RECOVERY.json',{'original_stop_retained':'STOP_NOTICES.json','cause':'pymupdf not installed; not access denial','resolution':'Existing project Swift PDFKit extractor, no installation','successful_first_query_and_pdf_reused':True,'network_retries':0})
(O/'READOUT.md').write_text('''# 2026H1 十项纯现金事实候选\n\n10项均由巨潮原始JSON按代码请求及准确除息日唯一匹配，并逐项对照公司主实施公告；登记/除息/派息完整，登记日均为原signal前一观察日，派息均等于除息。10项公司A股人民币毛现金均与原inputs-v1/actions精确现金相同。\n\n- 富瀚微300613：d_cash=0.08，公告d_ref=0.0792388。\n- 有研硅688432：d_cash=0.055，公告d_ref=0.0548；CSV的0.05500000000000001仅浮点序列化痕迹，原JSON每10股0.55与原action精确0.055一致。\n- 其余d_ref保留null，未从d_cash或可转债调价推填。两个转债辅助公告不作为主实施公告。扬杰科技采用A股5月8日派息，不采用GDR5月15日转付日。\n\n保留原响应bytes、URL、实际获取时间、PDF、PDFKit文本及sha256。初次本地解析缺pymupdf错误保留，改用已有Swift脚本，已成功请求未重取，无网络重试/denial。API未回显证券身份，身份链为请求scode+冻结sid+公告证券代码。当前获取的历史材料不是PIT存档。\n\n只生成事实/适配候选，生产准入仍false；未运行经济/账户，未修改行情或旧报告。d_source仅用于冻结因子坐标，d_cash用于公司毛现金，d_ref仅公告参考扣减，三者不混用。统一80%仅研究情景，不代表真实税率或实际到账。独审后另行有限准入。\n''')
save(O/'OUTPUT_HASHES.json',{str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(json.loads((O/'SUMMARY.json').read_text()),indent=2))
