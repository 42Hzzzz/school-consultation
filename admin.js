const alertBox = document.getElementById("alertBox");
const liveClock = document.getElementById("liveClock");
const adminStaffList = document.getElementById("adminStaffList");
const consultationTable = document.getElementById("consultationTable");
const statusFilter = document.getElementById("statusFilter");

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
  return `
    <span class="badge ${hoursClass}">${escapeHtml(staff.work_hours_label)}</span>
    <span class="badge ${staff.availability}">${escapeHtml(staff.availability_label)}</span>
    <span class="badge ${staff.consultable ? "consultable" : "not-consultable"}">
      ${staff.consultable ? "可接受咨询" : escapeHtml(staff.consult_reason)}
    </span>
  `;
}

async function loadMeta() {
  const res = await fetch("/api/meta");
  const data = await res.json();
  liveClock.innerHTML = `当前时间：<strong>${escapeHtml(data.server_time)}</strong>（${escapeHtml(data.weekday)}）`;
}

async function loadStaff() {
  const res = await fetch("/api/staff");
  const staff = await res.json();

  adminStaffList.innerHTML = staff
    .map(
      (person) => `
      <div class="admin-staff-item" data-id="${person.id}">
        <div>
          <strong>${escapeHtml(person.name)}</strong>
          <span style="color: var(--text-muted); font-size: 0.875rem;">
            ${escapeHtml(person.title)} · ${escapeHtml(person.department_name)}
          </span>
          <div class="status-row">${renderStatusBadges(person)}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 6px;">
            工作时间：${escapeHtml(person.work_schedule)}
          </div>
        </div>
        <div class="admin-controls">
          <select class="availability-select" data-id="${person.id}">
            ${window.AVAILABILITY_OPTIONS.map(
              ([value, label]) =>
                `<option value="${value}" ${person.availability === value ? "selected" : ""}>${escapeHtml(label)}</option>`
            ).join("")}
          </select>
          <input type="text" class="note-input" data-id="${person.id}"
            placeholder="状态备注（选填）" value="${escapeHtml(person.availability_note)}"
            style="min-width: 180px; padding: 8px 10px; font-size: 0.85rem;">
          <button type="button" class="btn btn-primary btn-sm save-btn" data-id="${person.id}">保存</button>
        </div>
      </div>
    `
    )
    .join("");

  adminStaffList.querySelectorAll(".save-btn").forEach((btn) => {
    btn.addEventListener("click", () => saveAvailability(Number(btn.dataset.id)));
  });
}

async function saveAvailability(staffId) {
  const select = adminStaffList.querySelector(`.availability-select[data-id="${staffId}"]`);
  const noteInput = adminStaffList.querySelector(`.note-input[data-id="${staffId}"]`);

  try {
    const res = await fetch(`/api/staff/${staffId}/availability`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        availability: select.value,
        availability_note: noteInput.value.trim(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "保存失败");
    showAlert(data.message, "success");
    await loadStaff();
  } catch (err) {
    showAlert(err.message, "error");
  }
}

async function loadConsultations() {
  const params = new URLSearchParams();
  if (statusFilter.value) params.set("status", statusFilter.value);

  const res = await fetch(`/api/consultations?${params}`);
  const rows = await res.json();

  if (!rows.length) {
    consultationTable.innerHTML =
      '<tr><td colspan="6" class="empty-state">暂无咨询记录</td></tr>';
    return;
  }

  consultationTable.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${escapeHtml(row.created_at.replace("T", " "))}</td>
        <td>${escapeHtml(row.student_name)}<br><small>${escapeHtml(row.student_id)}</small></td>
        <td>${escapeHtml(row.staff_name)}<br><small>${escapeHtml(row.department_name)}</small></td>
        <td>
          <strong>${escapeHtml(row.topic)}</strong>
          ${row.message ? `<br><small>${escapeHtml(row.message)}</small>` : ""}
        </td>
        <td>${escapeHtml(row.status_label)}</td>
        <td>
          <select class="status-select" data-id="${row.id}">
            ${Object.entries(window.STATUS_LABELS)
              .map(
                ([value, label]) =>
                  `<option value="${value}" ${row.status === value ? "selected" : ""}>${escapeHtml(label)}</option>`
              )
              .join("")}
          </select>
        </td>
      </tr>
    `
    )
    .join("");

  consultationTable.querySelectorAll(".status-select").forEach((select) => {
    select.addEventListener("change", () =>
      updateConsultationStatus(Number(select.dataset.id), select.value)
    );
  });
}

async function updateConsultationStatus(id, status) {
  try {
    const res = await fetch(`/api/consultations/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "更新失败");
    showAlert(data.message, "success");
  } catch (err) {
    showAlert(err.message, "error");
    await loadConsultations();
  }
}

statusFilter.addEventListener("change", loadConsultations);
document.getElementById("refreshConsultations").addEventListener("click", loadConsultations);

async function refreshAll() {
  await loadMeta();
  await loadStaff();
  await loadConsultations();
}

refreshAll();
setInterval(async () => {
  await loadMeta();
  await loadStaff();
}, 60000);
