"""Compare the 21 standard completed cohorts; incomplete cohorts excluded."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
for ticker, filename, color in [('QLD', 'qld_reference_results.json', '#2463a6'),
                                 ('TQQQ', 'results.json', '#dd7134')]:
    rows = [r for r in json.loads((ROOT/filename).read_text())['results'] if r['complete']]
    years = [r['start_year'] for r in rows]
    axes[0].plot(years, [r['final_value'] for r in rows], color=color, marker='o', label=f'{ticker} final')
    axes[0].plot(years, [r['max_account_value'] for r in rows], color=color, linestyle='--', alpha=.75,
                 label=f'{ticker} historical peak')
    axes[1].plot(years, [r['xirr']*100 for r in rows], color=color, marker='o', label=ticker)
axes[0].axhline(200000, color='#777', linestyle=':', label='Total contributions: $200,000')
axes[0].set_yscale('log')
axes[0].set_ylabel('Account value (USD, log scale)')
axes[0].set_title('20-year annual DCA: $10,000 per year\n21 completed windows; pre-inception ETF returns are simulated')
axes[0].legend(ncol=2)
axes[1].axhline(0, color='#777', linewidth=1)
axes[1].set_ylabel('Final XIRR (%)')
axes[1].set_xlabel('Window start year (end at last trading day of start year + 19)')
axes[1].set_xticks(years[::2])
axes[1].legend()
for ax in axes:
    ax.grid(alpha=.2)
fig.savefig(ROOT/'comparison.png', dpi=160)
plt.close(fig)
