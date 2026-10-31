// فحص منطق لوحة RIFDAN (JavaScript) ببدائل DOM وPlotly.
// تنبيه صريح: يستخدم jsdom مع Plotly بديل (stub) يسجّل مدخلات الرسم؛ فهو يفحص المنطق ومدخلات العرض
// ولا يُعد اختباراً بصرياً في متصفح حقيقي (Chrome/Edge/الجوال) ولا اختباراً لتنزيل الملفات فعلياً.
// التشغيل من جذر المشروع:  npm install --prefix validation   ثم   node validation/validate_dashboard.cjs
// يقرأ حالات التصفية المحفوظة في validation/results/filter_cases.json؛ ويعيد python validation/validate_project.py توليدها من الملف الخام.
const fs = require('fs'), path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');
const root = path.resolve(__dirname, '..');
const html0 = fs.readFileSync(path.join(root, 'outputs/dashboard/RIFDAN_Dashboard.html'), 'utf8');
const resultsDir = path.join(root, 'validation', 'results'), casesPath = path.join(resultsDir, 'filter_cases.json');
if (!fs.existsSync(casesPath)) { console.error('لم يوجد ' + path.relative(root, casesPath) + ' — شغّل أولاً: python validation/validate_project.py (يولّد حالات التصفية)'); process.exit(2); }
const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8')).cases;
const M = JSON.parse(fs.readFileSync(path.join(root, 'outputs/metrics.json'), 'utf8'));

// استبدال سكربت Plotly (الأكبر حجماً) ببديل يسجّل الاستدعاءات
let big = '', m, re = /<script>([\s\S]*?)<\/script>/g;
while ((m = re.exec(html0))) if (m[1].length > big.length) big = m[1];
const html = html0.replace('<script>' + big + '</script>', '<script>window.__calls=[];window.Plotly={react:function(id,tr,lay){window.__calls.push({id:id,tr:tr,lay:lay});return Promise.resolve()}};</script>');

const errors = [], blobs = [], revoked = [], clicks = [];
const vc = new VirtualConsole(); vc.on('jsdomError', e => errors.push(String(e.detail || e.message))); vc.on('error', e => errors.push(String(e)));
const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole: vc, pretendToBeVisual: true, beforeParse(w) {
  w.URL.createObjectURL = b => { blobs.push(b); return 'blob:test/' + blobs.length; };
  w.URL.revokeObjectURL = u => revoked.push(u);
  w.HTMLAnchorElement.prototype.click = function () { clicks.push({ href: this.href, download: this.download }); };
  w.matchMedia = q => ({ matches: false, media: q, onchange: null, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent() { return false; } });  // jsdom does not implement matchMedia
} });
const w = dom.window, d = w.document, ev = c => w.eval(c), $ = s => d.querySelector(s);
const results = [];
const T = (name, ok, detail = '') => { results.push({ name, ok: !!ok, detail }); console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? '  [' + detail + ']' : '')); };
const near = (a, b, e = 1e-6) => Math.abs(a - b) <= e;
const setF = f => ev(`Object.assign(F,{from:monthOf("${f.from_ym}"),to:monthOf("${f.to_ym}"),year:"${f.year}",ini:${f.ini},pay:${f.pay}})`);
const go = (p, f) => { if (f) setF(f); ev(`cur="${p}";rendered={};render()`); };
const calls = id => w.__calls.filter(c => c.id === id);
const nav = p => $(`nav button[data-p=${p}]`).click();
const DIM = ev('DIM'), maxMonth = ev('maxMonth'), MONTHS = ev('MONTHS');
const fire = (id, v) => { $(id).value = v; $(id).dispatchEvent(new w.Event('change')); };
const Fstate = () => JSON.parse(ev('JSON.stringify(F)'));

(async () => {
  // ---- 1) 60 حالة تصفية مقابل pandas
  let okCount = 0, bad = [];
  for (const c of cases) {
    setF(c.filters);
    const r = JSON.parse(ev('JSON.stringify((()=>{const R=agg(F);const T=aggT(F);return {n:R.n,s:R.s,heat:R.heat,iS:R.iS,iN:R.iN,pN:R.pN,T:T,top:R.n?topN(R.iS,1)[0].i:null}})())'));
    let ok = r.n === c.n && near(r.s, c.s) && JSON.stringify(r.heat) === JSON.stringify(c.heat) && c.init_s.every((v, i) => near(v, r.iS[i])) && c.init_n.every((v, i) => v === r.iN[i]) && c.pay_n.every((v, i) => v === r.pN[i]);
    ok = ok && r.T.length === c.distinct_titles && c.titles.every(t => { const x = r.T.find(y => y.t === t.t); return x && x.n === t.n && near(x.s, t.s); });
    ok = ok && (c.n === 0 ? r.top === null : r.top === c.top_initiative);
    // مدخلات العرض في الصفحة الأولى: المبادرة الأعلى في مؤشرات الأداء والرسم
    go('p1');
    if (c.n > 0) {
      const kp = [...d.querySelectorAll('#kpis .kpi .v')].map(x => x.textContent);
      const ci = calls('c_ini').pop(), xs = ci.tr[0].x, ys = ci.tr[0].y;
      ok = ok && kp[4] === DIM.initiatives[c.top_initiative] && xs.every((v, i) => i === 0 || v >= xs[i - 1]) && ys[ys.length - 1] === DIM.initiatives[c.top_initiative] && near(xs[xs.length - 1], Math.max(...c.init_s));
      ok = ok && kp[1] === Math.round(c.n).toLocaleString('en-US');
    } else ok = ok && $('#empty').style.display === 'flex';
    w.__calls.length = 0; if (ok) okCount++; else bad.push(c.id);
  }
  T('60 حالة تصفية: الأعداد والمبالغ والخريطة الحرارية وتجميع العناوين وتوزيع المبادرات والمبادرة الأعلى', okCount === 60, `${okCount}/60 ${bad.length ? 'فشل: ' + bad.join(',') : ''}`);

  // ---- 2) ترتيب المبادرات (إصلاح topN)
  setF(cases[0].filters);
  const tn = JSON.parse(ev('JSON.stringify(topN([5,9,1,9,0],3))'));
  T('topN يرتب القيم العددية تنازلياً ويكسر التعادل بالفهرس', JSON.stringify(tn) === JSON.stringify([{ v: 9, i: 1 }, { v: 9, i: 3 }, { v: 5, i: 0 }]), JSON.stringify(tn));
  go('p3'); const cti = calls('c_topini').pop(), tx = cti.tr[0].x, ty = cti.tr[0].y;
  T('رسم أعلى المبادرات غير فارغ ومرتب والأعلى «مشروع»', tx.length >= 10 && tx.every((v, i) => i === 0 || v >= tx[i - 1]) && ty[ty.length - 1] === DIM.initiatives[cases[0].top_initiative], ty[ty.length - 1]);
  const ca = calls('c_avgini').pop(); T('رسم متوسط التبرع حسب المبادرة يُرسم بقيم عددية', ca && ca.tr[0].x.length > 0 && ca.tr[0].x.every(v => typeof v === 'number' && isFinite(v)));
  const cit = calls('c_initrend').pop(); T('رسم أعلى 5 مبادرات عبر الزمن يحوي 5 سلاسل', cit && cit.tr.length === 5);
  go('p4', cases[0].filters); const hz = calls('c_heat').pop().tr[0].z; T('الخريطة الحرارية في اللوحة = pandas (بلا مرشحات)', JSON.stringify(hz) === JSON.stringify(cases[0].heat));

  // ---- 3) مقارنة المبادرتين: المقام من النطاق دون مرشح المبادرة
  const cmpShare = (A, B) => { $('#cmpA').value = A; $('#cmpB').value = B; go('p3'); const row = [...d.querySelectorAll('#cmpTbl tr')].find(r => r.textContent.includes('حصة')); return [...row.querySelectorAll('td')].slice(1).map(x => parseFloat(x.textContent)); };
  setF(cases[0].filters); let sh = cmpShare(0, 1); const c0 = cases[0];
  T('المقارنة بلا مرشح مبادرة: النسبتان = pandas', near(sh[0], c0.init_s[0] / c0.s * 100, .06) && near(sh[1], c0.init_s[1] / c0.s * 100, .06), sh.join(' / '));
  const cp = cases.find(c => c.filters.pay === 1 && c.filters.ini === -1 && c.filters.year === 'all' && c.filters.from_ym === c0.filters.from_ym);
  setF({ ...cp.filters, ini: 21 }); sh = cmpShare(0, 1);
  T('مرشح مبادرة عام (21) مع وسيلة دفع: المقام من النطاق دون المبادرة، النسبة ≤ 100 والقيم = pandas', sh[0] <= 100 && sh[1] <= 100 && sh[0] + sh[1] <= 100.1 && near(sh[0], cp.init_s[0] / cp.s * 100, .06) && near(sh[1], cp.init_s[1] / cp.s * 100, .06), sh.join(' / '));
  const c21 = cases.find(c => c.filters.year === '2021' && c.filters.ini === -1 && c.filters.pay === -1);
  const none = c21.init_n.findIndex(v => v === 0);
  setF({ ...c21.filters, ini: none }); sh = cmpShare(0, 1);
  T('مبادرة مرشّحة بلا بيانات في النطاق: تظهر رسالة والمقارنة تعمل بنسب صحيحة', none >= 0 && !$('#p3note').hidden && $('#empty').style.display === 'none' && $('#cmpTbl table') && near(sh[0], c21.init_s[0] / c21.s * 100, .06) && sh[0] <= 100, `ini=${none} ${sh.join(' / ')}`);
  ev('F.ini=-1');

  // ---- 4) المرشحات الزمنية وحالات الفراغ
  ev('Object.assign(F,{from:0,to:maxMonth,year:"all",ini:-1,pay:-1})'); $('#reset').click(); go('p1');
  const lastM = MONTHS[maxMonth];
  T('مرشح التاريخ قائمتا أشهر بلا حقول تاريخ يومية', d.querySelectorAll('input[type=date]').length === 0 && $('#fFrom').options.length === MONTHS.length && $('#fTo').options.length === MONTHS.length && $('#fFrom').value === MONTHS[0] && $('#fTo').value === lastM, `${MONTHS.length} شهراً`);
  fire('#fFrom', '2022-05'); const stA = JSON.stringify(Fstate()); fire('#fTo', '2022-04');
  T('مرشح الأشهر يرفض المعكوس (بداية بعد نهاية) ويستعيد حقل النهاية ويحتفظ بالحالة', !$('#err').hidden && $('#err').textContent.includes('بعد') && JSON.stringify(Fstate()) === stA && $('#fTo').value === lastM, $('#err').textContent.slice(0, 40));
  $('#reset').click();
  fire('#fFrom', '2022-04'); fire('#fTo', '2022-04');
  const okRange = $('#err').hidden && ev('F.from') === ev('monthOf("2022-04")') && ev('F.to') === ev('monthOf("2022-04")') && $('#status').textContent.includes('2022-04');
  T('نطاق أشهر صحيح يُقبل وتختفي رسالة الخطأ', okRange, $('#status').textContent.slice(0, 60));
  const keep = JSON.stringify(Fstate()); fire('#fTo', '2022-03');
  T('اختيار معكوس بعد نطاق صحيح يحتفظ بالنطاق ويعيد قيم الحقول', JSON.stringify(Fstate()) === keep && $('#fTo').value === '2022-04' && !$('#err').hidden);
  $('#reset').click();
  T('إعادة الضبط تستعيد كل المرشحات وتزيل رسالة الخطأ', $('#err').hidden && ev('F.from') === 0 && ev('F.to') === maxMonth && $('#fYear').value === 'all' && $('#fIni').value === '-1' && $('#fPay').value === '-1' && $('#fFrom').value === MONTHS[0]);
  fire('#fFrom', '2021-02'); fire('#fTo', '2021-02'); let emptyOk = true;
  for (const p of ['p1', 'p3', 'p4']) { nav(p); emptyOk = emptyOk && $('#empty').style.display === 'flex'; }
  for (const p of ['p2', 'p5']) { nav(p); emptyOk = emptyOk && $('#empty').style.display === 'none' && $('#' + p).style.visibility !== 'hidden'; }
  T('فترة بلا سجلات (فبراير 2021): حالة فراغ دون تعطل، والصفحات الثابتة تعمل', emptyOk && errors.length === 0, errors.slice(0, 1).join());
  $('#reset').click(); nav('p1');

  // ---- 5) الملاحظات والخطط ومعنى النتائج
  const gn = $('#gnote').textContent;
  T('الملاحظة العامة: كامل العينة + جزئية/فراغ + الريال السعودي + المنطقة الزمنية + وصف تاريخي', ['كامل العينة', 'جزئيان', 'بالريال السعودي', 'المنطقة الزمنية غير موثقة', 'وصف تاريخي', 'ليست وصفاً للوضع الحالي'].every(x => gn.includes(x)));
  nav('p5');
  const pl = [...d.querySelectorAll('#plans .ins')];
  T(`صفحة القرار: ${M.insights.length} توصيات و${M.action_plans.length} خطط بكل الحقول المطلوبة`,
    d.querySelectorAll('#insAll .ins').length === M.insights.length && pl.length === M.action_plans.length
    && pl.every(p => ['المسؤول المقترح', 'المدة', 'التصميم', 'KPI', 'قاعدة القرار', 'حدود التفسير'].every(x => p.textContent.includes(x))));
  T('مذكرة الأولوية ظاهرة (الحجم المالي لا العائد)', $('#prio').textContent.includes('الحجم المالي') && $('#prio').textContent.includes('لا تمثل'));
  const plansTxt = pl.map(x => x.textContent).join(' '); T('الخطط لا تحوي نسب تحسن أو أهدافاً مالية مختلقة', !/(ارتفاع|زيادة|تحسن)\s*(بنسبة|بمقدار)?\s*\d+\s*%/.test(plansTxt));
  go('p3', cases[0].filters); T('شرح مقام المقارنة ظاهر', $('#cmpNote').textContent.includes('مرشح المبادرة العام لا يطبّق على المقارنة'));
  nav('p2'); const pb = $('#predBox').textContent, P = M.prediction;
  T('صفحة المتبرعين: نتائج التحقق منفصلة عن الاختبار وبنفس أرقام metrics.json', pb.includes('مجموعة التحقق') && pb.includes('الاختبار اللاحق') && pb.includes('عدد التبرعات') && pb.includes(P.test.auc.toFixed(3)) && pb.includes(P.baseline.test_auc.toFixed(3)) && Object.values(P.validation).every(v => pb.includes(v.auc.toFixed(3))));
  const rc = calls('c_rec').pop(); T('توزيع الحداثة في اللوحة: 1,371 والفئة الأولى 446', rc.tr[0].y.reduce((a, b) => a + b, 0) === 1371 && rc.tr[0].y[0] === 446 && rc.tr[0].x[0] === '30 يوماً فأقل');

  for (const pg of ['p1', 'p2', 'p3', 'p4', 'p5']) go(pg, cases[0].filters);                // عرض كل الصفحات قبل فحص النص المرئي
  const vis = d.body.cloneNode(true); vis.querySelectorAll('script,style').forEach(n => n.remove());   // استبعاد نص السكربت (فيه بيانات خام)
  T('اسم وسيلة الدفع يظهر «أبل باي» (بالياء) ولا يظهر «أبل باى» في أي نص مرئي (كل الصفحات)', [...d.querySelectorAll('#fPay option')].some(o => o.textContent === 'أبل باي') && vis.textContent.includes('أبل باي') && !vis.textContent.includes('أبل باى'));
  T('وحدة المبلغ: مؤشرات الإجمالي والمتوسط بالريال السعودي (ر.س)', ev('go=null;1') && (go('p1', cases[0].filters), [...d.querySelectorAll('#kpis .kpi .l')].filter(x => x.textContent.includes('ر.س')).length === 2));
  // ---- 6) تصدير CSV وتحرير رابط Blob
  const csvFor = async f => { setF(f); blobs.length = revoked.length = clicks.length = 0; $('#dl').click(); await new Promise(r => setTimeout(r, 30));
    const txt = await new Promise(res => { const fr = new w.FileReader(); fr.onload = () => res(fr.result); fr.readAsText(blobs[0]); }); return txt; };
  for (const [lbl, c] of [['كامل العينة', cases[0]], ['سنة 2022', cases[2]]]) {
    const txt = await csvFor(c.filters), lines = txt.replace(/^\ufeff/, '').trim().split('\n'), body = lines.slice(1).map(l => l.split(','));
    T(`ملف CSV (${lbl}): ترويسة وأعداد ومبالغ تطابق pandas`, lines[0] === 'year_month,transactions,amount' && body.reduce((a, r) => a + +r[1], 0) === c.n && near(body.reduce((a, r) => a + +r[2], 0), c.s) && body.every(r => +r[1] > 0), `${body.length} شهراً`);
    T(`ملف CSV (${lbl}): اسم الملف صحيح وحُرّر رابط Blob بعد الاستخدام`, clicks[0] && clicks[0].download === 'rifdan_monthly_summary.csv' && revoked.length === 1 && revoked[0] === clicks[0].href);
  }
  // ---- 7) ضوابط الخصوصية وخط الواجهة في النسخة العامة
  const pool = DIM.titles[DIM.titles.length - 1];
  setF(cases[0].filters); const allT = JSON.parse(ev('JSON.stringify(aggT(F))'));
  T('العناوين المحجوبة لا تظهر في ترتيب الفرص، والمجمّع غير معروض', allT.length === DIM.titles.length - 1 && !allT.some(x => x.t === pool));
  T('مكعبات اللوحة بلا تاريخ يومي، وأنماط الساعة أعداد فقط', !('h' in ev('D.A')) && !('day' in ev('D.A')) && !('day' in ev('D.B')) && !('s' in ev('D.H')) && !('s' in ev('D.HY')));
  T('الملاحظة العامة تشرح الأشهر الكاملة', $('#gnote').textContent.includes('الأشهر الكاملة'));
  go('p3'); go('p4'); T('ملاحظتا الخصوصية ظاهرتان', $('#titlesPrivacy').textContent.includes('لحماية الخصوصية') && $('#hoursPrivacy').textContent.includes('أشهر كاملة') && $('#titlesPrivacy').textContent.includes('مستوى السنة'));
  T('عنوان التبويب', d.title === 'RIFDAN | لوحة التحليلات', d.title);
  T('خط IBM Plex Sans Arabic مضمّن بوزنين', (html0.match(/@font-face\{font-family:"IBM Plex Sans Arabic"/g) || []).length === 2);

  T('لا أخطاء JavaScript أثناء كل الفحوص', errors.length === 0, errors.slice(0, 2).join(' | '));

  const pass = results.filter(r => r.ok).length;
  console.log(`\n${pass}/${results.length} فحصاً ناجحاً (jsdom + Plotly بديل؛ ليس اختباراً بصرياً في متصفح حقيقي)`);
  fs.writeFileSync(path.join(resultsDir, 'dashboard_validation.json'), JSON.stringify({ passed: pass, total: results.length, results, note: 'jsdom + Plotly stub; not a real-browser visual test' }, null, 1));
  process.exit(pass === results.length ? 0 : 1);
})().catch(e => { console.error('EXC', e); process.exit(2); });
