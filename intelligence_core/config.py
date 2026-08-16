"""Configuration contract — configuration != core code (directive §9).

Config MAY: source path, feed, patterns, keywords, event mapping, format hints.
Config may NEVER: access-control bypass, identity verification rules, temporal
normalization semantics, evidence governance, entity ownership, database ownership.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .detect import SUPPORTED_EVENT_TYPES

FORBIDDEN_CONFIG_KEYS = {
    "bypass", "captcha", "captcha_solution", "identity_rules", "entity",
    "entity_mapping", "timezone_rule", "timezone_inference", "evidence_governance",
    "db_owner", "database", "rendering", "playwright", "browser"}


class ConfigViolation(Exception):
    pass


@dataclass
class SourceConfig:
    code: str
    name: str
    institution_id: str
    source_path: str
    feed_format: str = "rss"              # rss | html_index
    link_pattern: str = ""
    patterns: list = field(default_factory=list)   # [(regex, pattern_type)]
    event_type: str = ""
    content_keywords: list = field(default_factory=list)
    configuration_version: str = "1"

    def __post_init__(self) -> None:
        self.validate()               # construction-time enforcement (config != core code)

    def validate(self) -> None:
        if self.event_type not in SUPPORTED_EVENT_TYPES:
            raise ConfigViolation(
                f"[{self.code}] event_type '{self.event_type}' not among the six supported "
                "types (directive §10: no new event types)")
        if self.feed_format not in ("rss", "html_index"):
            raise ConfigViolation(f"[{self.code}] feed_format must be rss|html_index")
        if self.feed_format == "html_index" and not self.link_pattern:
            raise ConfigViolation(f"[{self.code}] html_index requires link_pattern")
        blob = {k.lower() for k in self.__dict__}
        bad = blob & FORBIDDEN_CONFIG_KEYS
        if bad:
            raise ConfigViolation(
                f"[{self.code}] forbidden configuration domain(s): {sorted(bad)} — "
                "belongs to Core engineering, never configuration (directive §9)")
        if not self.institution_id:
            raise ConfigViolation(f"[{self.code}] institution_id required (D6 binding)")


def config_from_dict(d: dict) -> SourceConfig:
    bad = {k.lower() for k in d} & FORBIDDEN_CONFIG_KEYS
    if bad:
        raise ConfigViolation(
            f"forbidden configuration domain(s) in source dict: {sorted(bad)} — "
            "belongs to Core engineering, never configuration (directive §9)")
    cfg = SourceConfig(
        code=d["code"], name=d.get("name", d["code"]),
        institution_id=d.get("institution_id", ""),
        source_path=d.get("source_path") or d.get("feedUrl", ""),
        feed_format=d.get("feed_format", "rss"),
        link_pattern=d.get("link_pattern", ""),
        patterns=[(p, t) for p, t in d.get("patterns", [])],
        event_type=d.get("event_type", ""),
        content_keywords=d.get("content_keywords", []),
        configuration_version=d.get("configuration_version", "1"))
    cfg.validate()
    return cfg
