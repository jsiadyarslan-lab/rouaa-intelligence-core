"""V13 §2-9 — Recall Recovery: Structured Extraction + Nav FN Fix + Semantic Gate FN Fix + Multilingual + New Patterns.

§2: Structured-document extraction (tables, lists, labeled values, key:value)
§3: Navigation FN fix (MIXED classifier: NAVIGATION_ONLY / MIXED / SEMANTIC_CONTENT)
§4: Semantic-gate FN fix (expanded context patterns)
§7: Multilingual patterns (Japanese, Chinese, Arabic, Russian)
§9: New patterns (basis points, seasonally adjusted, yield, spread, volume)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))


# ══════════════════════════════════════════════════════════
# §2 — STRUCTURED DOCUMENT EXTRACTION
# ══════════════════════════════════════════════════════════

STRUCTURED_PATTERNS = [
    # Table row: "GDP growth | 2.1%" or "GDP growth: 2.1%"
    (r"(?i)(gdp\s+growth|inflation\s+rate|unemployment\s+rate|policy\s+rate|interest\s+rate)\s*[|:]\s*(\d+(?:\.\d+)?)\s*%?", "structured_rate"),
    # Labeled value: "Rate: 5.25%"
    (r"(?i)\b(rate|growth|inflation|unemployment|interest)\s*:\s*(\d+(?:\.\d+)?)\s*%?", "labeled_rate"),
    # List item with percentage: "- GDP growth: 2.1%"
    (r"(?i)^\s*[-•*]\s*(.+?)\s*[:\-]\s*(\d+(?:\.\d+)?)\s*%", "list_percentage"),
]

# §9 — New recall patterns
NEW_RECALL_PATTERNS = [
    (r"\b(\d+(?:\.\d+)?)\s*basis\s+points?\b", "basis_points"),
    (r"\bseasonally\s+adjusted\b.*?\b(\d+(?:\.\d+)?)\s*%", "seasonally_adjusted"),
    (r"\b(\d+(?:\.\d+)?)\s*%\b.*?\bseasonally\s+adjusted\b", "seasonally_adjusted"),
    (r"\byield\s+(?:of\s+|was\s+|is\s+)?(\d+(?:\.\d+)?)\s*%", "yield_rate"),
    (r"\bspread\s+(?:of\s+|was\s+|is\s+)?(\d+(?:\.\d+)?)\s*(?:%|basis\s+points?)", "spread"),
    (r"\b(?:volume|turnover)\s+(?:of\s+|was\s+)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|billion)?", "volume"),
    (r"\btrade\s+(?:value|balance|deficit|surplus)\s+(?:of\s+|was\s+)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "trade_value"),
    (r"\b(?:production|output)\s+(?:rose|increased|grew|declined|fell)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "production_change"),
    (r"\bemployment\s+(?:rose|increased|fell|decreased)\s+(?:by\s+)?(\d+(?:,\d{3})+)", "employment_change"),
    (r"\bindex\s+(?:rose|fell|increased|decreased)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:%|points?)", "index_change"),
    (r"\b(\d+(?:\.\d+)?)\s*%\s*(?:quarter[- ]over[- ]quarter|qoq|q/q)", "qoq_change"),
    (r"\b(\d+(?:\.\d+)?)\s*%\s*(?:year[- ]over[- ]year|yoy|y/y)", "yoy_change"),
    (r"\b(\d+(?:\.\d+)?)\s*%\s*(?:month[- ]over[- ]month|mom|m/m)", "mom_change"),
]

# §7 — Multilingual patterns
MULTILINGUAL_PATTERNS = {
    "ja": [
        (r"政策金利\s*[はを]\s*(\d+(?:\.\d+)?)\s*%", "policy_rate"),
        (r"金利\s*[はを]\s*(\d+(?:\.\d+)?)\s*%", "rate_value"),
        (r"(?:消費者物価|インフレ)\s*(?:上昇)?率\s*[はを]\s*(\d+(?:\.\d+)?)\s*%", "inflation_rate"),
        (r"(?:完全)?失業率\s*[はを]\s*(\d+(?:\.\d+)?)\s*%", "unemployment_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
    ],
    "zh": [
        (r"政策利率\s*[为是]\s*(\d+(?:\.\d+)?)\s*%", "policy_rate"),
        (r"利率\s*[为是]\s*(\d+(?:\.\d+)?)\s*%", "rate_value"),
        (r"(?:消费者物价|通胀)\s*(?:上升)?率\s*[为是]\s*(\d+(?:\.\d+)?)\s*%", "inflation_rate"),
        (r"失业率\s*[为是]\s*(\d+(?:\.\d+)?)\s*%", "unemployment_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
    ],
    "ar": [
        (r"سعر\s+الفائدة\s+(?:\d+(?:\.\d+)?)\s*%", "rate_value"),
        (r"معدل\s+التضخم\s+(?:\d+(?:\.\d+)?)\s*%", "inflation_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
    ],
    "ru": [
        (r"процентн\w+\s+ставк\w+\s+(?:\d+(?:[.,]\d+)?)\s*%", "rate_value"),
        (r"инфляц\w+\s+(?:\d+(?:[.,]\d+)?)\s*%", "inflation_rate"),
        (r"\b(\d+(?:[.,]\d+)?)\s*%", "percentage_statistic"),
    ],
}

# Multilingual semantic context
MULTILINGUAL_EVENT_CONTEXT = {
    "ja": {
        "monetary_policy_decision": {
            "required_patterns": [r"(?:金融政策|政策金利|金利)", r"(?:決定|発表|公表)"],
            "all_required": True, "exclusion_patterns": [],
        },
        "statistical_release": {
            "required_patterns": [r"(?:統計|データ|指数|指標)", r"(?:四半期|月次|年次)"],
            "all_required": True, "exclusion_patterns": [],
        },
        "regulatory_enforcement": {
            "required_patterns": [r"(?:処分|罰金|制裁|同意|命令)", r"(?:委員会|庁|機関)"],
            "all_required": True, "exclusion_patterns": [],
        },
    },
    "zh": {
        "monetary_policy_decision": {
            "required_patterns": [r"(?:货币政策|利率|政策利率)", r"(?:决定|公布|宣布)"],
            "all_required": True, "exclusion_patterns": [],
        },
        "statistical_release": {
            "required_patterns": [r"(?:统计|数据|指数|指标)", r"(?:季度|月度|年度)"],
            "all_required": True, "exclusion_patterns": [],
        },
        "regulatory_enforcement": {
            "required_patterns": [r"(?:处罚|罚款|同意|命令)", r"(?:委员会|局|机构)"],
            "all_required": True, "exclusion_patterns": [],
        },
    },
}


# ══════════════════════════════════════════════════════════
# §3 — NAVIGATION FALSE-NEGATIVE FIX
# ══════════════════════════════════════════════════════════

def classify_navigation_precise(excerpt: str) -> str:
    """V13 precise navigation classifier.

    Returns:
      NAVIGATION_ONLY — pure navigation/UI content
      MIXED — contains both navigation AND semantic content
      SEMANTIC_CONTENT — actual semantic content (should NOT be rejected)
    """
    if not excerpt:
        return "SEMANTIC_CONTENT"

    excerpt_lower = excerpt.lower()

    nav_keywords = [
        "menu", "navigation", "breadcrumb", "sidebar", "navbar",
        "skip to", "search form", "search box",
        "facebook", "twitter", "linkedin", "youtube", "instagram",
        "copyright", "©", "all rights reserved",
        "page ", "p. ",
        "contact us", "email", "phone",
        "click here", "read more", "share", "print", "download",
        "cookie", "privacy notice", "terms of use",
        "browse page", "news articles",
        "share sensitive information", "homepage",
    ]

    nav_indicators = sum(1 for kw in nav_keywords if kw in excerpt_lower)
    if "share sensitive information" in excerpt_lower: nav_indicators += 2
    if "homepage" in excerpt_lower and "menu" in excerpt_lower: nav_indicators += 2
    if "browse page" in excerpt_lower: nav_indicators += 2

    semantic_keywords = [
        "rate", "growth", "inflation", "gdp", "unemployment",
        "penalty", "fine", "settlement", "charged", "enforcement",
        "consent order", "cease", "desist", "injunction",
        "million", "billion", "percent", "percentage",
        "quarter", "monthly", "annual", "increase", "decrease",
        "bank", "central", "reserve", "commission", "authority",
        "decision", "announce", "policy", "statistical",
        "release", "report", "figure", "estimate",
        "basis points", "seasonally adjusted", "yield", "spread",
    ]

    semantic_indicators = sum(1 for kw in semantic_keywords if kw in excerpt_lower)

    if nav_indicators >= 3 and semantic_indicators == 0:
        return "NAVIGATION_ONLY"
    elif nav_indicators >= 2 and semantic_indicators >= 1:
        return "MIXED"
    elif nav_indicators >= 3 and semantic_indicators >= 2:
        return "MIXED"
    elif nav_indicators <= 1:
        return "SEMANTIC_CONTENT"
    else:
        return "NAVIGATION_ONLY"


def is_navigation_content_v13(excerpt: str) -> bool:
    """V13 navigation check — only rejects NAVIGATION_ONLY (keeps MIXED)."""
    return classify_navigation_precise(excerpt) == "NAVIGATION_ONLY"


# ══════════════════════════════════════════════════════════
# §4 — SEMANTIC GATE FALSE-NEGATIVE FIX
# ══════════════════════════════════════════════════════════

EXPANDED_EVENT_CONTEXT = {
    "monetary_policy_decision": {
        "required_patterns": [
            r"\b(monetary\s+policy|policy\s+rate|interest\s+rate|key\s+rate|"
            r"base\s+rate|benchmark\s+rate|central\s+bank\s+rate)\b",
            r"\b(decid(?:e|ed|ion)|announc(?:e|ed|ement)|statement\s+on|"
            r"press\s+release|press\s+conference|policy\s+(?:meeting|committee)|"
            r"rate\s+(?:decision|change|move|cut|hike)|"
            r"maintain(?:ed)?\s+(?:the\s+)?rate|"
            r"rais(?:e|ed)\s+(?:the\s+)?rate|"
            r"cut\s+(?:the\s+)?rate|"
            r"lower(?:ed)?\s+(?:the\s+)?rate)\b",
        ],
        "all_required": True,
        "exclusion_patterns": [
            r"\b(gdp\s+(?:growth|estimate|advance|release)|"
            r"economic\s+indicators?\s+(?:report|release)|"
            r"statistical\s+release|cpi\s+(?:report|release)|"
            r"employment\s+situation\s+report)\b",
            # V29.1 §4 — Narrow CIMPA/CDS/fail-fee disqualifier ONLY.
            # V29's broad securities/bond/clearing exclusions caused -2.88pp
            # recall regression by rejecting valid monetary docs that mention
            # "securities" (ECB payment systems) or "bond" (BOJ purchase programs).
            # This pattern targets ONLY the specific Canadian market-notice
            # pattern that caused the 3 V28 TRUE_EVENT_FPs.
            r"\b(CIMPA|CDS\s+announce\s+the\s+start\s+of\s+the\s+trial\s+period|"
            r"fail\s+fee\s+framework)\b",
        ],
    },
    "statistical_release": {
        "required_patterns": [
            r"\b(statistic(?:s|al)?|data\s+(?:release|report)|index|indicator|"
            r"survey|estimate|figure|table|chart)\b",
            r"\b(quarter|monthly|annual|year(?:\s+over\s+year)?|"
            r"period|seasonally\s+adjusted|period[- ]over[- ]period|"
            r"q[1-4]\s+\d{4}|fiscal\s+year|calendar\s+year|"
            r"preliminary|final|revised|advance\s+estimate)\b",
        ],
        "all_required": True,
        "exclusion_patterns": [],
    },
    "regulatory_enforcement": {
        "required_patterns": [
            r"\b(consent\s+order|cease\s+(?:-|\s+)and\s+(?:-|\s+)desist|"
            r"injunction|penalty\s+(?:of|imposed|assessed)|"
            r"disgorgement|settlement\s+(?:agreement|order)|"
            r"fine\s+(?:of|imposed|assessed)|"
            r"charged\s+with|sued\s+for|"
            r"enforcement\s+(?:action|proceeding|order)|"
            r"order\s+(?:to\s+cease|to\s+desist|of\s+prohibition)|"
            r"fined|penalized|sanction(?:ed|s)|"
            r"agreed\s+to\s+(?:pay|settle)|"
            r"ordered\s+to\s+pay|"
            r"violat(?:e|ed|ion)\s+(?:of|securities|banking))\b",
            r"\b(sec|cftc|fca|esma|consob|bafin|finra|"
            r"regulator|regulatory|commission|authority|"
            r"supervisory|enforcement\s+division|"
            r"defendant|respondent|respondents|"
            r"court|tribunal|judge|magistrate)\b",
        ],
        "all_required": True,
        "exclusion_patterns": [
            r"\b(op[- ]?ed|speech|testimony|remarks|keynote|"
            r"commentary|opinion\s+piece|blog\s+post)\b",
        ],
    },
}


def validate_event_context_v13(event_type: str, document_text: str, language: str = "en") -> tuple[bool, str]:
    """V13 semantic gate — expanded context + multilingual support."""
    if language != "en" and language in MULTILINGUAL_EVENT_CONTEXT:
        requirements = MULTILINGUAL_EVENT_CONTEXT[language].get(event_type)
        if requirements:
            required_matches = sum(1 for p in requirements["required_patterns"] if re.search(p, document_text, re.IGNORECASE))
            if requirements.get("all_required", True) and required_matches < len(requirements["required_patterns"]):
                return False, f"missing context ({required_matches}/{len(requirements['required_patterns'])}) [lang={language}]"
            for excl in requirements.get("exclusion_patterns", []):
                if re.search(excl, document_text, re.IGNORECASE):
                    return False, f"exclusion match [lang={language}]"
            return True, f"context valid ({required_matches}) [lang={language}]"

    requirements = EXPANDED_EVENT_CONTEXT.get(event_type)
    if not requirements:
        return True, "no requirements"

    text_lower = document_text.lower()
    required_matches = sum(1 for p in requirements["required_patterns"] if re.search(p, text_lower))

    if requirements.get("all_required", True) and required_matches < len(requirements["required_patterns"]):
        return False, f"missing context ({required_matches}/{len(requirements['required_patterns'])})"

    for excl in requirements.get("exclusion_patterns", []):
        if re.search(excl, text_lower):
            return False, f"exclusion match"

    return True, f"context valid ({required_matches}/{len(requirements['required_patterns'])})"


def get_multilingual_patterns(language: str) -> list:
    """Get extraction patterns for the document's language."""
    return MULTILINGUAL_PATTERNS.get(language, [])


def get_new_recall_patterns() -> list:
    """Get the new recall patterns (basis points, seasonally adjusted, etc.)."""
    return NEW_RECALL_PATTERNS


def get_structured_patterns() -> list:
    """Get structured document patterns."""
    return STRUCTURED_PATTERNS
