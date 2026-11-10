"""Bounded offline extension on existing THS485, same frozen diagnostic; no accounts."""
import argparse,json,hashlib,datetime
from pathlib import Path
import pandas as pd,numpy as np
import diagnose_volume_shape as diagnostic
from run_pv_segment_round import write
from stock_actions import parse_ths_rights
ROOT=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research')

def main(source,out,root):
    out.mkdir(exist_ok=False);base=root/'data/ths-refresh-20261018';cohort=base/'validated-input-balanced-second500.json';protocol=json.loads((source/'protocol.json').read_text());protocol.update(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='Extension frozen after ETF17/HK7 yielded only8matched pairs; before this A485 event diagnostic, existing histories already researched',universe='Exactly485 previously validated THS snapshots; current surviving selected pool, not historicalPIT universe; roughly750bars per symbol, actual dates audited',price_outcome='Existing theoretical-ex-price signal_close, NOT cash-account total return. Same-bar raw OHLC, actual stored volume corrected for shares using parsed rights. Synthetic event bars excluded by zero volume.',cohort_sha256=hashlib.sha256(cohort.read_bytes()).hexdigest(),changes='Universe extension only; same feature/event/matching thresholds, no loosening to obtain favorable result. No account or sector-membership claim.')
    f=out/'protocol.json';write(f,protocol);write(out/'freeze.json',dict(sha256=hashlib.sha256(f.read_bytes()).hexdigest(),a485_diagnostic_outputs_seen=False))
    audit=[];inputs={str(cohort):hashlib.sha256(cohort.read_bytes()).hexdigest()}
    def load():
        pool={}
        for rec in json.loads(cohort.read_text())['records']:
            code=rec['ths_symbol'];s=rec['symbol'];paths={'signal':base/f'{code}-signal.parquet','history':base/f'ths-raw/{code}.json','rights':base/f'rights/{code}.json'}
            for kind,p in paths.items():
                h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==rec[kind+'_sha256'],(s,kind);inputs[str(p)]=h
            z=pd.read_parquet(paths['signal']);raw=z[['open','high','low','close','volume']].copy();sig=z[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda c:c.replace('signal_',''));sig['volume']=raw.volume;splits=[];rights=json.loads(paths['rights'].read_text())
            for row in rights['records']:
                event_date=pd.to_datetime(str(row['1']),format='%Y%m%d')
                if event_date<=raw.index.min() or event_date>raw.index.max():continue
                e=parse_ths_rights(code,row);ratio=1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share'];date=e['effective_date']
                if ratio!=1 and pd.Timestamp(date) in raw.index:splits.append(dict(date=date,ratio=ratio))
            pool[s]=dict(raw=raw,signal=sig,splits=splits);geometry=raw.high.ge(raw[['open','close']].max(axis=1)-1e-8)&raw.low.le(raw[['open','close']].min(axis=1)+1e-8);audit.append(dict(symbol=s,rows=len(z),first=str(z.index[0].date()),last=str(z.index[-1].date()),invalid_geometry=int((~geometry).sum()),synthetic_rows=int(z.synthetic_event_bar.sum()),share_events=len(splits)))
        write(out/'data-audit.json',audit);write(out/'verified-inputs.json',inputs);return {'a485':pool},audit
    diagnostic.assets=load;diagnostic.main(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--research-root',type=Path,default=ROOT);a=p.parse_args();main(a.source,a.output,a.research_root)
