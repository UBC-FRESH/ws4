# Process fire-regime risk accounts

Status: implemented (P214)
Phase: P214 (#1246)
Date: 2026-11-14
Related: `notes/design/ws4-process-fire-regime.md`,
`ws4/opt/fire_risk.py`

## 1. Purpose

P212/P213 report fire-regime distributions per process scenario. P214 maps them to the account
frame the existing optimizer risk aggregation consumes.

This is a reporting bridge; the optimizer search is unchanged.

## 2. Accounts

For each scenario at the final offset:

- `fire.regime.total_burned_ha`
- `fire.regime.burn_probability`
- `fire.regime.annual_burn_rate`
- `fire.regime.escaped_fires_per_year`
- `fire.regime.mean_fire_size_ha`
- `fire.regime.max_fire_size_ha`
- `fire.regime.fire_count`
- `fire.regime.fire_return_interval_years`, only when defined

Zero fire intentionally omits FRI rather than writing zero.

## 3. Risk aggregation

`fire_regime_account_values` returns `offset`, `account`, `value`, and `scenario` rows. The test
feeds them to `risk_account_values` with a mean target. The result is a `risk.mean.*` row and an
effective target on that pseudo-account.

## 4. Evidence

- Process fire-risk tests: 4 passed.
- Two-scenario ensemble: stable rows and totals.
- Zero fire: FRI omitted, fire count 0.
- Mean risk aggregation produces `risk.mean.0.fire.regime.annual_burn_rate`.

## 5. Limits

- Final-period only.
- No optimizer search integration.
- Distributional, not observed-perimeter validation.
- FRI has no defined value for zero fire and is omitted.
