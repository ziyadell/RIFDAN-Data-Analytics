"""Build report/executive_summary.pdf (eight pages) from outputs/metrics.json and outputs/figures.

Usage (from the project root): python scripts/build_report.py
Font: IBM Plex Sans Arabic when a fonts/ folder is present, otherwise DejaVu Sans.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtl_pdf import *
import base64, io, re
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Image, PageBreak, KeepTogether, Table, TableStyle, Spacer

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "outputs" / "metrics.json").read_text(encoding="utf-8")); FIG = ROOT / "outputs" / "figures"
register()
f = lambda x, d=0: f"{x:,.{d}f}"
o, d, q, a, dup = M["overview"], M["donors"], M["quality_before"], M["quality_after"], M["duplicates"]
ini, pay, seg, pred, INS, PLANS = M["initiatives"], M["payments"], M["segmentation"], M["prediction"], M["insights"], M["action_plans"]
pk = M["peak_window"]; top_i = ini[0]; rec = next(i for i in ini if i["initiative"] == "التبرع الدوري")
URL = "https://open.data.gov.sa/ar/datasets/view/cc3b177a-5e5d-4845-bb92-6119b1322b05"
NAME = "A sample of donations for different IDs in Ehsan"
NOTICE = f"يحتوي هذا العمل على معلومات من مجموعة البيانات «{NAME}» المنشورة في منصة البيانات المفتوحة السعودية ({URL}) والمتاحة بموجب رخصة البيانات المفتوحة (ODC Attribution License: https://open.data.gov.sa/ar/pages/policies/license)، النسخة 2.0."
def logo_flowable(size=50):
    """Logo read from the data URI embedded in the dashboard, so the project holds no separate image file."""
    html = (ROOT / "outputs" / "dashboard" / "RIFDAN_Dashboard.html").read_text(encoding="utf-8")
    m = re.search(r'<img class="logo" id="logo" src="data:image/png;base64,([A-Za-z0-9+/=]+)"', html)
    assert m, "الشعار غير موجود في الداشبورد"
    return Image(io.BytesIO(base64.b64decode(m.group(1))), width=size, height=size, mask="auto")
def img(name, w=1.0, ratio=.4): return Image(str(FIG / name), width=CW * w, height=CW * w * ratio)
def small(text, c=colors.grey): return P(text, 7.8, color=c)
S = []

# ============ الصفحة 1: الغلاف والملخص والمشكلة والبيانات ============
_hd = Table([[[P("رفدان | RIFDAN", 24, "B", EM, lead=30), P("نظام تحليلات التبرعات ودعم القرار: من البيانات إلى استدامة العطاء", 12, "B", BLUE),
               P("إعداد: زياد جماح  |  مشروع تحليل بيانات للقطاع غير الربحي", 9, color=colors.grey)], logo_flowable(50)]], colWidths=[CW - 58, 58])
_hd.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
S += [_hd, Spacer(1, 6)]
def kpi(v, l): return [P(v, 13, "B", BLUE, "C", 19), P(l, 7.6, color=colors.HexColor("#555555"), align="C", lead=10.5)]
k = Table([[kpi(f(o["transactions"]), "عملية تبرع"), kpi(f(d["observed_donors"]), "معرّف متبرع مرصود"), kpi(f(o["total_amount"]), "إجمالي المبلغ (ر.س)"),
            kpi(f(o["median"]) + " / " + f(o["mean"], 1), "الوسيط / المتوسط (ر.س)"), kpi(f(dup["duplicate_rows"]), "سجل مكرر معلَّم"), kpi(f(len(ini)), "مبادرة")][::-1]], colWidths=[CW / 6] * 6)
k.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .5, GREY), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FB")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
S += [k]
S += h2("1. الملخص التنفيذي")
S.append(para(f"حللنا عينة من {f(o['transactions'])} عملية تبرع في منصة إحسان لمعرفات متبرعين عددها {f(d['observed_donors'])}، بين {o['date_min'][:10]} و{o['date_max'][:10]}، بإجمالي {f(o['total_amount'])} ر.س (المبالغ بالريال السعودي؛ ولا ينص قاموس بيانات المصدر على الوحدة صراحةً). أبرز ما ظهر:"))
S += bullets([
    f"التبرع شديد التركّز: الوسيط {f(o['median'])} ر.س والمتوسط {f(o['mean'],1)} ر.س؛ و{o['share_txn_le10_pct']:.0f}% من العمليات 10 ر.س فأقل لكنها {o['amount_share_le10_pct']:.0f}% فقط من المبالغ.",
    f"معرّف واحد يمثل {d['top1_donor_amount_share_pct']:.1f}% من المبالغ، وأعلى 1% من المعرفات تمثل {d['top1pct_donors_amount_share_pct']:.1f}%؛ فالأرقام الإجمالية حساسة لقلة من المتبرعين.",
    f"المبادرة الأعلى مساهمة «{top_i['initiative']}» ({top_i['amount_share_pct']:.1f}% من المبالغ)، بينما «التبرع الدوري» يمثل {rec['txn_share_pct']:.1f}% من العمليات و{rec['amount_share_pct']:.1f}% من المبالغ.",
    f"{d['repeat_rate_pct']:.0f}% من المعرفات ظهرت في أكثر من عملية داخل العينة؛ وقسّم K-Means المعرفات إلى {seg['k']} شرائح.",
    f"نموذج تنبؤ استكشافي بتقسيم زمني (تدريب ثم تحقق ثم اختبار): AUC الاختبار {pred['test']['auc']:.3f} مقابل {pred['baseline']['test_auc']:.3f} لخط الأساس «عدد التبرعات»، أي {pred['verdict']}.",
    f"{len(INS)} توصيات مرتبة بحسب الحجم المالي المتأثر، و{len(PLANS)} خطط متابعة وتجريب."])
_top = INS[0]
S += callout(f"البدء بـ«{_top['title']}»: {_top['action']} وهو الموضوع الأكبر أثراً مالياً في العينة ({_top['affected_amount_share_pct']}% من المبالغ). ثم تشغيل خطة «{PLANS[0]['title']}» بقاعدة قرار معلنة قبل التجربة.", lead="القرار الموصى به:")
S += callout("جميع الأنماط مرصودة في عينة وليست أسباباً مثبتة لسلوك المتبرعين، ولا تُعمَّم على كل متبرعي المنصة، وهي وصف تاريخي لا يمثل الوضع الحالي.", lead="تنبيه منهجي:")
S += h2("2. المشكلة")
S.append(para("تحتاج الجهات غير الربحية إلى فهم أنماط التبرع لتحسين تخطيط الحملات وتعزيز الاستدامة المالية: كيف تتغير التبرعات عبر الزمن؟ أي المبادرات تجذب التبرع؟ كيف تختلف شرائح المتبرعين؟ وما الإجراءات التي يمكن تجربتها؟ يحوّل المشروع سجلات التبرع التاريخية إلى مؤشرات وتوصيات وخطط تجربة قابلة للقياس."))
S += h2("3. وصف البيانات")
S += bullets([f"المصدر: منصة البيانات المفتوحة السعودية ({URL})، والبيانات متاحة بموجب رخصة البيانات المفتوحة v2.0 (سدايا، مارس 2023) التي تسمح بالاستخدام والتعديل بشرط ذكر المصدر.",
              "الأعمدة الستة: UserID، CreationTime، Title (فرصة التبرع)، Amount، InitiativeName، PaymentMethod. لا توجد بيانات جغرافية أو تكاليف أو أهداف تمويلية، فلم تُحسب مؤشرات تعتمد عليها.",
              f"الحجم قبل التنظيف: {f(q['records'])} سجلاً، {f(q['unique_user_ids'])} معرفاً، {q['unique_initiatives']} مبادرة، {f(q['unique_titles'])} عنواناً ({f(o['unique_titles'])} بعد التنظيف)، {len(q['payment_methods'])} وسائل دفع.",
              "الأوقات كما سُجلت (المنطقة الزمنية غير موثقة)، وصيغة التاريخ شهر/يوم/سنة."])
S.append(PageBreak())

# ============ الصفحة 2: التنظيف والمنهجية ============
S += h2("4. تنظيف البيانات")
S.append(para("يُقاس الأثر بوحدته: عمود أو خلية أو سجل."))
S.append(Spacer(1, 3))
S.append(KeepTogether(tbl([["الخطوة", "الوحدة", "المشكلة", "الإجراء", "العدد"]] + [[c["step"], c["unit"], c["issue"], c["action"], f(c["records_affected"])] for c in M["cleaning_log"]], [.12, .09, .31, .38, .10], size=8.2)))
S += callout(f"لم تُحذف السجلات المكررة ({dup['duplicate_rows']} سجلاً، {dup['duplicate_share_rows_pct']:.2f}% من العدد و{dup['duplicate_share_amount_pct']:.2f}% من المبالغ) لأنها قد تكون تبرعات حقيقية (الوقت بالدقيقة ولا يوجد رقم عملية)؛ عُلِّمت فقط. حساسية النتائج: الإجمالي {f(dup['total_with'])} ر.س مع التكرارات و{f(dup['total_without'])} ر.س بدونها، والمتوسط {dup['mean_with']:.1f} ر.س مقابل {dup['mean_without']:.1f} ر.س.", lead="قرار التكرار:")
S.append(para(f"قبل التنظيف: {f(q['records'])} سجلاً (بخليتين فارغتين أو غير صالحتين ومسافات زائدة في كل قيم المبلغ). بعد التنظيف: {f(a['records'])} سجلاً؛ استُبعد سجل واحد بمبلغ غير رقمي، ولا توجد مبالغ صفرية أو سالبة أو تواريخ غير صالحة. الملف الناتج data_clean/cleaned_donations.csv."))
S += h2("5. المنهجية")
S += bullets(["تحليل البيانات بلغة Python، وهو قابل لإعادة التشغيل من الدفتر analysis.ipynb أو من السكربت scripts/run_analysis.py.",
              "كل حسابات اللوحة الأساسية تُحسب في Python ثم تُمرَّر إلى اللوحة كتجميعات.",
              "التحليل الزمني: لا يُحسب نمو شهري إلا بين شهرين متتاليين مكتملين وحجم السابق 100 عملية فأكثر. الشهران الأول والأخير جزئيان، ولا توجد سجلات في فبراير 2021.",
              "المتبرع المتكرر = معرّف ظهر في أكثر من عملية داخل العينة (لا يمثل تاريخه الكامل). الحداثة تُحسب بالأيام حتى اليوم التالي لآخر تاريخ في العينة، وتشمل الفئة الأولى القيمة صفر.",
              f"التحقق الزمني للنموذج: ثلاث نقاط قطع متتابعة ({pred['cutoffs']['train']} ثم {pred['cutoffs']['validation']} ثم {pred['cutoffs']['test']}) وأفق {pred['horizon_days']} يوماً؛ تُحسب الخصائص من ما قبل نقطة القطع والتسمية من الأيام الـ{pred['horizon_days']} بعدها. يُقارَن النموذجان على التحقق فقط، ثم يُعاد تدريب المختار على التدريب والتحقق ويُقيَّم مرة واحدة على الاختبار."])
S.append(PageBreak())

# ============ الصفحة 3: النتائج ============
S += h2("6. أهم النتائج")
pkm = max([m for m in M["monthly"] if not m["partial"]], key=lambda m: m["transactions"])
S.append(img("01_monthly_trend.png", .92, .38))
S.append(para(f"أعلى شهر نشاطاً {pkm['year_month']} بـ {f(pkm['transactions'])} عملية. لا تثبت البيانات سبب الارتفاع أو استقرار النمط الموسمي. الشهران الأول والأخير جزئيان ولا سجلات في فبراير 2021."))
S.append(Spacer(1, 3))
S.append(KeepTogether([tbl([["المبادرة", "إجمالي المبلغ (ر.س)", "العمليات", "المتوسط (ر.س)", "حصة المبلغ %"]] + [[r["initiative"], f(r["amount"]), f(r["transactions"]), f(r["avg"], 1), f(r["amount_share_pct"], 1)] for r in ini[:5]], [.3, .2, .16, .16, .18], size=8.2),
                       Spacer(1, 4),
                       tbl([["وسيلة الدفع", "العمليات", "إجمالي المبلغ (ر.س)", "المتوسط (ر.س)", "حصة العمليات %"]] + [[r["payment_method"], f(r["transactions"]), f(r["amount"]), f(r["avg"], 1), f(r["txn_share_pct"], 1)] for r in pay], [.28, .18, .2, .16, .18], size=8.2)]))
S.append(Spacer(1, 4)); S.append(img("06_activity_heatmap.png", .9, .345))
S.append(para(f"أعلى نافذة نشاط: {pk['day']} من {pk['hour_start']:02d}:00 إلى {pk['hour_start']+2:02d}:59 بـ {f(pk['transactions'])} عملية من {f(pk['distinct_donors'])} معرفاً في {f(pk['distinct_dates'])} يوماً مختلفاً."))
S.append(PageBreak())

# ============ الصفحة 4: توزيع المبالغ + الشرائح ============
S += h2("6. أهم النتائج (تابع): توزيع المبالغ")
S.append(KeepTogether(tbl([["فئة المبلغ (ر.س)", "نسبة العمليات %", "نسبة المبالغ %"]] + [[b["band"], f(b["count_pct"], 1), f(b["amount_pct"], 1)] for b in M["amount_bands"]], [.4, .3, .3], size=8.2)))
S += h2("7. التحليلات المتقدمة")
S += h3("تقسيم المتبرعين (RFM + K-Means)")
_sk = max(seg["silhouette_by_k"], key=seg["silhouette_by_k"].get)
S.append(para("الخصائص: الحداثة والتكرار والقيمة بعد log1p والتوحيد. قُيّم k من 2 إلى 6 بمعامل Silhouette (" + "، ".join(f"k={k}: {v:.2f}" for k, v in seg["silhouette_by_k"].items()) + f")، واختير k={seg['k']} لتوفير ثلاث شرائح قابلة للتفسير؛ وهو الأعلى بين 3 و6 وليس الأفضل إحصائياً (k={_sk}: {seg['silhouette_by_k'][_sk]:.2f}). تعني القيمة المنخفضة نسبياً حدوداً غير حادة بين الشرائح، وأسماء الشرائح قاعدية. والتقسيم ثابت: إعادة التجميع ببذور عشوائية أخرى تعطي التوزيع نفسه (أدنى معامل تطابق Adjusted Rand = {seg['stability_ari_min']:.2f})."))
S.append(Spacer(1, 3))
S.append(KeepTogether(tbl([["الشريحة", "المعرفات", "حصة المعرفات %", "حصة المبالغ %", "وسيط التكرار", "وسيط الأيام منذ آخر تبرع"]] + [[s["segment"], f(s["donors"]), f(s["donor_share_pct"], 1), f(s["amount_share_pct"], 1), f(s["frequency_median"]), f(s["recency_median"])] for s in seg["segments"]], [.24, .12, .16, .16, .14, .18], size=8.2)))
S.append(Spacer(1, 4)); S.append(Image(str(FIG / "09_donor_segments.png"), width=CW * .7, height=CW * .7 * .56))
S.append(Spacer(1, 4))
_rc = list(d["recency_dist"].items()); _w = 1 / (len(_rc) + 1)
S.append(KeepTogether(h3("توزيع الحداثة (الأيام منذ آخر تبرع حتى نهاية العينة، عدد المعرفات)") + [tbl([[k_ for k_, _ in _rc] + ["المجموع"], [f(v) for _, v in _rc] + [f(sum(d["recency_dist"].values()))]], [_w] * (len(_rc) + 1), size=8.2)]))
S.append(PageBreak())

# ============ زمن عودة المتبرع ============
S += h2("7. التحليلات المتقدمة (تابع): زمن عودة المتبرع")
_sv = M["survival"]; _vs = M["value_sizing"]; _pt = M["peak_test"]
_grp = [g for g in _sv["groups"] if g["name"].startswith("مبلغ أول تبرع")][0]
_lr = _sv["tests"][_grp["name"]]
_pay = [g for g in _sv["groups"] if g["name"].startswith("وسيلة الدفع")][0]
_lrp = _sv["tests"][_pay["name"]]
S.append(para(
    f"يقيس هذا القسم المدة بين أول تبرع مرصود للمعرّف وتبرعه التالي بمقدّر كابلان-ماير. "
    f"من لم يعد حتى نهاية الفترة يُعامل كمشاهدة مراقَبة (right-censored) لا كحالة فشل، لأن حذفه يرفع معدل العودة صناعياً. "
    f"ويقتصر الفوج على المعرفات التي يقع أول تبرع لها قبل آخر {_sv['entry_cutoff_days']} يوماً من العينة لتتاح لكل معرّف نافذة متابعة كافية: "
    f"{f(_sv['cohort'])} معرّفاً، عاد منهم {f(_sv['returned'])} وبقي {f(_sv['censored'])} مراقَباً."))
S.append(Spacer(1, 3))
S.append(KeepTogether(tbl([["معدل العودة خلال", "30 يوماً", "60 يوماً", "90 يوماً", "وسيط زمن العودة"],
                           ["كامل الفوج"] + [f(_sv["return_rate_pct"][k], 1) + "%" for k in ("30", "60", "90")]
                           + [f"{f(_sv['median_days_to_second'])} يوماً"]], [.28, .17, .17, .17, .21], size=8.2)))
S.append(Spacer(1, 4))
S += h3("مقارنة المجموعات باختبار Log-rank")
S.append(tbl([["المجموعة", "عدد المعرفات", "عودة خلال 30 يوماً", "وسيط الأيام", "نتيجة الاختبار"]]
             + [[l["name"], f(l["n"]), f(l["return_rate_pct"]["30"], 1) + "%", f(l["median_days"]),
                 (f"مربع كاي {f(_lr['statistic'], 2)}، p = {_lr['p_value']:.4f}" if i == 0 else "")]
                for i, l in enumerate(_grp["levels"])]
             + [[l["name"], f(l["n"]), f(l["return_rate_pct"]["30"], 1) + "%", f(l["median_days"]),
                 (f"مربع كاي {f(_lrp['statistic'], 2)}، p = {_lrp['p_value']:.2f}" if i == 0 else "")]
                for i, l in enumerate(_pay["levels"])], [.30, .15, .18, .14, .23], size=7.8))
S.append(Spacer(1, 3))
S.append(para(
    f"الفرق بحسب حجم أول تبرع دال إحصائياً (p = {_lr['p_value']:.4f}): من كان أول تبرع له عند الوسيط فأقل عاد أسرع. "
    f"ولا يظهر فرق دال بحسب وسيلة الدفع (p = {_lrp['p_value']:.2f})، وهو ما يسحب الأساس من أي توصية تُبنى على وسيلة الدفع وحدها. "
    f"والدلالة لا تثبت سبباً: قد يكون التبرع الصغير تجربة أولى منخفضة الالتزام يسهل تكرارها."))
S.append(Spacer(1, 4))
S.append(Image(str(FIG / "11_time_to_second_gift.png"), width=CW * .68, height=CW * .68 * .511))
S.append(Spacer(1, 5))
_cx = M["cox"]; _amt = [t for t in _cx["terms"] if t["term"] == "log_first_amount"][0]
_sig = [t for t in _cx["terms"] if t["significant"]]
S += h3("ضبط المربِكات بنموذج Cox للمخاطر النسبية")
S.append(para(
    f"اختبار Log-rank يقارن مجموعتين فقط، فلا يفصل حجم أول تبرع عن المبادرة التي دخل منها المتبرع. "
    f"ولذلك أُدخلت المبادرة ووسيلة الدفع وحجم أول تبرع معاً في نموذج Cox على {f(_cx['n'])} معرّفاً. "
    f"والنتيجة أن أثر حجم التبرع يزول بعد الضبط (نسبة خطر {_amt['hazard_ratio']:.3f}، فاصل ثقة 95%: "
    f"{_amt['ci95'][0]:.3f}–{_amt['ci95'][1]:.3f}، p = {_amt['p_value']:.2f})، وأن ما يفسّر تفاوت زمن العودة هو باب الدخول: "
    + "، ".join(f"«{t['term'].replace('ini_', '')}» بنسبة خطر {t['hazard_ratio']:.2f} (p = {t['p_value']:.4f})" for t in _sig)
    + f" مقارنةً بمبادرة «{_cx['reference']['ini']}». ونسبة خطر أقل من واحد تعني عودة أبطأ."))
S.append(Spacer(1, 3))
S.append(Image(str(FIG / "12_cox_hazard_ratios.png"), width=CW * .72, height=CW * .72 * .59))
S.append(Spacer(1, 3))
S.append(small(f"يفترض النموذج تناسب المخاطر ولم تُختبر هذه الفرضية. ودرجة التطابق (C-index = {_cx['concordance']:.3f}) "
               f"قريبة من الصدفة، أي أن العوامل المتاحة تفسّر جزءاً صغيراً من التباين."))
S.append(Spacer(1, 4))
S.append(para("ثبات المعدل عبر الزمن: " + M["cohorts"]["note"]))
S.append(Spacer(1, 5))
S += h3("القيمة المالية لرفع معدل العودة نقطة مئوية واحدة")
S.append(para(
    f"يُقدَّر حجم الرافعة بحدّين بدل رقم واحد. الأدنى: {_vs['formula_low']}. "
    f"والأعلى: {_vs['formula_high']}. أي بين {f(_vs['lower_bound_share_pct'], 2)}% و{f(_vs['upper_bound_share_pct'], 2)}% من إجمالي العينة. "
    f"{_vs['limitation']} والرافعة صغيرة بمقياس العينة، فقيمة التجربة في التعلّم المنهجي أكثر منها في العائد المباشر."))
S.append(Spacer(1, 4))
S += h3(f"اختبار فرق المبالغ في نافذة الذروة ({_pt['window']})")
S.append(para(
    f"تتكرر التبرعات من المعرّف نفسه، فالمشاهدات ليست مستقلة وقيمة p من اختبار مان-ويتني متفائلة تحت هذا الارتباط. "
    f"لذلك بُني الحكم على إعادة معاينة عنقودية على مستوى المعرّف ({f(_pt['cluster_bootstrap']['resamples'])} إعادة): "
    f"حجم الأثر الرتبي {_pt['rank_biserial']:+.3f}، وفاصل الفرق في الوسيط "
    f"[{_pt['cluster_bootstrap']['ci95'][0]:+.1f}, {_pt['cluster_bootstrap']['ci95'][1]:+.1f}] "
    f"وفي المتوسط [{_pt['cluster_bootstrap_mean']['ci95'][0]:+.1f}, {_pt['cluster_bootstrap_mean']['ci95'][1]:+.1f}] "
    f"كلاهما يشمل الصفر. {_pt['verdict']}."))
S.append(PageBreak())

# ============ الصفحة 5: النموذج + التوصيات ============
S += h2("7. التحليلات المتقدمة (تابع): نموذج التنبؤ الاستكشافي")
S.append(para(f"الهدف: هل يتبرع المعرّف مجدداً خلال {pred['horizon_days']} يوماً؟ تقسيم زمني متتابع: التدريب (قطع {pred['cutoffs']['train']})، التحقق (قطع {pred['cutoffs']['validation']})، الاختبار (قطع {pred['cutoffs']['test']}). أحجام المجموعات {f(pred['sizes']['train'])} و{f(pred['sizes']['validation'])} و{f(pred['sizes']['test'])} معرفاً."))
S.append(Spacer(1, 3))
vr = [[("%s (المختار)" % k_) if k_ == pred["chosen_model"] else k_, f(v["auc"], 3), f(v["precision"], 2), f(v["recall"], 2)] for k_, v in pred["validation"].items()]
S.append(KeepTogether([tbl([["مجموعة التحقق: مقارنة النماذج", "AUC", "الدقة", "الاسترجاع"]] + vr + [["خط الأساس: " + pred["baseline"]["name"], f(pred["baseline"]["validation_auc"], 3), "-", "-"]], [.46, .18, .18, .18], size=8.2),
                       Spacer(1, 4),
                       tbl([["الاختبار اللاحق (تقييم واحد)", "AUC", "الدقة", "الاسترجاع"], [f"{pred['test']['model']} بعد إعادة التدريب على التدريب والتحقق", f(pred["test"]["auc"], 3), f(pred["test"]["precision"], 2), f(pred["test"]["recall"], 2)],
                            ["خط الأساس: " + pred["baseline"]["name"], f(pred["baseline"]["test_auc"], 3), "-", "-"]], [.46, .18, .18, .18], size=8.2)]))
S.append(Spacer(1, 3))
S.append(para(f"اختير النموذج حسب AUC التحقق فقط، ولم يُستخدم الاختبار للمفاضلة. النتيجة: {pred['verdict']}. {pred['note']}"))
_SPLIT_AR = {"train": "التدريب", "validation": "التحقق", "test": "الاختبار"}
S.append(para("نسبة العائدين فعلياً تختلف بين النوافذ (" + "، ".join(f"{_SPLIT_AR[k]} {v*100:.1f}%" for k, v in pred["positive_rate"].items()) + f"). {pred['base_rate_note']}"))
S.append(small("الدقة: نسبة العائدين فعلياً بين من توقّع النموذج عودتهم. الاسترجاع: نسبة من اكتشفهم النموذج من جميع العائدين. ومقياس AUC مقياس تمييز وليس نسبة دقة تصنيف."))
S += h2("8. التوصيات")
S.append(para(M["priority_note"]))
S.append(Spacer(1, 3))
S.append(tbl([["التوصية", "الأولوية (نسبة المبالغ المتأثرة)", "الإجراء المقترح"]] + [[i["title"], f"{i['priority']} ({i['affected_amount_share_pct']}%)", i["action"]] for i in INS], [.25, .17, .58], size=7.8))
S.append(PageBreak())

# ============ الصفحة 6: خطط التنفيذ والحدود والإسناد ============
S += h2("9. خطط التنفيذ والأثر المتوقع")
S.append(para("ثلاث خطط للتجربة أو المتابعة. الأثر المتوقع فرضية تُقاس بالتجربة، ولا يتضمن التقرير أهدافاً مالية ولا نسب تحسن ولا نتائج تجارب."))
def plan_block(p):
    rows = [[P(p["title"] + " — " + p["kind"], 8.6, "B", colors.white), ""],
            [P("المسؤول والمدة", 7.6, "B", BLUE), P(p["owner"] + ". " + p["duration"], 7.6)],
            [P("التصميم", 7.6, "B", BLUE), P(p["design"], 7.6)], [P("مؤشر الأداء", 7.6, "B", BLUE), P(p["kpi"], 7.6)],
            [P("مرجع وصفي", 7.6, "B", BLUE), P(p["reference"], 7.6)], [P("قاعدة القرار", 7.6, "B", BLUE), P(p["decision_rule"], 7.6)],
            [P("حدود التفسير", 7.6, "B", BLUE), P(p["limits"], 7.6)]]
    t = Table([rows[0]] + [r[::-1] for r in rows[1:]], colWidths=[CW * .84, CW * .16])   # merged title row keeps its own order
    t.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (1, 0), BLUE), ("GRID", (0, 0), (-1, -1), .4, GREY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return KeepTogether([t, Spacer(1, 4)])
for p in PLANS: S.append(plan_block(p))
S += h2("10. حدود الاستنتاج")
S += bullets([f"البيانات عينة ({f(a['records'])} عملية بعد التنظيف) بين {o['date_min'][:10]} و{o['date_max'][:10]}، ولا تمثل كل متبرعي المنصة؛ و«المتكرر» أو «المنقطع» توصيف داخل العينة فقط لأن المعرّف لا يمثل السجل الكامل للمتبرع.",
              "الارتباطات (الشهر، والساعة، ووسيلة الدفع) ليست سببية، ولم يُضبط أثر الحملات الداخلية أو الموسم. المبالغ بالريال السعودي، والمنطقة الزمنية ومعنى «نقاط قطاف» غير موثقين في المصدر.",
              f"معرّف واحد بنحو {d['top1_donor_amount_share_pct']:.0f}% من المبالغ يحرّف المتوسطات؛ لذلك يُعرض الوسيط مع تحليل الحساسية. فصل الشرائح محدود، ونموذج التنبؤ على نافذة اختبار واحدة استكشافي.",
              "الرخصة لا تنطبق على البيانات الشخصية (البند 4.3-د)؛ فلا تُنشر المعرفات، والداشبورد يعرض تجميعات فقط."])
S.append(Spacer(1, 4)); S.append(small("إسناد: " + NOTICE + " التنظيف والتحليل من إعداد مؤلف المشروع ولا يعنيان اعتماد مانح الترخيص."))

from reportlab.pdfgen.canvas import Canvas as _Canvas
class NumberedCanvas(_Canvas):
    """يؤجّل رسم التذييل حتى يُعرف العدد الكلي للصفحات، فلا يُكتب الرقم يدوياً."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._pages = []
    def showPage(self):
        self._pages.append(dict(self.__dict__)); self._startPage()
    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self.saveState(); self.setFont("R", 8); self.setFillColor(colors.grey)
            self.drawCentredString(W / 2, 9 * mm, f"{self._pageNumber} / {total}"); self.restoreState()
            super().showPage()
        super().save()
def footer(c, doc): pass
out = ROOT / "report" / "executive_summary.pdf"; out.parent.mkdir(exist_ok=True)
doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=13 * mm, bottomMargin=16 * mm, title="RIFDAN Executive Summary", author="Ziyad Jammah")
doc.addPageTemplates([PageTemplate(id="a", frames=[Frame(LM, 16 * mm, CW, H - 29 * mm, 0, 0, 0, 0)], onPage=footer)]); doc.build(S, canvasmaker=NumberedCanvas)
print("saved", out.relative_to(ROOT))
