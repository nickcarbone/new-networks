"""Download any ITU Operational Bulletins newer than the last one on file.

Tries issue numbers after the newest data/pdftext/<n>.txt until one is not found.
For each new issue: saves the PDF and Word file under work/ob/, converts the PDF to
data/pdftext/<n>.txt. Prints the new issue numbers, one per line, on stdout.

Usage: python3 -I scripts/fetch_bulletins.py <repo_root>
"""
import datetime, os, subprocess, sys, urllib.error, urllib.request

BASE = "https://www.itu.int/dms_pub/itu-t/opb/sp/"
root = sys.argv[1]
txt_dir = os.path.join(root, "data", "pdftext")
work = os.path.join(root, "work", "ob")
os.makedirs(work, exist_ok=True)


def get(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (New Networks gazette)"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
    if not data[:5] == b"%PDF-" and dest.endswith(".pdf"):
        return False
    open(dest, "wb").write(data)
    return True


have = sorted(int(f[:-4]) for f in os.listdir(txt_dir) if f.endswith(".txt"))
n = have[-1] + 1
year = datetime.date.today().year
new = []
while True:
    found = None
    for y in (year, year + 1, year - 1):
        pdf = os.path.join(work, f"T-SP-OB.{n}-{y}-OAS-PDF-E.pdf")
        if get(f"{BASE}T-SP-OB.{n}-{y}-OAS-PDF-E.pdf", pdf):
            found = y
            break
    if not found:
        break
    get(f"{BASE}T-SP-OB.{n}-{found}-OAS-MSW-E.docx", os.path.join(work, f"T-SP-OB.{n}-{found}-OAS-MSW-E.docx"))
    subprocess.run(["pdftotext", "-layout", pdf, os.path.join(txt_dir, f"{n}.txt")], check=True)
    new.append(n)
    n += 1
for x in new:
    print(x)
print(f"newest on file now: {(new or have)[-1]}", file=sys.stderr)
