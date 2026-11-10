"""Offline source-grounded review of the 22 fixed Shenzhen notices; no strategy."""
from pathlib import Path
from decimal import Decimal as D
import json,re,hashlib,datetime
import pandas as pd
O=Path(__file__).resolve().parent;B=O.parent
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def date(s):
 a=re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日',s);return datetime.date(*map(int,a.groups())).isoformat()
records=[]
targets=json.loads((O/'PRE_RUN_SEAL.json').read_text())['targets']
for t in targets:
 sid=t['sid']
 if not sid.endswith('.SZ'):continue
 pages=json.loads((O/'notice_pdf'/(sid+'.text.json')).read_text())['pages']
 pages=[{'page':x['page'],'text':re.sub(r'\s+','',x['text'])} for x in pages]
 full=''.join(p['text'] for p in pages)
 meta=json.loads((O/'notice_pdf'/(sid+'.json')).read_text())
 raw=json.loads((O/'raw'/(sid+'.json')).read_text())['raw']['records']
 hit=[r for r in raw if r.get('F020D')==t['status_day']];assert len(hit)==1;r=hit[0]
 assert sid[:6] in full
 def find(pattern,match_number=0):
  out=[]
  for pg in pages:
   for m in re.finditer(pattern,pg['text']):
    out.append({'page':pg['page'],'match':m.group(),'groups':m.groups(),'text':pg['text'][max(0,m.start()-65):min(len(pg['text']),m.end()+100)]})
  return out[match_number] if len(out)>match_number else None
 def find_across(pattern):
  m=re.search(pattern,full)
  if not m:return None
  offset=0;begin=None;end=None
  for pg in pages:
   last=offset+len(pg['text'])
   if begin is None and m.start()<last:begin=pg['page']
   if m.end()<=last:end=pg['page'];break
   offset=last
  return {'page':begin,'page_end':end,'match':m.group(),'groups':m.groups(),'text':full[max(0,m.start()-45):m.end()+30],'method':'Concatenated adjacent page text; original page boundaries retained'}
 def datefield(pattern):
  e=find(pattern+r'(2022年\d{1,2}月\d{1,2}日)')
  return (date(e['groups'][-1]),e) if e else (None,None)
 rec,er=datefield(r'股权登记日(?:为)?[：:]?')
 ex,ee=datefield(r'除权除息日(?:为)?[：:]?')
 listing,el=datefield(r'(?:起始交易日为|新增可流通股份上市日（红利发放日）：)')
 pay,ep=datefield(r'现金红利将于')
 assert rec==r['F018D'] and ex==r['F020D'] and pay==r['F023D'],(sid,rec,ex,pay)
 assert listing is None or listing==ex
 bonus=D(str(r.get('F010N') or 0))/10;transfer=D(str(r.get('F011N') or 0))/10;cash=D(str(r['F012N']))/10
 # Record exact per10 amounts only when their distribution language is in the notice.
 cash10=cash*10;transfer10=transfer*10;bonus10=bonus*10
 ec=None
 for pg in pages:
  for m in re.finditer(r'每10股(?:派发现金红利人民币|派发现金股利人民币|派发现金红利|派发现金股利|派送现金人民币|派现金红利|派现金|派)([0-9.]+)元',pg['text']):
   if D(m.group(1))==cash10:
    ec={'page':pg['page'],'text':pg['text'][max(0,m.start()-45):m.end()+70]};break
  if ec:break
 assert ec,(sid,'cash explicit match absent')
 et=None;eb=None
 if transfer:
  for pg in pages:
   for m in re.finditer(r'每10股转增([0-9.]+)股',pg['text']):
    if D(m.group(1))==transfer10:et={'page':pg['page'],'text':pg['text'][max(0,m.start()-50):m.end()+100]};break
   if et:break
  assert et,(sid,'transfer explicit match absent')
 if bonus:
  for pg in pages:
   for m in re.finditer(r'每10股送红股([0-9.]+)股',pg['text']):
    if D(m.group(1))==bonus10:eb={'page':pg['page'],'text':pg['text'][max(0,m.start()-50):m.end()+100]};break
   if eb:break
  assert eb
 else:eb=find(r'不送红股|送红股0股')
 capital=find(r'本次转增股本的资本公积金全部为股票发行所形成的股本溢价，无需缴纳个人所得税')
 capital_mention=find(r'溢价')
 fractional=find(r'不足1股的部分.{0,180}?(?:一致|现金方案)。')
 if fractional is None:fractional=find_across(r'不足1股的部分.{0,180}?(?:一致|现金方案)。')
 schedule=find(r'持股1个月（含1个月）以内，每10股补缴税款(?:人民币)?([0-9.]+)元.{0,180}?(?:不需补缴税款|不需要补缴税款)。')
 if schedule is None:schedule=find_across(r'持股1个月（含1个月）以内，每10股补缴税款(?:人民币)?([0-9.]+)元.{0,180}?(?:不需补缴税款|不需要补缴税款)。')
 # These three exact parameter pairs are explicitly stated in the implementation notices.
 refs={'000672.SZ':('0.7943066','0.1985766',5),'002568.SZ':('0.49791413','0.39833131',4),'002881.SZ':('0.134333','0.296323',4)}
 ref=None
 if sid in refs:
  dr,rr,pg=refs[sid];text=pages[pg-1]['text'];assert dr in text and rr in text
  ref={'cash':dr,'share_change':rr,'split':str(1+D(rr)),'page':pg,'text':text,'formula_operator_status':'Missing operator in printed final equation; parameters stated separately, no repaired formula inferred' if sid=='002881.SZ' else 'Explicit formula'}
 reasons=[]
 if listing is None:reasons.append('NEW_UNRESTRICTED_LISTING_DATE_NOT_STATED_IN_THIS_NOTICE')
 if transfer and capital is None:reasons.append('CAPITAL_PREMIUM_AND_EXEMPTION_NOT_BOTH_EXPLICIT')
 if bonus:reasons.append('BONUS_TAX_REQUIRES_SEPARATE_CONTRACT')
 if sid=='300655.SZ':reasons.append('FRACTIONAL_SHARE_ALLOCATION_UNDETERMINED')
 records.append({'sid':sid,'security_class':'A shares; B/H schedules excluded','announcement_date':r['F006D'],'notice_index_datetime':str(pd.Timestamp(meta['metadata']['announcementTime'],unit='ms',tz='UTC').tz_convert('Asia/Shanghai')),'record_date':rec,'ex_date':ex,'pay_date':pay,'listing_date':listing,'cash_per_old_share':str(cash),'bonus_per_old_share':str(bonus),'transfer_per_old_share':str(transfer),'capital_premium_explicit':capital is not None,'transfer_tax_exempt_explicit':capital is not None,'capital_source_text':capital['text'] if capital else None,'capital_source_related_mention':capital_mention['text'] if capital_mention else None,'bonus_tax_base_per_bonus_share':None,'tax_basis_text':schedule['text'] if schedule else None,'supplemental_short_hold_tax_per10':schedule['groups'][0] if schedule else None,'fractional_rule_text':fractional['text'] if fractional else None,'fractional_rule_status':'DESCENDING_REMAINDER_EQUAL_REMAINDERS_RANDOM' if fractional else 'NOT_STATED_IN_NOTICE','actual_fractional_allocation':None,'official_reference_cash':ref['cash'] if ref else None,'official_reference_share_change':ref['share_change'] if ref else None,'official_reference_split':ref['split'] if ref else None,'notice_url':meta['url'],'source_pdf_sha256':meta['sha256'],'evidence':{'record_date':er,'ex_date':ee,'pay_date':ep,'listing_date':el,'cash':ec,'bonus':eb,'transfer':et,'capital_source_and_tax':capital,'tax_schedule':schedule,'fractional':fractional,'official_reference':ref},'block_reasons':reasons,'review_scope':'Full relevant text reviewed; strict first-pilot eligibility uses explicit premium+exemption only, not temporary cash non-withholding language'})
assert len(records)==22
save(O/'REVIEW_SZ_22.json',{'records':records,'scope':'22 fixed Shenzhen A-share implementation notices; not a strategy result'})
print(json.dumps({'rows':len(records),'listing_documented':sum(x['listing_date'] is not None for x in records),'premium_and_tax_explicit':[x['sid'] for x in records if x['capital_premium_explicit']],'missing_listing':[x['sid'] for x in records if x['listing_date'] is None]},ensure_ascii=False))
