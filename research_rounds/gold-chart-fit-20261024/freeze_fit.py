from pathlib import Path
import json,hashlib,datetime
from fit_models import configurations
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    files=['fit_models.py','targets.json','data/sina-AU0.csv','data/sge-Au9999.csv']
    baseline=ROOT/'research_rounds/pv-participation-response-20261020/code'
    temperature=ROOT/'research_rounds/temperature-prototype-20261023/temperature.py'
    protocol=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='Bounded in-sample imitation of screenshot timing, not recovering a proprietary algorithm or selecting a profitable strategy',
      observations='2024 start warmup; screenshot date window inferred from geometry; report extra data through 2026-10-23 separately',
      targets='Five visually interpreted pairs; printed Sep01 and Oct22 anchor years inferred as 2025; other centers +/-3 observations. Date uncertainty is geometric, not a statistical confidence interval.',
      original_code={str(p.relative_to(ROOT)):sha(p) for p in [baseline/'numeric.py',baseline/'participation.py',temperature]},inputs_and_imitation_code={s:sha(HERE/s) for s in files},configurations=configurations(),
      rules={'EMA':'Close above EMA(n)+band*prior ATR14 starts; close <= EMA(n)-band*prior ATR14 ends. Same-day EMA includes current close, known at close.',
      'Channel':'Close > prior n close maximum starts; close <= prior m close minimum ends.',
      'ATR':'Close > prior n close maximum starts; monotonically raised stop max(old stop, maximum close since entry - k*prior ATR14); close <= stop ends.',
      'VolumeATR':'ATR rules with entry requiring volume/prior21median >=1.5 and close location >=2/3. Volume can veto entry.',
      'execution':'Close-time state only; no actual fills. All controls prohibit same-day reentry after exit; warmup64. Continuous contract is not an executable instrument.'},
      evaluation={'score':'.5 * state mismatch outside uncertainty bands + .5 * event edit distance / (30*10)',
      'event_matching':'By type and order. Distance outside reference date band; every extra and every missing event costs30 observations. Count all events, including 2026 non-target rebounds.',
      'controls':'Original frozen quantity-price; original price-only ablation; temperature structure; temperature >=4 triggered persistent structure; temperature >=4 daily state (semantic diagnostic). Algorithms retained unchanged.',
      'sensitivity':'Re-evaluate nonprinted date uncertainty +/-1 and +/-5 observations and inferred screenshot cutoff +/-3 observations, no refitting grid or rules.'},
      stopping='Exactly36 finite configurations plus fixed controls, one run. No expansion if poor fit. No P&L/account, no promotion. Preserve failures and raw/chart measurement repairs.',
      limitations='Image already viewed. All fitted dates/parameters are development evidence; prefix consistency only checks causal runtime with retrospectively chosen parameters, not out-of-sample training.')
    with (HERE/'fit-protocol.json').open('x') as f:json.dump(protocol,f,ensure_ascii=False,indent=2);f.write('\n')
    print('frozen',len(protocol['configurations']),'configurations',sha(HERE/'fit-protocol.json'))
if __name__=='__main__':main()
