"""Static excerpt only. No price source, indicator, account, route or financial replay."""
from pathlib import Path
import hashlib,json

ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4')
OLD=ROOT/'upside_state_v1/examples_semis'
OUT=ROOT/'upside_revision_v1/examples';OUT.mkdir(parents=True,exist_ok=True)
SOURCE={}
def read(name):
 p=OLD/name;SOURCE[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

winner=read('WINNER_605358_2026_05_20_SAVED_CONTEXT.json')
gold=read('GOLD_PREENTRY_BREAKOUT_AND_ORIGINAL_PERMISSIONS.json')
all25=read('ALL25_SAVED_ROLE_HOLDING_CHAINS.json')
price=read('KEY_DATE_INPUTS.json')
quantities=read('AGGREGATE_LAYER_QUANTITY_FACTS.json')
t5=read('FOUR_PAPER_T5_L10_INPUTS.json')
summary=read('FINAL_STATUS.json')

save('SAVED_WINNER_FRESH_I_AND_CP_BRANCHES.json',dict(
 scope='Unmodified excerpts from previously sealed examples only; no new evidence/feature/replay.',
 original_opportunities=winner['saved_original_opportunities'],original_funding=winner['saved_original_funding'],
 original_rank_policy=winner['saved_original_rank_policy'],
 saved_NAV_and_cash=winner['daily_header'],stock_qty=winner['stock_qty'],stock_original_layers=winner['stock_original_layers'],stock_capital=winner['stock_capital'],stock_NAV_weight_pct=winner['stock_NAV_weight_pct'],
 original_industry_state=winner['latest_industry_event'],industry_capital=winner['industry_capital'],industry_known_line_risk=winner['industry_known_line_risk'],
 original_next_open_cash_before_original_reservations=winner['next_OPEN_cash_after_original_sells_before_original_new_reservations'],original_next_open_spendable_before_original_reservations=winner['next_OPEN_spendable_before_original_reservations'],
 missing=winner['missing'],
 argument='May11/12/13 and May20 original core_Q true with held true and CP absent are typed HELD_I opportunities in principle; May14/15/18 I_target persistence with core_Q false cannot create new I events. Original May19 CP opportunity was attempted and rejected for real cash/sector-capital constraints.'))

focus=[r for r in all25 if r['layer']in[674,677,684,702,1019,1059,1075]]
save('SAVED_GOLD_LATE_ADD_AND_PROTECTION_TRADEOFF.json',dict(
 scope='Original historical events and saved scalar risk fields, no new order/risk sizing.',
 original_Gold_funding=gold['original_funding'],original_Gold_opportunities=gold['original_opportunities'],
 saved_702_I_minimum_risk=gold['last_add_702_existing_minimum_I_risk'],saved_702_common_floor_arithmetic=gold['common_floor_arithmetic_for_702'],
 original_layers=focus,
 previously_saved_price_examples=[r for r in price if(r['sid']=='603061.SH'and r['day']in['2026-01-16','2026-01-19','2026-01-20','2026-01-28','2026-02-11'])],
 previously_saved_T5_examples=[r for r in t5['rows']if r['sid']=='603061.SH'],
 original_aggregate_quantities=quantities,
 argument='Early and late Gold buys all had visible trend and higher-close evidence; observed late loss cannot justify retrospectively selecting a two-add cap. Original I-based minimum100 can fail while genuine CP-based MOBILE filled under its distinct nominal/protection contract. No assertion that CP satisfies a new unified risk budget without its own actual-price fee calculation.'))

save('SAVED_HARDLINE_AND_PERSISTENT_I_COUNTEREXAMPLES.json',dict(
 scope='Previously saved values only.',
 examples=[r for r in price if(r['sid']=='300666.SZ'and r['day']=='2026-01-29')or(r['sid']=='301611.SZ'and r['day']in['2026-01-29','2026-02-10'])or(r['sid']=='300623.SZ'and r['day']=='2026-03-03')],
 original_universe_and_layer_scope=summary['saved_layer_scope'],
 limits='These are diagnostic examples requested after outcomes, not an ex-ante universe or a proof of net policy benefit.'))
save('SCOPE.json',dict(status='STATIC_REUSE_COMPLETE',new_accounts=0,new_backtests=0,new_indicators=0,new_raw_price_reads=0,new_price_queries=0,new_financial_replays=0,new_order_or_route=0,originals_changed=False,selection='Only sealed examples from preceding read-only review; no whole-market extraction or new outcome labels.'))
SOURCE[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
save('SOURCE_SHA256.json',SOURCE)
print('Static saved-input excerpts complete; 0 new prices/indicators/accounts/routes/replays.')
