"""فحص جاهزية المستودع العام: يعمل دون البيانات الخام، ولا يطبع أي معرّف متبرع.

التشغيل من جذر المشروع:  python validation/validate_public_release.py [--raw مسار_الملف_الخام.csv]
دون --raw يفحص البنية والتراخيص وبنية المخرجات. ومع --raw يضيف بحثاً نصياً عن كل معرّف في الملفات المنشورة.
لا يقرأ هذا الفحص الصور (PNG وصور الدفتر وصور PDF)؛ فهذه تحتاج مراجعة بصرية. ويخرج برمز 1 إذا فشل أي فحص."""
import argparse, csv, json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--raw"); args = ap.parse_args()
sys.stdout.reconfigure(encoding="utf-8")
CHECKS, SKIPPED = [], []
def check(name, ok, detail=""):
    CHECKS.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
def skip(name, why):
    SKIPPED.append(name); print(f"SKIP {name}  [{why}]")
read = lambda rel: (ROOT / rel).read_text(encoding="utf-8")
DATASET_URL = "https://open.data.gov.sa/ar/datasets/view/cc3b177a-5e5d-4845-bb92-6119b1322b05"
TABULAR = {".csv", ".tsv", ".xls", ".xlsx", ".xlsm", ".ods", ".parquet", ".feather", ".pkl", ".pickle", ".sqlite", ".sqlite3", ".db"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".ipynb_checkpoints"}

# ---------- 1) الملفات التي ستُنشر
in_git = shutil.which("git") and subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True).returncode == 0
if in_git:
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    published = [ROOT / p for p in listed.split("\0") if p]
else:
    published = [f for f in ROOT.rglob("*") if f.is_file() and not SKIP_DIRS & set(f.relative_to(ROOT).parts)]
rel = lambda f: f.relative_to(ROOT).as_posix()
tabular = [rel(f) for f in published if f.suffix.lower() in TABULAR]
local_only = [x for x in tabular if not in_git and x.startswith(("data_raw/", "data_clean/"))]
check("لا ملفات بيانات جدولية ضمن ما سيُنشر", not set(tabular) - set(local_only), sorted(set(tabular) - set(local_only))[:5])
if local_only: print(f"INFO {len(local_only)} ملف CSV محلي في data_raw/data_clean يتجاهله .gitignore")
big = [rel(f) for f in published if f.stat().st_size > 50 * 1024 * 1024]
check("لا ملف يتجاوز 50 ميجابايت", not big, big)

ignore = read(".gitignore")
check(".gitignore يحظر مجلدي البيانات وملفات CSV والملفات المؤقتة", all(p in ignore for p in ("data_raw/*", "data_clean/*", "*.csv", "__pycache__/", "node_modules/", ".ipynb_checkpoints/", ".env")))
if in_git:
    sample = ["data_raw/x.csv", "data_clean/cleaned_donations.csv", "outputs/copy.csv", "report/other.pdf", "report/deck.pptx", "project_usage_log.md", "scripts/__pycache__/a.pyc", "validation/node_modules/a.js"]
    missed = [p for p in sample if subprocess.run(["git", "check-ignore", "-q", "--no-index", p], cwd=ROOT).returncode != 0]
    kept = [p for p in ("data_raw/README.md", "data_raw/LICENSE_NOTICE.txt", "data_clean/LICENSE_NOTICE.txt", "report/executive_summary.pdf") if subprocess.run(["git", "check-ignore", "-q", "--no-index", p], cwd=ROOT).returncode == 0]
    check("قواعد .gitignore تعمل فعلياً في git", not missed and not kept, missed + kept)
else:
    skip("قواعد .gitignore في git", "المجلد ليس مستودع git بعد")

# ---------- 2) التراخيص والإسناد
for f in ("data_license/Open_Data_License_Ar.pdf", "data_license/ATTRIBUTION_AR.md", "data_raw/LICENSE_NOTICE.txt", "data_clean/LICENSE_NOTICE.txt", "data_raw/README.md"):
    check(f"موجود: {f}", (ROOT / f).is_file())
ofl = read("fonts/LICENSE_OFL.txt")
sections = ["SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007", "PREAMBLE", "DEFINITIONS", "PERMISSION & CONDITIONS", "TERMINATION", "DISCLAIMER", "Reserved Font Name"]
conditions = ["1) Neither the Font Software", "2) Original or Modified Versions", "3) No Modified Version", "4) The name(s) of the Copyright Holder(s)", "5) The Font Software, modified or unmodified"]
check("الخطوط: نص رخصة OFL 1.1 كامل بأقسامه وشروطه الخمسة وإشعار IBM", all(s in ofl for s in sections + conditions) and "IBM Corp." in ofl)
import base64, hashlib
FONT = {w: (ROOT / "fonts" / f"IBMPlexSansArabic-{w}.ttf").read_bytes() for w in ("Regular", "Bold")}
fonts_doc = read("fonts/README.md")
check("الخطوط: ملفا IBM Plex Sans Arabic يطابقان بصمات النسخ الرسمية الموثقة", all(hashlib.sha256(b).hexdigest() in fonts_doc for b in FONT.values()))
mit = read("LICENSE")
check("الرخصة: ملف MIT بصيغته القياسية", mit.startswith("MIT License\n\nCopyright (c) ") and "Permission is hereby granted" in mit and "Scope" not in mit)
_scope = read("README.md"); _scope = _scope[_scope.index("## Licensing"):]
check("الرخصة: README يحدد نطاق MIT ويحفظ رخص الأطراف الأخرى", all(x in _scope for x in ("eligible original project code", "no ownership of third-party material is claimed", "Saudi Open Data License", "SIL Open Font License", "Plotly", "RIFDAN name and logo")))
readme = read("README.md")
check("README: الإسناد ورابط المصدر وشرح الحصول على البيانات", DATASET_URL in readme and "ODC Attribution License" in readme and "data_raw/README.md" in readme)
dash = read("outputs/dashboard/RIFDAN_Dashboard.html")
check("الداشبورد: رابط مصدر البيانات موجود", DATASET_URL in dash)
LICENSE_URL = "https://open.data.gov.sa/ar/pages/policies/license"
check("الإشعار (البند 6.2): رابط نص الرخصة في README والداشبورد ومصدر التقرير", all(LICENSE_URL in x for x in (read("README.md"), dash, read("scripts/build_report.py"), read("data_license/ATTRIBUTION_AR.md"))))
check("الداشبورد: عنوان التبويب", "<title>RIFDAN | لوحة التحليلات</title>" in dash)
check("الداشبورد: الخطان مضمّنان دون تعديل", all(base64.b64encode(b).decode() in dash for b in FONT.values()))

# ---------- 3) خلو المخرجات من أعمدة أو بنى على مستوى المتبرع
data_txt = read("outputs/dashboard_data.json")
start = dash.index("const D=", dash.index("</main></div>")) + len("const D=")
_, length = json.JSONDecoder().raw_decode(dash[start:])
check("الداشبورد: البيانات المضمّنة مطابقة لملف dashboard_data.json", dash[start:start + length] == data_txt.replace("</", "<\\/"))
check("الداشبورد: لا حقل معرّف متبرع", not re.search(r"user_?id", data_txt, re.I) and not re.search(r"user_?id", dash[start:start + length], re.I))
_D = json.loads(data_txt)
check("الخصوصية: لا تاريخ يومي في المكعبات، وأنماط الساعة أعداد فقط", set(_D["A"]) == {"m", "i", "p", "n", "s"} and set(_D["B"]) == {"m", "t", "i", "p", "n", "s"} and set(_D["H"]) == {"m", "d", "h", "i", "p", "n"} and set(_D["HY"]) == {"y", "d", "h", "n"} and set(_D["BY"]) == {"y", "t", "i", "n", "s"})
check("الخصوصية: خلايا العناوين الصغيرة مضمومة إلى السنة أو كامل الفترة", min(_D["B"]["n"]) >= _D["meta"]["privacy"]["min_cell"] >= 3 and all(n >= 3 for y, n in zip(_D["BY"]["y"], _D["BY"]["n"]) if y))
check("الخصوصية: لا طوابع زمنية بالدقيقة في JSON والدفتر", not re.search(r"202[0-3]-\d\d-\d\d[ T]\d\d:\d\d", data_txt + read("outputs/metrics.json") + re.sub(r'"image/png": "[^"]*"', "", read("analysis.ipynb"))))
check("الخصوصية: العناوين المعروضة مطابقة لقاعدة الحد الأدنى المعلنة", _D["meta"]["privacy"]["public_titles"] == len(_D["dims"]["titles"]) - 1 and _D["meta"]["privacy"]["min_donors"] >= 5)

D, M = json.loads(data_txt), json.loads(read("outputs/metrics.json"))
donors = M["donors"]["observed_donors"]
def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path + "/" + str(k), k, v
            yield from walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        yield path, None, o
        for v in o: yield from walk(v, path + "[]")
for name, obj in (("metrics.json", M), ("dashboard_data.json", D), ("filter_cases.json", json.loads(read("validation/results/filter_cases.json")))):
    nodes = list(walk(obj))
    idlike = [p for p, k, v in nodes if k and re.search(r"user|donor_?id", str(k), re.I) and not isinstance(v, (int, float))]
    # قيم هذه الحقول أعداد فقط (عدد المعرّفات أو القيم المفقودة) ولا تحوي معرّفاً.
    perdonor = [p for p, k, v in nodes if isinstance(v, list) and len(v) == donors]
    check(f"{name}: لا حقول معرّفات نصية ولا مصفوفات بطول عدد المتبرعين", not idlike and not perdonor, (idlike + perdonor)[:4])

nb = json.loads(read("analysis.ipynb"))
outs = [o for c in nb["cells"] for o in c.get("outputs", [])]
texts = []
for o in outs:
    if "text" in o: texts.append("".join(o["text"]))
    for mt, v in o.get("data", {}).items():
        if mt.startswith("text/"): texts.append("".join(v) if isinstance(v, list) else str(v))
tables = [t for t in texts if re.search(r"<th>UserID</th>", t)]
rows_ok = all(all(cell == "***" for cell in re.findall(r"<th>\d+</th>\s*<td>(.*?)</td>", t, re.S)) for t in tables)
check("الدفتر: عمود UserID في الجداول المحفوظة مقنّع بالكامل", tables and rows_ok, f"{len(tables)} جدول")
_mask_ok = all(len(re.findall(r"<td>\*\*\*</td>", t_)) == 3 * len(re.findall(r"<th>\d+</th>", t_)) for t_ in tables)
check("الدفتر: الوقت الدقيق والعنوان مقنّعان في الصفوف المعروضة", _mask_ok)
check("الدفتر: لا مسارات أجهزة محلية ولا أخطاء محفوظة", not re.search(r"/home/|/Users/|[A-Za-z]:\\\\Users|/content/", "\n".join(texts)) and not any(o.get("output_type") == "error" for o in outs))

# ---------- 4) بحث نصي عن المعرّفات (يتطلب الملف الخام محلياً)
if args.raw:
    with open(args.raw, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    col = next(c for c in rows[0] if c.strip() == "UserID")
    ids = {r[col].strip() for r in rows}
    alpha = {i for i in ids if re.search(r"[A-Za-z]", i)}; digit = ids - alpha
    token = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9]{4}(?![A-Za-z0-9_])")
    clean = lambda s: re.sub(r"[A-Za-z0-9+/]{120,}={0,2}", "", re.sub(r"data:[A-Za-z/+.-]+;base64,[A-Za-z0-9+/=]+", "", s))
    plotly_end = dash.index("</script>", dash.index("plotly.js v"))
    sources = {"analysis.ipynb (النص والمخرجات)": "\n".join(texts + ["".join(c["source"]) for c in nb["cells"]]), "RIFDAN_Dashboard.html (دون مكتبة Plotly)": dash[:dash.index("plotly.js v")] + dash[plotly_end:]}
    for f in published:
        if f.suffix in {".json", ".md", ".txt", ".py", ".cjs"} and not f.parent.name.startswith("data_"): sources[rel(f)] = f.read_text(encoding="utf-8")
    try:
        import pymupdf
        for f in published:
            if f.suffix == ".pdf": sources[rel(f)] = "\n".join(p.get_text() for p in pymupdf.open(f))
    except ImportError:
        skip("نص ملفات PDF", "مكتبة pymupdf غير مثبتة")
    hits = {k: sum(t in alpha for t in token.findall(clean(v))) for k, v in sources.items()}
    check(f"لا أي من {len(alpha):,} معرّفاً يحتوي حروفاً في {len(sources)} مصدراً نصياً", not any(hits.values()), {k: v for k, v in hits.items() if v})
    strings = [v for o in (M, D) for _, _, v in walk(o) if isinstance(v, str)]
    check(f"لا أي من {len(digit)} معرّفاً رقمياً كقيمة نصية مستقلة في JSON", not any(s.strip() in digit for s in strings))
    print(f"INFO المعرّفات الرقمية ({len(digit)}) أرقام من 4 خانات قد تطابق مبالغ أو فهارس صدفةً؛ لذا تُراجع تطابقاتها في سياقها.")
else:
    skip("البحث النصي عن المعرّفات", "مرّر --raw بعد تنزيل الملف الخام")

print(f"\n{sum(CHECKS)}/{len(CHECKS)} فحصاً ناجحاً" + (f" | تخطّي {len(SKIPPED)}: " + "؛ ".join(SKIPPED) if SKIPPED else ""))
print("خارج نطاق هذا الفحص: الصور والرسوم، وتحتاج مراجعة بصرية.")
sys.exit(0 if all(CHECKS) else 1)
