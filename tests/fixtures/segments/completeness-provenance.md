# Segment completeness fixtures

The four `S100Z461`, `S100Z468`, `S100Z46T`, and `S100Z4HA` `.json.gz` fixtures
contain original EDINET CSV rows with a Member context, excluding TextBlock rows.
They retain non-segment axes as negative controls; amounts and context names are
unchanged. Input: saved `2026-10-02c` corpus, reviewed 2026-10-05. Each JSON includes
SHA-256 hashes of its original filing ZIP and saved compressed CSV plus context
witnesses derived independently from original instance definitions on
`jpcrp_cor:OperatingSegmentsAxis`. Tests specify the missing member's current-year
external revenue directly, rather than snapshotting parser output.

The fix warns when an unknown member shares the identified segment table's
metrics. It does not infer that member's axis from numeric values, manufacture a
segment, or assert that a False warning proves completeness. Unknown-only tables
with no recognizable segment anchor remain a limitation of flattened CSV input.

T7 fixtures `S100Z488`, `S100Z404` use the same saved corpus and `S100YG5L`
uses Fable's saved original ORIX package/CSV. Selection and hash rules are identical.
Independent original-source checks:

- S100Z488 instance uses standard `jpcrp_cor:OtherReportableSegmentsMember` on
  OperatingSegmentsAxis. The definition/presentation linkbases put it beneath
  `TotalOfReportableSegmentsAndOthersMember`. Its 8,193,000,000 external revenue
  is an other/reconciling row, not an individual reportable segment.
- S100Z404 definition/presentation linkbases nest KantoAreaGreenBusiness,
  KansaiAreaGreenBusiness, and OverseasGreenBusiness under GreenBusiness.
  Its subtotal and children are all returned because flattened CSV lacks this
  hierarchy; summing every row double counts. No hierarchy inference was added.
- S100YG5L tags employee counts on the segment axis. Returned rows contain only
  NumberOfEmployees. Nonempty rows and segments_text_only=False do not assert
  that revenue/profit metrics exist. Callers must inspect metric keys.
