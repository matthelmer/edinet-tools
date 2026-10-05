"""
Segments parser — Operating Segments matrix extraction from Doc 120.

Per spec §5.1 (0.7.0): typed extraction of axis-tagged segment data
(OperatingSegmentsAxis members) into SegmentRow records.

Handles per-audit variance:
- Per-filer custom-element namespaces (jpcrp030000-asr_<EDINET>-000:* or
  jpcrp030000-asr_<EDINET>-000<MemberName>Member without colon)
- Total/ReconcilingItems naming variance allowlist
- NonConsolidatedMember axis nesting (Temairazu)
- '－' null coercion for ReconcilingItems empty cells
- TextBlock fallback flag (segments_text_only=True) for US-GAAP filers
  (Komatsu shape: no axis-discrete segment rows, data buried in TextBlock)
"""
import re
from dataclasses import dataclass, field


@dataclass
class SegmentRow:
    """A single segment's metrics for one period.

    segment_name: e.g., 'Asia-Pacific', 'Industrial Goods', 'Reconciling'.
        Sourced from the axis-member name in the context_id.
    axis_family: e.g., 'OperatingSegments', 'ReportableSegments'.
        Identifies which axis-family the row belongs to.
    metrics: dict mapping metric-name (e.g., 'Sales', 'OperatingProfit') to
        the raw string value from the CSV. Multiple metrics under one segment_name.
    period: e.g., 'CurrentYear', 'PriorYear'. Derived from base_context.
    consolidation_axis: 'Consolidated' / 'NonConsolidated' / None.
        None for filings that don't tag a consolidation axis (most large filers).
    """
    segment_name: str
    axis_family: str
    metrics: dict = field(default_factory=dict)
    period: str = ''
    consolidation_axis: str | None = None


# Pattern to strip the per-filer EDINET code prefix from custom member names.
# Handles: E07801-000HRTechnologyReportableSegment → HRTechnologyReportableSegment
# and:     E03606-000RetailAndDigitalBusinessGroup → RetailAndDigitalBusinessGroup
_EDINET_FILER_PREFIX_RE = re.compile(r'^E\d{5}-\d{3}')

# Base context period tokens (stripped from member extraction)
_BASE_CONTEXT_TOKENS = {
    'CurrentYearDuration', 'Prior1YearDuration', 'Prior2YearDuration',
    'Prior3YearDuration', 'Prior4YearDuration', 'CurrentYearInstant',
    'Prior1YearInstant', 'FilingDateInstant',
}

# Consolidation member names
_CONSOLIDATION_MEMBERS = {'NonConsolidated', 'Consolidated'}

# Segment-axis member-name suffixes — the high-confidence anchors. A member
# whose cleaned name ends with one of these is unambiguously an operating /
# reportable segment, regardless of accounting standard or industry. Validated
# against 24 diverse filers (insurers, banks, trading houses, IFRS, J-GAAP):
# these are useful anchors, but some filers use other member names.
_SEGMENT_NAME_SUFFIXES = (
    'ReportableSegments', 'ReportableSegment',
    'OperatingSegments', 'OperatingSegment',
    'BusinessGroup',   # MUFG-style bank ("RetailAndDigitalBusinessGroup")
)

# Reconciling / Total / Corporate member names that are aggregation rows of the
# segment table (NOT individual segments). These are admitted ONLY when they
# co-occur with a segment-exclusive element (see parse_segments_from_csv), which
# anchors them to the actual segment table and keeps same-named members from
# other axes (a geographic "Other", an equity "Total") out.
_AGGREGATION_MEMBERS = {
    'ReconcilingItems',
    'ReportableSegments',
    'TotalOfReportableSegmentsAndOthers',
    'OperatingSegmentsNotIncludedInReportableSegmentsAndOtherRevenueGeneratingBusinessActivities',
    'TotalOfCustomerBusinessUnit',
    'Total',
    'Other',
    'Adjustments',
    'UnallocatedAmountsAndElimination',
    'CorporateExpensesAndElimination',
    'CorporateShared',
}

# The subset of _AGGREGATION_MEMBERS whose NAME is unambiguously a segment-table
# reconciliation row. These are safe to SEED the no-anchor path from (their element
# profile defines the segment table). The generic members above (`Total`, `Other`,
# `Adjustments`, `CorporateShared`, ...) are deliberately excluded — they also appear
# in equity / geographic / employee tables, so seeding from them would pull in noise.
_SEGMENT_AGGREGATION_SEEDS = {
    'ReconcilingItems',
    'ReportableSegments',
    'TotalOfReportableSegmentsAndOthers',
    'OperatingSegmentsNotIncludedInReportableSegmentsAndOtherRevenueGeneratingBusinessActivities',
    'TotalOfCustomerBusinessUnit',
}

# TextBlock element names that indicate US-GAAP filings when present with substantive content
_USGAAP_TEXTBLOCK_INDICATORS = {
    'NotesToConsolidatedFinancialStatementsUSGAAPTextBlock',
}

# Minimum character length for a TextBlock to be considered "substantive"
_TEXTBLOCK_SUBSTANTIVE_LEN = 100

# Keywords indicating US-GAAP standard in a TextBlock value
_USGAAP_KEYWORDS = ('米国会計基準', 'U.S. GAAP', 'US GAAP', 'USGAAP')


def _clean_member_name(member_name: str) -> str:
    """Strip per-filer EDINET code prefix from custom member names.

    Examples:
        'E07801-000HRTechnologyReportableSegment' -> 'HRTechnologyReportableSegment'
        'E03606-000RetailAndDigitalBusinessGroup' -> 'RetailAndDigitalBusinessGroup'
        'AirConditioningAndRefrigerationEquipmentReportableSegments' -> unchanged
    """
    return _EDINET_FILER_PREFIX_RE.sub('', member_name)


def _parse_context_members(context_id: str) -> tuple[str, list[str]]:
    """Parse context_id into (period, [member_names]).

    Handles the two EDINET context_id shapes for Member tokens:
    1. Standard: 'CurrentYearDuration_jpcrp_cor:FooMember' — colon present
    2. Custom-filer: 'CurrentYearDuration_jpcrp030000-asr_E07801-000FooMember' — no colon
       (filer namespace and member name are concatenated into one token after the last '_')

    Returns:
        (period_token, [cleaned_member_names_without_Member_suffix])
    """
    if not context_id:
        return '', []

    # Split on underscores, reassemble namespace-prefix tokens
    # A logical token is: plain parts (no colon) followed by the colon-containing part.
    # Then the local-name portion (after colon) is the member name.
    raw_parts = context_id.split('_')
    tokens: list[str] = []
    pending: list[str] = []

    for part in raw_parts:
        if ':' in part:
            pending.append(part)
            tokens.append('_'.join(pending))
            pending = []
        else:
            if pending:
                tokens.append('_'.join(pending))
                pending = []
            pending.append(part)

    if pending:
        tokens.append('_'.join(pending))

    period = ''
    members: list[str] = []

    for token in tokens:
        # Get local name (after colon if present)
        local_name = token.split(':')[-1] if ':' in token else token

        if local_name in _BASE_CONTEXT_TOKENS:
            period = local_name
        elif local_name.endswith('Member') and len(local_name) > len('Member'):
            raw_member = local_name[:-len('Member')]
            cleaned = _clean_member_name(raw_member)
            members.append(cleaned)
        # else: ignore intermediate namespace-only tokens

    return period, members


def _is_usgaap_textblock_filer(csv_files: list) -> bool:
    """Detect US-GAAP filers whose segment data is buried in a TextBlock.

    Heuristic:
    1. A known US-GAAP TextBlock indicator element is present with substantive content, OR
    2. Any TextBlock mentions US-GAAP keywords (catches Komatsu's BusinessResultsOfGroupTextBlock
       which contains '米国会計基準' in the value).
    """
    for csv_file in csv_files or []:
        for row in csv_file.get('data', []) or []:
            elem_id = row.get('要素ID', '') or ''
            value = row.get('値', '') or ''

            if len(value) < _TEXTBLOCK_SUBSTANTIVE_LEN:
                continue

            local_name = elem_id.split(':')[-1] if ':' in elem_id else elem_id

            # Known US-GAAP TextBlock indicator
            if local_name in _USGAAP_TEXTBLOCK_INDICATORS:
                return True

            # Any TextBlock containing US-GAAP keywords
            if local_name.endswith('TextBlock'):
                if any(kw in value for kw in _USGAAP_KEYWORDS):
                    return True

    return False


def parse_segments_from_csv(csv_files: list) -> tuple:
    """Parse Operating Segments matrix from Doc 120 CSV files.

    Returns:
        (segments: list[SegmentRow], segments_text_only: bool, extraction_incomplete: bool)

    A securities report tags MANY dimensional tables with `Member`-context_ids
    that are NOT operating segments — major-shareholders (`No1MajorShareholders`),
    directors (`SatoruKomiya`), equity components (`RetainedEarnings`), generic
    enumeration rows (`Row1`). Selecting "any non-consolidation member" sweeps
    all of these in. So we identify the operating-segment members via an
    **anchored union** (a heuristic over CSV context names, not axis definitions):

      1. **Anchors** — members whose cleaned name ends in a segment-axis suffix
         (`_SEGMENT_NAME_SUFFIXES`). Unambiguous individual segments.
      2. **Segment-exclusive elements** — element local-names carried by anchor
         members but by NO non-anchor, non-aggregation member in this filing.
      3. **Aggregation rows** — `_AGGREGATION_MEMBERS` admitted only when they
         carry a segment-exclusive element (anchors them to the segment table).

    The segment set is anchors ∪ qualifying-aggregation. Unknown members sharing
    its metrics raise extraction_incomplete instead of being guessed as segments.
    The flag is conservative: a different axis can share the same metrics. A False
    flag does not certify completeness, especially without recognizable anchors.

    Returns:
        (segments: list[SegmentRow], segments_text_only: bool, extraction_incomplete: bool)

    `segments_text_only=True` is returned for US-GAAP / Toyota-shape filers whose
    segment data lives in a TextBlock and yields no axis-discrete rows.
    """
    from .extraction import coerce_numeric_value

    # Pass 1: collect every dimensional fact, indexed by member, tracking which
    # element local-names each member carries (for the segment-exclusive test).
    facts: list[tuple] = []                 # (segment_name, consolidation_axis, period, local, value)
    member_elems: dict[str, set] = {}       # segment_name -> set(element local-names)
    anchors: set = set()

    for csv_file in csv_files or []:
        for row in csv_file.get('data', []) or []:
            context_id = row.get('コンテキストID', '') or ''
            if 'Member' not in context_id:
                continue  # Skip non-dimensional rows

            period, members = _parse_context_members(context_id)
            if not members:
                continue

            consolidation_axis: str | None = None
            segment_members: list[str] = []
            for member in members:
                if member in _CONSOLIDATION_MEMBERS:
                    consolidation_axis = member
                else:
                    segment_members.append(member)
            if not segment_members:
                continue  # Only a consolidation member, no segment name

            segment_name = segment_members[-1]

            elem_id = row.get('要素ID', '') or ''
            local_name = elem_id.split(':')[-1] if ':' in elem_id else elem_id
            if not local_name or local_name == '要素ID' or local_name.endswith('TextBlock'):
                # TextBlock members carry directors/footnotes; not segment metrics.
                continue

            value = coerce_numeric_value(row.get('値', '') or '')
            facts.append((segment_name, consolidation_axis, period, local_name, value))
            member_elems.setdefault(segment_name, set()).add(local_name)
            if any(segment_name.endswith(suffix) for suffix in _SEGMENT_NAME_SUFFIXES):
                anchors.add(segment_name)

    # No-anchor seeding: filers that name segments by industry/sector
    # (ElectronicsIndustry, GeneralIndustry) have no suffix anchor, so `anchors` is
    # empty and the anchored union below would yield a silent []. Seed anchors from
    # the segment-specific aggregation rows present (_SEGMENT_AGGREGATION_SEEDS):
    # their element profile defines the segment table, and the sibling members that
    # share it are the real segments. Require >= 2 such siblings — a genuine segment
    # table has >= 2 reportable segments; a lone member sharing the reconciliation
    # profile (e.g. JAL's DividendsReceived) is a reconciliation artifact, not a
    # segment, and must not be admitted.
    if not anchors:
        seed_aggs = {m for m in member_elems if m in _SEGMENT_AGGREGATION_SEEDS}
        if seed_aggs:
            seed_elems: set = set().union(*(member_elems[m] for m in seed_aggs))
            candidates = {
                m for m in member_elems
                if m not in _AGGREGATION_MEMBERS and (member_elems[m] & seed_elems)
            }
            if len(candidates) >= 2:
                anchors = candidates

    # Pass 2: anchored-union membership.
    anchor_elems: set = set().union(*(member_elems[m] for m in anchors)) if anchors else set()
    non_segment = [m for m in member_elems if m not in anchors and m not in _AGGREGATION_MEMBERS]
    other_elems: set = set().union(*(member_elems[m] for m in non_segment)) if non_segment else set()
    segment_exclusive = anchor_elems - other_elems
    qualifying_aggregation = {
        m for m in member_elems
        if m in _AGGREGATION_MEMBERS and (member_elems[m] & segment_exclusive)
    }
    segment_members_set = anchors | qualifying_aggregation

    # Build one SegmentRow per (segment_name, consolidation_axis, period).
    segments_by_key: dict[tuple, SegmentRow] = {}
    for segment_name, consolidation_axis, period, local_name, value in facts:
        if segment_name not in segment_members_set:
            continue
        axis_family = 'TotalReconciling' if segment_name in _AGGREGATION_MEMBERS else 'OperatingSegments'
        key = (segment_name, consolidation_axis, period)
        if key not in segments_by_key:
            segments_by_key[key] = SegmentRow(
                segment_name=segment_name,
                axis_family=axis_family,
                metrics={},
                period=period,
                consolidation_axis=consolidation_axis,
            )
        if value is not None:
            # Store metric using local element name (preserves IFRS/BNK suffixes;
            # canonical mapping is the caller's responsibility).
            segments_by_key[key].metrics[local_name] = value

    segments = list(segments_by_key.values())

    # US-GAAP / Toyota-shape fallback: no axis-discrete segments extracted, and
    # the filing is a US-GAAP TextBlock filer → flag for the iXBRL HTML path.
    if not segments and _is_usgaap_textblock_filer(csv_files):
        return [], True, False

    # CSV context names omit axis definitions. An unfamiliar member carrying the
    # same metrics as the identified segment table may belong to that table, or
    # to another dimensional table. Do not silently call extraction complete and
    # do not guess the member's axis. The caller can inspect the source context.
    # In particular a standard total is not evidence that individual segments
    # were found (single-segment filings can tag a custom name as well).
    seed_elems = set().union(*(
        member_elems[m] for m in member_elems if m in _SEGMENT_AGGREGATION_SEEDS
    ))
    table_elems = anchor_elems | seed_elems
    unresolved_members = {
        m for m in member_elems
        if m not in segment_members_set and m not in _AGGREGATION_MEMBERS
        and member_elems[m] & table_elems
    }
    extraction_incomplete = bool(unresolved_members) or (
        not (anchors - _AGGREGATION_MEMBERS) and bool(seed_elems)
    )
    return segments, False, extraction_incomplete
