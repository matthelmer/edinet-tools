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
      3. Strip all internal whitespace.
      4. Lowercase.

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
    s = ''.join(s.split())
    return s.lower()
