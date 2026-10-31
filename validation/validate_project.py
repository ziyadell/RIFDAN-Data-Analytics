"""فحص مستقل لمخرجات مشروع RIFDAN: لا يعيد استخدام كود run_analysis.py بل يعيد الاشتقاق من الملف الخام.

التشغيل من جذر المشروع:  python validation/validate_project.py [--baseline-dir مجلد_نسخة_سابقة] [--original-csv مسار_الأصل]
يتطلب الملف الخام في data_raw (انظر data_raw/README.md). يعيد توليد validation/results/filter_cases.json: 60 حالة تصفية بنتائج pandas المتوقعة (بذرة ثابتة 7)
يقرؤها validation/validate_dashboard.cjs؛ ويكتب validation/results/validation_report.json. يخرج برمز 1 إذا فشل أي فحص.
جميع الفحوص تعمل دون مكتبات إضافية خارج متطلبات المشروع."""
import argparse, hashlib, json, random, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--baseline-dir"); ap.add_argument("--original-csv"); args = ap.parse_args()
import shutil, subprocess
CHECKS = []; SKIPPED = []
def check(name, ok, detail=""):
    CHECKS.append(dict(name=name, ok=bool(ok), detail=str(detail))); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
DOW = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]

# ---------- 1) الخام → المنظف (اشتقاق مستقل)
raw_path = next(iter(sorted((ROOT / "data_raw").glob("*.csv"))), None)
if raw_path is None: sys.exit("لم يُعثر على الملف الخام في data_raw؛ انظر data_raw/README.md. وللفحص دون بيانات: python validation/validate_public_release.py")
raw = pd.read_csv(raw_path, dtype=str, encoding="utf-8-sig", keep_default_na=False); raw.columns = [c.strip() for c in raw.columns]
for c in raw.columns: raw[c] = raw[c].str.strip()
amt = pd.to_numeric(raw["Amount"].str.replace(",", "", regex=False), errors="coerce")
exp = raw[amt.notna()].copy(); exp["amount"] = amt[amt.notna()].values
exp["created_at"] = pd.to_datetime(exp["CreationTime"], format="%m/%d/%Y %H:%M")
cl = pd.read_csv(ROOT / "data_clean" / "cleaned_donations.csv", encoding="utf-8-sig", parse_dates=["created_at"])
M = json.loads((ROOT / "outputs" / "metrics.json").read_text(encoding="utf-8"))
D = json.loads((ROOT / "outputs" / "dashboard_data.json").read_text(encoding="utf-8"))
check("الخام: 40,931 سجلاً ومبلغ غير رقمي واحد", len(raw) == 40931 and int(amt.isna().sum()) == 1, f"{len(raw)} / {int(amt.isna().sum())}")
check("المنظف: 40,930 عملية", len(cl) == 40930 == len(exp), len(cl))
check("المنظف: إجمالي المبلغ 1,537,545", abs(cl.amount.sum() - 1537545) < 1e-6 and abs(exp.amount.sum() - 1537545) < 1e-6, cl.amount.sum())
check("المنظف: 1,371 معرّفاً و22 مبادرة", cl.user_id.nunique() == 1371 and cl.initiative.nunique() == 22, f"{cl.user_id.nunique()} / {cl.initiative.nunique()}")
key = ["UserID", "CreationTime", "Title", "Amount", "InitiativeName", "PaymentMethod"]
dup_exp = int(exp.duplicated(subset=key).sum())
check("202 سجلاً مكرراً معلّماً دون حذف", int(cl.is_exact_duplicate.sum()) == dup_exp == 202 and len(cl) == len(exp), dup_exp)
check("التواريخ والمبالغ في المنظف تطابق الاشتقاق المستقل من الخام",
      (np.sort(cl.created_at.values) == np.sort(exp.created_at.values)).all() and (np.sort(cl.amount.values) == np.sort(exp.amount.values)).all())
for col_c, col_r in (("initiative", "InitiativeName"), ("payment_method", "PaymentMethod")):
    a = cl.groupby(col_c).amount.agg(["size", "sum"]).sort_index(); b = exp.groupby(col_r).amount.agg(["size", "sum"]).sort_index()
    check(f"تجميع {col_c} يطابق الخام", a.equals(b))
check("الفترة 2020-12-14 → 2023-07-13", str(cl.created_at.min().date()) == "2020-12-14" and str(cl.created_at.max().date()) == "2023-07-13")
O = M["overview"]
check("metrics.json يطابق إعادة الحساب (العدد والمجموع والمتوسط والوسيط)", O["transactions"] == len(cl) and abs(O["total_amount"] - cl.amount.sum()) < 1e-6 and abs(O["mean"] - cl.amount.mean()) < 1e-9 and O["median"] == cl.amount.median())

# ---------- 2) الحداثة والتوزيعات
REF = cl.created_at.max().normalize() + pd.Timedelta(days=1)
g = cl.groupby("user_id").agg(freq=("amount", "size"), last=("created_at", "max")); g["rec"] = (REF - g["last"]).dt.days
rec = pd.cut(g.rec, [0, 30, 90, 180, 365, np.inf], include_lowest=True).value_counts().sort_index().tolist()
mr = list(M["donors"]["recency_dist"].values())
check("الحداثة: مجموع الفئات = إجمالي المعرفات (1,371)", sum(mr) == 1371 == len(g), sum(mr))
check("الحداثة: الفئة الأولى 446 (تشمل recency = 0)", mr[0] == rec[0] == 446 and mr == rec, f"{mr}")
check("توزيع التكرار والقيمة: المجموع = 1,371", sum(M["donors"]["freq_dist"].values()) == 1371 == sum(M["donors"]["value_dist"].values()))

# ---------- 3) الفصل الزمني لنموذج التنبؤ
P = M["prediction"]; cuts = {k: pd.Timestamp(v) for k, v in P["cutoffs"].items()}; H = pd.Timedelta(days=P["horizon_days"])
check("نقاط القطع 2022-10-16 / 2023-01-14 / 2023-04-14 والأفق 90 يوماً", [P["cutoffs"][k] for k in ("train", "validation", "test")] == ["2022-10-16", "2023-01-14", "2023-04-14"] and P["horizon_days"] == 90)
check("النوافذ متتابعة ولا تتداخل ونافذة الاختبار مكتملة", cuts["train"] + H == cuts["validation"] and cuts["validation"] + H == cuts["test"] and cuts["test"] + H <= cl.created_at.max())
for k, c in cuts.items():
    hist = cl[cl.created_at < c]; users = hist.user_id.unique(); fut = set(cl[(cl.created_at >= c) & (cl.created_at < c + H)].user_id)
    rate = np.mean([u in fut for u in users])
    check(f"{k}: الحجم ونسبة الإيجابيين تطابق إعادة الحساب المستقلة", len(users) == P["sizes"][k] and abs(rate - P["positive_rate"][k]) < 1e-9, f"{len(users)} / {rate:.4f}")
best_val = max(P["validation"], key=lambda m: P["validation"][m]["auc"])
check("النموذج المختار = الأعلى AUC على التحقق فقط", P["chosen_model"] == best_val == P["test"]["model"], best_val)
check("خط الأساس باسم «عدد التبرعات»", P["baseline"]["name"] == "عدد التبرعات")
check("نتائج التحقق منفصلة عن الاختبار", "validation" in P and "test" in P and "auc" in P["test"] and all("auc" in v for v in P["validation"].values()))

# ---------- 4) بيانات اللوحة (المكعبات) تطابق المنظف
dims = D["dims"]; ii = {k: i for i, k in enumerate(dims["initiatives"])}; pi = {k: i for i, k in enumerate(dims["payments"])}; ti = {k: i for i, k in enumerate(dims["titles"])}
d0 = pd.Timestamp(D["meta"]["d0"])
cl["_month"] = (cl.created_at.dt.year - d0.year) * 12 + cl.created_at.dt.month - d0.month
PUB, POOL = dims["titles"][:-1], dims["titles"][-1]; _pubset = set(PUB)
_k = cl.assign(i=cl.initiative.map(ii), p=cl.payment_method.map(pi), t=cl.title.map(ti).fillna(ti[POOL]).astype(int), d=(cl.created_at.dt.dayofweek + 2) % 7, y=cl.created_at.dt.year)
MIN_CELL = D["meta"]["privacy"]["min_cell"]
_k["small_amount"] = _k.groupby(["_month", "i", "p"]).amount.transform("size") < MIN_CELL
_k["small_title"] = _k.groupby(["_month", "t", "i", "p"]).amount.transform("size") < MIN_CELL
_few = _k[_k.small_amount].groupby("y").size().loc[lambda s_: s_ < MIN_CELL].index; _k["hy"] = _k.y.where(~_k.y.isin(list(_few) + [y + 1 for y in _few]), 0); _k["by"] = _k.y.where(_k[_k.small_title].groupby(["y", "t", "i"]).amount.transform("size") >= MIN_CELL, 0)
_same = lambda mine, D_key, names, cols: (lambda d_: len(mine) == len(d_) and (mine.values == d_.values).all())(pd.DataFrame({n: D[D_key][c] for n, c in zip(names, cols)}).sort_values(names[:-1] if names[-1] == "size" else names[:-2]))
A = _k.groupby(["_month", "i", "p"]).amount.agg(["size", "sum"]).reset_index()
check("المكعب A يطابق التجميع الشهري المستقل (كل الصفوف)", _same(A, "A", ["_month", "i", "p", "size", "sum"], ["m", "i", "p", "n", "s"]), len(A))
Hc = _k[~_k.small_amount].groupby(["_month", "d", "hour", "i", "p"]).size().reset_index(name="size")
check("المكعب H يطابق التجميع المستقل (كل الصفوف)", _same(Hc, "H", ["_month", "d", "hour", "i", "p", "size"], ["m", "d", "h", "i", "p", "n"]), len(Hc))
Hy = _k[_k.small_amount].groupby(["hy", "d", "hour"]).size().reset_index(name="size")
check("المكعب HY يطابق التجميع المستقل، ومجموع الساعات محفوظ", _same(Hy.astype(int), "HY", ["hy", "d", "hour", "size"], ["y", "d", "h", "n"]) and sum(D["H"]["n"]) + sum(D["HY"]["n"]) == len(cl), len(Hy))
B = _k[~_k.small_title].groupby(["_month", "t", "i", "p"]).amount.agg(["size", "sum"]).reset_index()
By = _k[_k.small_title].groupby(["by", "t", "i"]).amount.agg(["size", "sum"]).reset_index()
check("المكعبان B وBY يطابقان التجميع المستقل، والمجموع الكلي محفوظ", _same(B, "B", ["_month", "t", "i", "p", "size", "sum"], ["m", "t", "i", "p", "n", "s"]) and _same(By, "BY", ["by", "t", "i", "size", "sum"], ["y", "t", "i", "n", "s"]) and sum(D["B"]["n"]) + sum(D["BY"]["n"]) == len(cl) and abs(sum(D["B"]["s"]) + sum(D["BY"]["s"]) - cl.amount.sum()) < 1e-6, f"{len(B)} / {len(By)}")
_tt = cl.groupby("title").agg(n=("amount", "size"), donors=("user_id", "nunique")); _pr = D["meta"]["privacy"]
_withheld = set(re.findall(r'"([0-9a-f]{64})"', (ROOT / "scripts" / "run_analysis.py").read_text(encoding="utf-8")))
check("الخصوصية: كل عنوان معروض استخدمه 5 معرّفات و5 عمليات فأكثر، ولا عنوان من قائمة الحجب", all(_tt.loc[t, "donors"] >= _pr["min_donors"] and _tt.loc[t, "n"] >= _pr["min_transactions"] for t in PUB) and len(_withheld) == 2 and not any(sha_s in _withheld for sha_s in (hashlib.sha256(t.encode("utf-8")).hexdigest() for t in PUB)), f"{len(PUB)} / {len(_tt)}")
check("الخصوصية: لا تاريخ دقيق في المكعبات، وأنماط الساعة أعداد فقط، وخلايا العناوين والساعات الصغيرة مضمومة إلى السنة", set(D["A"]) == {"m", "i", "p", "n", "s"} and set(D["B"]) == {"m", "t", "i", "p", "n", "s"} and set(D["H"]) == {"m", "d", "h", "i", "p", "n"} and set(D["HY"]) == {"y", "d", "h", "n"} and set(D["BY"]) == {"y", "t", "i", "n", "s"} and min(D["B"]["n"]) >= MIN_CELL and all(n >= MIN_CELL for y, n in zip(D["BY"]["y"], D["BY"]["n"]) if y) and all(v >= MIN_CELL for y, v in pd.Series(D["HY"]["n"]).groupby(pd.Series(D["HY"]["y"])).sum().items() if y))
_hidden = [t for t in _tt.index if t not in _pubset and t not in ii]  # اسم المبادرة المطابق لعنوان ليس تسريباً
_txts = {f: (ROOT / f).read_text(encoding="utf-8") for f in ("outputs/dashboard_data.json", "outputs/metrics.json", "analysis.ipynb", "validation/results/filter_cases.json") if (ROOT / f).exists()}
_leak = {f: sum(json.dumps(t, ensure_ascii=False) in x or f"<td>{t}</td>" in x for t in _hidden) for f, x in _txts.items()}
check("الخصوصية: لا عنوان محجوب كقيمة كاملة في ملفات JSON والدفتر", not any(_leak.values()), {f: v for f, v in _leak.items() if v})
check("أبعاد اللوحة: 22 مبادرة و3 وسائل دفع", len(dims["initiatives"]) == 22 and len(dims["payments"]) == 3)
check(f"اللوحة: التوصيات والخطط ومذكرة الأولوية ({len(D['insights'])} توصيات و{len(D['plans'])} خطط)",
      len(D["insights"]) == len(M["insights"]) and len(D["plans"]) == len(M["action_plans"]) and "الحجم المالي" in D["priority_note"])
check("اللوحة تحمل نفس نتائج النموذج المعتمدة في metrics.json", D["prediction"]["test"]["auc"] == P["test"]["auc"] and D["prediction"]["chosen_model"] == P["chosen_model"])
check("اللوحة: توزيع الحداثة يساوي metrics.json", D["donors"]["recency_dist"] == M["donors"]["recency_dist"])
_nob64 = lambda s: re.sub(r"data:[A-Za-z/+.-]+;base64,[A-Za-z0-9+/=]+", "", s)
ids = set(cl.user_id.astype(str)); alpha_ids = {i for i in ids if re.search(r"[A-Za-z]", i)}
dtxt = (ROOT / "outputs" / "dashboard_data.json").read_text(encoding="utf-8"); tpl = (ROOT / "outputs" / "dashboard" / "RIFDAN_Dashboard.html").read_text(encoding="utf-8")
toks = lambda t: set(re.findall(r"(?<![A-Za-z0-9_])[A-Za-z0-9]{4}(?![A-Za-z0-9_])", t))
check("لا طوابع زمنية بالدقيقة في ملفات JSON", not re.search(r"20\d\d-\d\d-\d\d[ T]\d\d:\d\d", dtxt + (ROOT / "outputs" / "metrics.json").read_text(encoding="utf-8")))
check("لا معرّفات متبرعين (تحتوي حروفاً) في بيانات اللوحة وقالبها", not (alpha_ids & toks(dtxt)) and not (alpha_ids & toks(_nob64(tpl))) and "user_id" not in dtxt and "UserID" not in dtxt)

# ---------- 5) 60 حالة تصفية مستقلة لفحص منطق JavaScript
rng = random.Random(7); case_list = []
_months = [str(x) for x in pd.period_range(cl.created_at.min(), cl.created_at.max(), freq="M")]; _mi = {m: i for i, m in enumerate(_months)}
_yr = {y: (min(i for i, m in enumerate(_months) if m[:4] == str(y)), max(i for i, m in enumerate(_months) if m[:4] == str(y))) for y in sorted({int(m[:4]) for m in _months})}
def mk(f, t, year="all", ini=-1, pay=-1): return dict(from_ym=f, to_ym=t, year=year, ini=ini, pay=pay)
_a, _z = _months[0], _months[-1]
specs = [mk(_a, _z)]
specs += [mk(_a, _z, year=str(y)) for y in (2021, 2022, 2023)]
specs += [mk(_a, _z, ini=i) for i in (0, 3, 11, 21)] + [mk(_a, _z, pay=p) for p in (0, 1, 2)]
specs += [mk("2021-02", "2021-02"), mk("2022-04", "2022-04"), mk("2023-07", "2023-07")]
while len(specs) < 60:
    a, b = sorted(rng.sample(range(len(_months)), 2))
    y = rng.choice(["all", "all", "all", "2021", "2022", "2023"])
    specs.append(mk(_months[a], _months[b], year=y, ini=rng.choice([-1, -1, -1] + list(range(8)) + [rng.randrange(22)]), pay=rng.choice([-1, -1, 0, 1, 2])))
cl["_small_amount"] = _k.small_amount; cl["_small_title"] = _k.small_title; cl["_hy"] = _k.hy; cl["_by"] = _k.by
for k, sp in enumerate(specs):
    mf, mt = _mi[sp["from_ym"]], _mi[sp["to_ym"]]
    m = cl._month.between(mf, mt)
    if sp["year"] != "all": m &= cl.year == int(sp["year"])
    if sp["ini"] >= 0: m &= cl.initiative == dims["initiatives"][sp["ini"]]
    if sp["pay"] >= 0: m &= cl.payment_method == dims["payments"][sp["pay"]]
    # الخلايا الصغيرة مضمومة إلى السنة: تدخل عند شمول السنة كاملة في النطاق فقط
    ycov = {y for y, (a, b) in _yr.items() if mf <= a and mt >= b and (sp["year"] == "all" or int(sp["year"]) == y)}
    if sp["year"] == "all" and mf == 0 and mt == len(_months) - 1: ycov = ycov | {0}
    in_y = cl._hy.isin(ycov)
    in_y_t = cl._by.isin(ycov)
    if sp["ini"] >= 0: in_y_t = in_y_t & (cl.initiative == dims["initiatives"][sp["ini"]])
    h_rows = (m & ~cl._small_amount) | (cl._small_amount & in_y & (sp["ini"] < 0) & (sp["pay"] < 0))
    t_rows = ((m & ~cl._small_title) | (cl._small_title & in_y_t & (sp["pay"] < 0))) & cl.title.isin(_pubset)
    sp_t = cl[t_rows]
    s = cl[m]; heat = cl[h_rows].pivot_table(index="day_of_week", columns="hour", values="amount", aggfunc="size", fill_value=0).reindex(index=DOW, columns=range(24), fill_value=0)
    iS = s.groupby("initiative").amount.sum().reindex(dims["initiatives"], fill_value=0); iN = s.groupby("initiative").size().reindex(dims["initiatives"], fill_value=0)
    pN = s.groupby("payment_method").size().reindex(dims["payments"], fill_value=0)
    tt = sp_t.groupby("title").amount.agg(["size", "sum"]).reset_index().sort_values(["sum", "title"], ascending=[False, True]).head(5)
    case_list.append(dict(id=k, filters=sp, n=int(len(s)), s=float(s.amount.sum()), heat=heat.values.tolist(), init_s=iS.tolist(), init_n=iN.tolist(), pay_n=pN.tolist(),
                          top_initiative=(int(np.argmax(iS.values)) if len(s) else None), distinct_titles=int(sp_t.title.nunique()),
                          titles=[dict(t=r.title, n=int(r["size"]), s=float(r["sum"])) for _, r in tt.iterrows()]))
out = ROOT / "validation" / "results"; out.mkdir(parents=True, exist_ok=True)
(out / "filter_cases.json").write_text(json.dumps(dict(seed=7, cases=case_list), ensure_ascii=False), encoding="utf-8")
check("توليد 60 حالة تصفية بنتائج pandas المتوقعة", len(case_list) == 60 and any(c["n"] == 0 for c in case_list), f"{sum(c['n']==0 for c in case_list)} حالات فارغة")

# ---------- 6أ) الداشبورد: ملف واحد مكتفٍ ذاتياً ببيانات مطابقة وشعار مضمّن
import base64, struct
_dash = (ROOT / "outputs" / "dashboard" / "RIFDAN_Dashboard.html").read_text(encoding="utf-8")
_m = re.search(r'<img class="logo" id="logo" src="data:image/png;base64,([A-Za-z0-9+/=]+)"', _dash)
_png = base64.b64decode(_m.group(1)) if _m else b""
_w, _h = struct.unpack(">II", _png[16:24]) if _png[:8] == b"\x89PNG\r\n\x1a\n" else (0, 0)
check("الداشبورد: الشعار مضمّن مرة واحدة بصيغة Data URI (1254×1254 بقناة شفافية)، ويُشتق منه الـ Favicon",
      len(re.findall(r'<img class="logo" id="logo" src="data:image/png;base64,', _dash)) == 1 and (_w, _h) == (1254, 1254)
      and _png[25] == 6 and 'l.href=document.getElementById("logo").src' in _dash)
_markup = _dash[:_dash.index("<script>", _dash.index("</main></div>"))]  # الواجهة دون مصدر Plotly المصغّر
check("الداشبورد: ملف واحد مكتفٍ ذاتياً بلا مراجع خارجية، ومكتبة Plotly مضمّنة",
      not re.findall(r'(?:src|href)="(?!data:|#|https?:)[^"]+"', _markup) and "plotly.js v" in _dash)
_ds = _dash.index("const D=", _dash.index("</main></div>")) + len("const D=")
_, _dl = json.JSONDecoder().raw_decode(_dash[_ds:])
check("الداشبورد: البيانات المضمّنة مطابقة لملف dashboard_data.json حرفياً", _dash[_ds:_ds + _dl] == dtxt.replace("</", "<\\/"))
_dash_ins = json.JSONDecoder().raw_decode(_dash[_ds:])[0]["insights"]
check("الداشبورد والتقرير وREADME وmetrics متفقة على عدد التوصيات",
      len(_dash_ins) == len(M["insights"]) and f"{len(M['insights'])} recommendations" in (ROOT / "README.md").read_text(encoding="utf-8"))
_pdf = (ROOT / "report" / "executive_summary.pdf").read_bytes()
import unicodedata
pdf_text = unicodedata.normalize("NFKC", subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(ROOT / "report" / "executive_summary.pdf"), "-"],
                                 capture_output=True, encoding="utf-8", errors="replace").stdout) if shutil.which("pdftotext") else ""
if not pdf_text: SKIPPED.append("فحص نص التقرير (أداة pdftotext غير متوفرة)")
check("التقرير: الشعار مضمّن بأبعاده الأصلية 1254×1254", b"/Width 1254" in _pdf and b"/Height 1254" in _pdf)
_readme_assets = {"assets/dashboard-preview.png"}  # لقطة الداشبورد المعروضة في README هي الاستثناء الوحيد
_pngs = sorted(x for x in (str(f.relative_to(ROOT)).replace("\\", "/") for f in ROOT.rglob("*.png") if "node_modules" not in f.parts) if x not in _readme_assets)
check("لا نسخة ملف صورة للشعار: كل ملفات PNG هي رسوم outputs/figures",
      len(_pngs) == len(list((ROOT / "outputs/figures").glob("*.png"))) and all(x.startswith("outputs/figures/") for x in _pngs),
      "؛ ".join(x for x in _pngs if not x.startswith("outputs/figures/")))

# ---------- 6أ-1) الاتساق الإملائي لاسم وسيلة الدفع في مخرجات العرض
check("العرض: «أبل باي» مكتوبة بالياء في الداشبورد والتقرير، مع بقاء البيانات بإملاء المصدر",
      "replace(/أبل باى/g,'أبل باي')" in _dash and "أبل باى" in dtxt
      and (not pdf_text or ("أبل باى" not in pdf_text and "أبل باي" in pdf_text)))

def _strip_b64(s):
    """يتجاهل البيانات المضمَّنة بصيغة Base64 (الصور داخل الدفتر وروابط البيانات) قبل فحص النص."""
    s = re.sub(r"data:[A-Za-z/+.-]+;base64,[A-Za-z0-9+/=]+", "", s)
    return re.sub(r"[A-Za-z0-9+/]{120,}={0,2}", "", s)
# ---------- 6أ-2) العملة: الريال السعودي (ر.س) فقط في كل الملفات النصية
_bad = re.compile(r"USD|دولار|يورو|\bEUR\b|€|£|درهم|جنيه|دينار|\d\s?\$|\$\s?\d|وحدة المبلغ غير موثقة|\d\s+وحدات")
_scan = [f for pat in ("*.md", "outputs/*.json", "scripts/*.py") for f in ROOT.glob(pat)] + [ROOT / "analysis.ipynb"]
_found = [f"{f.relative_to(ROOT)}: {m.group(0)}" for f in _scan for m in [_bad.search(_strip_b64(f.read_text(encoding="utf-8")))] if m]  # يُستثنى نص Base64 للشعار
check("العملة: لا إشارة إلى عملة غير الريال السعودي ولا إلى «وحدات» أو «وحدة غير موثقة» للمبالغ في الملفات النصية", not _found, "؛ ".join(_found))
_unit_files = ["README.md", "scripts/run_analysis.py", "scripts/build_report.py", "outputs/metrics.json"]
check("العملة: وحدة «ر.س» حاضرة في README والتحليل والتقرير والداشبورد والمخرجات", all("ر.س" in (ROOT / f).read_text(encoding="utf-8") for f in _unit_files))

# ---------- 6ب) الدفتر ≡ السكربت، ونسخ HTML ≡ Markdown، وروابط README وهيكلته
nbp = ROOT / "analysis.ipynb"; src = (ROOT / "scripts" / "run_analysis.py").read_text(encoding="utf-8")
norm = lambda s: s.replace("\r\n", "\n").strip()
src_code = [norm(c.partition("\n")[2]) for c in re.split(r"(?m)^# %%", src)[1:] if "[markdown]" not in c.partition("\n")[0]]
nb = json.loads(nbp.read_text(encoding="utf-8")); nb_code = [c for c in nb["cells"] if c["cell_type"] == "code"]
nb_src = [norm("".join(c["source"])) for c in nb_code]
check("الدفتر: خلايا الكود (عدا خلية تثبيت المكتبات الأولى) تطابق مقاطع scripts/run_analysis.py حرفياً", nb_src[1:] == src_code, f"{len(nb_src) - 1} خلية / {len(src_code)} مقطعاً")
check("الدفتر: النتائج محفوظة (كل خلايا الكود منفّذة ولها ترقيم تنفيذ، ومعظمها يحمل مخرجات)",
      all(c.get("execution_count") for c in nb_code) and sum(bool(c.get("outputs")) for c in nb_code) >= len(nb_code) // 2 and not any(o.get("output_type") == "error" for c in nb_code for o in c.get("outputs", [])),
      f"{sum(bool(c.get('outputs')) for c in nb_code)}/{len(nb_code)} خلية بمخرجات")
check("الدفتر: لا مسارات أجهزة محلية في المخرجات المحفوظة", not re.search(r"/home/|/Users/|C:\\\\Users", json.dumps(nb, ensure_ascii=False)))
rd0 = (ROOT / "README.md").read_text(encoding="utf-8"); badl = []
for u in re.findall(r"\]\(([^)\s]+)\)", rd0):
    if re.match(r"(https?:|mailto:|#)", u): continue
    if not (ROOT / u.split("#")[0]).exists(): badl.append(u)
check("README: كل الروابط النسبية تشير إلى ملفات موجودة", not badl, "؛ ".join(badl))
stack, tree_bad, tree_n = [], [], 0
for ln in re.search(r"```\n(RIFDAN-Data-Analytics/.*?)```", rd0, re.S).group(1).splitlines()[1:]:
    m = re.match(r"^([│ ]*)[├└]── (\S+)", ln)
    if not m: continue
    depth = len(m.group(1)) // 4; name = m.group(2); stack = stack[:depth] + [name.rstrip("/")]; tree_n += 1
    if not (ROOT / Path(*stack)).exists(): tree_bad.append("/".join(stack))
check("README: كل مسار في «بنية المشروع» موجود فعلاً (لا أسماء ملفات غير موجودة)", tree_n >= 20 and not tree_bad, f"{tree_n} مسارا؛ مفقود: {tree_bad[:4]}")
check("README: لا إشارة إلى data_raw/README.txt المدمج في README", "data_raw/README.txt" not in rd0)


import ast
_map = {"sklearn": "scikit-learn", "bidi": "python-bidi", "arabic_reshaper": "arabic-reshaper"}
_req = {re.split(r"[<>=!~\s\[]", ln.strip(), maxsplit=1)[0].lower().replace("_", "-") for ln in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.lstrip().startswith("#")}
_imp = set()
for f in (ROOT / "scripts").glob("*.py"):
    _tree = ast.parse(f.read_text(encoding="utf-8")); _opt = {id(x) for tn in ast.walk(_tree) if isinstance(tn, ast.Try) for bn in tn.body for x in ast.walk(bn)}  # الاستيراد الاختياري داخل try لا يُعدّ مطلوباً
    for n in ast.walk(_tree):
        if id(n) in _opt: continue
        if isinstance(n, ast.Import): _imp |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module: _imp.add(n.module.split(".")[0])
_need = {_map.get(m, m).lower() for m in _imp if m not in sys.stdlib_module_names and m not in {f.stem for f in (ROOT / "scripts").glob("*.py")}}
check("requirements.txt: يضم كل مكتبة خارجية تستوردها سكربتات scripts/", _need <= _req, f"ينقص: {sorted(_need - _req)}")
check("README: يشير إلى requirements.txt ولا يزعم غيابه", "`requirements.txt`" in rd0 and "لا يوجد `requirements.txt`" not in rd0)
_extras = [str(f.relative_to(ROOT)) for pat in ("*.md", "scripts/*", "validation/*.cjs", "validation/package.json") for f in ROOT.glob(pat) if f.is_file() and re.search(r"الحزمة الإضافية|RIFDAN-development-extras|make_notebook", f.read_text(encoding="utf-8", errors="ignore"))]
check("لا ذكر لحزمة إضافية أو أداة خارج الحزمة في ملفات المشروع", not _extras, "؛ ".join(_extras))

# ---------- 7) اتساق التوثيق مع النتائج
rd = (ROOT / "README.md").read_text(encoding="utf-8")
need = ["40,930", "1,537,545", "1,371", "202", f"{P['test']['auc']:.3f}", f"{P['baseline']['test_auc']:.3f}", f"{P['validation']['Logistic Regression']['auc']:.3f}"]
check("README يذكر الأرقام الأساسية ونتائج النموذج بنفس قيم metrics.json", all(x in rd for x in need), [x for x in need if x not in rd])

# ---------- 7ب) سلامة تحليل البقاء ونموذج Cox
SV, CX, CH, VZ = M["survival"], M["cox"], M["cohorts"], M["value_sizing"]
check("البقاء: الفوج = من عاد + من بقي مراقَباً", SV["cohort"] == SV["returned"] + SV["censored"],
      f"{SV['cohort']} ≠ {SV['returned']}+{SV['censored']}")
_curve = [c["survival"] for c in SV["curve"]]
check("البقاء: منحنى كابلان-ماير غير متزايد ومحصور بين صفر وواحد",
      all(_curve[i] >= _curve[i + 1] - 1e-12 for i in range(len(_curve) - 1)) and all(0 <= v <= 1 for v in _curve))
def _surv_at(curve, t):
    v = [c["survival"] for c in curve if c["day"] <= t]
    return v[-1] if v else 1.0
check("البقاء: معدلات العودة المعلنة مطابقة للمنحنى المحفوظ",
      all(abs((1 - _surv_at(SV["curve"], int(h))) * 100 - r) < 1e-6 for h, r in SV["return_rate_pct"].items()))
check("البقاء: كل مجموعة مقارَنة لا تقل عن 30 معرّفاً",
      all(l["n"] >= 30 for g in SV["groups"] for l in g["levels"]))
check("البقاء: قيم p لاختبارات Log-rank داخل المجال الصحيح",
      all(t["p_value"] is None or 0 <= t["p_value"] <= 1 for t in SV["tests"].values()))
check("Cox: نسبة الخطر داخل فاصل الثقة لكل عامل",
      all(t["ci95"][0] <= t["hazard_ratio"] <= t["ci95"][1] for t in CX["terms"]),
      [t["term"] for t in CX["terms"] if not (t["ci95"][0] <= t["hazard_ratio"] <= t["ci95"][1])])
check("Cox: وسم الدلالة متسق مع استبعاد فاصل الثقة للواحد",
      all(t["significant"] == (t["ci95"][1] < 1 or t["ci95"][0] > 1) for t in CX["terms"]),
      [t["term"] for t in CX["terms"] if t["significant"] != (t["ci95"][1] < 1 or t["ci95"][0] > 1)])
check("Cox: فئة المرجع ليست ضمن معاملات النموذج",
      not any(t["term"] == "ini_" + CX["reference"]["ini"] for t in CX["terms"]))
check("الأفواج: كل فوج شهري معروض لا يقل عن 30 معرّفاً، والنسب بين صفر ومئة",
      all(m["donors"] >= 30 and 0 <= m["return_30d_pct"] <= 100 for m in CH["months"]))
check("التقدير المالي: الحد الأدنى لا يتجاوز الأعلى وكلاهما موجب",
      0 < VZ["lower_bound_sar"] <= VZ["upper_bound_sar"])
_dash_keys = json.JSONDecoder().raw_decode(_dash[_ds:])[0]
check("الداشبورد: صفحة زمن العودة موجودة ببياناتها (بقاء وCox وأفواج وتقدير مالي)",
      'data-p="p6"' in _dash and 'id="p6"' in _dash and "renderSurvival" in _dash
      and all(k in _dash_keys for k in ("survival", "cox", "cohorts", "value_sizing")))
check("التقرير وREADME يذكران نتيجة ضبط المربِكات بنموذج Cox",
      "Cox" in rd0 and ("Cox" in pdf_text or not pdf_text))

# ---------- 7ج) شجرة الملفات في README تطابق محتوى الحزمة فعلياً
_tree = re.search(r"## Repository structure\s*```(.*?)```", rd0, re.S)
if not _tree:
    SKIPPED.append("مطابقة شجرة الملفات (لم يُعثر على القسم في README)")
else:
    _listed = set()
    for _ln in _tree.group(1).splitlines():
        _nm = re.sub(r"^[\s│├└─]+", "", _ln).strip()
        if _nm and not _nm.endswith("RIFDAN-Data-Analytics/"):
            _listed.add(_nm.rstrip("/"))
    _IGN = {"__pycache__", "results", "node_modules", ".ipynb_checkpoints", ".git", "package-lock.json"}
    _actual = set()
    for _f in ROOT.rglob("*"):
        _rel = _f.relative_to(ROOT)
        if any(x in _IGN for x in _rel.parts) or _f.suffix in {".pyc", ".log", ".csv"}:
            continue
        if _f.is_file():
            _actual.add(_f.name)
            _actual.add(_rel.parts[0].rstrip("/"))
    _missing = sorted(x for x in _actual if x not in _listed)
    check("README: شجرة ملفات المشروع تذكر كل ملف موجود فعلاً", not _missing, _missing[:8])

# ---------- 8) مقارنة بايتية (اختيارية)
if args.original_csv: check("الملف الخام يطابق الأصل المرفوع بايتاً ببايت", sha(raw_path) == sha(args.original_csv), sha(raw_path)[:16])
if args.baseline_dir:
    bd = Path(args.baseline_dir)
    check("الملف الخام يطابق النسخة السابقة بايتاً ببايت", sha(raw_path) == sha(next(iter(sorted((bd / "data_raw").glob("*.csv"))))))
    check("الملف المنظف يطابق النسخة السابقة بايتاً ببايت", sha(ROOT / "data_clean" / "cleaned_donations.csv") == sha(bd / "data_clean" / "cleaned_donations.csv"))

res = dict(passed=sum(c["ok"] for c in CHECKS), total=len(CHECKS), skipped=SKIPPED, checks=CHECKS, raw_sha256=sha(raw_path), cleaned_sha256=sha(ROOT / "data_clean" / "cleaned_donations.csv"))
(out / "validation_report.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n{res['passed']}/{res['total']} فحصاً ناجحاً" + (f" | تخطّي {len(SKIPPED)}: " + "؛ ".join(SKIPPED) if SKIPPED else "")); sys.exit(0 if res["passed"] == res["total"] else 1)
