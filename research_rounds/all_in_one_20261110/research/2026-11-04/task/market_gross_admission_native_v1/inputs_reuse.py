"""Exact existing input functions; import wiring only, no cost adapter import."""
from pathlib import Path
import gross_adapter as C
SOURCE=Path(__file__).resolve().parent.parent/'capacity_cost_guard_v1/capacity_inputs.py'
original=SOURCE.read_text();needle='import capacity_adapter as C';assert original.count(needle)==1
derived=original.replace(needle,'# C supplied by the gross-only caller; original input body unchanged')
exec(compile(derived,str(SOURCE),'exec'),globals())
