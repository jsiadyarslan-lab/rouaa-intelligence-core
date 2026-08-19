"""D6 — entity resolution. Brand is NEVER identity; domains bind only via recorded verification.

Regression anchor (directive §7): bmf.de != German Ministry of Finance.
"""
from __future__ import annotations
from .contracts import Institution


class EntityResolutionError(Exception):
    pass


class InstitutionRegistry:
    def __init__(self):
        self._by_id: dict[str, Institution] = {}
        self._domain_bindings: dict[str, str] = {}   # domain -> institution_id (verified only)

    def add_institution(self, inst: Institution) -> None:
        if inst.institution_id in self._by_id:
            raise EntityResolutionError(f"duplicate institution_id {inst.institution_id}")
        self._by_id[inst.institution_id] = inst
        for binding in inst.verified_domains:
            self._bind(inst.institution_id, binding["domain"], binding["verification_evidence"])

    def _bind(self, institution_id: str, domain: str, evidence: str) -> None:
        if not evidence:
            raise EntityResolutionError(
                f"domain {domain} requires verification_evidence (D6: verified bindings only)")
        domain = domain.lower().strip()
        owner = self._domain_bindings.get(domain)
        if owner and owner != institution_id:
            raise EntityResolutionError(
                f"domain {domain} already verified to {owner}; refusing rebind to {institution_id} "
                "(use supersede_entity_correction)")
        self._domain_bindings[domain] = institution_id

    def resolve(self, domain_or_url: str) -> Institution | None:
        """Resolve by VERIFIED DOMAIN only. Hostname extraction from URL allowed."""
        d = domain_or_url.strip().lower()
        if "://" in d or "/" in d:
            d = d.split("://", 1)[-1].split("/", 1)[0]
        iid = self._domain_bindings.get(d)
        if iid is None and d.startswith("www."):   # www-form of a verified apex binding
            iid = self._domain_bindings.get(d[4:])
        return self._by_id.get(iid) if iid else None

    def assert_association(self, domain: str, institution_id: str) -> Institution:
        """BMF regression gate: associating an unverified/wrong domain must FAIL loudly."""
        inst = self.resolve(domain)
        if inst is None:
            raise EntityResolutionError(
                f"domain '{domain}' has no verified entity binding — association REJECTED "
                "(hostname->entity inference forbidden, D6; bmf.de precedent)")
        if inst.institution_id != institution_id:
            raise EntityResolutionError(
                f"domain '{domain}' is verified to {inst.institution_id}, not {institution_id} "
                "— misattribution REJECTED")
        return inst

    def resolve_by_brand(self, brand: str):  # explicitly forbidden path
        raise EntityResolutionError(
            "brand/abbreviation lookup is forbidden as identity (D6; 'BMF' collides across "
            "Bundesministerium der Finanzen and Buerener Maschinenfabrik)")

    def supersede_entity_correction(self, domain: str, from_inst: str, to_inst: str,
                                    reason: str, evidence: str) -> None:
        """History-preserving correction (append to both institutions' history; rebind domain)."""
        if not evidence:
            raise EntityResolutionError("superseding correction requires evidence")
        old = self._by_id[from_inst]; new = self._by_id[to_inst]
        old.history.append({"type": "ENTITY_CORRECTION", "domain": domain,
                            "superseded_by": to_inst, "reason": reason, "evidence": evidence})
        new.history.append({"type": "ENTITY_CORRECTION", "domain": domain,
                            "supersedes": from_inst, "reason": reason, "evidence": evidence})
        self._domain_bindings[domain.lower()] = to_inst
