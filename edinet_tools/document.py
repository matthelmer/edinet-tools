"""
Document class for EDINET filings.

Wraps EDINET API responses with convenient accessors.
"""
from datetime import datetime
from typing import Any


class Document:
    """
    An EDINET document (filing).

    Wraps API response data with convenient accessors.
    """

    def __init__(self, data: dict[str, Any], client: Any = None):
        self._data = data
        self._client = client

    @property
    def doc_id(self) -> str:
        """EDINET document ID."""
        return self._data.get('docID', '')

    @property
    def doc_type_code(self) -> str:
        """Document type code (e.g., '350')."""
        return self._data.get('docTypeCode', '')

    @property
    def doc_type(self):
        """Document type as DocType object."""
        from .doc_types import doc_type as get_doc_type
        return get_doc_type(self.doc_type_code)

    @property
    def doc_type_name(self) -> str | None:
        """English name of the document type (e.g., 'Large Shareholding Report')."""
        dt = self.doc_type
        return dt.name_en if dt else None

    @property
    def filer_edinet_code(self) -> str:
        """EDINET code of the filing entity."""
        return self._data.get('edinetCode', '')

    @property
    def filer_name(self) -> str:
        """Name of the filing entity (from API response)."""
        return self._data.get('filerName', '')

    @property
    def filing_datetime(self) -> datetime | None:
        """When the document was filed."""
        submit_dt = self._data.get('submitDateTime', '')
        if submit_dt:
            try:
                return datetime.strptime(submit_dt, '%Y-%m-%d %H:%M')
            except ValueError:
                # Try alternative format
                try:
                    return datetime.strptime(submit_dt, '%Y-%m-%d')
                except ValueError:
                    return None
        return None

    @property
    def filer(self):
        """The Entity that filed this document."""
        if self.filer_edinet_code:
            from .entity import entity_by_edinet_code
            return entity_by_edinet_code(self.filer_edinet_code)
        return None

    @property
    def doc_description(self) -> str | None:
        """Document description from API."""
        return self._data.get('docDescription')

    @property
    def securities_code(self) -> str | None:
        """Securities code if applicable."""
        return self._data.get('secCode')

    @property
    def period_start(self) -> str | None:
        """Start of reporting period."""
        return self._data.get('periodStart')

    @property
    def period_end(self) -> str | None:
        """End of reporting period."""
        return self._data.get('periodEnd')

    def fetch(self) -> bytes:
        """
        Fetch document content.

        Returns:
            Document content as bytes (typically a ZIP file)
        """
        from ._client import _get_client

        client = self._client if self._client is not None else _get_client()
        return client.download_filing_raw(self.doc_id)

    def parse(self):
        """
        Parse this document and return a typed report.

        Returns:
            ParsedReport subclass based on document type
        """
        from .parsers import parse
        return parse(self)

    def __repr__(self) -> str:
        filer = self.filer_name or 'Unknown'
        if len(filer) > 20:
            filer = filer[:17] + '...'
        dt = self.filing_datetime
        dt_str = dt.strftime('%Y-%m-%d') if dt else '?'
        return f"Document(id='{self.doc_id}', type={self.doc_type_code}, filer='{filer}', date={dt_str})"
