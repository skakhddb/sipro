"""Jadwal angsuran KPR (simulasi anuitas) — SATU rumus untuk staf & portal pembeli.

Masa fixed memakai bunga produk; sesudahnya, bila produk punya bunga floating, angsuran
dihitung ulang atas sisa pokok untuk sisa tenor. Angka adalah SIMULASI, bukan angka bank.
"""


def annuity(principal: int, rate_pct: float, months: int) -> int:
    if principal <= 0 or months <= 0:
        return 0
    r = float(rate_pct or 0) / 100 / 12
    if r == 0:
        return round(principal / months)
    return round(principal * r / (1 - (1 + r) ** (-months)))


def yearly_schedule(plafon: int, tenor_months: int, rate_pct: float,
                    fixed_years: int | None = None, floating_rate_pct: float | None = None) -> dict:
    plafon, tenor = int(plafon or 0), int(tenor_months or 0)
    if plafon <= 0 or tenor <= 0:
        return {"rows": [], "fixed_installment": 0, "floating_installment": None,
                "total_interest": 0, "total_paid": 0, "fixed_months": 0}
    fixed_months = min(tenor, int(fixed_years or 0) * 12) if fixed_years else tenor
    has_float = floating_rate_pct is not None and fixed_months < tenor \
        and float(floating_rate_pct) != float(rate_pct)
    if not has_float:
        fixed_months = tenor
    inst = annuity(plafon, rate_pct, tenor)
    float_inst = None
    balance, rate, rows = plafon, float(rate_pct), []
    year = {"year": 1, "months": 0, "principal_paid": 0, "interest_paid": 0, "installment": inst, "rate": rate, "phase": "fixed"}
    total_interest = total_paid = 0
    for m in range(1, tenor + 1):
        if m == fixed_months + 1 and has_float:
            rate = float(floating_rate_pct)
            inst = float_inst = annuity(balance, rate, tenor - fixed_months)
            year["installment"], year["rate"], year["phase"] = inst, rate, "floating"
        interest = round(balance * rate / 100 / 12)
        principal = inst - interest if m < tenor else balance
        if m == tenor:
            inst_now = balance + interest
        else:
            inst_now = inst
        balance -= principal
        year["months"] += 1
        year["principal_paid"] += principal
        year["interest_paid"] += interest
        total_interest += interest
        total_paid += inst_now
        if m % 12 == 0 or m == tenor:
            year["balance_end"] = max(balance, 0)
            rows.append(year)
            year = {"year": year["year"] + 1, "months": 0, "principal_paid": 0, "interest_paid": 0,
                    "installment": inst, "rate": rate, "phase": "floating" if m >= fixed_months and has_float else "fixed"}
    return {"rows": rows, "fixed_installment": annuity(plafon, rate_pct, tenor), "floating_installment": float_inst,
            "fixed_months": fixed_months if has_float else tenor, "floating_rate_pct": float(floating_rate_pct) if has_float else None,
            "total_interest": total_interest, "total_paid": total_paid}
