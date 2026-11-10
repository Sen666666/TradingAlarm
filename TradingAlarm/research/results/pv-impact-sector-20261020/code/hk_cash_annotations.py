"""Strict cash-component parsing; currency alternatives and ADS amounts are not extra cash."""
import re
from decimal import Decimal
NUMBER=r'(?:0|[1-9]\d*)(?:\.\d+)?'
LABEL=r'(?:每股)?(?:第[一二三四](?:期|次|季度))?(?:中期股息|中期息|末期股息|末期息|特别股息|特别息|股息|息)(?:每股)?'
CURRENCY={'港元':'HKD','美元':'USD','英镑':'GBP'}
def parse_cash(text):
 components=[]
 for token in text.replace('；',';').split(';'):
  if not token:continue
  m=re.fullmatch(LABEL+'('+NUMBER+r')(港元|美元)',token)
  if m:
   components.append({'amount':Decimal(m[1]),'currency':CURRENCY[m[2]],'alternatives':{},'unit_alternatives':[]});continue
  m=re.fullmatch(r'相当于('+NUMBER+r')(港元|美元|英镑)',token)
  if m and components:
   currency=CURRENCY[m[2]]
   if currency==components[-1]['currency'] or currency in components[-1]['alternatives']:raise ValueError('duplicate currency alternative')
   components[-1]['alternatives'][currency]=Decimal(m[1]);continue
  m=re.fullmatch(r'每股美国存托股('+NUMBER+r')(港元|美元)',token)
  if m and components:
   components[-1]['unit_alternatives'].append({'basis':'ADS','amount':Decimal(m[1]),'currency':CURRENCY[m[2]]});continue
  raise ValueError('unsupported cash annotation:'+token)
 if not components:raise ValueError('empty cash annotation')
 return components
