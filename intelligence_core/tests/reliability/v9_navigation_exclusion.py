"""V9 §9 — Navigation/UI Exclusion.

Explicitly prevent navigation, headers, footers, menus, page numbers,
breadcrumbs, social media links, and contact info from becoming evidence.

These are non-semantic document elements that should not produce facts.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))


# Patterns that identify navigation/UI/non-semantic content
NAVIGATION_UI_PATTERNS = [
    # Navigation menus
    r"\b(menu|navigation|breadcrumb|sidebar|navbar)\b",
    r"\b(skip\s+to\s+(?:main|content))\b",
    r"\b(search\s+(?:form|box|button))\b",
    # Social media
    r"\b(facebook|twitter|linkedin|youtube|instagram)\b",
    # Contact info
    r"\b(contact\s+us|email|phone|address|tel:|mailto:)\b",
    # Header/footer
    r"\b(copyright|©|all\s+rights\s+reserved)\b",
    r"\b(homepage|home\s+page)\b",
    # Page numbers
    r"\bpage\s+\d+\b",
    r"\bp\.\s*\d+\b",
    # UI labels
    r"\b(click\s+here|read\s+more|share|print|download)\b",
    # Cookie/privacy notices
    r"\b(cookie|privacy\s+notice|terms\s+of\s+use)\b",
    # Browse/listing labels
    r"\b(browse\s+page|news\s+articles|press\s+releases?)\b",
]

# Compile patterns
COMPILED_NAV_PATTERNS = [re.compile(p, re.IGNORECASE) for p in NAVIGATION_UI_PATTERNS]


def is_navigation_content(excerpt: str) -> bool:
    """Check if an excerpt is primarily navigation/UI content.

    Returns True if the excerpt contains navigation/UI elements
    that make it unsuitable as primary evidence.
    """
    if not excerpt:
        return False

    excerpt_lower = excerpt.lower()

    # Count navigation pattern matches
    nav_matches = 0
    for pattern in COMPILED_NAV_PATTERNS:
        if pattern.search(excerpt):
            nav_matches += 1

    # If 2+ navigation patterns match, it's likely navigation content
    if nav_matches >= 2:
        return True

    # Single strong signals
    # Check for "share sensitive information" (SEC boilerplate)
    if "share sensitive information" in excerpt_lower:
        return True

    # Check for "homepage Menu" (SEC navigation)
    if "homepage" in excerpt_lower and "menu" in excerpt_lower:
        return True

    # Check for "Browse page" (Eurostat navigation)
    if "browse page" in excerpt_lower:
        return True

    # Check for "Search form" (navigation)
    if "search form" in excerpt_lower:
        return True

    # Check for social media links
    if any(social in excerpt_lower for social in ["facebook", "twitter", "linkedin", "youtube"]):
        return True

    # Check for copyright/footer
    if "copyright" in excerpt_lower or "©" in excerpt:
        return True

    # Check for "all rights reserved"
    if "all rights reserved" in excerpt_lower:
        return True

    # Check for page number patterns
    if re.search(r"\bpage\s+\d+\b", excerpt_lower):
        return True
    if re.search(r"\bp\.\s*\d+\b", excerpt_lower):
        return True

    # Check for contact info
    if re.search(r"\b(contact\s+us|email|phone|\+?\d{3,}[-\s]?\d{3,})\b", excerpt_lower):
        return True

    # Check for UI labels
    if re.search(r"\b(click\s+here|read\s+more)\b", excerpt_lower):
        return True

    return False


def filter_navigation_facts(facts: list) -> tuple[list, list]:
    """Filter out facts whose evidence is primarily navigation/UI content.

    Returns:
      (clean_facts, removed_facts)
    """
    clean = []
    removed = []

    for f in facts:
        excerpt = f.excerpt if hasattr(f, 'excerpt') else f.get('excerpt', '')
        if is_navigation_content(excerpt):
            removed.append(f)
        else:
            clean.append(f)

    return clean, removed


def test_navigation_exclusion():
    """Test the navigation exclusion."""
    print(f"\n--- Testing Navigation/UI Exclusion ---")

    test_cases = [
        # Should be EXCLUDED
        ("Share sensitive information only on official, secure websites. SEC homepage Menu Close Search", True, "SEC homepage boilerplate"),
        ("Browse page News articles Environment and energy PUBLISHED: 13 August 2026", True, "Eurostat browse page"),
        ("Skip to main content Search form Navigation menu", True, "navigation menu"),
        ("Facebook Twitter LinkedIn YouTube Instagram", True, "social media links"),
        ("© 2026 Bureau of Economic Analysis. All rights reserved.", True, "copyright footer"),
        ("Page 74 of 120", True, "page number"),
        ("Contact us: info@example.com | Phone: +1-234-567", True, "contact info"),
        ("Click here to read more about this topic", True, "UI label"),
        # Should NOT be excluded (semantic content)
        ("The Federal Reserve Board today announced a consent order against XYZ Bank. The bank was fined $5 million.", False, "enforcement action"),
        ("GDP increased 2.1 percent in the first quarter of 2026, according to the Bureau of Economic Analysis.", False, "statistical release"),
        ("The ECB Governing Council decided to raise the key interest rate by 25 basis points.", False, "monetary policy decision"),
    ]

    passed = 0
    failed = 0
    for text, should_exclude, description in test_cases:
        is_nav = is_navigation_content(text)
        if is_nav == should_exclude:
            passed += 1
            print(f"  ✓ {description}: {'EXCLUDED' if is_nav else 'KEPT'} (correct)")
        else:
            failed += 1
            print(f"  ✗ {description}: {'EXCLUDED' if is_nav else 'KEPT'} (WRONG — should be {'excluded' if should_exclude else 'kept'})")

    print(f"\n  Results: {passed}/{len(test_cases)} passed")
    return failed == 0


if __name__ == "__main__":
    success = test_navigation_exclusion()
    sys.exit(0 if success else 1)
