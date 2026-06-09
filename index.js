let departments = [];
let staffList = [];
let selectedDeptId = "";
let selectedStaff = null;

const deptGrid = document.getElementById("deptGrid");
const deptFilters = document.getElementById("deptFilters");
const staffListEl = document.getElementById("staffList");
const searchInput = document.getElementById("searchInput");
const consultableOnly = document.getElementById("consultableOnly");
const consultPanel = document.getElementById("consultPanel");
const selectedBanner = document.getElementById("selectedBanner");
const consultForm = document.getElementById("consultForm");
const alertBox = document.getElementById("alertBox");
const liveClock = document.getElementById("liveClock");

function showAlert(message, type = "success") {
  alertBox.textContent = message;
  alertBox.className = `alert show ${type}`;
  setTimeout(() => {
    alertBox.className = "alert";
  }, 4000);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function renderStatusBadges(staff) {
  const hoursClass = staff.in_work_hours ? "in-hours" : "out-hours";
  const availClass = staff.availability;
  const consultClass = staff.consultable ? "consultable" : "not-consultable";
  return `
    <div class="status-row">
      <span class="badge ${hoursClass}">${escapeHtml(staff.work_hours_label)}</span>
      <span class="badge ${availClass}">${escapeHtml(staff.availability_label)}</span>
      <span class="badge ${consultClass}">${staff.consultable ? "可接受咨询" : escapeHtml(staff.consult_reason)}</span>
    </div>
  `;
}

function renderDepartments() {
  deptGrid.innerHTML = departments
    .map(
      (dept) => `
      <article class="dept-card ${selectedDeptId === String(dept.id) ? "selected" : ""}" data-id="${dept.id}">
        <h3>${escapeHtml(dept.name)}</h3>
        <p>${escapeHtml(dept.description)}</p>
        <div class="dept-meta">
          <span>📍 ${escapeHtml(dept.location)} · ☎ ${escapeHtml(dept.phone)}</span>
          <span>🕐 ${escapeHtml(dept.work_days_label)} ${escapeHtml(dept.work_start)}-${escapeHtml(dept.work_end)}</span>
          <span class="badge ${dept.in_work_hours ? "in-hours" : "out-hours"}">${escapeHtml(dept.work_hours_label)}</span>
          <span>可咨询 ${dept.available_count}/${dept.staff_count} 人</span>
        </div>
      </article>
    `
    )
    .join("");

  deptGrid.querySelectorAll(".dept-card").forEach((card) => {
    card.addEventListener("click", () => {
      const id = card.dataset.id;
      selectedDeptId = selectedDeptId === id ? "" : id;
      updateDeptFilterChips();
      renderDepartments();
      loadStaff();
    });
  });
}

function updateDeptFilterChips() {
  deptFilters.querySelectorAll(".chip").forEach((chip) => {
    const dept = chip.dataset.dept;
    chip.classList.toggle("active", dept === selectedDeptId);
  });
}

function renderStaff() {
  if (!staffList.length) {
    staffListEl.innerHTML = '<div class="empty-state">暂无符合条件的咨询对象</div>';
    return;
  }

  staffListEl.innerHTML = staffList
    .map(
      (staff) => `
      <article class="staff-card ${staff.consultable ? "consultable" : "unavailable"}">
        <div>
          <div class="staff-head">
            <h3>${escapeHtml(staff.name)}</h3>
            <span class="staff-title">${escapeHtml(staff.title)} · ${escapeHtml(staff.department_name)}</span>
          </div>
          <div class="staff-info">
            <span>专长：${escapeHtml(staff.specialties || "综合咨询")}</span>
            <span>办公：${escapeHtml(staff.office || staff.department_location)}</span>
            <span>电话：${escapeHtml(staff.phone)} · 邮箱：${escapeHtml(staff.email)}</span>
            <span>工作时间：${escapeHtml(staff.work_schedule)}</span>
            ${staff.availability_note ? `<span>备注：${escapeHtml(staff.availability_note)}</span>` : ""}
          </div>
          ${renderStatusBadges(staff)}
        </div>
        <div class="staff-actions">
          <button type="button" class="btn btn-primary btn-sm consult-btn"
            data-id="${staff.id}" ${staff.consultable ? "" : "disabled"}>
            ${staff.consultable ? "发起咨询" : "暂不可咨询"}
          </button>
        </div>
      </article>
    `
    )
    .join("");

  staffListEl.querySelectorAll(".consult-btn").forEach((btn) => {
    btn.addEventListener("click", () => openConsultPanel(Number(btn.dataset.id)));
  });
}

function openConsultPanel(staffId) {
  selectedStaff = staffList.find((s) => s.id === staffId);
  if (!selectedStaff || !selectedStaff.consultable) return;

  document.getElementById("staffId").value = staffId;
  selectedBanner.innerHTML = `
    您将向 <strong>${escapeHtml(selectedStaff.name)}</strong>
    （${escapeHtml(selectedStaff.title)}，${escapeHtml(selectedStaff.department_name)}）提交咨询。
    当前状态：<span class="badge consultable">可接受咨询</span>
  `;
  consultPanel.classList.add("open");
  consultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeConsultPanel() {
  consultPanel.classList.remove("open");
  selectedStaff = null;
  consultForm.reset();
}

async function loadMeta() {
  const res = await fetch("/api/meta");
  const data = await res.json();
  liveClock.innerHTML = `当前时间：<strong>${escapeHtml(data.server_time)}</strong>（${escapeHtml(data.weekday)}）`;
}

async function loadDepartments() {
  const res = await fetch("/api/departments");
  departments = await res.json();

  departments.forEach((dept) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.dataset.dept = String(dept.id);
    chip.textContent = dept.name;
    chip.addEventListener("click", () => {
      selectedDeptId = chip.dataset.dept;
      updateDeptFilterChips();
      renderDepartments();
      loadStaff();
    });
    deptFilters.appendChild(chip);
  });

  renderDepartments();
}

async function loadStaff() {
  const params = new URLSearchParams();
  if (selectedDeptId) params.set("department_id", selectedDeptId);
  if (consultableOnly.checked) params.set("consultable", "1");
  if (searchInput.value.trim()) params.set("q", searchInput.value.trim());

  const res = await fetch(`/api/staff?${params}`);
  staffList = await res.json();
  renderStaff();
}

consultForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    staff_id: Number(document.getElementById("staffId").value),
    student_name: document.getElementById("studentName").value.trim(),
    student_id: document.getElementById("studentId").value.trim(),
    contact: document.getElementById("contact").value.trim(),
    topic: document.getElementById("topic").value.trim(),
    message: document.getElementById("message").value.trim(),
    preferred_time: document.getElementById("preferredTime").value,
  };

  const btn = document.getElementById("submitBtn");
  btn.disabled = true;

  try {
    const res = await fetch("/api/consultations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "提交失败");
    showAlert(data.message, "success");
    closeConsultPanel();
    await loadStaff();
    await loadDepartments();
  } catch (err) {
    showAlert(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("cancelConsult").addEventListener("click", closeConsultPanel);
searchInput.addEventListener(
  "input",
  debounce(() => loadStaff(), 300)
);
consultableOnly.addEventListener("change", loadStaff);

deptFilters.querySelector('[data-dept=""]').addEventListener("click", () => {
  selectedDeptId = "";
  updateDeptFilterChips();
  renderDepartments();
  loadStaff();
});

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

async function refreshAll() {
  await loadMeta();
  await loadDepartments();
  await loadStaff();
}

refreshAll();
setInterval(refreshAll, 60000);
