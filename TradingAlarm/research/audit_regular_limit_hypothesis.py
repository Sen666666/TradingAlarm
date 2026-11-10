"""Consistency audit only: non-ST main-board ordinary-session 10% hypothesis.
An in-band bar DOES NOT prove that day's official restriction or absence of exceptions.
"""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def rounded_limits(reference,rate,tick='.01'):
    ref=Decimal(str(reference));r=Decimal(str(rate));t=Decimal(str(tick))
    if not all(x.is_finite() for x in (ref,r,t)) or ref<=0 or not 0<r<1 or t<=0:raise ValueError('invalid inputs')
    lower=((ref*(1-r)/t).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*t
    upper=((ref*(1+r)/t).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*t
    return float(lower),float(upper)

def main():
    counts=dict(checked=0,outside=0,excluded_board=0,excluded_st=0,excluded_suspended=0,invalid=0);exceptions=[]
    for p in sorted((ROOT/'data/stock-state-windows').glob('*.json')):
        d=json.loads(p.read_text());symbol=d['symbol']
        if not (symbol.startswith(('000','001','002','003')) and symbol.endswith('.SZ')):counts['excluded_board']+=len(d['rows']);continue
        for row in d['rows']:
            if row['tradestatus']!='1':counts['excluded_suspended']+=1;continue
            if row['isST']!='0':counts['excluded_st']+=1;continue
            try:
                reference=float(row['preclose'])
                # Tiny-price boundary conventions are explicitly outside this audit.
                if reference<1:counts['invalid']+=1;continue
                lo,hi=rounded_limits(reference,.1)
                prices={k:float(row[k]) for k in ['open','high','low','close']}
                counts['checked']+=1
                outside=min(prices.values())<lo-.005 or max(prices.values())>hi+.005
                if outside:counts['outside']+=1;exceptions.append(dict(symbol=symbol,date=row['date'],preclose=reference,hypothetical_lower=lo,hypothetical_upper=hi,prices=prices))
            except (ValueError,KeyError):counts['invalid']+=1
    report=dict(counts=counts,exceptions=exceptions,execution_certified=False,scope='SZ non-ST mainboard,reference>=1,ordinary-session10% hypothesis only; no claim exceptions excluded',sources=['https://www.szse.cn/www/investor/knowledge/t20230308_599141.html','https://www.szse.cn/lawrules/rule/repeal/rules/P020231230545143336292.pdf'],limitation='Out-of-band records identify exceptions or data errors requiring investigation. In-band records cannot certify exact daily limits. No rules added to execution guard.')
    (ROOT/'results/stock-data-audit/regular-limit-hypothesis.json').write_text(json.dumps(report,indent=2));print(counts);print(exceptions[:6])
if __name__=='__main__':main()
