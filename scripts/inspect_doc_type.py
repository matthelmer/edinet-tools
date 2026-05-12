"""Download sample filings from EDINET API and inspect their XBRL CSV elements.
Usage: python scripts/inspect_doc_type.py --doc-type 130 --samples 5
       python scripts/inspect_doc_type.py --doc-type 120,130 --samples 5  # compare two types
"""
import argparse
import os
import time
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from edinet_tools.api import fetch_documents_list, fetch_document
from edinet_tools.parsers.extraction import extract_csv_from_zip


def find_samples(doc_type_code: str, num_samples: int = 5, days_back: int = 365) -> list[dict]:
    """Find sample filings of a given doc type from the EDINET API."""
    samples = []
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    d = end_date

    while d >= start_date and len(samples) < num_samples:
        try:
            result = fetch_documents_list(d)
            docs = result.get('results', [])
            for doc in docs:
                if doc.get('docTypeCode') == doc_type_code and doc.get('csvFlag') == '1':
                    samples.append(doc)
                    print(f"  Found: {doc['docID']} - {doc.get('filerName', '?')} ({doc.get('docDescription', '?')})")
                    if len(samples) >= num_samples:
                        break
        except Exception as e:
            print(f"  Error on {d}: {e}")
        d -= timedelta(days=1)
        time.sleep(0.5)

    return samples


def inspect_elements(doc_id: str) -> dict:
    """Download a filing and inspect its XBRL elements."""
    zip_bytes = fetch_document(doc_id)
    csv_files = extract_csv_from_zip(zip_bytes)

    elements = {}
    for csv_file in csv_files:
        for row in csv_file.get('data', []):
            # CSV uses Japanese column headers
            elem_id = row.get('\u8981\u7d20ID', '')  # 要素ID
            value = row.get('\u5024', '')  # 値
            context = row.get('\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8ID', '')  # コンテキストID
            if elem_id and value:
                if elem_id not in elements:
                    elements[elem_id] = []
                elements[elem_id].append({'value': str(value)[:100], 'context': context})

    return elements


def compare_element_sets(samples_by_type: dict[str, list[dict]]):
    """Compare which XBRL elements appear across doc types."""
    all_elements = {}
    for doc_type, element_lists in samples_by_type.items():
        combined = set()
        for elements in element_lists:
            combined.update(elements.keys())
        all_elements[doc_type] = combined

    types = list(all_elements.keys())
    if len(types) == 2:
        a, b = types
        shared = all_elements[a] & all_elements[b]
        only_a = all_elements[a] - all_elements[b]
        only_b = all_elements[b] - all_elements[a]
        print(f"\n{'='*60}")
        print(f"COMPARISON: doc type {a} vs {b}")
        print(f"{'='*60}")
        print(f"Shared elements: {len(shared)}")
        print(f"Only in {a}: {len(only_a)}")
        if only_a:
            for e in sorted(only_a)[:20]:
                print(f"  {e}")
        print(f"Only in {b}: {len(only_b)}")
        if only_b:
            for e in sorted(only_b)[:20]:
                print(f"  {e}")
        overlap_pct = len(shared) / max(len(all_elements[a]), len(all_elements[b]), 1) * 100
        print(f"\nOverlap: {overlap_pct:.0f}% — {'SAFE to reuse parser' if overlap_pct > 80 else 'MAY need separate parser'}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--doc-type', required=True, help='Doc type code(s), comma-separated')
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--days-back', type=int, default=365)
    args = parser.parse_args()

    doc_types = [dt.strip() for dt in args.doc_type.split(',')]
    samples_by_type = {}

    for dt in doc_types:
        print(f"\n--- Finding {args.samples} samples of doc type {dt} ---")
        samples = find_samples(dt, args.samples, args.days_back)
        print(f"Found {len(samples)} samples")

        element_lists = []
        for sample in samples:
            print(f"\nInspecting {sample['docID']}...")
            try:
                elements = inspect_elements(sample['docID'])
                element_lists.append(elements)
                print(f"  {len(elements)} unique elements")
            except Exception as e:
                print(f"  Error: {e}")

        samples_by_type[dt] = element_lists

    if len(doc_types) == 2:
        compare_element_sets(samples_by_type)
    elif len(doc_types) == 1:
        dt = doc_types[0]
        if samples_by_type[dt]:
            all_elems = set()
            for elements in samples_by_type[dt]:
                all_elems.update(elements.keys())
            print(f"\n--- All unique elements across {len(samples_by_type[dt])} samples of doc type {dt} ---")
            print(f"Total unique elements: {len(all_elems)}")
            for e in sorted(all_elems):
                print(f"  {e}")
