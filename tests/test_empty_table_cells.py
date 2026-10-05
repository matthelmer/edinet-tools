"""Preserve actual empty columns; do not expand spans or nested tables."""
from pathlib import Path
import pytest
from edinet_tools.parsers._xbrl_model import html_to_text
from edinet_tools.parsers import parse_xbrl

@pytest.mark.parametrize('empty', ['<td/>', '<td />', '<td class="blank"/>', '<th/>', '<TH />'])
def test_self_closed_cell_keeps_middle_column(empty):
    assert html_to_text('<table><tr><td>a</td>'+empty+'<td>b</td></tr></table>') == 'a\t\tb'

@pytest.mark.parametrize('cells, expected', [
    ('<td/><td>x</td>', '\tx'),
    ('<td>x</td><td/>', 'x\t'),
    ('<td/><td/><td>x</td><td/>', '\t\tx\t'),
])
def test_empty_cells_keep_leading_trailing_and_repeated_positions(cells, expected):
    assert html_to_text('<table><tr>'+cells+'</tr></table>') == expected


def test_nested_self_closed_cells_keep_existing_outer_cell_contract():
    closed = '<table><tr><td>a<table><tr><td>x</td><td/><td>y</td></tr></table>z</td><td>b</td></tr></table>'
    explicit = closed.replace('<td/>', '<td></td>')
    assert html_to_text(closed) == html_to_text(explicit) == 'a x y z\tb'


def test_original_borrowing_row_has_six_cells_on_both_sources():
    package = (Path(__file__).parent / 'fixtures/xbrl/S100YXGK.zip').read_bytes()
    expected = ['福田光秀', '個人', '', '東京都中央区', '2', '22,492,209,100']
    for source in ('xbrl', 'instance'):
        report = parse_xbrl(package, '350', doc_id='S100YXGK', source=source)
        text = report.joint_holders[0].text_blocks['BreakdownOfBorrowingsTextBlock']
        rows = [line.split('\t') for line in text.splitlines()]
        assert expected in rows, (source, rows)
