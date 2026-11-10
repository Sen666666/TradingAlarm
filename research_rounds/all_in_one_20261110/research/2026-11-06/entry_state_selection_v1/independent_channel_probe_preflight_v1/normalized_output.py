"""Output-only dtype normalization. Frozen core and market values stay unchanged."""
from core import simulate as _frozen_simulate
def simulate(q):
 x=_frozen_simulate(q)
 x["receipt_id"]=x["receipt_id"].astype("string")
 return x
