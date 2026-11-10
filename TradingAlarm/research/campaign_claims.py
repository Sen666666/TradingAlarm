"""Non-tradable whole-share claims and their dividends, separate from strategy shares."""
import pandas as pd
from in_kind_ledger import InKindLedger
from campaign_engine import dividend_local_value


class CampaignClaims:
    def __init__(self, parents, recipients):
        self.parents=parents;self.assets=recipients;self.ledger=InKindLedger()
        self.receipts=[];self.processed=set();self.cash_paid=0.;self.events=[]
        for a in recipients.values():
            if a['splits'] or a['currency']!='HKD':raise ValueError('Claim recipient split/currency not supported')

    def quantities(self):
        result={n:0 for n in self.assets}
        for c in self.ledger.claims.values():result[c.recipient]+=c.whole
        return result

    def step(self,date,holdings,fx,fx_bps):
        date=pd.Timestamp(date);day=str(date.date())
        if self.processed and day<=max(self.processed):raise ValueError('Claim ledger requires increasing dates')
        self.processed.add(day)
        for n,a in self.parents.items():
            for e in a.get('in_kind',[]):
                if day!=e['ex_date'] or not holdings[n]:continue
                qty=holdings[n]
                if qty!=int(qty):raise ValueError('Non-integral parent inventory')
                c=self.ledger.accrue(n+day,e['recipient'],day,int(qty),e['numerator'],e['denominator'])
                self.events.append(dict(parent=n,date=day,recipient=e['recipient'],whole=c.whole,fraction=str(c.fraction)))
        for n,qty in self.quantities().items():
            if not qty:continue
            for e in self.assets[n]['dividends']:
                if e['ex_date']==day:self.receipts.append((n,qty,e))
        unpaid=[];paid=fees=0.
        for n,qty,e in self.receipts:
            value=qty*dividend_local_value(self.assets[n],e,date)*fx
            if date>=pd.Timestamp(e['pay_date']):
                fee=value*fx_bps/10000
                if e.get('currency','HKD')!='HKD' and not(e.get('settlement') and date>pd.Timestamp(e['settlement']['fixing'])):fee+=value*e.get('conversion_bps',10)/10000
                paid+=value-fee;fees+=fee
            else:unpaid.append((n,qty,e))
        self.receipts=unpaid;self.cash_paid+=paid
        return paid,fees

    def values(self,date,fx,field='close'):
        date=pd.Timestamp(date);values={}
        if self.processed and str(date.date())<max(self.processed):raise ValueError('Cannot mark future ledger state in the past')
        for n,qty in self.quantities().items():
            if not qty:values[n]=0.;continue
            history=self.assets[n]['raw'].loc[:date]
            if history.empty:raise ValueError('No dated claim mark')
            row=history.iloc[-1];price=row[field] if history.index[-1]==date else row.close
            values[n]=qty*float(price)*fx
        due=sum(qty*dividend_local_value(self.assets[n],e,date)*fx for n,qty,e in self.receipts)
        return values,float(due)
