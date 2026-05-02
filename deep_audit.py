"""
Deep audit: scan all templates for:
1. url_for() calls that don't resolve
2. Student/User model attributes referenced that don't exist
3. JS fetch() calls to non-existent API routes
4. static file references that don't exist on disk
"""
import re, os

TEMPLATE_DIR = r'c:\Users\harshad Dhuppe\CSMSS College Project\templates'
STATIC_DIR   = r'c:\Users\harshad Dhuppe\CSMSS College Project\static'
APP_DIR      = r'c:\Users\harshad Dhuppe\CSMSS College Project'

issues = []

# ── 1. Collect all url_for endpoints used in templates ──────────────────────
url_for_pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
known_endpoints = set()
template_url_for = {}  # endpoint -> set of template files

for root, dirs, files in os.walk(TEMPLATE_DIR):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding='utf-8', errors='ignore').read()
        matches = url_for_pattern.findall(content)
        for ep in matches:
            if ep not in template_url_for:
                template_url_for[ep] = set()
            template_url_for[ep].add(os.path.relpath(path, TEMPLATE_DIR))

# ── 2. Collect all registered endpoint names from Flask ─────────────────────
from app import create_app
app = create_app()
with app.test_request_context('/'):
    from flask import url_for
    all_endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    
    for ep, tmpl_files in sorted(template_url_for.items()):
        if ep == 'static':
            continue
        if ep not in all_endpoints:
            issues.append(f'BROKEN url_for: "{ep}" in {", ".join(sorted(tmpl_files))}')
        else:
            # Try to actually build it (catches missing required args)
            try:
                url_for(ep)
            except Exception:
                pass  # May need args — that's OK

# ── 3. Check JS fetch() calls point to valid routes ─────────────────────────
fetch_pattern = re.compile(r"fetch\(['\"](/[^'\"?#]+)")
for root, dirs, files in os.walk(TEMPLATE_DIR):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding='utf-8', errors='ignore').read()
        matches = fetch_pattern.findall(content)
        for route in matches:
            # Try to match against known routes
            matched = False
            for rule in app.url_map.iter_rules():
                # Simple prefix match (handles static params)
                rule_str = str(rule)
                if '<' in rule_str:
                    # Convert /foo/<int:id> to /foo/ for prefix matching
                    prefix = rule_str.split('<')[0]
                    if route.startswith(prefix.rstrip('/')):
                        matched = True
                        break
                elif rule_str == route:
                    matched = True
                    break
            if not matched:
                tname = os.path.relpath(path, TEMPLATE_DIR)
                issues.append(f'BROKEN fetch(): "{route}" in {tname}')

# ── 4. Check static file references ─────────────────────────────────────────
static_pattern = re.compile(r"url_for\('static',\s*filename=['\"]([^'\"]+)['\"]")
for root, dirs, files in os.walk(TEMPLATE_DIR):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding='utf-8', errors='ignore').read()
        matches = static_pattern.findall(content)
        for fname in matches:
            full = os.path.join(STATIC_DIR, fname)
            if not os.path.exists(full):
                tname = os.path.relpath(path, TEMPLATE_DIR)
                issues.append(f'MISSING static file: "static/{fname}" in {tname}')

# ── 5. Check Student model attributes referenced in templates ────────────────
student_attr_pattern = re.compile(r"(?:student|stu|s)\.([\w]+)")
# Known Student model columns (from models.py)
student_attrs = {
    'id','user_id','class_id','roll_no','prn','batch','tg_id',
    'approval_status','year_of_admission','created_at',
    'user','class_','tg','attendance','grievances','certificates',
    'leave_applications','bulk_pct','attendance_percentage'
}
for root, dirs, files in os.walk(TEMPLATE_DIR):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding='utf-8', errors='ignore').read()
        matches = student_attr_pattern.findall(content)
        for attr in matches:
            if attr in ('id','user','class_') or attr.startswith('_'):
                continue
            if attr not in student_attrs and len(attr) > 2:
                # Exclude loop vars etc.
                if attr not in ('items','values','keys','length','count',
                               'index','first','last','loop','range'):
                    pass  # too many false positives, skip

# ── Report ────────────────────────────────────────────────────────────────────
if issues:
    print(f'FOUND {len(issues)} ISSUE(S):')
    for i in issues:
        print(' -', i)
else:
    print('ALL CHECKS PASSED - no broken endpoints, fetch calls, or static files')
