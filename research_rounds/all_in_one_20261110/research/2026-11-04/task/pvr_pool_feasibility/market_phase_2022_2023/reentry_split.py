"""Reuse independently extracted prior closed campaigns, not a new trade engine."""
from pathlib import Path
from decimal import Decimal as D
import analyze_phase as A
O=A.O
SOURCE=A.T/'loss_correction/no60_behavior_v1/continuation2023/PVR_NO60-CAMPAIGNS.json'
def main():
 campaigns=A.read(SOURCE)
 assert abs(sum((D(x['net'])for x in campaigns),D(0))-D('-254573.0416219099465'))<D('.000001')
 stocks=A.read(O/'ALL_PHASE_STOCK_WEALTH.json')['NO60'];legs=A.read(O/'HS300_ALL_LEGS.json');out=[]
 for leg in legs:
  rr=[r for r in stocks if r['leg']==leg['id']and r['cohort']=='previously_bought_but_flat_reentry'];groups={};details=[]
  for r in rr:
   previous=[x for x in campaigns if x['sid']==r['sid']and x['position_closed']and x['closed'][:10]<=leg['left']]
   assert previous,r['sid'];last=max(previous,key=lambda x:x['closed']);v=D(last['net'])
   label='last_prior_closed_campaign_negative'if v<0 else'last_prior_closed_campaign_nonnegative'
   x=groups.setdefault(label,dict(stocks=0,phase_wealth=D(0),actual_buy_cash=D(0)));x['stocks']+=1;x['phase_wealth']+=D(r['net_PnL']);x['actual_buy_cash']+=D(r['actual_buy_cash'])
   details.append(dict(sid=r['sid'],name=r['name'],previous_campaign_close=last['closed'],previous_campaign_net=last['net'],previous_claim_status=last['claim_status'],
    phase_wealth=r['net_PnL'],actual_phase_buy_cash=r['actual_buy_cash'],classification=label))
  out.append(dict(leg=leg['id'],groups=groups,stocks=details))
 A.save('REENTRY_PRIOR_CAMPAIGN_SPLIT.json',dict(source=str(SOURCE),source_sha256=A.sha(SOURCE),source_all_campaigns_sum_matches_full_NAV=True,
  scope='whole-stock phase wealth grouped by latest actually position-closed campaign before phase. Prior economic wealth includes recognized unpaid claims; no delete-trade CF or new gate.',rows=out))
 A.SRC[str(Path(__file__))]=A.sha(__file__);A.save('REENTRY_SPLIT_SOURCE_SHA256.json',A.SRC)
 print('PRIOR_CAMPAIGN_REENTRY_SPLIT_PASS')
if __name__=='__main__':main()
