"""Standard-selection policy shared by the financial parsers.

The filing declares its accounting standard (AccountingStandardsDEI). The
contract for every declared financial field:

    When a usable fact for the field's concept exists in the filing's declared
    standard, at the eligible context and period, another standard's fact
    cannot outrank it. A missing own-standard fact follows the field's
    declared fallback. Ownership basis (owners / total), consolidation scope
    and period are preserved independently of the standard.

A field's `FieldPolicy` names the standards that tag its concept with an
element of their own (`standards`; an element's standard is read from its
taxonomy name, `element_standard`) and what happens when the declared
standard's own fact is missing (`fallback`):

    'legacy' -- the field's existing waterfall (the legacy table), which may
                serve another standard's fact (the only source the filing gives);
    'none'   -- honest None: the legacy table is closed to that standard;
    'n/a'    -- one standard (or none) tags the concept: nothing competes.

`fallback` is either one of those words, for every declared standard, or a
mapping {declared standard: word}; a standard the mapping does not name keeps
the legacy table. A mapping may name a standard with no element of its own:
'none' then closes the legacy table to it. The scalar 'none' closes the legacy
table to `standards` only.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Union

from .extraction import Tier, _tier_in_scope

JGAAP, IFRS, USGAAP = "Japan GAAP", "IFRS", "US GAAP"
FALLBACKS = ("legacy", "none", "n/a")


@dataclass(frozen=True)
class FieldPolicy:
    """How one financial field chooses between accounting standards."""

    concept: str
    standards: tuple
    fallback: Union[str, Mapping]
    neutral: tuple = ()


def fallback_for(policy: FieldPolicy, standard) -> str:
    """The fallback that applies to a filing declaring `standard`."""
    if isinstance(policy.fallback, Mapping):
        return policy.fallback.get(standard, "legacy")
    return policy.fallback


def closed_standards(policy: FieldPolicy) -> tuple:
    """The declared standards the legacy table is closed to."""
    if isinstance(policy.fallback, Mapping):
        return tuple(s for s, f in policy.fallback.items() if f == "none")
    return tuple(policy.standards) if policy.fallback == "none" else ()


def element_standard(element_id: str) -> str:
    """The accounting standard an element belongs to, from its taxonomy name:
    'US GAAP' / 'IFRS' when the local name carries the standard
    (...USGAAPSummaryOfBusinessResults, ...IFRSSummaryOfBusinessResults,
    ...IFRS, including filer-local namespaces); 'Japan GAAP' for the jppfs_cor
    financial-statement taxonomy and the unmarked ...SummaryOfBusinessResults
    highlights elements; otherwise 'neutral', which a FieldPolicy must name
    explicitly (the name alone does not establish neutrality)."""
    prefix, _, local = element_id.rpartition(":")
    if "USGAAP" in local:
        return USGAAP
    if local.endswith("IFRS") or "IFRSSummaryOfBusinessResults" in local:
        return IFRS
    if prefix == "jppfs_cor" or local.endswith("SummaryOfBusinessResults"):
        return JGAAP
    return "neutral"


def table_elements(*tables) -> tuple:
    """Every element the tables read, in table order, without repeats."""
    seen = []
    for table in tables:
        for tier in table:
            for el in tier.elements:
                if el not in seen:
                    seen.append(el)
    return tuple(seen)


def close_legacy(legacy: tuple, policy: FieldPolicy) -> tuple:
    """The legacy table with every tier closed to the standards whose
    fallback is 'none'."""
    closed = closed_standards(policy)
    if not closed:
        return legacy
    return tuple(replace(t, exclude_standards=(t.exclude_standards or ()) + closed) for t in legacy)


def with_own_standard_first(legacy: tuple, policy: FieldPolicy) -> tuple:
    """A field's resolved tier table: one stage per declared standard, then
    the legacy waterfall.

    Each stage holds, in legacy order, the legacy tiers' elements of that
    standard only, scoped to it (standards=(std,)), with no chain of its own:
    a filing that declares the standard reads its own facts before any other
    standard's. A legacy tier out of scope for a standard (the 0.7.1
    operating-income gate) contributes nothing to that standard's stage. A
    last-resort tier keeps its place after the stage's other tiers but is not
    deferred past the legacy table (it is the standard's own fact). A field
    that only one standard tags has no stage: its legacy table already reads
    that standard's fact first.

    The legacy table follows: it serves a filing without a declared standard,
    and, under the 'legacy' fallback, a filing whose own-standard fact is
    missing. It is closed to every standard whose fallback is 'none'
    (`close_legacy`), so a missing own fact is an honest None there."""
    stage = []
    if len(policy.standards) >= 2:
        ordered = [t for t in legacy if not t.last_resort] + [t for t in legacy if t.last_resort]
        for std in policy.standards:
            for tier in ordered:
                if not _tier_in_scope(tier, std):
                    continue
                own = tuple(e for e in tier.elements if element_standard(e) == std)
                if own:
                    stage.append(
                        Tier(
                            own if len(own) > 1 else own[0],
                            standards=(std,),
                            suffix_match=tier.suffix_match,
                        )
                    )
    return tuple(stage) + close_legacy(legacy, policy)


def own_standard_stage(legacy: tuple, policy: FieldPolicy) -> tuple:
    """The own-standard stage alone (the per-share fields resolve it with
    coerce semantics before their legacy scan)."""
    full = with_own_standard_first(legacy, policy)
    return full[: len(full) - len(legacy)]
