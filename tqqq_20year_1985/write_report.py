"""Write the combined report 34 without creating a duplicate docs entry."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT.parent / 'docs'
qld = json.loads((ROOT/'qld_reference_results.json').read_text())
tqqq = json.loads((ROOT/'results.json').read_text())


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |',
                      '| '+' | '.join(['---']*len(headers))+' |']
                     + ['| '+' | '.join(map(str, row))+' |' for row in rows])+'\n'


def money(value):
    return f'{value/10000:,.2f}'


def percent(value):
    return f'{value*100:.2f}%'


lines = [
    '# QLD与TQQQ普通年度定投：40组滚动20年，最终与峰值结果', '',
    '每年1月首个有行情交易日收盘投入10,000美元，全仓持有各自基金，无额外初始本金。QLD与TQQQ使用相同投入日期、起点和截止日期，分别独立回测。计划起点1985—2024，各40组；完整窗口覆盖20个投入年度、本金200,000美元。数据截至2026-10-30。1985组首笔1985-01-31，单列特殊起点；1986—2006起点21组标准完整；2007—2024起点18组未完成。2007组已投20笔，但尚未到2027年计划结束日。', '',
    '投入年份1985—2004的期末为2004年最后交易日。XIRR按实际现金流日期计算；峰值资产、利润及收益率均使用峰值当天本金，峰值仅为事后记录，没有假设在峰值卖出。表中金额单位均为**万美元**。', '',
    '## 21组标准完整20年汇总', '',
]
summary_rows = []
for ticker, data in [('QLD', qld), ('TQQQ', tqqq)]:
    s = data['summary']
    summary_rows.append([ticker, money(s['median_final']), money(s['worst_final']), money(s['best_final']),
                         percent(s['median_xirr']), percent(s['worst_xirr']), percent(s['best_xirr']),
                         f"{s['loss_windows']}/21", percent(s['worst_nav_drawdown'])])
lines.append(table(['基金', '期末资产中位数', '最差期末资产', '最好期末资产', 'XIRR中位数',
                    '最差XIRR', '最好XIRR', '亏损组数', '最差净值回撤'], summary_rows))
lines += [
    'TQQQ的中位数收益更高，但亏损组数和最差亏损明显更大。最差完整窗口同为1989—2008：QLD期末16.02万美元、XIRR−2.17%；TQQQ期末2.53万美元、XIRR−28.31%，相对20万美元本金亏损87.34%。1985特殊起点未计入上述21组统计，TQQQ该组也略有亏损。', '',
]
headers = ['投入年份', '状态', '本金', '期末/截止资产', '最终利润', '最终XIRR', '最大净值回撤',
           '最高资产', '最高日期', '峰值本金', '峰值利润', '峰值收益率', '峰值XIRR']
for ticker, data in [('QLD', qld), ('TQQQ', tqqq)]:
    lines += [f'## {ticker}：40组最终与峰值结果', '']
    rows = []
    for r in data['results']:
        rows.append([f"{r['start_year']}—{r['start_year']+19}", r['status'], money(r['invested']),
                     money(r['final_value']), money(r['profit']), percent(r['xirr']), percent(r['max_nav_drawdown']),
                     money(r['max_account_value']), r['max_account_date'], money(r['principal_at_max_account']),
                     money(r['profit_at_max_account']), percent(r['simple_return_at_max_account']),
                     '—' if r['xirr_at_max_account'] is None else percent(r['xirr_at_max_account'])])
    lines.append(table(headers, rows))
lines += [
    '## 模型与核验', '',
    'QLD实际行情从2006-06-21起，TQQQ从2010-02-11起；此前分别模拟每日2倍、3倍收益，扣前一已知IRX国债利率的1倍、2倍融资成本及假设1%年费，按实际日历天数摊销。QQQ成立前使用NDX价格回报，缺少该阶段指数股息；其后用QQQ调整收盘价。基金成立后用各自实际调整收盘价，计入分配再投资与基金内部费用，不再额外扣费。当前两只基金都没有全程实际行情的完整20年窗口，所有已结束组均含成立前模拟。来源为纳斯达克官方NDX历史及Yahoo Finance NDX、IRX、QQQ、QLD、TQQQ行情。', '',
    'QLD沿用此前已核验结果。本次TQQQ以50位Decimal独立重建每日价格，逐日按各买入批次独立估值，核对40组本金与账户资产、全部峰值日期及最高累计收益率日期；最终和峰值XIRR另用终值复利方程检查，共80项。2011年以后14组还直接用原始TQQQ调整收盘价估值，绕过模拟归一化。与此前30组10年TQQQ普通定投在相同终点的结果逐组一致。', '',
    '最高资产对应的收益率不一定是最高累计收益率，后者和最终累计收益率另存完整CSV。最大净值回撤剔除外部入金影响，不是账户相对本金亏损。允许碎股，未计个人税费、佣金、点差及滑点；IRX及1%模拟年费是模型假设，滚动窗口重叠，历史盈利比例不能当作未来概率。', '',
    '[80组QLD与TQQQ完整CSV](../tqqq_20year_1985/80组_QLD与TQQQ最终与峰值.csv) · '
    '[TQQQ独立核验](../tqqq_20year_1985/verification.json) · '
    '[QLD独立核验](../qld_20year_1985/independent_audit.json) · '
    '[可复现计算脚本](../tqqq_20year_1985/study.py)', '',
    '![QLD与TQQQ最终资产和历史峰值对照](../tqqq_20year_1985/comparison.png)',
]
(DOCS/'34_QLD1985起40组20年普通定投.md').write_text('\n'.join(lines)+'\n')
index = DOCS/'README.md'
text = index.read_text()
text = text.replace('[34 QLD普通定投：20年完整汇总]', '[34 QLD与TQQQ普通定投：20年完整汇总]')
text = text.replace('40组最终与峰值结果合为一表；保留最高收益率CSV及独立核验',
                    'QLD、TQQQ各40组；最终资产、利润、XIRR、回撤及峰值利润；完整CSV与独立核验')
index.write_text(text)
print('Updated report 34 and README.')
