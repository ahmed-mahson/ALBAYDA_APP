const panels = [...document.querySelectorAll(".tool-panel")];
const resultsElement = document.querySelector("#results");
const statusElement = document.querySelector("#status-message");
const toastElement = document.querySelector("#toast");
let toastTimer;
let lastSupremeQuery = null;
let installPrompt = null;
const loadedOptionPanels = new Set();
const panelOptionPromises = new Map();
let caseTypeSources = {};

const fieldLabels = {
  "رقم القضية": ["رقم القضية", "رقم الدعوى"],
  "المدعي": ["المدعي"],
  "المدعى عليه": ["المدعى عليه"],
  "نوع القضية": ["نوع القضية"],
  "القاضي المختص": ["برئاسة القاضي"],
  "موضوع القضية": ["موضوعها", "موضوع القضية"],
  "حالة القضية": ["حالة القضية"],
  "تاريخ الجلسة القادمة": ["الجلسة القادمة"],
  "تاريخ الورود": ["تاريخ ورودها"],
};

function showToast(message) {
  toastElement.textContent = message;
  toastElement.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastElement.hidden = true; }, 5000);
}

function setStatus(message = "", kind = "") {
  statusElement.textContent = message;
  statusElement.className = `status-message ${kind}`.trim();
  statusElement.hidden = !message;
}

function setLoading(message) {
  resultsElement.hidden = true;
  resultsElement.replaceChildren();
  setStatus(message, "loading");
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let message = "تعذر تنفيذ الطلب.";
    try { message = (await response.json()).error || message; } catch {}
    throw new Error(message);
  }
  return response;
}

function showJsonError(error) {
  setStatus(error instanceof Error ? error.message : "تعذر الاتصال بالخادم.", "error");
}

function openPanel(id) {
  for (const panel of panels) panel.hidden = panel.id !== id;
  resultsElement.hidden = true;
  resultsElement.replaceChildren();
  setStatus("");
  const labels = {
    "case-panel": "الاستعلام عن قضية",
    "sessions-panel": "قائمة الجلسات",
    "ad-panel": "إنشاء إعلان حضور جلسة",
    "supreme-panel": "الاستعلام عن قضايا المحكمة العليا",
  };
  document.querySelector("#workspace-title").textContent = labels[id] || "اختر الخدمة المطلوبة";
  document.querySelector(".workspace").scrollIntoView({ behavior: "smooth", block: "start" });
  initializePanelOptions(id);
}

function addItemGrid(container, record, fields = fieldLabels) {
  const grid = document.createElement("div");
  grid.className = "result-grid";
  for (const [label, candidates] of Object.entries(fields)) {
    const key = candidates.find((candidate) => Object.hasOwn(record, candidate));
    const value = key ? record[key] : "";
    if (!value) continue;
    const item = document.createElement("div");
    item.className = "result-item";
    const name = document.createElement("b");
    name.textContent = `${label}:`;
    const text = document.createElement("span");
    text.textContent = String(value);
    item.append(name, text);
    grid.append(item);
  }
  container.append(grid);
}

function renderCases(payload) {
  resultsElement.replaceChildren();
  const summary = document.createElement("p");
  summary.className = "result-summary";
  summary.textContent = payload.count ? `عدد النتائج: ${payload.count}` : "لم يتم العثور على نتائج مطابقة.";
  resultsElement.append(summary);
  for (const record of payload.results) {
    const card = document.createElement("article");
    card.className = "result-card";
    const title = document.createElement("h3");
    title.textContent = `القضية رقم ${record["رقم القضية"] || "—"}`;
    card.append(title);
    addItemGrid(card, record);
    const actions = document.createElement("div");
    actions.className = "result-actions";
    const reportButton = document.createElement("button");
    reportButton.type = "button";
    reportButton.className = "secondary-button";
    reportButton.textContent = "تنزيل تفاصيل القضية PDF";
    reportButton.addEventListener("click", async () => {
      setStatus("جارٍ إنشاء تفاصيل القضية PDF…", "loading");
      try {
        await downloadPdf("/api/cases/report", { case_number: record["رقم القضية"] });
        setStatus("");
      } catch (error) { showJsonError(error); }
    });
    const adButton = document.createElement("button");
    adButton.type = "button";
    adButton.className = "secondary-button";
    adButton.textContent = "تحرير إعلان حضور لهذه القضية";
    adButton.addEventListener("click", () => openAdEditor(record));
    actions.append(reportButton, adButton);
    card.append(actions);
    resultsElement.append(card);
  }
  resultsElement.hidden = false;
  setStatus("");
}

function renderSessions(payload) {
  resultsElement.replaceChildren();
  const summary = document.createElement("p");
  summary.className = "result-summary";
  summary.textContent = payload.count ? `جلسات ${payload.date} — عدد الجلسات: ${payload.count}` : `لا توجد جلسات مسجلة بتاريخ ${payload.date}.`;
  resultsElement.append(summary);
  if (payload.results.length) {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headerRow = document.createElement("tr");
    for (const label of ["رقم القضية", "نوع القضية", "المدعي", "المدعى عليه", "القاضي", "المحكمة"]) {
      const th = document.createElement("th");
      th.textContent = label;
      headerRow.append(th);
    }
    head.append(headerRow);
    const body = document.createElement("tbody");
    for (const record of payload.results) {
      const row = document.createElement("tr");
      for (const value of [record["رقم القضية"], record["نوع القضية"], record["المدعي"], record["المدعى عليه"], record["برئاسة القاضي"], record["المحكمة"]]) {
        const cell = document.createElement("td");
        cell.textContent = value || "—";
        row.append(cell);
      }
      body.append(row);
    }
    table.append(head, body);
    wrap.append(table);
    resultsElement.append(wrap);
  }
  resultsElement.hidden = false;
  setStatus("");
}

function renderSupreme(payload) {
  resultsElement.replaceChildren();
  const summary = document.createElement("p");
  summary.className = "result-summary";
  summary.textContent = payload.count ? `عدد النتائج: ${payload.count}` : "لا توجد نتائج مطابقة.";
  resultsElement.append(summary);
  for (const result of payload.results) {
    const card = document.createElement("article");
    card.className = "result-card";
    const title = document.createElement("h3");
    title.textContent = result["الطاعن/الملتمس"] || result["الطاعن / الملتمس"] || "نتيجة من المحكمة العليا";
    card.append(title);
    const fields = Object.fromEntries(
      Object.keys(result).map((key) => [key, [key]]),
    );
    addItemGrid(card, result, fields);
    resultsElement.append(card);
  }
  resultsElement.hidden = false;
  setStatus("");
}

async function openAdEditor(record = {}) {
  openPanel("ad-panel");
  await initializePanelOptions("ad-panel");
  const form = document.querySelector("#ad-form");
  const selectedType = Object.keys(caseTypeSources).find((type) =>
    caseTypeSources[type].includes(record["نوع القضية"]),
  );
  if (selectedType) {
    form.elements.case_type.value = selectedType;
    try {
      await loadJudges(form.elements.judge_filter, selectedType, false);
    } catch (error) {
      showJsonError(error);
      return;
    }
    form.elements.judge_filter.value = record["برئاسة القاضي"] || "";
  }
  const nextDate = /^\d{4}-\d{2}-\d{2}$/.test(record["الجلسة القادمة"] || "")
    ? record["الجلسة القادمة"] : document.querySelector("#session-date").value;
  form.elements.case_number.value = record["رقم القضية"] || "";
  form.elements.session_date.value = nextDate || "اليوم";
  form.elements.plaintiff.value = record["المدعي"] || "";
  form.elements.defendant.value = record["المدعى عليه"] || "";
  form.elements.judge.value = record["برئاسة القاضي"] || "";
  document.querySelector(".workspace").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function downloadPdf(path, payload) {
  const response = await postJson(path, payload);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  const filename = encoded ? decodeURIComponent(encoded[1]) : "court-document.pdf";
  if (window.AlbaydaAndroid && typeof window.AlbaydaAndroid.saveFile === "function") {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    }
    window.AlbaydaAndroid.saveFile(filename, blob.type, btoa(binary));
    return;
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function replaceOptions(select, values, placeholder, includeAll = false) {
  const options = [];
  if (includeAll) options.push(new Option(placeholder, "all"));
  else options.push(new Option(placeholder, ""));
  for (const value of values) options.push(new Option(value, value));
  select.replaceChildren(...options);
}

async function fetchCaseOptions(caseType = "all") {
  const response = await postJson("/api/cases/options", { case_type: caseType });
  return response.json();
}

async function loadJudges(select, caseType, includeAll) {
  select.disabled = true;
  try {
    const options = await fetchCaseOptions(caseType);
    replaceOptions(
      select,
      options.judges,
      includeAll ? "كافة القضاة" : "اختر القاضي",
      includeAll,
    );
    select.disabled = false;
  } catch (error) {
    select.disabled = false;
    throw error;
  }
}

function initializePanelOptions(panelId) {
  if (loadedOptionPanels.has(panelId)) return Promise.resolve();
  if (panelOptionPromises.has(panelId)) return panelOptionPromises.get(panelId);
  if (!["case-panel", "sessions-panel", "ad-panel"].includes(panelId)) return Promise.resolve();

  const loading = (async () => {
    setStatus("جارٍ تحميل الأقسام والقضاة من ملف القضايا…", "loading");
    try {
      const allOptions = await fetchCaseOptions();
      caseTypeSources = allOptions.case_type_sources || {};
      if (panelId === "case-panel") {
        const form = document.querySelector("#case-form");
        replaceOptions(form.elements.case_type, allOptions.case_types, "جميع الأقسام", true);
        replaceOptions(form.elements.judge, allOptions.judges, "كافة القضاة", true);
      } else if (panelId === "sessions-panel") {
        replaceOptions(
          document.querySelector("#sessions-form").elements.judge,
          allOptions.judges,
          "جميع القضاة",
          true,
        );
      } else {
        const form = document.querySelector("#ad-form");
        replaceOptions(form.elements.case_type, allOptions.case_types, "اختر نوع القضية");
        replaceOptions(form.elements.judge_filter, [], "اختر القاضي");
      }
      loadedOptionPanels.add(panelId);
      setStatus("");
    } catch (error) {
      showJsonError(error);
    } finally {
      panelOptionPromises.delete(panelId);
    }
  })();
  panelOptionPromises.set(panelId, loading);
  return loading;
}

async function loadMeta() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("تعذر الاتصال بخادم التطبيق.");
    const status = await response.json();
    document.querySelector("#logout-button").hidden = !status.authentication_required;
    if (!status.source_configured) {
      setStatus("تعذر إعداد ملف سجل القضايا في Google Drive.", "error");
      return;
    }
    setStatus("");
  } catch (error) {
    showJsonError(error);
  }
}

for (const button of document.querySelectorAll("[data-open]")) {
  button.addEventListener("click", () => openPanel(button.dataset.open));
}

document.querySelector("#case-search-type").addEventListener("change", async (event) => {
  try {
    await loadJudges(
      document.querySelector("#case-search-judge"),
      event.currentTarget.value,
      true,
    );
  } catch (error) { showJsonError(error); }
});

document.querySelector("#ad-case-type").addEventListener("change", async (event) => {
  const judgeSelect = document.querySelector("#ad-judge-filter");
  if (!event.currentTarget.value) {
    replaceOptions(judgeSelect, [], "اختر القاضي");
    return;
  }
  try {
    await loadJudges(judgeSelect, event.currentTarget.value, false);
  } catch (error) { showJsonError(error); }
});

document.querySelector("#case-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setLoading("جارٍ البحث في سجل القضايا…");
  try {
    const response = await postJson("/api/cases/search", {
      query: form.elements.query.value,
      method: form.elements.method.value,
      case_type: form.elements.case_type.value,
      judge: form.elements.judge.value,
    });
    renderCases(await response.json());
  } catch (error) { showJsonError(error); }
});

document.querySelector("#sessions-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setLoading("جارٍ البحث عن الجلسات…");
  try {
    const response = await postJson("/api/sessions/search", {
      date: form.elements.date.value,
      judge: form.elements.judge.value,
    });
    renderSessions(await response.json());
  } catch (error) { showJsonError(error); }
});

document.querySelector("#sessions-pdf").addEventListener("click", async () => {
  const form = document.querySelector("#sessions-form");
  if (!form.reportValidity()) return;
  setStatus("جارٍ إنشاء قائمة الجلسات PDF…", "loading");
  try {
    await downloadPdf("/api/sessions/pdf", {
      date: form.elements.date.value,
      judge: form.elements.judge.value,
    });
    setStatus("");
  } catch (error) { showJsonError(error); }
});

document.querySelector("#lookup-ad-case").addEventListener("click", async () => {
  const form = document.querySelector("#ad-form");
  if (!form.elements.case_type.value || !form.elements.judge_filter.value) {
    setStatus("اختر نوع القضية والقاضي أولاً.", "error");
    return;
  }
  if (!form.elements.case_number.value.trim()) {
    form.elements.case_number.reportValidity();
    return;
  }
  setLoading("جارٍ البحث عن القضية في ملف سجل القضايا…");
  try {
    const response = await postJson("/api/cases/search", {
      query: form.elements.case_number.value,
      method: "number",
      case_type: form.elements.case_type.value,
      judge: form.elements.judge_filter.value,
    });
    const payload = await response.json();
    const record = payload.results[0];
    if (!record) throw new Error("لم أجد القضية بهذا الرقم ضمن النوع والقاضي المحددين.");
    form.elements.case_number.value = record["رقم القضية"] || form.elements.case_number.value;
    form.elements.plaintiff.value = record["المدعي"] || "";
    form.elements.defendant.value = record["المدعى عليه"] || "";
    form.elements.judge.value = record["برئاسة القاضي"] || "";
    setStatus("تم جلب بيانات القضية من ملف Google Drive. راجعها أو حرّرها قبل إنشاء الإعلان.");
  } catch (error) { showJsonError(error); }
});

document.querySelector("#ad-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setStatus("جارٍ إنشاء إعلان الحضور PDF…", "loading");
  try {
    await downloadPdf("/api/attendance-ad", {
      case_number: form.elements.case_number.value,
      session_date: form.elements.session_date.value,
      case_type: form.elements.case_type.value,
      judge_filter: form.elements.judge_filter.value,
      plaintiff: form.elements.plaintiff.value,
      defendant: form.elements.defendant.value,
      judge: form.elements.judge.value,
    });
    setStatus("تم إنشاء الإعلان. راجع بياناته قبل استخدامه رسمياً.");
  } catch (error) { showJsonError(error); }
});

document.querySelector("#supreme-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  lastSupremeQuery = {
    name: data.get("name"),
    decision_number: data.get("decision_number"),
    case_type: data.get("case_type"),
    authority: data.get("authority"),
  };
  setLoading("جارٍ الاتصال بموقع المحكمة العليا…");
  try {
    const response = await postJson("/api/supreme-court/search", lastSupremeQuery);
    renderSupreme(await response.json());
  } catch (error) { showJsonError(error); }
});

document.querySelector("#supreme-pdf").addEventListener("click", async () => {
  if (!lastSupremeQuery) {
    showToast("أجرِ بحثاً أولاً قبل تنزيل التقرير.");
    return;
  }
  setStatus("جارٍ إنشاء تقرير المحكمة العليا PDF…", "loading");
  try {
    await downloadPdf("/api/supreme-court/report", lastSupremeQuery);
    setStatus("");
  } catch (error) { showJsonError(error); }
});

document.querySelector("#session-date").value = "اليوم";
document.querySelector("#ad-form").elements.session_date.value = "اليوم";

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  document.querySelector("#install-button").hidden = false;
});

document.querySelector("#install-button").addEventListener("click", async () => {
  if (!installPrompt) return;
  await installPrompt.prompt();
  installPrompt = null;
  document.querySelector("#install-button").hidden = true;
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    const response = await postJson("/api/logout", {});
    if (!response.ok) throw new Error("تعذر تسجيل الخروج.");
    window.location.replace("/login");
  } catch (error) { showJsonError(error); }
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      showToast("تعذر تفعيل العمل دون اتصال. ستظل الخدمات تعمل عند توفر الشبكة.");
    });
  });
}

loadMeta();
