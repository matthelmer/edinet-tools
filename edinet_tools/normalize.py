"""Normalization helpers for entity-name matching."""

import unicodedata

__all__ = ['normalize_for_matching']


def normalize_for_matching(s):
    """Normalize a Japanese or English entity-name string for matching.

    Applies, in order:
      1. NFKC Unicode normalization (folds full-width <-> half-width Latin,
         folds ideographic space U+3000 to ASCII space, folds gaiji like
         ㈱ U+3231 to '(株)', etc.).
      2. Common kabushiki-gaisha rewrites: '(株)' -> '株式会社',
         '(有)' -> '有限会社'.
      3. Collapse runs of whitespace into a single ASCII space; strip
         leading and trailing whitespace.
      4. Lowercase.

    Whitespace is preserved (not stripped) because in English names it
    separates words and is load-bearing for substring matching — e.g.
    stripping would let a query 'Toyota' match 'Toyo Tanso' via the
    collapsed form 'toyotanso'. In Japanese, NFKC already folds the
    ideographic space U+3000 to ASCII space, so '稲葉　進' and '稲葉 進'
    collapse to the same key. The rare no-space form '稲葉進' does NOT
    collapse to the spaced form — Layer 2 callers needing that handle
    it via additional pre-search stripping.

    Idempotent: normalize_for_matching(normalize_for_matching(x)) ==
    normalize_for_matching(x).

    Returns the empty string for None or empty input.

    Args:
        s: Input string, or None.

    Returns:
        Normalized string suitable for use as a dictionary key in
        entity-name lookups.
    """
    if not s:
        return ""
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('(株)', '株式会社')
    s = s.replace('(有)', '有限会社')
    # Strip katakana middle dot (・ U+30FB) and Latin middle dot (· U+00B7).
    # In Japanese company names these are transliteration separators with
    # inconsistent presence across data sources — 'モルガン・スタンレー' and
    # 'モルガンスタンレー' refer to the same entity.
    s = s.replace('・', '').replace('·', '')
    s = ' '.join(s.split())
    return s.lower()
