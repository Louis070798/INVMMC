let money = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

let compactMoney = new Intl.NumberFormat("vi-VN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

function updateLocaleFormatters(lang) {
  const locale = lang === "vi" ? "vi-VN" : "en-US";
  money = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  });
  compactMoney = new Intl.NumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: 1,
  });
}

const state = {
  projects: [],
  integrations: [],
  summary: null,
  lang: localStorage.getItem("lang") || "en",
  theme: localStorage.getItem("theme") || "light",
};

// Apply initial locale formatting rules
updateLocaleFormatters(state.lang);

const els = {
  periodSelect: document.querySelector("#periodSelect"),
  projectSelect: document.querySelector("#projectSelect"),
  exportProject: document.querySelector("#exportProject"),
  refreshBtn: document.querySelector("#refreshBtn"),
  periodLabel: document.querySelector("#periodLabel"),
  rangeLabel: document.querySelector("#rangeLabel"),
  kpiBudget: document.querySelector("#kpiBudget"),
  kpiActual: document.querySelector("#kpiActual"),
  kpiCommitted: document.querySelector("#kpiCommitted"),
  kpiAvailable: document.querySelector("#kpiAvailable"),
  kpiPending: document.querySelector("#kpiPending"),
  kpiTransfers: document.querySelector("#kpiTransfers"),
  budgetSub: document.querySelector("#budgetSub"),
  actualSub: document.querySelector("#actualSub"),
  committedSub: document.querySelector("#committedSub"),
  availableSub: document.querySelector("#availableSub"),
  pendingValue: document.querySelector("#pendingValue"),
  transferValue: document.querySelector("#transferValue"),
  budgetTrack: document.querySelector("#budgetTrack"),
  actualTrack: document.querySelector("#actualTrack"),
  committedTrack: document.querySelector("#committedTrack"),
  availableTrack: document.querySelector("#availableTrack"),
  navPending: document.querySelector("#navPending"),
  navTransfers: document.querySelector("#navTransfers"),
  projectBars: document.querySelector("#projectBars"),
  approvalRows: document.querySelector("#approvalRows"),
  attachmentRows: document.querySelector("#attachmentRows"),
  integrationList: document.querySelector("#integrationList"),
  reportScope: document.querySelector("#reportScope"),
  saveState: document.querySelector("#saveState"),
  projectDialog: document.querySelector("#projectDialog"),
  projectForm: document.querySelector("#projectForm"),
  footerProjects: document.querySelector("#footerProjects"),
  footerBudget: document.querySelector("#footerBudget"),
  footerActual: document.querySelector("#footerActual"),
  footerCommitted: document.querySelector("#footerCommitted"),
  footerAvailable: document.querySelector("#footerAvailable"),
  footerPending: document.querySelector("#footerPending"),
  footerTransfers: document.querySelector("#footerTransfers"),
  tabTitle: document.querySelector("#tabTitle"),
  tabSubtitle: document.querySelector("#tabSubtitle"),
  telegramBotName: document.querySelector("#telegramBotName"),
  telegramWebhookSecret: document.querySelector("#telegramWebhookSecret"),
  telegramWebhookUrl: document.querySelector("#telegramWebhookUrl"),
  telegramTokenStatus: document.querySelector("#telegramTokenStatus"),
  saveTelegramBotFather: document.querySelector("#saveTelegramBotFather"),
  transferExportPeriod: document.querySelector("#transferExportPeriod"),
  transferExportRange: document.querySelector("#transferExportRange"),
  transferExportStart: document.querySelector("#transferExportStart"),
  transferExportEnd: document.querySelector("#transferExportEnd"),
  transferExportProject: document.querySelector("#transferExportProject"),
  transferExportBtn: document.querySelector("#transferExportBtn"),
};

const tabLabels = {
  vi: {
    dashboard: ["Bảng điều khiển", "Tổng quan ngân sách, phê duyệt và chứng từ theo dự án."],
    projects: ["Dự án", "Quản lý danh mục dự án, ngân sách và mức sử dụng."],
    approvals: ["Hàng chờ duyệt", "Theo dõi các đề nghị chi đang chờ kiểm tra hoặc phê duyệt."],
    integrations: ["Kết nối", "Cấu hình Telegram BotFather, ngân hàng/VietQR và MoMo."],
    reports: ["Báo cáo", "Xuất báo cáo theo dự án, ngày, tuần hoặc tháng."],
    transfers: ["Chứng từ & Giao dịch", "Kiểm tra ảnh chuyển khoản và chứng từ gửi từ Telegram."],
    settings: ["Cài đặt", "Thông tin cấu hình vận hành local và production."],
  },
  en: {
    dashboard: ["Dashboard", "Overview of budget, approvals, and documents by project."],
    projects: ["Projects", "Manage project portfolios, budgets, and utilization."],
    approvals: ["Approval Queue", "Track expense requests waiting for verification or approval."],
    integrations: ["Integrations", "Configure Telegram BotFather, banks/VietQR, and MoMo."],
    reports: ["Reports", "Export reports by project, day, week, or month."],
    transfers: ["Documents & Transfers", "Check transfer images and documents sent from Telegram."],
    settings: ["Settings", "Local and production system setting details."],
  }
};

function qs() {
  const params = new URLSearchParams();
  params.set("period", els.periodSelect.value);
  if (els.projectSelect.value) params.set("project_id", els.projectSelect.value);
  return params;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function loadProjects() {
  state.projects = await api("/api/v1/projects");
  const current = els.projectSelect.value;
  const exportCurrent = els.exportProject.value;
  const transferExportCurrent = els.transferExportProject.value;

  const allProjectsText = state.lang === "vi" ? "Tất cả dự án" : "All Projects";
  els.projectSelect.innerHTML = `<option value="">${allProjectsText}</option>`;
  els.exportProject.innerHTML = `<option value="">${allProjectsText}</option>`;
  els.transferExportProject.innerHTML = `<option value="">${allProjectsText}</option>`;

  for (const project of state.projects) {
    const label = `${project.code} - ${project.name}`;
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = label;
    els.projectSelect.append(option);

    const exportOption = document.createElement("option");
    exportOption.value = project.id;
    exportOption.textContent = label;
    els.exportProject.append(exportOption);

    const transferOption = document.createElement("option");
    transferOption.value = project.id;
    transferOption.textContent = label;
    els.transferExportProject.append(transferOption);
  }

  els.projectSelect.value = current;
  els.exportProject.value = exportCurrent;
  els.transferExportProject.value = transferExportCurrent;
}

async function loadIntegrations() {
  state.integrations = await api("/api/v1/integrations");
  renderIntegrations();
  hydrateTelegramSetup();
}

async function loadSummary() {
  state.summary = await api(`/api/v1/dashboard/summary?${qs().toString()}`);
  renderSummary();
}

function renderSummary() {
  const summary = state.summary;
  const kpis = summary.kpis;
  const committed = summary.approval_queue.reduce((sum, item) => sum + item.amount, 0);
  const totalBudget = kpis.total_budget || 1;
  const selectedProject = state.projects.find((project) => project.id === els.projectSelect.value);
  const actualPct = percent(kpis.total_actual, totalBudget);
  const committedPct = percent(committed, totalBudget);
  const availablePct = percent(kpis.available, totalBudget);
  const pendingValue = summary.approval_queue.reduce((sum, item) => sum + item.amount, 0);
  const transferValue = summary.attachments.reduce((sum, item) => sum + (item.amount_hint || 0), 0);

  els.periodLabel.textContent = state.lang === "vi" ? "Đồng bộ lúc: Vừa xong" : "Last synced: just now";
  els.rangeLabel.textContent = rangeLabel(summary.period);
  els.kpiBudget.textContent = shortVnd(kpis.total_budget);
  els.kpiActual.textContent = shortVnd(kpis.total_actual);
  els.kpiCommitted.textContent = shortVnd(committed);
  els.kpiAvailable.textContent = shortVnd(kpis.available);
  els.kpiPending.textContent = kpis.pending_approvals;
  els.kpiTransfers.textContent = kpis.unmatched_transfers;

  const dict = translations[state.lang];
  els.budgetSub.textContent = dict.lbl_100_percent;
  els.actualSub.textContent = `${actualPct.toFixed(1)}% ${dict.lbl_percent_of_budget}`;
  els.committedSub.textContent = `${committedPct.toFixed(1)}% ${dict.lbl_percent_of_budget}`;
  els.availableSub.textContent = `${availablePct.toFixed(1)}% ${dict.lbl_percent_of_budget}`;
  els.pendingValue.textContent = money.format(pendingValue);
  els.transferValue.textContent = money.format(transferValue);
  els.budgetTrack.style.width = "100%";
  els.actualTrack.style.width = `${Math.min(actualPct, 100)}%`;
  els.committedTrack.style.width = `${Math.min(committedPct, 100)}%`;
  els.availableTrack.style.width = `${Math.min(availablePct, 100)}%`;
  els.navPending.textContent = kpis.pending_approvals;
  els.navTransfers.textContent = kpis.unmatched_transfers;

  els.reportScope.textContent = selectedProject
    ? (state.lang === "vi" ? `Phạm vi: ${selectedProject.code} - ${selectedProject.name}` : `Scope: ${selectedProject.code} - ${selectedProject.name}`)
    : (state.lang === "vi" ? "Phạm vi: tất cả dự án" : "Scope: all projects");

  renderProjectChart(summary.projects);
  renderApprovalRows(summary.approval_queue);
  renderAttachmentRows();
  renderFooter(kpis, committed, summary.projects.length, transferValue);
}

function renderProjectChart(projects) {
  els.projectBars.innerHTML = "";
  if (!projects.length) {
    const text = state.lang === "vi" ? "Chưa có dự án nào" : "No projects available";
    els.projectBars.innerHTML = `<div class="empty">${text}</div>`;
    return;
  }

  const maxBudget = Math.max(...projects.map((project) => project.budget), 1);
  for (const project of projects.slice(0, 7)) {
    const group = document.createElement("div");
    group.className = "chart-group";
    const budgetHeight = Math.max((project.budget / maxBudget) * 100, 4);
    const actualHeight = Math.max((project.actual / maxBudget) * 100, project.actual > 0 ? 4 : 0);
    group.innerHTML = `
      <div class="bar-values">
        <span>${compactMoney.format(project.budget)}</span>
        <span>${compactMoney.format(project.actual)}</span>
      </div>
      <div class="bar-pair">
        <i class="budget-bar" style="height:${budgetHeight}%"></i>
        <i class="actual-bar" style="height:${actualHeight}%"></i>
      </div>
      <strong>${project.code}</strong>
      <small>${project.name}</small>
    `;
    els.projectBars.append(group);
  }
}

function renderApprovalRows(rows) {
  els.approvalRows.innerHTML = "";
  if (!rows.length) {
    const text = state.lang === "vi" ? "Chưa có phê duyệt nào" : "No pending approvals";
    els.approvalRows.innerHTML = `<tr><td colspan="7">${text}</td></tr>`;
    return;
  }
  for (const item of rows.slice(0, 5)) {
    const project = projectById(item.project_id);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.id}</td>
      <td>${project?.code || item.project_id}</td>
      <td>${item.description}</td>
      <td class="amount">${shortVnd(item.amount)}</td>
      <td>${item.project_id.replace("prj-", "user-")}</td>
      <td>${formatDate(item.created_at)}</td>
      <td>${statusPill(item.status)}</td>
    `;
    els.approvalRows.append(tr);
  }
}

function transactionTypeLabel(type) {
  if (type === "thu") return '<span class="pill pill-thu">THU</span>';
  if (type === "chi") return '<span class="pill pill-chi">CHI</span>';
  return '<span class="pill">?</span>';
}

function renderAttachmentRows() {
  const rows = state.attachments || [];
  els.attachmentRows.innerHTML = "";
  if (!rows.length) {
    const text = state.lang === "vi" ? "Chưa có chứng từ nào" : "No documents yet";
    els.attachmentRows.innerHTML = `<tr><td colspan="8">${text}</td></tr>`;
    return;
  }
  const limit = document.body.dataset.tab === "transfers" ? 100 : 5;
  for (const item of rows.slice(0, limit)) {
    const project = projectById(item.project_id);
    const file = item.file_url
      ? `<a class="file-link" href="${item.file_url}" target="_blank" rel="noreferrer">Open</a>`
      : "-";
    const editLabel = state.lang === "vi" ? "Sửa" : "Edit";
    const deleteLabel = state.lang === "vi" ? "Xóa" : "Delete";
    const confirmLabel = state.lang === "vi" ? "Xác nhận" : "Confirm";
    const confirmButton = item.review_status === "confirmed"
      ? ""
      : `<button type="button" class="confirm" data-confirm-att="${item.id}">${confirmLabel}</button>`;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDateTime(item.received_at)}</td>
      <td>${project?.code || "-"}</td>
      <td>${transactionTypeLabel(item.transaction_type)}</td>
      <td class="amount">${item.amount_hint ? shortVnd(item.amount_hint) : "-"}</td>
      <td>${item.counterparty || "-"}</td>
      <td><span class="receipt-preview">${file}</span></td>
      <td>${statusPill(item.review_status)}</td>
      <td class="row-actions">
        ${confirmButton}
        <button type="button" data-edit-att="${item.id}">${editLabel}</button>
        <button type="button" class="danger" data-del-att="${item.id}">${deleteLabel}</button>
      </td>
    `;
    els.attachmentRows.append(tr);
  }
}

async function loadAttachments() {
  state.attachments = await api("/api/v1/attachments?limit=100");
  renderAttachmentRows();
}

function renderIntegrations() {
  els.integrationList.innerHTML = "";
  for (const integration of state.integrations) {
    const item = document.createElement("div");
    item.className = "integration-item";
    const meta = integrationMeta(integration.key);
    item.innerHTML = `
      <span class="provider-icon ${meta.className}">${meta.icon}</span>
      <div class="integration-copy">
        <strong>${integration.display_name}</strong>
        <small>${meta.detail(integration)}</small>
        <span class="connection ${integration.enabled ? "ok" : "warn"}"><i></i>${formatStatus(integration.status)}</span>
      </div>
      <div class="integration-config">
        <input aria-label="${integration.display_name} config" value='${JSON.stringify(integration.config)}' data-config="${integration.key}" />
        <label><input type="checkbox" ${integration.enabled ? "checked" : ""} data-toggle="${integration.key}" /> Enabled</label>
      </div>
      <button type="button" data-save="${integration.key}">Configure</button>
    `;
    els.integrationList.append(item);
  }
}

function hydrateTelegramSetup() {
  const telegram = state.integrations.find((item) => item.key === "telegram");
  if (!telegram) return;
  const config = telegram.config || {};
  els.telegramBotName.value = config.bot_username || "";
  els.telegramWebhookSecret.value = config.webhook_secret || "";
  els.telegramWebhookUrl.value = config.webhook_url || `${window.location.origin}/telegram/webhook`;
  els.telegramTokenStatus.value = config.token_status || "env";
}

async function saveTelegramSetup() {
  const config = {
    bot_username: els.telegramBotName.value.trim(),
    webhook_secret: els.telegramWebhookSecret.value.trim(),
    webhook_url: els.telegramWebhookUrl.value.trim(),
    token_status: els.telegramTokenStatus.value,
    managed_by: "BotFather",
    setup_note: "Store TELEGRAM_BOT_TOKEN in .env for production.",
  };
  await api("/api/v1/integrations/telegram", {
    method: "PATCH",
    body: JSON.stringify({ enabled: true, status: "botfather_configured", config }),
  });
  els.saveState.textContent = "Telegram setup saved";
  await loadIntegrations();
  setTimeout(() => {
    els.saveState.textContent = "";
  }, 1600);
}

function renderFooter(kpis, committed, projectCount, transferValue) {
  if (state.lang === "vi") {
    els.footerProjects.textContent = `Dự án: ${projectCount}`;
    els.footerBudget.textContent = `Tổng ngân sách: ${money.format(kpis.total_budget)}`;
    els.footerActual.textContent = `Thực chi: ${money.format(kpis.total_actual)}`;
    els.footerCommitted.textContent = `Cam kết: ${money.format(committed)}`;
    els.footerAvailable.textContent = `Ngân sách còn trống: ${money.format(kpis.available)}`;
    els.footerPending.textContent = `Chờ duyệt: ${kpis.pending_approvals}`;
    els.footerTransfers.textContent = `Chuyển khoản chưa khớp: ${kpis.unmatched_transfers} (${money.format(transferValue)})`;
  } else {
    els.footerProjects.textContent = `Projects: ${projectCount}`;
    els.footerBudget.textContent = `Total Budget: ${money.format(kpis.total_budget)}`;
    els.footerActual.textContent = `Total Actual: ${money.format(kpis.total_actual)}`;
    els.footerCommitted.textContent = `Committed: ${money.format(committed)}`;
    els.footerAvailable.textContent = `Remaining Budget: ${money.format(kpis.available)}`;
    els.footerPending.textContent = `Pending Approvals: ${kpis.pending_approvals}`;
    els.footerTransfers.textContent = `Unmatched Transfers: ${kpis.unmatched_transfers} (${money.format(transferValue)})`;
  }
}

function statusPill(status) {
  const cls = ["paid", "reconciled", "closed", "active", "matched", "confirmed"].includes(status)
    ? "ok"
    : ["rejected", "budget_exceeded", "unmatched", "duplicate"].includes(status)
      ? "risk"
      : "waiting";
  return `<span class="status ${cls}">${status}</span>`;
}

function integrationMeta(key) {
  const map = {
    telegram: {
      className: "telegram",
      icon: "✈",
      detail: (item) => `Bot: @${item.config?.bot_username || item.config?.bot_username_hint || "not_checked"}`,
    },
    bank: {
      className: "bank",
      icon: "▥",
      detail: (item) => `Provider: ${(item.config && item.config.provider) || "Bank API"}`,
    },
    momo: {
      className: "momo",
      icon: "mo",
      detail: () => "Wallet: business sandbox",
    },
  };
  return map[key] || { className: "bank", icon: "API", detail: () => "External provider" };
}

function projectById(projectId) {
  return state.projects.find((project) => project.id === projectId);
}

function percent(value, total) {
  return total ? (value / total) * 100 : 0;
}

function formatStatus(status) {
  return status.replaceAll("_", " ");
}

function shortVnd(value) {
  if (state.lang === "en") {
    return `${compactMoney.format(value).replace(" ", " ")} VND`;
  }
  return `${compactMoney.format(value).replace(" ", " ")} đ`;
}

function rangeLabel(period) {
  if (state.lang === "vi") {
    if (period === "day") return "Hôm nay";
    if (period === "week") return "Tuần này";
    return "Tháng này";
  }
  if (period === "day") return "Today";
  if (period === "week") return "Current week";
  return "Current month";
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function saveIntegration(key) {
  const toggle = document.querySelector(`[data-toggle="${key}"]`);
  const configInput = document.querySelector(`[data-config="${key}"]`);
  let config = {};
  try {
    config = JSON.parse(configInput.value || "{}");
  } catch {
    els.saveState.textContent = "Invalid JSON";
    return;
  }
  await api(`/api/v1/integrations/${key}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled: toggle.checked, status: toggle.checked ? "configured" : "disabled", config }),
  });
  els.saveState.textContent = "Saved";
  await loadIntegrations();
  setTimeout(() => {
    els.saveState.textContent = "";
  }, 1500);
}

async function createProject(event) {
  event.preventDefault();
  const formData = new FormData(els.projectForm);
  await api("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify({
      code: formData.get("code"),
      name: formData.get("name"),
      owner: formData.get("owner"),
      department: formData.get("department"),
      budget_amount: Number(formData.get("budget_amount")),
    }),
  });
  els.projectDialog.close();
  els.projectForm.reset();
  await refreshAll();
}

function exportReport() {
  const params = new URLSearchParams();
  params.set("period", state.exportPeriod || "month");
  if (state.exportPeriod === "custom") {
    const start = document.querySelector("#exportStartDate").value;
    const end = document.querySelector("#exportEndDate").value;
    if (!start || !end) {
      alert(state.lang === "vi" ? "Vui lòng chọn ngày bắt đầu và ngày kết thúc." : "Please pick a start date and an end date.");
      return;
    }
    if (end < start) {
      alert(state.lang === "vi" ? "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu." : "End date must be on or after the start date.");
      return;
    }
    params.set("start_date", start);
    params.set("end_date", end);
  }
  const projectId = els.exportProject.value;
  if (projectId) params.set("project_id", projectId);
  const reportType = document.querySelector("#exportType").value;
  const base = reportType === "transfers" ? "/api/v1/transfers/export" : "/api/v1/reports/export";
  window.location.href = `${base}?${params.toString()}`;
}

function exportTransfers() {
  const period = els.transferExportPeriod.value;
  const params = new URLSearchParams();
  params.set("period", period);
  if (period === "custom") {
    const start = els.transferExportStart.value;
    const end = els.transferExportEnd.value;
    if (!start || !end) {
      alert(state.lang === "vi" ? "Vui lòng chọn ngày bắt đầu và ngày kết thúc." : "Please pick a start date and an end date.");
      return;
    }
    if (end < start) {
      alert(state.lang === "vi" ? "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu." : "End date must be on or after the start date.");
      return;
    }
    params.set("start_date", start);
    params.set("end_date", end);
  }
  const projectId = els.transferExportProject.value;
  if (projectId) params.set("project_id", projectId);
  window.location.href = `/api/v1/transfers/export?${params.toString()}`;
}

function setActiveTab(tab) {
  const normalized = tabLabels[state.lang][tab] ? tab : "dashboard";
  const [title, subtitle] = tabLabels[state.lang][normalized];
  document.body.dataset.tab = normalized;
  els.tabTitle.textContent = title;
  els.tabSubtitle.textContent = subtitle;

  document.querySelectorAll("[data-tab]").forEach((link) => {
    link.classList.toggle("active", link.dataset.tab === normalized && !link.classList.contains("sub"));
  });

  document.querySelectorAll("[data-views]").forEach((section) => {
    const views = section.dataset.views.split(",");
    section.hidden = !views.includes(normalized);
  });
}

function activeTabFromHash() {
  return window.location.hash.replace("#", "") || "dashboard";
}

async function refreshAll() {
  await loadProjects();
  await loadIntegrations();
  await loadSummary();
  await loadAttachments();
}

els.periodSelect.addEventListener("change", loadSummary);
els.projectSelect.addEventListener("change", loadSummary);
els.refreshBtn.addEventListener("click", refreshAll);
document.querySelector("#newProjectBtn").addEventListener("click", () => els.projectDialog.showModal());
document.querySelector("#closeProjectDialog").addEventListener("click", () => els.projectDialog.close());
els.projectForm.addEventListener("submit", createProject);
state.exportPeriod = "month";
document.querySelectorAll("#exportPeriodButtons [data-export]").forEach((button) => {
  button.addEventListener("click", () => {
    state.exportPeriod = button.dataset.export;
    document.querySelectorAll("#exportPeriodButtons [data-export]").forEach((other) => {
      other.classList.toggle("selected", other === button);
    });
    document.querySelector("#customRange").hidden = state.exportPeriod !== "custom";
  });
});
document.querySelector("#exportReportBtn").addEventListener("click", exportReport);
els.transferExportPeriod.addEventListener("change", () => {
  els.transferExportRange.hidden = els.transferExportPeriod.value !== "custom";
});
els.transferExportBtn.addEventListener("click", exportTransfers);
els.saveTelegramBotFather.addEventListener("click", saveTelegramSetup);
document.querySelectorAll("[data-tab]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const tab = link.dataset.tab;
    window.location.hash = tab;
    setActiveTab(tab);
  });
});
window.addEventListener("hashchange", () => setActiveTab(activeTabFromHash()));
els.integrationList.addEventListener("click", (event) => {
  const key = event.target.dataset.save;
  if (key) saveIntegration(key);
});

async function checkAuth() {
  try {
    state.user = await api("/api/v1/auth/me");
    if (state.user) {
      const nameEl = document.querySelector(".username");
      if (nameEl) nameEl.textContent = state.user.full_name || state.user.email;

      const roleEl = document.querySelector(".role");
      if (roleEl) {
        const displayRole = state.user.roles.map(r => r.replace("_", " ")).join(", ");
        roleEl.textContent = displayRole;
      }

      const avatarEl = document.querySelector(".avatar");
      if (avatarEl && state.user.full_name) {
        avatarEl.textContent = state.user.full_name.charAt(0).toUpperCase();
      }
    }
  } catch (error) {
    console.error("Unauthorized. Redirecting to login...", error);
    window.location.href = "/static/login.html";
  }
}

// Log out button listener
const logoutBtn = document.querySelector("#logoutBtn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } catch (e) {
      console.error("Logout failed but clearing session...", e);
    }
    window.location.href = "/static/login.html";
  });
}

// Handle Dialog forms for Expense
const newExpenseBtn = document.querySelector("#newExpenseBtn");
const expenseDialog = document.querySelector("#expenseDialog");
const closeExpenseDialog = document.querySelector("#closeExpenseDialog");
const expenseForm = document.querySelector("#expenseForm");
const expenseProjectSelect = document.querySelector("#expenseProjectSelect");
const expenseAmountInput = document.querySelector("#expenseAmountInput");
const expenseApprovalLevel = document.querySelector("#expenseApprovalLevel");

if (newExpenseBtn && expenseDialog) {
  newExpenseBtn.addEventListener("click", () => {
    // Populate projects select in dialog dynamically
    expenseProjectSelect.innerHTML = "";
    for (const project of state.projects) {
      const option = document.createElement("option");
      option.value = project.id;
      option.textContent = `${project.code} - ${project.name}`;
      expenseProjectSelect.append(option);
    }
    expenseDialog.showModal();
  });
}

if (closeExpenseDialog && expenseDialog) {
  closeExpenseDialog.addEventListener("click", () => expenseDialog.close());
}

if (expenseAmountInput && expenseApprovalLevel) {
  expenseAmountInput.addEventListener("input", () => {
    const val = Number(expenseAmountInput.value) || 0;
    if (val <= 0) {
      expenseApprovalLevel.textContent = state.lang === "vi" ? "Nhập số tiền hợp lệ." : "Enter a valid amount.";
      expenseApprovalLevel.style.color = "var(--text-muted)";
    } else if (val <= 2000000) {
      expenseApprovalLevel.textContent = state.lang === "vi" ? "Hạn mức đề xuất: Project Manager duyệt" : "Proposed limit: Approved by Project Manager";
      expenseApprovalLevel.style.color = "var(--green)";
    } else if (val <= 20000000) {
      expenseApprovalLevel.textContent = state.lang === "vi" ? "Hạn mức đề xuất: PM + Finance Controller duyệt" : "Proposed limit: Approved by PM + Finance Controller";
      expenseApprovalLevel.style.color = "var(--primary)";
    } else if (val <= 100000000) {
      expenseApprovalLevel.textContent = state.lang === "vi" ? "Hạn mức đề xuất: Department Head + Finance Manager duyệt" : "Proposed limit: Approved by Department Head + Finance Manager";
      expenseApprovalLevel.style.color = "var(--yellow)";
    } else if (val <= 500000000) {
      expenseApprovalLevel.textContent = state.lang === "vi" ? "Hạn mức đề xuất: CFO duyệt" : "Proposed limit: Approved by CFO";
      expenseApprovalLevel.style.color = "var(--orange)";
    } else {
      expenseApprovalLevel.textContent = state.lang === "vi" ? "Hạn mức lớn: Cần CEO / Board phê duyệt" : "Large limit: CEO / Board approval required";
      expenseApprovalLevel.style.color = "var(--red)";
    }
  });
}

if (expenseForm) {
  expenseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(expenseForm);
    const amount = Number(formData.get("amount"));

    try {
      await api("/api/v1/expenses", {
        method: "POST",
        body: JSON.stringify({
          project_id: formData.get("project_id"),
          requester_id: state.user?.id || "user-admin",
          amount: amount,
          currency: "VND",
          budget_line_code: formData.get("budget_line_code"),
          vendor_id: formData.get("vendor_id"),
          description: formData.get("description"),
        }),
      });
      expenseDialog.close();
      expenseForm.reset();
      await refreshAll();
    } catch (err) {
      alert("Lỗi khi gửi yêu cầu đề nghị chi: " + err.message);
    }
  });
}

// ---- Attachment (chung tu) CRUD ----
const attachmentDialog = document.querySelector("#attachmentDialog");
const attachmentForm = document.querySelector("#attachmentForm");
const attachmentDialogTitle = document.querySelector("#attachmentDialogTitle");
const attachmentFileLabel = document.querySelector("#attachmentFileLabel");
const attachProjectSelect = document.querySelector("#attachProjectSelect");
const newAttachmentBtn = document.querySelector("#newAttachmentBtn");

function fillAttachProjectSelect(selectedCode) {
  const noneText = state.lang === "vi" ? "Chưa gắn dự án" : "No project";
  attachProjectSelect.innerHTML = `<option value="">${noneText}</option>`;
  for (const project of state.projects) {
    const option = document.createElement("option");
    option.value = project.code;
    option.textContent = `${project.code} - ${project.name}`;
    attachProjectSelect.append(option);
  }
  attachProjectSelect.value = selectedCode || "";
}

function openAttachmentDialog(item) {
  attachmentForm.reset();
  attachmentForm.elements.id.value = item?.id || "";
  const project = item ? projectById(item.project_id) : null;
  fillAttachProjectSelect(project?.code || "");
  if (item) {
    attachmentDialogTitle.textContent = state.lang === "vi" ? `Sửa chứng từ ${item.id}` : `Edit document ${item.id}`;
    attachmentForm.elements.transaction_type.value = item.transaction_type || "unknown";
    attachmentForm.elements.amount.value = item.amount_hint ?? "";
    attachmentForm.elements.counterparty.value = item.counterparty || "";
    attachmentForm.elements.bank_name.value = item.bank_name || "";
    attachmentForm.elements.reference.value = item.reference || "";
    attachmentForm.elements.transacted_at.value = item.transacted_at || "";
    attachmentForm.elements.note.value = item.note || "";
    attachmentFileLabel.hidden = true;
  } else {
    attachmentDialogTitle.textContent = state.lang === "vi" ? "Thêm chứng từ" : "Add document";
    attachmentFileLabel.hidden = false;
  }
  attachmentDialog.showModal();
}

function attachmentErrorMessage(raw) {
  const map = {
    missing_transaction_type: "Chưa rõ THU hay CHI — chọn loại giao dịch trước khi xác nhận.",
    missing_amount: "Chưa có số tiền — nhập số tiền trước khi xác nhận.",
    missing_project: "Chưa gắn dự án — chọn dự án trước khi xác nhận.",
    project_not_found: "Mã dự án không tồn tại.",
    invalid_amount: "Số tiền không hợp lệ.",
    attachment_not_found: "Chứng từ không còn tồn tại.",
  };
  for (const [key, message] of Object.entries(map)) {
    if (raw.includes(key)) return message;
  }
  return raw;
}

async function submitAttachmentForm(event) {
  event.preventDefault();
  const id = attachmentForm.elements.id.value;
  // Nut nao duoc bam quyet dinh trang thai: Luu (cho duyet) hoac Luu & Xac nhan.
  const reviewStatus = event.submitter?.dataset.review || "pending_review";
  try {
    if (id) {
      await api(`/api/v1/attachments/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          project_code: attachmentForm.elements.project_code.value,
          transaction_type: attachmentForm.elements.transaction_type.value,
          amount_hint: attachmentForm.elements.amount.value === "" ? null : Number(attachmentForm.elements.amount.value),
          counterparty: attachmentForm.elements.counterparty.value,
          bank_name: attachmentForm.elements.bank_name.value,
          reference: attachmentForm.elements.reference.value,
          transacted_at: attachmentForm.elements.transacted_at.value,
          note: attachmentForm.elements.note.value,
          review_status: reviewStatus,
        }),
      });
    } else {
      const formData = new FormData();
      formData.set("project_code", attachmentForm.elements.project_code.value);
      formData.set("transaction_type", attachmentForm.elements.transaction_type.value);
      formData.set("amount", attachmentForm.elements.amount.value);
      formData.set("counterparty", attachmentForm.elements.counterparty.value);
      formData.set("bank_name", attachmentForm.elements.bank_name.value);
      formData.set("reference", attachmentForm.elements.reference.value);
      formData.set("transacted_at", attachmentForm.elements.transacted_at.value);
      formData.set("note", attachmentForm.elements.note.value);
      const fileInput = attachmentForm.elements.file;
      if (fileInput.files.length) formData.set("file", fileInput.files[0]);
      const created = await createAttachment(formData);
      // POST luon tao o trang thai cho duyet; xac nhan ngay thi PATCH tiep.
      if (reviewStatus === "confirmed") {
        await api(`/api/v1/attachments/${created.id}`, {
          method: "PATCH",
          body: JSON.stringify({ review_status: "confirmed" }),
        }).catch((error) => alert(attachmentErrorMessage(error.message)));
      }
    }
    attachmentDialog.close();
    attachmentForm.reset();
    await loadSummary();
    await loadAttachments();
  } catch (error) {
    alert(attachmentErrorMessage(error.message));
  }
}

async function createAttachment(formData) {
  let response = await fetch("/api/v1/attachments", { method: "POST", body: formData });
  if (response.status === 409) {
    const keep = confirm(
      state.lang === "vi"
        ? "Ảnh này TRÙNG với chứng từ đã có. Vẫn lưu chứ?"
        : "This image DUPLICATES an existing document. Save anyway?"
    );
    if (!keep) throw new Error(state.lang === "vi" ? "Đã hủy vì trùng ảnh." : "Cancelled: duplicate image.");
    formData.set("force", "true");
    response = await fetch("/api/v1/attachments", { method: "POST", body: formData });
  }
  if (!response.ok) throw new Error(await response.text());
  const created = await response.json();
  state.attachments = [created, ...(state.attachments || [])];
  return created;
}

async function confirmAttachment(id) {
  try {
    await api(`/api/v1/attachments/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: "confirmed" }),
    });
    await loadSummary();
    await loadAttachments();
  } catch (error) {
    alert(attachmentErrorMessage(error.message));
  }
}

async function deleteAttachment(id) {
  const message = state.lang === "vi"
    ? `Xóa chứng từ ${id}? Ảnh kèm theo cũng bị xóa.`
    : `Delete document ${id}? Its image file is removed too.`;
  if (!confirm(message)) return;
  try {
    await api(`/api/v1/attachments/${id}`, { method: "DELETE" });
    await loadSummary();
    await loadAttachments();
  } catch (error) {
    alert(attachmentErrorMessage(error.message));
  }
}

if (newAttachmentBtn) {
  newAttachmentBtn.addEventListener("click", () => openAttachmentDialog(null));
}
document.querySelector("#closeAttachmentDialog").addEventListener("click", () => attachmentDialog.close());
attachmentForm.addEventListener("submit", submitAttachmentForm);
els.attachmentRows.addEventListener("click", (event) => {
  const editId = event.target.dataset.editAtt;
  const deleteId = event.target.dataset.delAtt;
  const confirmId = event.target.dataset.confirmAtt;
  if (editId) {
    const item = (state.attachments || []).find((row) => row.id === editId);
    if (item) openAttachmentDialog(item);
  }
  if (deleteId) deleteAttachment(deleteId);
  if (confirmId) confirmAttachment(confirmId);
});

const translations = {
  vi: {
    nav_overview: "Tổng quan",
    nav_projects: "Dự án",
    nav_reports: "Báo cáo",
    nav_approvals: "Phê duyệt",
    nav_integrations: "Kết nối",
    nav_transfers: "Giao dịch",
    nav_settings: "Cài đặt",
    card_title: "Thẻ hệ thống",
    card_active_conn: "Kết nối hoạt động",
    card_host: "Máy chủ lưu trữ",
    card_host_val: "Cơ sở dữ liệu nội bộ",
    card_webhook: "Trạng thái Webhook",
    card_webhook_val: "Đã kết nối",
    ctrl_title: "Bộ điều khiển",
    ctrl_period: "Chọn kì hạn",
    ctrl_project: "Lọc dự án",
    btn_new_project: "+ Tạo dự án",
    btn_new_expense: "+ Đề nghị chi",
    opt_today: "Hôm nay",
    opt_week: "Tuần này",
    opt_month: "Tháng này",
    opt_all_projects: "Tất cả dự án",
    kpi_budget: "Tổng ngân sách",
    kpi_actual: "Tổng thực chi",
    kpi_committed: "Đã cam kết chi",
    kpi_available: "Mức khả dụng",
    kpi_pending: "Yêu cầu chờ duyệt",
    kpi_transfers: "Giao dịch chưa khớp",
    lbl_100_percent: "100% kế hoạch",
    lbl_percent_of_budget: "so với dự toán",
    opt_export_day: "Theo ngày",
    opt_export_month: "Theo tháng",
    opt_export_year: "Theo năm",
    opt_export_custom: "Tùy chọn khoảng ngày",
    btn_export_transfers: "Xuất báo cáo",
    lbl_report_type: "Loại báo cáo",
    opt_report_projects: "Tổng hợp dự án (ngân sách, thu/chi)",
    opt_report_transfers: "Chi tiết giao dịch (thu/chi)",
    opt_p_day: "Ngày",
    opt_p_week: "Tuần",
    opt_p_month: "Tháng",
    opt_p_year: "Năm",
    opt_p_custom: "Tùy chọn",
    lbl_from: "Từ ngày",
    lbl_to: "Đến ngày",
    btn_export: "Xuất CSV",
    btn_new_attachment: "+ Thêm chứng từ",
    th_counterparty: "Đối tác",
    th_review: "Duyệt",
    th_actions: "Thao tác",
  },
  en: {
    nav_overview: "Overview",
    nav_projects: "Projects",
    nav_reports: "Reports",
    nav_approvals: "Approvals",
    nav_integrations: "Integrations",
    nav_transfers: "Transfers",
    nav_settings: "Settings",
    card_title: "System Card",
    card_active_conn: "Active Connection",
    card_host: "Storage Host",
    card_host_val: "Local Database",
    card_webhook: "Webhook Status",
    card_webhook_val: "Connected",
    ctrl_title: "Dashboard Controls",
    ctrl_period: "Select Period",
    ctrl_project: "Filter Project",
    btn_new_project: "+ New Project",
    btn_new_expense: "+ Request Expense",
    opt_today: "Today",
    opt_week: "This week",
    opt_month: "This month",
    opt_all_projects: "All Projects",
    kpi_budget: "Total Budget",
    kpi_actual: "Total Actual",
    kpi_committed: "Committed",
    kpi_available: "Remaining Budget",
    kpi_pending: "Pending Approvals",
    kpi_transfers: "Unmatched Transfers",
    lbl_100_percent: "100% of plan",
    lbl_percent_of_budget: "of budget",
    opt_export_day: "By day",
    opt_export_month: "By month",
    opt_export_year: "By year",
    opt_export_custom: "Custom range",
    btn_export_transfers: "Export Report",
    lbl_report_type: "Report type",
    opt_report_projects: "Project summary (budget, in/out)",
    opt_report_transfers: "Transaction detail (in/out)",
    opt_p_day: "Day",
    opt_p_week: "Week",
    opt_p_month: "Month",
    opt_p_year: "Year",
    opt_p_custom: "Custom",
    lbl_from: "From",
    lbl_to: "To",
    btn_export: "Export CSV",
    btn_new_attachment: "+ Add document",
    th_counterparty: "Counterparty",
    th_review: "Review",
    th_actions: "Actions",
  }
};

function updateLanguageTexts() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (translations[state.lang] && translations[state.lang][key]) {
      const badge = el.querySelector(".badge");
      if (badge) {
        const textNode = el.childNodes[0];
        if (textNode && textNode.nodeType === Node.TEXT_NODE) {
          textNode.textContent = translations[state.lang][key];
        } else {
          el.firstChild.textContent = translations[state.lang][key] + " ";
        }
      } else {
        el.textContent = translations[state.lang][key];
      }
    }
  });
}

// Initialize Theme
document.documentElement.setAttribute("data-theme", state.theme);
const themeToggle = document.querySelector("#themeToggle");
if (themeToggle) {
  themeToggle.textContent = state.theme === "dark" ? "🌙" : "☀️";
  themeToggle.addEventListener("click", () => {
    state.theme = state.theme === "light" ? "dark" : "light";
    localStorage.setItem("theme", state.theme);
    document.documentElement.setAttribute("data-theme", state.theme);
    themeToggle.textContent = state.theme === "dark" ? "🌙" : "☀️";
  });
}

// Initialize Language Switcher
const langSelect = document.querySelector("#langSelect");
if (langSelect) {
  langSelect.value = state.lang;
  langSelect.addEventListener("change", (e) => {
    state.lang = e.target.value;
    localStorage.setItem("lang", state.lang);
    updateLocaleFormatters(state.lang);
    updateLanguageTexts();
    setActiveTab(activeTabFromHash()); // Refresh active screen headers
    refreshAll().catch(() => { });
  });
}

// Trigger initial translations
updateLanguageTexts();

setActiveTab(activeTabFromHash());
checkAuth().then(() => {
  return refreshAll();
}).catch((error) => {
  if (els.periodLabel) {
    els.periodLabel.textContent = `Dashboard error: ${error.message}`;
  }
});
