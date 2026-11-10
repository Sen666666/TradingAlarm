"""Reformat saved screening results without recomputing signals."""
import json
from snapshot import OUT,BASE,finalize
import pandas as pd
if __name__=='__main__':
    roster=pd.read_csv(BASE/'audit-snapshot/cap-join-hk-cachedfx-check-03/current-snapshot-selection.csv',dtype=str).fillna('').to_dict('records')
    d=json.loads((OUT/'workbook-data.json').read_text())
    finalize(roster,d['sectors'],json.loads((OUT/'stock-signals.json').read_text()),json.loads((OUT/'protocol.json').read_text()))
