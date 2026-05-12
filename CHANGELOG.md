# Changelog

## v0.6.0 — 2026-05-12

### Added

- `normalize_for_matching(s)` — public name-matching helper. NFKC normalization, `(株)` → `株式会社` / `(有)` → `有限会社` rewrites, katakana / Latin middle-dot stripping (`・` U+30FB, `·` U+00B7), whitespace collapse (runs folded to a single ASCII space; whitespace preserved between words so `Toyota` doesn't match `Toyo Tanso`), lowercase. Idempotent.
- `entity_by_corporate_number(num)` — O(1) lookup by 13-digit 法人番号 (Japan Corporate Number).
- `Entity.name_phonetic` and `Entity.corporate_number` now populated for classifier-path entities. Sourced from the `Submitter Name (phonetic)` and `Submitter's Japan Corporate Number` columns of `EdinetcodeDlInfo.csv`.
- GitHub Actions CI workflow (`.github/workflows/test.yml`) — multi-Python test matrix on push and pull_request.

### Changed

- `search_entities()` — O(1) exact-match via reverse index; substring-fallback path uses pre-normalized forms on both sides. Visually-identical strings with different Unicode encodings (full-width vs half-width Latin, `（` vs `(`, `㈱` vs `株式会社`, middle-dot variants like `モルガン・スタンレー` vs `モルガンスタンレー`) now resolve to the same entity.
- `search_entities()` bidirectional whitespace handling — when a query like `山田太郎` doesn't exact-match, falls back to the whitespace-collapsed catalog form, recovering names where the catalog stores them with internal spaces (`山田 太郎`). Particularly relevant for Japanese individual-filer names.
- `entity_by_ticker()` — O(N) scan replaced with O(1) reverse-index lookup. Now also handles alphanumeric tickers (`192A`, `263A`, `275A`-class).
- `EntityClassifier` listed-flag parsing — the FSA catalog's 上場区分 column has used both `'Listed company'` (English) and `'上場'` (Japanese) at different times; the classifier now accepts either form so bundled snapshots and freshly-downloaded catalogs both work.

### Not changed

- Public API signatures and return shapes — drop-in upgrade for existing callers.

### Known limitations (documented as xfail tests)

- Punctuation / symbol / abbreviation variance (`Co Ltd` ↔ `Co., Ltd.`, `&` ↔ `and`, `Inc` ↔ `Incorporated`).
- Queries with trailing parentheticals longer than the catalog name (e.g. `(信託口)` trust-account suffixes) — downstream consumers needing this should pre-strip before calling `search_entities`.
- Trust banks (`日本マスタートラスト信託銀行` etc.) are not in the EDINET catalog at all — they exist in the 法人番号 corporate registry only. v0.7.0+ may add a `法人番号公表サイト` ingestion layer to cover them.

## v0.5.0

Typed parsers for all 42 EDINET document types.

## v0.4.3

Add `fetch_and_parse` API. Expose `industry` field on `Entity`.
