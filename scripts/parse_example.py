"""Parse a specific EDINET filing and display structured results.

Usage:
    python scripts/parse_example.py S100XPGA       # Auto-detects doc type
    python scripts/parse_example.py S100XVAY 080   # Override doc type
"""
import re
import sys
from dotenv import load_dotenv

load_dotenv()

from types import SimpleNamespace
from edinet_tools.api import fetch_document, fetch_documents_list
from edinet_tools.parsers import parse
from edinet_tools import doc_type


def lookup_doc_type(doc_id):
    from datetime import date, timedelta
    import time
    d = date.today()
    end = d - timedelta(days=90)
    while d >= end:
        try:
            result = fetch_documents_list(d)
            for doc in result.get('results', []):
                if doc.get('docID') == doc_id:
                    return doc['docTypeCode']
        except Exception:
            pass
        d -= timedelta(days=1)
        time.sleep(0.3)
    return None


def trunc(text, length=62):
    if not text:
        return ''
    text = str(text).replace('\n', ' ').replace('\r', '').strip()
    text = re.sub(r'\s+', ' ', text)
    if len(text) <= length:
        return text
    return text[:length - 1] + '…'


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_example.py <doc_id> [doc_type_code]")
        sys.exit(1)

    doc_id = sys.argv[1]
    doc_type_code = sys.argv[2] if len(sys.argv) > 2 else None

    if doc_type_code is None:
        print(f"Looking up {doc_id}...", end=' ', flush=True)
        doc_type_code = lookup_doc_type(doc_id)
        if doc_type_code is None:
            print("not found.")
            sys.exit(1)
        print(f"doc type {doc_type_code}")

    dt = doc_type(doc_type_code)
    doc = SimpleNamespace(
        doc_id=doc_id,
        doc_type_code=doc_type_code,
        fetch=lambda: fetch_document(doc_id),
    )
    report = parse(doc)

    # Company identity
    name = None
    for f in ['company_name', 'target_company_name',
              'acquirer_name', 'filer_name']:
        val = getattr(report, f, None)
        if val:
            name = val
            break
    name_en = (getattr(report, 'filer_name_en', None)
               or getattr(report, 'company_name_en', None))
    edinet_code = getattr(report, 'filer_edinet_code', None)
    filing_date = getattr(report, 'filing_date', None)
    is_amendment = getattr(report, 'is_amendment', False)

    print()
    print(f"  edinet-tools v0.5.0")
    print()
    if name:
        print(f"  {name}")
    if name_en:
        print(f"  {name_en}")
    print()
    if dt:
        print(f"  Filing      {dt.name_en}")
        print(f"              {dt.name_jp}")
    if filing_date:
        print(f"  Date        {filing_date}")
    if edinet_code:
        print(f"  EDINET      {edinet_code}")

    # Content fields with clear labels
    skip = {
        'doc_id', 'doc_type_code', 'source_files', 'raw_fields',
        'unmapped_fields', 'text_blocks', 'filer_name', 'filer_name_en',
        'filer_edinet_code', 'security_code', 'company_name',
        'company_name_en', 'filing_date', 'is_amendment',
        'document_title', 'target_company_name',
        'target_company_address',
    }

    # Readable label overrides
    labels = {
        'acquirer_info_text': 'Acquirer',
        'opinion_text': 'Opinion',
        'share_classes_text': 'Shares',
        'officer_holdings_text': 'Officers',
        'extension_request_text': 'Extension',
        'inquiries_text': 'Inquiries',
        'profit_provision_text': 'Profit Prov.',
        'defense_policy_text': 'Defense',
        'result_text': 'Result',
        'period_text': 'Period',
        'announcement_text': 'Announced',
        'shares_acquired_text': 'Acquired',
        'evaluation_result_text': 'Evaluation',
        'scope_and_procedures_text': 'Scope',
        'framework_text': 'Framework',
        'shelf_registration_number': 'Shelf Reg #',
        'planned_period': 'Period',
        'security_types': 'Securities',
        'representative': 'Representative',
        'cfo': 'CFO',
        'remaining_balance': 'Remaining',
        'supplement_number': 'Supplement #',
        'holding_ratio_after': 'Holding %',
        'purchase_ratio': 'Purchase %',
        'ticker': 'Ticker',
    }

    print()
    shown = False
    for field in report.fields():
        if field in skip:
            continue
        val = getattr(report, field)
        if val is None or not str(val).strip():
            continue
        val_str = str(val).replace('\n', ' ').strip()
        if val_str in ('該当事項はありません。', '該当事項はありません'):
            continue

        label = labels.get(field,
                          field.replace('_text', '').replace('_', ' ').title())
        print(f"  {label:<14}{trunc(val_str)}")
        shown = True

    # Text blocks: show count and a few highlights
    if report.text_blocks:
        # Prioritized block labels for display
        priority_blocks = [
            ('OpinionAndBasisAndReasonOfOpinionRegardingSaidTenderOfferTextBlock', 'Board Opinion'),
            ('NameAndResidentialAddressOrLocationOfTenderOfferorTextBlock', 'Acquirer Details'),
            ('NumberOfShareCertificatesEtcAndNumberOfVotingRightsOwnedByOfficersTextBlock', 'Officer Holdings'),
            ('NotesCoverPageTextBlock', 'Filing Notes'),
            ('SuccessOrFailureOfTenderOfferTextBlock', 'TOB Outcome'),
            ('ResultOfEvaluationTextBlock', 'J-SOX Evaluation'),
            ('ScopeDateAndProceduresForEvaluationTextBlock', 'Evaluation Scope'),
            ('BasicFrameworkOfInternalControlRelatedToFinancialReportingTextBlock', 'Control Framework'),
        ]
        # Collect typed field values to avoid showing duplicates
        typed_vals = set()
        for f in report.fields():
            v = getattr(report, f)
            if v and isinstance(v, str):
                typed_vals.add(v.replace('\n', ' ').strip()[:50])

        highlights = []
        for key, label in priority_blocks:
            if key in report.text_blocks and len(highlights) < 3:
                val = str(report.text_blocks[key]).replace('\n', ' ').strip()
                if not val or val in ('該当事項はありません。', '該当事項はありません'):
                    continue
                # Skip if this duplicates a typed field
                if val[:50] in typed_vals:
                    continue
                highlights.append((label, val))

        print()
        print(f"  + {len(report.text_blocks)} text blocks available")

    # Footer
    n_fields = len([
        f for f in report.fields()
        if getattr(report, f) is not None
        and f not in ('doc_id', 'doc_type_code', 'source_files',
                      'raw_fields', 'unmapped_fields', 'text_blocks')
    ])
    print()
    print(f"  {type(report).__name__} · {n_fields} fields · {len(report.text_blocks)} text blocks")
    print()


if __name__ == "__main__":
    main()
