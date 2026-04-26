"""
Helper script: generates REAL_STUDENTS list from the downloaded Excel file.
Run: python gen_students.py
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('student_data_raw.json', encoding='utf-8') as f:
    data = json.load(f)

headers = data['headers']
rows    = data['rows']

def idx(col):
    return headers.index(col)

lines = []
for row in rows:
    prn      = str(row[idx('PRN')]                   or '').strip()
    name     = str(row[idx('Students Full Name')]     or '').strip()
    gender   = str(row[idx('Gender')]                 or '').strip()
    gender_c = 'M' if gender.lower().startswith('m') else 'F'
    dob      = str(row[idx('DOB')]                    or '').strip()
    category = str(row[idx('Category')]               or '').strip()
    mobile   = str(row[idx('Mobile No')]              or '').strip()
    email    = str(row[idx('Email-Id')]               or '').strip().lower()
    blood    = str(row[idx('Blood Group')]             or '').strip()
    aadhar   = str(row[idx('Aadhar Number')]          or '').strip()
    city     = str(row[idx('Student_City/Village')]   or '').strip().title()
    district = str(row[idx('Student District')]       or '').strip().title()
    state    = str(row[idx('Student State')]          or '').strip().title()
    pincode  = str(row[idx('Student Location Pincode')] or '').strip()

    line = (
        f'    ("{prn}", "{name}", "{gender_c}", "{dob}", '
        f'"{category}", "{mobile}", "{email}", '
        f'"{blood}", "{aadhar}", "{city}", "{district}", "{state}", "{pincode}"),'
    )
    lines.append(line)
    print(line)

print(f"\n# Total: {len(lines)} students")
