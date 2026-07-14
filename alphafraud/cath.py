"""CATH domain assignments for a chain, via the RCSB Data GraphQL instance features.

Used to decompose the comparison per structural domain, which exposes inter-domain hinge
errors that a single global superposition averages away. CATH lags deposition, so freshly
released structures often have no assignment yet -- callers fall back to AlphaFold-PAE
domain clustering (see compare.pae_domains) in that case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import config
from .http import graphql


@dataclass
class Domain:
    domain_id: str          # CATH code, e.g. "3.90.190.10"
    name: str               # superfamily description
    beg: int                # entity/label seq id (1-based, inclusive)
    end: int


_INSTANCE_FEATURE_QUERY = """
query($ids: [String!]!) {
  polymer_entity_instances(instance_ids: $ids) {
    rcsb_id
    rcsb_polymer_instance_feature {
      type name feature_id
      feature_positions { beg_seq_id end_seq_id }
    }
  }
}
"""


def domains_for_chain(entry_id: str, auth_asym_id: str) -> list[Domain]:
    """CATH domains for a chain instance ('<entry>.<chain>'). Empty if none assigned."""
    instance_id = f"{entry_id.upper()}.{auth_asym_id}"
    try:
        data = graphql(config.RCSB_GRAPHQL_URL, _INSTANCE_FEATURE_QUERY, {"ids": [instance_id]})
    except Exception:
        return []
    instances = data.get("polymer_entity_instances") or []
    if not instances or not instances[0]:
        return []
    domains: list[Domain] = []
    for feat in instances[0].get("rcsb_polymer_instance_feature") or []:
        if feat.get("type") != "CATH":
            continue
        for pos in feat.get("feature_positions") or []:
            beg, end = pos.get("beg_seq_id"), pos.get("end_seq_id")
            if beg is None or end is None:
                continue
            domains.append(
                Domain(
                    domain_id=feat.get("feature_id", "CATH"),
                    name=feat.get("name", ""),
                    beg=int(beg),
                    end=int(end),
                )
            )
    return domains
