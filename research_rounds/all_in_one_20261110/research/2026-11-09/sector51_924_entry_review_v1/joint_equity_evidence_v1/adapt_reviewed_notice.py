"""Manually reviewed notice facts, verified against local actions and source factor bridge only."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,sys,requests
import pandas as pd
O=Path(__file__).resolve().parent
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
B=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
cfg=read(sys.argv[1]);sid=cfg['sid'];ex=cfg['ex_date'];rec=cfg['record_date'];pay=cfg['pay_date'];dc=D(cfg['d_cash']);dr=D(cfg['d_ref']) if cfg.get('d_ref') else None
evidence={}
for key in ['html','pdf']:
 u=cfg[key+'_url'];p=O/(sid+'_'+cfg['notice_number']+'.'+key)
 if not p.exists():
  r=requests.get(u,timeout=30);r.raise_for_status()
  if key=='pdf':assert r.content.startswith(b'%PDF');p.write_bytes(r.content)
  else:r.encoding=cfg.get('html_encoding','utf-8');p.write_text(r.text)
 evidence[str(p)]=sha(p)
hp=O/(sid+'_'+cfg['notice_number']+'.html');html=hp.read_text()
for s in cfg['assert_html_fragments']:assert s in html,s
ap=AS/'inputs-v1/actions'/f'{sid}.json';a=read(ap);assert a['series_id']==sid
terms=[(i+1,x) for i,x in enumerate(a['events']) if x['effective_date']==ex];assert len(terms)==1
ordinal,term=terms[0];ds=D(term['cash_per_old_share']);assert D(term['split_ratio'])==1
m=next(x for x in read(U/'STOCK_MANIFEST.json') if x['symbol']==sid)
sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(sp)==m['source_sha256'][str(sp)]
z=pd.read_parquet(sp);dt=pd.Timestamp(ex);old=z[z.index<dt].iloc[-1];new=z.loc[dt]
fo,fn,pc=map(lambda x:D(str(x)),[old.adjustment_factor,new.adjustment_factor,old.raw_close]);res=fo*pc/(pc-ds)/fn-1
lineage=lambda x:tuple(str(x.get(k)) for k in ('source_kind','source_path','segment_id'))
assert lineage(old)==lineage(new) and abs(res)<D('1e-11') and str(old.name.date())==rec
pdf=O/(sid+'_'+cfg['notice_number']+'.pdf')
evidence.update({str(p):sha(p) for p in [ap,sp,Path(sys.argv[1])]})
ev={'sid':sid,'economic_event_id_candidate':f'{sid}|LOCAL_DISTRIBUTION_{ordinal:03}','event_type':'PURE_CASH','record_date':rec,'ex_date':ex,'pay_date':pay,'d_source':str(ds),'d_cash':str(dc),'d_ref':str(dr) if dr is not None else None,'local_action_ordinal':ordinal,'local_action_path':str(ap),'local_action_sha256':sha(ap),'signal_path':str(sp),'signal_sha256':sha(sp),'factor_old':str(fo),'factor_new':str(fn),'previous_close':str(pc),'previous_day':rec,'source_coordinate_residual':str(res),'official_reference_coordinate_residual':str(fo*pc/(pc-dr)/fn-1) if dr is not None else None,'same_lineage':True,'record_is_previous_observation':True,'scenario_not_PIT':True,'net80_per_registered_share':str(dc*D('.8')),'notice_date':cfg['notice_date'],'notice_signature_date':cfg.get('notice_signature_date'),'notice_number':cfg['notice_number'],'notice_url':cfg['pdf_url'],'notice':{'pdf_path':str(pdf),'pdf_sha256':sha(pdf),'url':cfg['pdf_url']},'source_type':'COMPANY_IMPLEMENTATION_NOTICE_MANUAL_CONTEXT_REVIEW','admission_scope':'BOUNDED_2024_09_02_TO_10_31_RESEARCH_FACTS_AND_COORDINATE_ONLY_NOT_PRODUCTION','evidence_hashes':evidence,'fact_notes':cfg['fact_notes'],'notice_date_scope':'document_or_publication_date_only_not_intraday_known_at'}
out=O/f'EXTRA_REVIEWED_EQUITY_EVENTS_{sid[:6]}_V1.json';save(out,[ev]);save(O/f'{sid[:6]}_FACT_REVIEW.json',{'status':'PASS_NOTICE_FACT_AND_SOURCE_COORDINATE_ONLY','event':ev,'adapter_path':str(out),'adapter_sha256':sha(out),'independent_review_required':True,'no_account_run':True})
print(json.dumps({'adapter':str(out),'sha256':sha(out),'record_date':rec,'ex_date':ex,'pay_date':pay,'d_cash':str(dc),'d_ref':str(dr) if dr is not None else None,'factor_old':str(fo),'factor_new':str(fn),'residual':str(res)},ensure_ascii=False,indent=2))
