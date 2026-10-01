"""Quarterly parser tier-table migration pins (0.8.0 stage-5 Task 7).

Behavior-preserving migration (0.8.0): no new gate, no new fields. The
per-standard gate arrived in 0.9.0 (test_standard_selection_policy_interim.py);
these tests pin the semantics the migration must not change — especially the eps coercion swap (the local marker tuple
+ bare except became coerce_numeric_value + guarded Decimal, equivalent
only because the shared null-marker set gained '―'/'—' first).
"""
from decimal import Decimal

from edinet_tools.parsers.quarterly import parse_quarterly_report

CYTD = 'CurrentYTDDuration'
CQI = 'CurrentQuarterInstant'
FDI = 'FilingDateInstant'


def _cf(*rows):
    return [{
        'filename': 'test.csv',
        'data': [
            {'要素ID': e, '項目名': '', 'コンテキストID': c, '相対年度': '',
             '連結・個別': '', '期間・時点': '', 'ユニットID': 'JPY',
             '単位': '', '値': v}
            for e, c, v in rows
        ],
    }]


def _parse(*rows, consolidated='true'):
    dei = [
        ('jpdei_cor:EDINETCodeDEI', FDI, 'E00000'),
        ('jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI',
         FDI, consolidated),
    ]
    return parse_quarterly_report(csv_files=_cf(*dei, *rows),
                                  doc_id='TEST', doc_type_code='140')


class TestEpsCoercionSwap:
    def test_real_eps_parses(self):
        r = _parse(('jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
                    CYTD, '123.45'))
        assert r.eps_basic_ytd == Decimal('123.45')

    def test_all_four_legacy_markers_are_none(self):
        for marker in ('－', '―', '-', '—'):
            r = _parse(('jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
                        CYTD, marker))
            assert r.eps_basic_ytd is None, repr(marker)

    def test_junk_string_is_silent_none_not_crash(self):
        """The legacy bare except swallowed non-numeric strings; the
        migrated guarded Decimal must keep that contract."""
        r = _parse(('jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
                    CYTD, '該当なし'))
        assert r.eps_basic_ytd is None


class TestTierTablesPreserveWaterfalls:
    def test_jgaap_primary_wins(self):
        r = _parse(('jppfs_cor:NetSales', CYTD, '1000'),
                   ('jpigp_cor:RevenueIFRS', CYTD, '2000'))
        assert r.revenue_ytd == 1000

    def test_ifrs_fallback_fires_when_primary_absent(self):
        r = _parse(('jpigp_cor:RevenueIFRS', CYTD, '2000'))
        assert r.revenue_ytd == 2000

    def test_ifrs_fallback_fires_when_primary_is_marker(self):
        r = _parse(('jppfs_cor:NetSales', CYTD, '－'),
                   ('jpigp_cor:RevenueIFRS', CYTD, '2000'))
        assert r.revenue_ytd == 2000

    def test_ifrs_standard_never_reads_jgaap_operating_income(self):
        """The quarterly gate (0.9.0): an IFRS filing that tags only the
        J-GAAP operating-income element gets None, not the J-GAAP figure.
        0.8.0 pinned the opposite so this change would arrive as its own
        predicted change; this is that change."""
        rows = [('jpdei_cor:AccountingStandardsDEI', FDI, 'IFRS'),
                ('jppfs_cor:OperatingIncome', CYTD, '777')]
        r = _parse(*rows)
        assert r.operating_profit_ytd is None

    def test_undeclared_standard_still_reads_jgaap_operating_income(self):
        r = _parse(('jppfs_cor:OperatingIncome', CYTD, '777'))
        assert r.operating_profit_ytd == 777

    def test_balance_sheet_and_prior_periods(self):
        r = _parse(('jppfs_cor:Assets', CQI, '5000'),
                   ('jppfs_cor:NetAssets', CQI, '3000'),
                   ('jppfs_cor:NetSales', 'Prior1YTDDuration', '900'))
        assert r.total_assets == 5000
        assert r.net_assets == 3000
        assert r.prior_revenue_ytd == 900

    def test_consolidated_never_borrows_parent(self):
        r = _parse(('jppfs_cor:NetSales', f'{CYTD}_NonConsolidatedMember',
                    '1000'))
        assert r.revenue_ytd is None

    def test_nonconsolidated_prefers_member_context(self):
        r = _parse(('jppfs_cor:NetSales', f'{CYTD}_NonConsolidatedMember', '1000'),
                   ('jppfs_cor:NetSales', CYTD, '9999'),
                   consolidated='false')
        assert r.revenue_ytd == 1000
