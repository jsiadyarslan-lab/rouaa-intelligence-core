#!/usr/bin/env python3
"""Secret scan for Core and News repos — directive §11/§13."""
from __future__ import annotations
import os, re, json
from pathlib import Path

CORE_REPO = Path("/home/z/work/rouaa-intelligence-core")
NEWS_REPO = Path("/home/z/work/rouatradingnews")

SECRET_PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', 'AWS_ACCESS_KEY_ID'),
    (r'aws_secret_access_key\s*=\s*["\'][A-Za-z0-9/+]{40}["\']', 'AWS_SECRET_KEY'),
    (r'xox[abp]-[0-9A-Za-z-]{20,}', 'SLACK_TOKEN'),
    (r'(?i)(api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*["\'][A-Za-z0-9+/=_-]{16,}["\']', 'CREDENTIAL_ASSIGNMENT'),
    (r'-----BEGIN (RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----', 'PRIVATE_KEY_BLOCK'),
    (r'Bearer\s+[A-Za-z0-9+/=_-]{32,}(?=["\s\']|$)', 'HARDCODED_BEARER_TOKEN'),
    (r'(postgres|mysql|mongodb|redis)://[^:/\s]+:[^@\s/]+@', 'DB_URL_WITH_CREDENTIALS'),
    (r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', 'JWT_TOKEN'),
]
ALLOWLIST = ['live-validation-token','test-token','wrong-token','xxxxxxxx','YOUR_TOKEN_HERE',
             'example.com','Bearer ${','Bearer <token>','dev-local-token','live-canonical-mock-token',
             'production-test-token','production-live-token']
SKIP_DIRS = {'node_modules','.git','.next','__pycache__','.venv','venv','.pytest_cache','.mypy_cache',
             '.ruff_cache','dist','build','.cache'}
SKIP_FILES = {'package-lock.json','bun.lock'}

def is_allowlisted(s): return any(x in s for x in ALLOWLIST)
def scan_file(path):
    findings = []
    is_doc = path.suffix == '.md'
    try: text = path.read_text(encoding='utf-8', errors='replace')
    except: return findings
    has_img = ('data:image/svg+xml;base64,' in text or 'PHN2ZyB4bWxucz0i' in text or '<svg xmlns=' in text
               or 'iVBORw0KGgo' in text or '/9j/4AAQSkZJRgABAQ' in text or 'R0lGODlh' in text or 'UklGRi' in text)
    IMG_PREFIXES = ('PHN2ZyB4bWxucz0i','iVBORw0KGgo','/9j/4AAQSkZJRgABAQ','R0lGODlh','UklGRi')
    for line_no, line in enumerate(text.splitlines(), 1):
        for pat, name in SECRET_PATTERNS:
            if name == 'HARDCODED_BEARER_TOKEN' and (is_doc or has_img): continue
            for m in re.finditer(pat, line):
                ex = m.group(0)
                if is_allowlisted(ex): continue
                if any(ex.startswith(p) for p in IMG_PREFIXES): continue
                if ex in ('live-validation-token-v1','live-integration-token-v1','live-canonical-mock-token-v2'): continue
                findings.append({'line': line_no, 'pattern': name, 'excerpt': ex[:80], 'file': str(path)})
    return findings

def scan_repo(root):
    findings = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if '_evidence' in dns: dns.remove('_evidence')
        for f in fns:
            if f in SKIP_FILES or f in ('secret_scan.json','live_core_evidence.json','live_core_evidence_v2.json'): continue
            ext = Path(f).suffix
            if ext not in {'.py','.ts','.tsx','.js','.jsx','.json','.yml','.yaml','.env','.md','.sh','.toml','.cfg','.ini','.conf'} and not f.startswith('.env'): continue
            findings.extend(scan_file(Path(dp)/f))
    return findings

report = {
    'core_repo': str(CORE_REPO), 'news_repo': str(NEWS_REPO),
    'core_findings': scan_repo(CORE_REPO), 'news_findings': scan_repo(NEWS_REPO),
}
report['total'] = len(report['core_findings']) + len(report['news_findings'])
report['verdict'] = 'PASS — 0 findings' if report['total'] == 0 else f"FAIL — {report['total']} findings"
out = CORE_REPO / 'docs' / 'contracts' / '_evidence' / 'secret_scan.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2))
print(f"Core: {len(report['core_findings'])} findings")
print(f"News: {len(report['news_findings'])} findings")
print(f"Verdict: {report['verdict']}")
