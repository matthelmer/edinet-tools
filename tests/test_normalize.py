"""Tests for normalize_for_matching."""

import pytest

from edinet_tools.normalize import normalize_for_matching


def test_empty_string():
    assert normalize_for_matching("") == ""


def test_none_input():
    assert normalize_for_matching(None) == ""


def test_lowercase():
    assert normalize_for_matching("TOYOTA") == "toyota"


def test_full_width_latin_folded():
    assert normalize_for_matching("ＵＦＪ") == "ufj"


def test_full_width_digits_folded():
    assert normalize_for_matching("１２３") == "123"


def test_ideographic_space_stripped():
    # full-width space U+3000 between surname and given name
    assert normalize_for_matching("稲葉　進") == "稲葉進"


def test_ascii_space_stripped():
    assert normalize_for_matching("Toyota Motor") == "toyotamotor"


def test_mixed_whitespace_stripped():
    assert normalize_for_matching("日本　生命 保険") == "日本生命保険"


def test_kabushiki_kaisha_gaiji_folded():
    # ㈱ (U+3231) -> NFKC -> (株) -> 株式会社
    assert normalize_for_matching("日立㈱") == "日立株式会社"


def test_kabushiki_kaisha_paren_form_folded():
    # already-(株) form
    assert normalize_for_matching("日立(株)") == "日立株式会社"


def test_yugen_kaisha_gaiji_folded():
    # ㈲ -> (有) -> 有限会社
    assert normalize_for_matching("㈲エスアンドアイ") == "有限会社エスアンドアイ"


def test_full_width_parens_folded():
    # NFKC folds （ to (
    assert normalize_for_matching("みずほ銀行（信託口）") == "みずほ銀行(信託口)"


def test_smbc_variants_collapse():
    # Real-world variance from corpjapan prod data:
    # catalog stores ＳＭＢＣ (full-width); extraction yields SMBC (half-width).
    # Both must normalize to the same key.
    assert normalize_for_matching("ＳＭＢＣ日興証券株式会社") == \
           normalize_for_matching("SMBC日興証券株式会社")


def test_idempotence():
    fixtures = [
        "Toyota Motor Corporation",
        "株式会社三菱ＵＦＪ銀行",
        "日立㈱",
        "日本　生命",
        "",
    ]
    for s in fixtures:
        once = normalize_for_matching(s)
        twice = normalize_for_matching(once)
        assert once == twice, f"Not idempotent: {s!r} -> {once!r} -> {twice!r}"
