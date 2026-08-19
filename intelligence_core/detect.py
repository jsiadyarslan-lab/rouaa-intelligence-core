"""Event detection — EVENT_TYPE_RULES carried verbatim (6 types, directive §10: unchanged).

D2 extension: events carry the exact fact-version snapshot used to derive them.
"""
from __future__ import annotations
from .contracts import Event, ObjState
from .identity import event_id as make_event_id

EVENT_TYPE_RULES = {
    "monetary_policy_decision": {
        "trigger_metrics": {"rate_decision", "policy_rate", "policy_rate_range"},
        "headline_template": "{source} {headline_verb}",
        "headline_subtypes": {
            "rate_maintain": "Maintains Policy Rate", "rate_hike": "Raises Policy Rate",
            "rate_cut": "Cuts Policy Rate", "rate_published": "Monetary Policy Decision",
            "rate_action": "Monetary Policy Decision"},
        "subtype_mapping": {"maintain": "rate_maintain", "hike": "rate_hike",
                            "raise": "rate_hike", "cut": "rate_cut", "lower": "rate_cut"},
        "summary_metrics": [
            {"metric": "rate_decision", "label": "Decision", "format": "raw"},
            {"metric": "policy_rate", "label": "Rate", "format": "percent"},
            {"metric": "policy_rate_range", "label": "Rate", "format": "percent"}],
        "subtype_from": "rate_decision"},
    "regulatory_enforcement": {
        "trigger_metrics": {"penalty_amount", "defendant_name", "action_type", "violation_type"},
        "headline_template": "{source} Regulatory Enforcement Action",
        "summary_metrics": [
            {"metric": "action_type", "label": "Action", "format": "raw"},
            {"metric": "defendant_name", "label": "Defendant", "format": "raw"},
            {"metric": "penalty_amount", "label": "Penalty", "format": "usd"}],
        "subtype_from": "action_type"},
    "statistical_release": {
        "trigger_metrics": {"inflation_rate", "gdp_growth", "unemployment_rate",
                            "employment_level", "statistic_value", "usd_amount",
                            "percentage_statistic", "cross_border_change"},
        "headline_template": "{source} Statistical Release",
        "summary_metrics": [
            {"metric": "inflation_rate", "label": "Inflation Rate", "format": "percent"},
            {"metric": "gdp_growth", "label": "GDP Growth", "format": "percent"},
            {"metric": "unemployment_rate", "label": "Unemployment Rate", "format": "percent"},
            {"metric": "employment_level", "label": "Employment", "format": "raw"},
            {"metric": "cross_border_change", "label": "Cross-Border Change", "format": "percent"},
            {"metric": "usd_amount", "label": "USD Amount", "format": "usd"}],
        "subtype_from": None},
    "earnings_release": {
        "trigger_metrics": {"revenue", "eps", "net_income", "gross_margin",
                            "yoy_change", "dividend_amount", "total_assets"},
        "headline_template": "{source} Earnings Release",
        "summary_metrics": [
            {"metric": "revenue", "label": "Revenue", "format": "usd"},
            {"metric": "net_income", "label": "Net Income", "format": "usd"},
            {"metric": "eps", "label": "EPS", "format": "usd"},
            {"metric": "dividend_amount", "label": "Dividend", "format": "usd"},
            {"metric": "gross_margin", "label": "Gross Margin", "format": "percent"}],
        "subtype_from": None},
    "sanctions_designation": {
        "trigger_metrics": {"designated_entity", "designated_country",
                            "sanctions_program", "action_type", "faq_topic"},
        "headline_template": "{source} Sanctions Action",
        "summary_metrics": [
            {"metric": "designated_entity", "label": "Entities", "format": "count"},
            {"metric": "sanctions_program", "label": "Programs", "format": "list"}],
        "subtype_from": "action_type"},
    "market_statistic_release": {
        "trigger_metrics": {"fx_turnover", "ird_turnover", "cds_turnover",
                            "usd_amount", "percentage_change"},
        "headline_template": "{source} Market Statistics Release",
        "summary_metrics": [
            {"metric": "fx_turnover", "label": "FX Turnover", "format": "usd"},
            {"metric": "ird_turnover", "label": "IRD Turnover", "format": "usd"},
            {"metric": "cds_turnover", "label": "CDS Turnover", "format": "usd"},
            {"metric": "usd_amount", "label": "USD Amount", "format": "usd"}],
        "subtype_from": None},
}

SUPPORTED_EVENT_TYPES = set(EVENT_TYPE_RULES)


def detect_event(facts: list, document_id: str, configured_event_type: str,
                 source_name: str = "", occurrence: int = 0,
                 derived_at: str = "") -> Event | None:
    """Mirrors detector.detect_event: >=1 fact whose metric is in trigger_metrics."""
    if configured_event_type not in EVENT_TYPE_RULES:
        raise ValueError(f"event_type '{configured_event_type}' not in the six supported types")
    rules = EVENT_TYPE_RULES[configured_event_type]
    triggering = [f for f in facts if f.metric in rules["trigger_metrics"]]
    if not triggering:
        return None
    # D2: snapshot = exact fact versions used for THIS derivation.
    snapshot = [{"fact_id": f.fact_id, "fact_version": f.fact_version} for f in triggering]
    eid = make_event_id(document_id, configured_event_type, occurrence)
    return Event(event_id=eid, event_version=1, document_id=document_id,
                 event_type=configured_event_type, fact_version_snapshot=snapshot,
                 occurrence=occurrence, status=ObjState.ACTIVE, derived_at=derived_at)


def build_headline(event: Event, source_name: str) -> str:
    tpl = EVENT_TYPE_RULES[event.event_type]["headline_template"]
    return tpl.format(source=source_name, headline_verb=event.event_type.replace("_", " ").title())
