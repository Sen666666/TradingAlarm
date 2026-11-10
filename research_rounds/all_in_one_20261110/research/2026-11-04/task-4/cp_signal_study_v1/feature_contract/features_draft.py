"""Draft only: pure trailing features, no file IO, labels, gates or accounts.

Parent must freeze FEATURE_CONTRACT.txt before producing study features.
All input rows are the same real CSI300 trading-calendar dates. No fill/dropna.
"""
import numpy as np
import pandas as pd

GROUPS={
 'relative_strength':tuple(f'{p}{h}{s}'for p in('RS_SM','RS_IM')for h in(5,20)for s in('','_delta5')),
 'price_structure':('channel20_position','EMA20_slope5','EMA60_slope5','drawdown20'),
 'amount_distribution':('amount_prior21median_ratio','up_day_fraction5','down_day_fraction5',
                        'up_amount_fraction5','down_amount_fraction5')}
FEATURES=sum(GROUPS.values(),())

def _finite_positive(s):
 s=pd.to_numeric(s,errors='coerce')
 return s.gt(0)&np.isfinite(s)

def _known_true(s):
 # Unknown is not silently promoted into a valid observed/eligible bar.
 return s.eq(True).fillna(False).astype(bool)

def _blocks(valid,identity):
 changed=identity.ne(identity.shift()).fillna(True)
 return (changed|~valid|~valid.shift(fill_value=False)).cumsum()

def _lag(s,block,n):return s.groupby(block,sort=False).shift(n)
def _roll(s,block,n,method,prior=False):
 return s.groupby(block,sort=False).transform(
     lambda v:getattr((v.shift(1)if prior else v).rolling(n,min_periods=n),method)())

def _price_view(frame):
 required=('close','segment','identity','observed','synthetic','price_eligible')
 missing=set(required)-set(frame.columns)
 if missing:raise ValueError('Missing declared input columns: '+','.join(sorted(missing)))
 c=pd.to_numeric(frame.close,errors='coerce').astype(float)
 valid=(_finite_positive(c)&_known_true(frame.observed)&frame.synthetic.eq(False).fillna(False)
        &_known_true(frame.price_eligible)&frame.segment.notna()&frame.identity.notna())
 identity=pd.Series(list(zip(frame.identity,frame.segment)),index=frame.index)
 block=_blocks(valid,identity)
 return c.where(valid),valid,block

def compute_features(stock,industry,market,*,industry_membership_known):
 """Return (17 numeric draft features, validity/provenance flags).

 Numeric IM values describe the supplied real industry index. Historical
 stock membership remains an independent mandatory provenance condition;
 a numeric value is not proof of PIT membership or an execution permission.
 """
 idx=market.index
 if not isinstance(idx,pd.DatetimeIndex)or idx.tz is not None:
  raise ValueError('Expected timezone-naive local trading-date DatetimeIndex')
 if not idx.is_unique or not idx.is_monotonic_increasing or not idx.equals(idx.normalize()):
  raise ValueError('Expected unique increasing normalized real trading dates')
 if not stock.index.equals(idx)or not industry.index.equals(idx):
  raise ValueError('All legs must already share the same market calendar; no implicit join/fill')
 if not industry_membership_known.index.equals(idx):raise ValueError('Membership clock must align')
 for col in('high','low','amount','amount_eligible'):
  if col not in stock:raise ValueError('Missing stock column '+col)
 C,cv,cb=_price_view(stock);I,iv,ib=_price_view(industry);M,mv,mb=_price_view(market)
 out=pd.DataFrame(index=idx)
 # Differences use identical t/t-h. Group boundaries prohibit crossing missing,
 # synthetic, source-segment or supplied-index-identity transitions.
 for prefix,A,av,ab in(('RS_SM',C,cv,cb),('RS_IM',I,iv,ib)):
  pair_id=pd.Series(list(zip(ab,mb)),index=idx);pair_block=_blocks(av&mv,pair_id)
  for h in(5,20):
   x=(np.log(A/_lag(A,ab,h))-np.log(M/_lag(M,mb,h)))*100
   out[prefix+str(h)]=x
   out[prefix+str(h)+'_delta5']=x-_lag(x,pair_block,5)
 # Prior channel excludes current high/low and preserves breakouts >1/<0.
 H=pd.to_numeric(stock.high,errors='coerce');L=pd.to_numeric(stock.low,errors='coerce')
 hl=(cv&_finite_positive(H)&_finite_positive(L)&L.le(C)&H.ge(C)&H.ge(L))
 high=_roll(H.where(hl),cb,20,'max',prior=True)
 low=_roll(L.where(hl),cb,20,'min',prior=True)
 out['channel20_position']=((C-low)/(high-low)).where((high-low).gt(0))
 for n in(20,60):
  ema=C.groupby(cb,sort=False).transform(lambda v:v.ewm(span=n,adjust=False,min_periods=n).mean())
  out['EMA'+str(n)+'_slope5']=np.log(ema/_lag(ema,cb,5))*100/5
 peak=_roll(C,cb,20,'max')
 out['drawdown20']=np.log(peak/C)*100
 # Amount has its own validity. Missing amount does not erase EMA/RS/channel.
 amount=pd.to_numeric(stock.amount,errors='coerce').astype(float)
 aq=(_finite_positive(amount)&_known_true(stock.observed)&stock.synthetic.eq(False).fillna(False)
     &_known_true(stock.amount_eligible)&stock.segment.notna()&stock.identity.notna())
 aid=pd.Series(list(zip(stock.identity,stock.segment)),index=idx);ab=_blocks(aq,aid)
 amount=amount.where(aq)
 prior_median=_roll(amount,ab,21,'median',prior=True)
 out['amount_prior21median_ratio']=(amount/prior_median).where(prior_median.gt(0))
 previous=_lag(C,cb,1);direction_known=C.notna()&previous.notna()
 up=C.gt(previous).astype(float).where(direction_known)
 down=C.lt(previous).astype(float).where(direction_known)
 out['up_day_fraction5']=_roll(up,cb,5,'sum')/5
 out['down_day_fraction5']=_roll(down,cb,5,'sum')/5
 # Flat days remain in the common denominator, neither counted as up nor down.
 total=_roll(amount,ab,5,'sum')
 amount_direction_known=aq&direction_known
 pair_block=_blocks(amount_direction_known,pd.Series(list(zip(cb,ab)),index=idx))
 out['up_amount_fraction5']=_roll((amount*up).where(amount_direction_known),pair_block,5,'sum')/total
 out['down_amount_fraction5']=_roll((amount*down).where(amount_direction_known),pair_block,5,'sum')/total
 out=out.loc[:,FEATURES].replace([np.inf,-np.inf],np.nan)
 quality=out.notna().add_suffix('_numeric_known')
 quality['stock_close_valid']=cv;quality['stock_amount_valid']=aq
 quality['industry_close_valid']=iv;quality['market_close_valid']=mv
 quality['industry_membership_known']=industry_membership_known.astype('boolean')
 return out,quality

if __name__=='__main__':raise SystemExit('Draft only. No execution entrypoint before root freeze.')
