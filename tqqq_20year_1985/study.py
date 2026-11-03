"""Reproducible 40-cohort TQQQ 20-calendar-year annual DCA and independent audit.

Run from any directory with Python 3. Inputs are the archived source-derived
daily prices and previously audited QLD cohort results in this folder.
"""
import csv
import datetime as dt
import json
import math
import statistics
from decimal import Decimal, getcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parent
END = '2026-10-30'
getcontext().prec = 50


def read_csv(name):
    with (ROOT / name).open(encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))


def save_csv(name, rows):
    with (ROOT / name).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def xirr(funding, end, value):
    """Solve discounted cash-flow NPV in rate space."""
    origin = dt.date.fromisoformat(funding[0]['date'])
    terms = [(float(r['contribution']), (dt.date.fromisoformat(r['date']) - origin).days / 365)
             for r in funding if r['date'] <= end]
    elapsed = (dt.date.fromisoformat(end) - origin).days / 365
    if elapsed == 0:
        return None

    def residual(rate):
        return value / (1 + rate) ** elapsed - sum(c / (1 + rate) ** t for c, t in terms)

    low, high = -.99999, 1.
    while residual(high) > 0:
        high = high * 2 + 1
    for _ in range(160):
        middle = (low + high) / 2
        if residual(middle) > 0:
            low = middle
        else:
            high = middle
    rate = (low + high) / 2
    assert abs(residual(rate)) < max(1e-6, value * 1e-12)
    return rate


def audit_xirr(funding, end, value):
    """Independent terminal compound-value equation in logarithmic growth."""
    terminal = dt.date.fromisoformat(end)
    terms = [(float(r['contribution']), (terminal - dt.date.fromisoformat(r['date'])).days / 365)
             for r in funding if r['date'] <= end]
    if not any(t for _, t in terms):
        return None
    low, high = -50., 10.
    for _ in range(160):
        middle = (low + high) / 2
        compound_value = sum(c * math.exp(middle * t) for c, t in terms)
        if compound_value > value:
            high = middle
        else:
            low = middle
    rate = math.expm1((low + high) / 2)
    residual = sum(c * (1 + rate) ** t for c, t in terms) - value
    assert abs(residual) < max(1e-6, value * 1e-12)
    return rate


inputs = read_csv('daily_inputs.csv')
assert inputs[0]['date'] == '1985-01-31' and inputs[-1]['date'] == END
dates = [r['date'] for r in inputs]
actual_dates = [r['date'] for r in inputs if r['tqqq_adjusted_close']]
assert actual_dates[0] == '2010-02-11'
assert all(r['tqqq_adjusted_close'] for r in inputs if r['date'] >= actual_dates[0])

# Daily model is explicitly 3x, with financing on two borrowed units.
prices = []
balance = 1.
scale = None
for row in inputs:
    day = row['date']
    factor = (1 + 3 * (float(row['underlying_current']) / float(row['underlying_previous']) - 1)
              - (2 * float(row['lagged_irx_yield']) + .01) * int(row['calendar_days']) / 365)
    assert factor > 0
    modeled = balance * factor
    if row['tqqq_adjusted_close']:
        actual = float(row['tqqq_adjusted_close'])
        if scale is None:
            scale = modeled / actual
        balance = actual * scale
        source = 'TQQQ实盘'
    else:
        balance = modeled
        source = '每日3倍模拟'
    prices.append(dict(date=day, fund_close=balance, source=source))
save_csv('hybrid_3x_daily.csv', prices)

# Rebuild daily prices independently with 50-digit Decimal arithmetic.
D = lambda value: Decimal(str(value))
decimal_prices = []
decimal_balance = D(1)
decimal_scale = None
for row in inputs:
    step = (D(1) + D(3) * (D(row['underlying_current']) / D(row['underlying_previous']) - D(1))
            - (D(2) * D(row['lagged_irx_yield']) + D('.01')) * D(row['calendar_days']) / D(365))
    decimal_balance *= step
    if row['tqqq_adjusted_close']:
        if decimal_scale is None:
            decimal_scale = decimal_balance / D(row['tqqq_adjusted_close'])
        decimal_balance = D(row['tqqq_adjusted_close']) * decimal_scale
    decimal_prices.append(decimal_balance)
path_error = max(abs(float(d / D(p['fund_close'])) - 1) for d, p in zip(decimal_prices, prices))
assert path_error < 1e-10

# New long-history normalization must preserve the earlier reviewed 10-year
# TQQQ cohort values, including both simulated and actual-only windows.
reference_10 = json.loads((ROOT/'10year_reference_results.json').read_text())
overlap_errors = []
for reference in reference_10:
    subset = [r for r in prices if f"{reference['start_year']}-01-01" <= r['date'] <= reference['end']]
    shares = 0.
    last_year = None
    for row in subset:
        if row['date'][:4] != last_year:
            last_year = row['date'][:4]
            shares += 10000 / row['fund_close']
    error = abs(shares * subset[-1]['fund_close'] / reference['final_value'] - 1)
    assert error < 1e-10
    overlap_errors.append(error)

results, all_funding, audit = [], [], []
for year in range(1985, 2025):
    positions = [i for i, day in enumerate(dates) if f'{year}-01-01' <= day < f'{year + 20}-01-01']
    funding = []
    units = principal = 0.
    previous_year = None
    fund_peak = 0.
    peak_date = None
    worst = 0.
    dd_dates = None
    daily = []
    for i in positions:
        row = prices[i]
        day, price = row['date'], row['fund_close']
        if day[:4] != previous_year:
            previous_year = day[:4]
            principal += 10000
            units += 10000 / price
            funding.append(dict(date=day, contribution=10000, fund_close=price))
            all_funding.append(dict(start_year=year, **funding[-1]))
        value = units * price
        if price > fund_peak:
            fund_peak, peak_date = price, day
        dd = price / fund_peak - 1
        if dd < worst:
            worst, dd_dates = dd, (peak_date, day)
        daily.append(dict(date=day, value=value, invested=principal,
                          profit=value-principal, simple_return=value/principal-1))
    ended = f'{year + 20}-01-01' <= END
    if ended:
        assert len(funding) == 20 and principal == 200000
    assert len(funding) == len({r['date'][:4] for r in funding})
    peak = max(daily, key=lambda r: r['value'])
    highest_return = max(daily, key=lambda r: r['simple_return'])
    terminal = daily[-1]
    result = dict(
        ticker='TQQQ', start_year=year, requested_end=f'{year+20}-01-01',
        first_deposit=daily[0]['date'], end=terminal['date'],
        status='1985特殊起点：1月31日' if year == 1985 else ('完整20年' if ended else '未满20年'),
        complete=ended and year != 1985, calendar_window_ended=ended,
        annual_deposits=len(funding), invested=principal,
        final_value=terminal['value'], profit=terminal['profit'], simple_return=terminal['simple_return'],
        xirr=xirr(funding, terminal['date'], terminal['value']), max_nav_drawdown=worst,
        drawdown_peak=dd_dates[0], drawdown_trough=dd_dates[1],
        max_account_value=peak['value'], max_account_date=peak['date'],
        principal_at_max_account=peak['invested'], profit_at_max_account=peak['profit'],
        simple_return_at_max_account=peak['simple_return'],
        xirr_at_max_account=xirr(funding, peak['date'], peak['value']),
        max_simple_return=highest_return['simple_return'], max_simple_return_date=highest_return['date'],
        account_at_max_simple_return=highest_return['value'], principal_at_max_simple_return=highest_return['invested'],
        model_days=sum(prices[i]['source'] != 'TQQQ实盘' for i in positions),
        actual_days=sum(prices[i]['source'] == 'TQQQ实盘' for i in positions))
    results.append(result)

    # Independent account construction sums each purchase lot's raw Decimal
    # price ratio, rather than using accumulated float shares.
    decimal_lots = []
    independent_values = []
    independent_principals = []
    invested = 0
    for i in positions:
        day = dates[i]
        if not decimal_lots or day[:4] != dates[decimal_lots[-1][0]][:4]:
            decimal_lots.append((i, D(10000)))
            invested += 10000
        independent_values.append(float(sum(amount * decimal_prices[i] / decimal_prices[buy_i]
                                            for buy_i, amount in decimal_lots)))
        independent_principals.append(invested)
    account_error = max(abs(value / row['value'] - 1) for value, row in zip(independent_values, daily))
    assert account_error < 1e-10
    peak_i = max(range(len(daily)), key=lambda i: independent_values[i])
    return_i = max(range(len(daily)), key=lambda i: independent_values[i] / independent_principals[i] - 1)
    assert daily[peak_i]['date'] == peak['date']
    assert daily[return_i]['date'] == highest_return['date']
    final_irr = audit_xirr(funding, terminal['date'], independent_values[-1])
    peak_irr = audit_xirr(funding, peak['date'], independent_values[peak_i])
    irr_error = max(abs(final_irr-result['xirr']), abs(peak_irr-result['xirr_at_max_account']))
    assert irr_error < 1e-9
    actual_error = None
    if year >= 2011:
        # Actual-only portfolios are additionally valued directly with the
        # unnormalized raw ETF adjusted closes, bypassing the model entirely.
        actual_lots = []
        errors = []
        for i, daily_row in zip(positions, daily):
            if not actual_lots or dates[i][:4] != dates[actual_lots[-1]][:4]:
                actual_lots.append(i)
            value = sum(10000 * float(inputs[i]['tqqq_adjusted_close']) /
                        float(inputs[buy_i]['tqqq_adjusted_close']) for buy_i in actual_lots)
            errors.append(abs(value / daily_row['value']-1))
        actual_error = max(errors)
        assert actual_error < 1e-10
    audit.append(dict(start_year=year, daily_account_relative_error=account_error,
                      xirr_absolute_error=irr_error, actual_only_relative_error=actual_error))

full = [r for r in results if r['complete']]
assert len(results) == 40 and len(full) == 21
summary = dict(ticker='TQQQ', windows=21, principal=200000,
               median_final=statistics.median(r['final_value'] for r in full),
               worst_final=min(r['final_value'] for r in full), best_final=max(r['final_value'] for r in full),
               median_xirr=statistics.median(r['xirr'] for r in full),
               worst_xirr=min(r['xirr'] for r in full), best_xirr=max(r['xirr'] for r in full),
               loss_windows=sum(r['profit'] < 0 for r in full),
               worst_nav_drawdown=min(r['max_nav_drawdown'] for r in full))
save_csv('40组_TQQQ最终与峰值.csv', results)
save_csv('annual_funding.csv', all_funding)
save_csv('audit_cohorts.csv', audit)
qld = json.loads((ROOT/'qld_reference_results.json').read_text())
combined = []
for row in qld['results']:
    combined.append({key: ('QLD' if key == 'ticker' else row[key]) for key in results[0]})
combined += results
save_csv('80组_QLD与TQQQ最终与峰值.csv', combined)
verification = dict(cohorts=40, complete_standard_windows=21, special_windows=1, unfinished_windows=18,
                    decimal_precision=50, max_raw_price_relative_error=path_error,
                    max_daily_account_relative_error=max(r['daily_account_relative_error'] for r in audit),
                    final_and_peak_xirr_checks=80,
                    max_xirr_absolute_error=max(r['xirr_absolute_error'] for r in audit),
                    actual_only_cohorts=14, actual_only_max_relative_error=max(
                        r['actual_only_relative_error'] for r in audit if r['actual_only_relative_error'] is not None),
                    all_peak_dates_and_highest_return_dates_verified=True,
                    prior_10year_cohorts_verified=len(overlap_errors),
                    prior_10year_max_relative_error=max(overlap_errors),
                    limitations=['Pre-2010 TQQQ is modeled, not an actual ETF return.',
                                 'Pre-QQQ NDX price returns omit dividends.',
                                 'IRX borrowing proxy and assumed 1% fee are model assumptions.',
                                 'Twenty contribution calendar years do not always mean 20 elapsed years.',
                                 'Overlapping cohorts are not independent observations.'])
(ROOT/'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2)+'\n')
(ROOT/'results.json').write_text(json.dumps(dict(as_of=END, window_years=20,
    annual_contribution=10000, results=results, summary=summary), ensure_ascii=False, indent=2)+'\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(verification, ensure_ascii=False, indent=2))
