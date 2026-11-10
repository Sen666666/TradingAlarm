"""Two additional HK ETFs, explicit event override and conservative order unit."""
import json,re,hashlib
from portfolio_data import ROOT,total_return_frame
from trend_engine import frame
from sector_factors import expanded_assets

def load_extended():
 assets=expanded_assets();audit=[]
 for code,sector,lot in [('02845','new_energy',50),('03110','broad_hk',100)]:
  source=ROOT/f'data/tencent-hk{code}.json';rows=json.loads(source.read_text())['data']['hk'+code]['day']
  raw=frame([dict(date=r[0],open=float(r[1]),close=float(r[2]),high=float(r[3]),low=float(r[4]),volume=float(r[5])) for r in rows]);div=[]
  for r in rows:
   for e in r[6:]:
    if not isinstance(e,dict) or any(e.get(k) for k in ['HGcontent','hgcgContent','ggContent']):raise ValueError('Unreviewed corporate action')
    match=re.fullmatch(r'(?:中期息|末期息)([0-9.]+)港元',e['FHcontent'])
    if not match:raise ValueError('Unreviewed dividend units')
    amount=float(match[1])
    if code=='03110' and e['cqr']=='2018-09-20':amount=1.51
    div.append(dict(ex_date=e['cqr'],pay_date=e['paixiri'],amount=amount))
  signal=total_return_frame(raw,div,[])
  if signal.close.pct_change().abs().max()>.4:raise ValueError('Large unexplained price jump')
  assets['HK'+code]=dict(raw=raw,signal=signal,dividends=div,splits=[],lot=lot,currency='HKD',kind='equity',sector=sector,volume_multiplier=1)
  audit.append(dict(symbol='HK'+code,rows=len(rows),first=str(raw.index[0].date()),last=str(raw.index[-1].date()),dividends=div,
    chosen_order_unit=lot,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    limitation='03110 uses conservative100-unit orders compatible with verified prior100/current50 board lots,not exact dated lot history;EV no vendor distributions and none found in issuer archive,not exhaustive audit.'))
 return assets,audit
if __name__=='__main__':
 _,a=load_extended();(ROOT/'results/hk-extension-loaded-audit.json').write_text(json.dumps(a,indent=2));print([(x['symbol'],x['rows']) for x in a])
