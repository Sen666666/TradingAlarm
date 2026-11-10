"""Explicit A-share action terms; signal coordinates and holder elections differ.

The no-subscription and targeted-issuance treatments are declared research
policies, not a certification of complete broker corporate-action accounting.
Original raw text/classification is retained for every record.
"""
import re
from decimal import Decimal
from datetime import date

def terms(row,source_id):
 text=row['471'];day=str(row['1'])
 match=re.fullmatch(r'(\d{4}-\d{2}-\d{2})\((.*?)\)\$',text)
 if not match or match[1].replace('-','')!=day:
  raise ValueError('unrecognized action/date: '+text)
 body=match[2].strip();effective=match[1]
 base={'effective_date':effective,'cash_per_old_share':'0','split_ratio':'1',
       'source_id':source_id,'raw_text':text,'paid_at':None,'new_shares_sellable_at':None}
 regular=re.fullmatch(r'每十股\s+(.+)',body)
 if regular:
  expression=regular[1]
  rights=re.fullmatch(r'配股(\d+(?:\.\d+)?)股\s+配股价(\d+(?:\.\d+)?)元',expression)
  if rights:
   ratio=Decimal(rights[1])/10;price=Decimal(rights[2])
   return dict(base,classification='rights_issue_no_subscription',rights_ratio=str(ratio),
      subscription_price=str(price),signal_cash_per_old_share=str(-ratio*price),
      signal_split_ratio=str(1+ratio),volume_split_ratio='1',
      holder_election='do_not_subscribe_no_cash_debit_no_extra_holder_shares',
      modeling_basis='declared_research_proxy')
  targeted=re.fullmatch(r'少数股东转增(\d+(?:\.\d+)?)股',expression)
  if targeted:
   return dict(base,classification='targeted_non_pro_rata_issuance',
      directed_shares_per_ten=str(Decimal(targeted[1])),
      holder_election='no_automatic_retail_entitlement_or_unit_adjustment',
      modeling_basis='declared_research_proxy_issuer_specific_entitlement_not_certified')
  toks=re.findall(r'(转增|送股|送|红利)(\d+(?:\.\d+)?)(股|元)',expression)
  remainder=re.sub(r'(转增|送股|送|红利)\d+(?:\.\d+)?(?:股|元)','',expression).strip()
  if not remainder and toks:
   values={}
   for kind,amount,unit in toks:
    kind='送股' if kind=='送' else kind
    if kind in values or unit!=('元' if kind=='红利' else '股'):raise ValueError('duplicate or invalid action unit')
    values[kind]=Decimal(amount)/10
   cash=values.get('红利',Decimal(0));split=1+values.get('送股',Decimal(0))+values.get('转增',Decimal(0))
   return dict(base,cash_per_old_share=str(cash),split_ratio=str(split),
      classification='ordinary_cash_and_pro_rata_bonus',modeling_basis='explicit_source_terms_pay_dates_unknown')
 consideration=re.fullmatch(r'每10股对价股票(\d+(?:\.\d+)?)股',body)
 if consideration:
  return dict(base,split_ratio=str(1+Decimal(consideration[1])/10),
     classification='public_holder_consideration_share_proxy',
     modeling_basis='declared_research_proxy_public_holder_eligibility')
 raise ValueError('unmodeled action: '+text)

def normalize(rows,source_id,first,last):
 events=[];ignored=[];unresolved=[];seen=set()
 for row in rows:
  rawday=str(row.get('1',''))
  if rawday<first.replace('-','') or rawday>last.replace('-',''):
   ignored.append({'row':row,'reason':'outside_source_origin_or_scope'});continue
  try:
   e=terms(row,source_id)
   if e['effective_date']==first:
    ignored.append({'row':row,'reason':'origin_is_post_event_coordinate_no_prior_holdings'});continue
   if e['effective_date'] in seen:
    old=next(x for x in events if x['effective_date']==e['effective_date'])
    if old['classification']!='ordinary_cash_and_pro_rata_bonus' or e['classification']!='ordinary_cash_and_pro_rata_bonus':
     raise ValueError('same-date nonordinary actions still unresolved')
    # Both statements explicitly quote per ten old shares on the same ex-date.
    # Add the cash amounts and pro-rata increments, never multiply two ratios.
    old['cash_per_old_share']=str(Decimal(old['cash_per_old_share'])+Decimal(e['cash_per_old_share']))
    old['split_ratio']=str(Decimal(old['split_ratio'])+Decimal(e['split_ratio'])-1)
    old.setdefault('raw_text_components',[old['raw_text']]).append(e['raw_text'])
    old['raw_text']=' | '.join(old['raw_text_components'])
    old['modeling_basis']='explicit_same_date_per_old_share_sum_research_mapping'
   else:
    seen.add(e['effective_date']);events.append(e)
  except ValueError as exc:unresolved.append({'row':row,'reason':str(exc)})
 return sorted(events,key=lambda x:x['effective_date']),ignored,unresolved
