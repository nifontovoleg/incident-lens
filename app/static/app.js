const selectedEvents = new Set();
let currentIncident = null;

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "incidents") loadIncidents();
    if (btn.dataset.tab === "diagnosis") loadLatestDiagnosis();
  });
});

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ? JSON.stringify(err.detail) : res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

function levelClass(level) {
  return `level-${level}`;
}

function formatTs(ts, createdAt) {
  return ts || new Date(createdAt).toLocaleString("ru-RU");
}

async function loadServices() {
  const services = await api("/events/services");
  const sel = document.getElementById("filter-service");
  sel.innerHTML = '<option value="">Все</option>';
  services.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    sel.appendChild(opt);
  });
}

async function loadEvents() {
  const service = document.getElementById("filter-service").value;
  const level = document.getElementById("filter-level").value;
  const params = new URLSearchParams();
  if (service) params.set("service", service);
  if (level) params.set("level", level);
  const events = await api(`/events?${params}`);
  const tbody = document.getElementById("events-tbody");
  tbody.innerHTML = "";
  events.forEach((e) => {
    const tr = document.createElement("tr");
    const checked = selectedEvents.has(e.event_id) ? "checked" : "";
    tr.innerHTML = `
      <td><input type="checkbox" class="event-check" data-id="${e.event_id}" ${checked}></td>
      <td>${formatTs(e.ts, e.created_at)}</td>
      <td>${e.service}</td>
      <td class="${levelClass(e.level)}">${e.level}</td>
      <td>${e.message}</td>
      <td class="event-id">${e.event_id}</td>
    `;
    tbody.appendChild(tr);
  });
  bindEventCheckboxes();
  updateSelectedCount();
}

function bindEventCheckboxes() {
  document.querySelectorAll(".event-check").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      const id = e.target.dataset.id;
      if (e.target.checked) selectedEvents.add(id);
      else selectedEvents.delete(id);
      updateSelectedCount();
    });
  });
}

function updateSelectedCount() {
  document.getElementById("selected-count").textContent = selectedEvents.size;
  document.getElementById("btn-create-incident").disabled = selectedEvents.size === 0;
}

document.getElementById("select-all-events").addEventListener("change", (e) => {
  document.querySelectorAll(".event-check").forEach((cb) => {
    cb.checked = e.target.checked;
    const id = cb.dataset.id;
    if (e.target.checked) selectedEvents.add(id);
    else selectedEvents.delete(id);
  });
  updateSelectedCount();
});

document.getElementById("btn-refresh-events").addEventListener("click", loadEvents);
document.getElementById("filter-service").addEventListener("change", loadEvents);
document.getElementById("filter-level").addEventListener("change", loadEvents);

document.getElementById("btn-create-incident").addEventListener("click", () => {
  document.getElementById("incident-event-ids").value = [...selectedEvents].join(", ");
  document.querySelector('.tab[data-tab="incidents"]').click();
});

document.getElementById("form-incident").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = document.getElementById("incident-title").value.trim();
  const idsRaw = document.getElementById("incident-event-ids").value;
  const event_ids = idsRaw.split(",").map((s) => s.trim()).filter(Boolean);
  if (!title || !event_ids.length) return alert("Укажите название и event_ids");
  try {
    const res = await api("/incidents", {
      method: "POST",
      body: JSON.stringify({ title, event_ids }),
    });
    alert(`Инцидент создан: ${res.incident_id}`);
    selectedEvents.clear();
    updateSelectedCount();
    loadIncidents();
  } catch (err) {
    alert(`Ошибка: ${err.message}`);
  }
});

async function loadIncidents() {
  const incidents = await api("/incidents");
  const list = document.getElementById("incidents-list");
  list.innerHTML = "";
  incidents.forEach((inc) => {
    const div = document.createElement("div");
    div.className = "incident-item";
    div.innerHTML = `
      <div>
        <strong>${inc.title}</strong>
        <div class="event-id">${inc.incident_id} · ${inc.event_ids.length} событий</div>
      </div>
      <span>${new Date(inc.created_at).toLocaleString("ru-RU")}</span>
    `;
    div.addEventListener("click", () => openIncident(inc));
    list.appendChild(div);
  });
}

async function openIncident(inc) {
  currentIncident = inc;
  document.getElementById("incident-detail").classList.remove("hidden");
  document.getElementById("incident-detail-title").textContent = inc.title;
  const container = document.getElementById("incident-events");
  container.innerHTML = "<p>Загрузка событий...</p>";
  const allEvents = await api("/events");
  const related = allEvents.filter((e) => inc.event_ids.includes(e.event_id));
  container.innerHTML = related.length
    ? `<ul>${related.map((e) => `<li class="${levelClass(e.level)}">[${e.level}] ${e.message}</li>`).join("")}</ul>`
    : "<p>Нет связанных событий</p>";
}

document.getElementById("btn-run-diagnosis").addEventListener("click", async () => {
  if (!currentIncident) return;
  const allEvents = await api("/events");
  const related = allEvents.filter((e) => currentIncident.event_ids.includes(e.event_id));
  const messages = related.map((e) => e.message);
  if (!messages.length) return alert("Нет сообщений для диагностики");
  try {
    const result = await api("/ai/diagnose", {
      method: "POST",
      body: JSON.stringify({
        title: currentIncident.title,
        messages,
        incident_id: currentIncident.incident_id,
      }),
    });
    showDiagnosis(result);
    document.querySelector('.tab[data-tab="diagnosis"]').click();
  } catch (err) {
    alert(`Ошибка диагностики: ${err.message}`);
  }
});

function showDiagnosis(data) {
  document.getElementById("diagnosis-empty").classList.add("hidden");
  document.getElementById("diagnosis-result").classList.remove("hidden");
  document.getElementById("diag-hypothesis").textContent = data.root_cause_hypothesis;
  const conf = document.getElementById("diag-confidence");
  conf.textContent = data.confidence;
  conf.className = `badge ${data.confidence}`;
  const reviewBadge = document.getElementById("diag-review-badge");
  const reviewBlock = document.getElementById("diag-review-block");
  if (data.needs_review) {
    reviewBadge.classList.remove("hidden");
    reviewBlock.classList.remove("hidden");
    const missing = document.getElementById("diag-missing");
    missing.innerHTML = data.next_steps
      .filter((s) => s.toLowerCase().includes("собрать") || s.toLowerCase().includes("уточн"))
      .map((s) => `<li>${s}</li>`)
      .join("") || data.next_steps.map((s) => `<li>${s}</li>`).join("");
  } else {
    reviewBadge.classList.add("hidden");
    reviewBlock.classList.add("hidden");
  }
  document.getElementById("diag-steps").innerHTML = data.next_steps
    .map((s) => `<li>${s}</li>`)
    .join("");
}

async function loadLatestDiagnosis() {
  const data = await api("/ai/diagnoses/latest");
  if (data) showDiagnosis(data);
}

loadServices().then(loadEvents);
