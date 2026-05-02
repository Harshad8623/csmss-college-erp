import re, os

template_dir = r'c:\Users\harshad Dhuppe\CSMSS College Project\templates'
app_dir = r'c:\Users\harshad Dhuppe\CSMSS College Project\app'
issues = []

for root, dirs, files in os.walk(app_dir):
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        content = open(path, encoding='utf-8', errors='ignore').read()
        # Match both single and double quoted template names
        matches = re.findall(r"render_template\(['\"]([^'\"]+)['\"]", content)
        for tpl in matches:
            full = os.path.join(template_dir, tpl)
            if not os.path.exists(full):
                issues.append(f'MISSING: {tpl}  (referenced in {os.path.basename(path)})')

if issues:
    for i in issues:
        print(i)
else:
    print('ALL TEMPLATES OK - every render_template() call has its file')
