/* Aura Gym AI – tiện ích giao diện dùng chung */
const RISK = ["Cực kỳ nguy hiểm", "Rủi ro cao", "Rủi ro trung bình", "An toàn"];
const DARK = document.documentElement.getAttribute("data-bs-theme") === "dark";
const RISK_COLORS = DARK ? { "Cực kỳ nguy hiểm": "#d9776a", "Rủi ro cao": "#dda06e", "Rủi ro trung bình": "#dcc07a", "An toàn": "#b4a9e0" }
  : { "Cực kỳ nguy hiểm": "#8e2f25", "Rủi ro cao": "#b8662e", "Rủi ro trung bình": "#c39a3e", "An toàn": "#8e82be" };
const RISK_CLASS = { "Cực kỳ nguy hiểm": "s-crit", "Rủi ro cao": "s-high", "Rủi ro trung bình": "s-med", "An toàn": "s-safe" };
const BRAND = DARK ? "#d6bfae" : "#4a3428";
const ACCENT = DARK ? "#b4a9e0" : "#8e82be";
const SILVER = DARK ? "#6e6973" : "#b9b8c0";
const CLV_COLORS = DARK ? { VIP: "#d6bfae", Medium: "#b4a9e0", Low: "#6e6973" } : { VIP: "#4a3428", Medium: "#8e82be", Low: "#b9b8c0" };
const GROUP_COLORS = { "Nhóm 1 – Ưu tiên số 1": RISK_COLORS["Cực kỳ nguy hiểm"], "Nhóm 2 – Ưu tiên số 2": RISK_COLORS["Rủi ro cao"],
  "Nhóm 3 – Ưu tiên số 3": RISK_COLORS["Rủi ro trung bình"], "Theo dõi sát": SILVER, "Nhóm 4 – Theo dõi": RISK_COLORS["An toàn"] };
const KIND_COLORS = { "Tự do": BRAND, "Lớp nhóm": ACCENT, "PT": SILVER };

// ---------- định dạng số kiểu Việt Nam ----------
const vn = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? "–" :
  Number(x).toLocaleString("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d });
const tr = x => (x === null || x === undefined || Number.isNaN(x)) ? "–" : vn(x / 1e6, 1) + " tr";
const vnd = x => (x === null || x === undefined) ? "–" : vn(x) + " đ";
const pct = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : vn(x * 100, d) + "%";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ddmm = iso => { if (!iso) return "–"; const d = new Date(iso); return isNaN(d) ? "–" : d.toLocaleDateString("vi-VN"); };

function badge(text, color) {
  return `<span class="badge-soft" style="color:${color}"><span class="dot" style="background:${color}"></span><span style="color:var(--ink-2)">${esc(text)}</span></span>`;
}
const riskOf = v => v >= 75 ? "Cực kỳ nguy hiểm" : v >= 50 ? "Rủi ro cao" : v >= 25 ? "Rủi ro trung bình" : "An toàn";
function scoreChip(v, level, lg) { return `<span class="score ${RISK_CLASS[level || riskOf(v)]}${lg ? " lg" : ""}" title="Churn Score ${v} – ${esc(level || riskOf(v))}">${v}</span>`; }
function scoreBar(v, color) {
  const level = Object.keys(RISK_COLORS).find(k => RISK_COLORS[k] === color) || riskOf(v);
  return scoreChip(v, level);
}
const AV = ["#5a4032", "#8a8f99", "#8a6a3a", "#6c5a7d", "#6b7f5a", "#7a5146"];
const avColor = n => "var(--brand-soft)";
function initials(name) {
  const p = String(name || "?").trim().split(/\s+/);
  return (p.length > 1 ? p[p.length - 2][0] + p[p.length - 1][0] : p[0][0]).toUpperCase();
}

// ---------- thông báo ----------
function toast(msg, kind = "success") {
  const icon = { success: "bi-check-circle-fill text-success", danger: "bi-x-circle-fill text-danger", warning: "bi-exclamation-triangle-fill text-warning", info: "bi-info-circle-fill text-primary" }[kind];
  const el = document.createElement("div");
  el.className = "toast align-items-center border";
  el.innerHTML = `<div class="d-flex"><div class="toast-body d-flex gap-2"><i class="bi ${icon}"></i><div>${msg}</div></div>
    <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  document.getElementById("toasts").appendChild(el);
  const t = new bootstrap.Toast(el, { delay: 4500 }); t.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}
async function api(url, body, method = "POST") {
  const opt = { method, headers: {} };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(url, opt);
  let j = {};
  try { j = await r.json(); } catch (e) { throw new Error("Máy chủ trả về lỗi " + r.status); }
  if (!r.ok) throw new Error(j.error || "Lỗi " + r.status);
  return j;
}
function copyText(text, btn) {
  const done = () => { toast("Đã sao chép tin nhắn"); if (btn) { const o = btn.innerHTML; btn.innerHTML = '<i class="bi bi-check2"></i> Đã chép'; setTimeout(() => btn.innerHTML = o, 1500); } };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done);
  else { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); done(); }
}

// ---------- Chart.js mặc định theo Metis ----------
function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function chartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.font.family = "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cssVar("--chart-text");
  Chart.defaults.borderColor = cssVar("--chart-grid");
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.padding = 14;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.backgroundColor = DARK ? "#3a312b" : "#2b211b";
  Chart.defaults.elements.bar.borderRadius = 3;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation.duration = 500;
}
const CHARTS = {};
function makeChart(id, cfg) {
  const el = document.getElementById(id);
  if (!el) return null;
  if (CHARTS[id]) CHARTS[id].destroy();
  CHARTS[id] = new Chart(el, cfg);
  return CHARTS[id];
}
const axisNoGrid = { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12 } };
const axisGrid = { grid: { color: () => cssVar("--chart-grid") }, border: { display: false }, beginAtZero: true };

// ---------- khung giao diện ----------
document.addEventListener("DOMContentLoaded", () => {
  chartDefaults();
  // menu trái
  document.getElementById("sidebarToggle")?.addEventListener("click", () => {
    if (window.innerWidth < 992) document.body.classList.toggle("sidebar-open");
    else { document.body.classList.toggle("sidebar-collapsed"); localStorage.setItem("aura-collapsed", document.body.classList.contains("sidebar-collapsed") ? "1" : ""); }
    setTimeout(() => Object.values(CHARTS).forEach(c => c.resize()), 280);
  });
  document.querySelector(".sidebar-backdrop")?.addEventListener("click", () => document.body.classList.remove("sidebar-open"));
  // sáng/tối
  document.getElementById("themeToggle")?.addEventListener("click", () => {
    const t = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-bs-theme", t); localStorage.setItem("aura-theme", t);
    document.querySelector("#themeToggle i").className = t === "dark" ? "bi bi-moon-stars" : "bi bi-sun";
    location.reload();
  });
  document.getElementById("fullscreenToggle")?.addEventListener("click", () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.(); else document.exitFullscreen?.();
  });
  // hoàn tác
  document.getElementById("undoBtn")?.addEventListener("click", () => bootstrap.Modal.getOrCreateInstance("#undoModal").show());
  document.getElementById("undoGo")?.addEventListener("click", async e => {
    const b = e.currentTarget; b.disabled = true; b.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Đang hoàn tác...';
    try { const j = await undo(); bootstrap.Modal.getInstance("#undoModal").hide(); afterUndo(j); }
    catch (err) { toast(err.message, "danger"); b.disabled = false; b.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Hoàn tác'; }
  });
  // chi nhánh
  const setBranch = v => { document.cookie = "cn=" + encodeURIComponent(v) + ";path=/;max-age=31536000;samesite=lax";
    const u = new URL(location.href); u.searchParams.delete("cn"); location.href = u.toString(); };
  document.getElementById("branchSelect")?.addEventListener("change", e => setBranch(e.target.value));
  document.querySelectorAll("[data-cn]").forEach(b => b.addEventListener("click", () => setBranch(b.dataset.cn)));
  // nhân viên
  const staffEl = document.getElementById("staffName");
  const staff = localStorage.getItem("aura-staff") || "Lễ tân";
  if (staffEl) staffEl.textContent = staff;
  document.querySelectorAll(".staff-name").forEach(e => e.textContent = staff);
  const g = document.getElementById("greet"); if (g) { const h = new Date().getHours(); g.textContent = h < 11 ? "Chào buổi sáng" : h < 14 ? "Chào buổi trưa" : h < 18 ? "Chào buổi chiều" : "Chào buổi tối"; }
  document.querySelectorAll(".avatar-staff").forEach(a => { a.textContent = initials(staff); a.style.background = avColor(staff); });
  document.getElementById("staffEdit")?.addEventListener("click", () => {
    const v = prompt("Tên nhân viên đang trực:", localStorage.getItem("aura-staff") || "Lễ tân");
    if (v && v.trim()) { localStorage.setItem("aura-staff", v.trim()); staffEl.textContent = v.trim();
      document.querySelectorAll(".avatar-staff").forEach(a => a.textContent = initials(v.trim())); toast("Đã đổi tên nhân viên"); }
  });
  // tìm kiếm nhanh hội viên
  const box = document.getElementById("globalSearch"), res = document.getElementById("searchResults");
  let timer, idx = -1;
  if (box) {
    document.addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); box.focus(); } });
    box.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = box.value.trim();
        if (q.length < 2) { res.style.display = "none"; return; }
        const items = await api("/api/search?q=" + encodeURIComponent(q), undefined, "GET");
        idx = -1;
        res.innerHTML = items.length ? items.map(i => `<a href="/hoi-vien/${encodeURIComponent(i.ma_hv)}"><span><b>${esc(i.ho_ten)}</b> <span class="text-secondary">· ${esc(i.ma_hv)} · ${esc(i.so_dien_thoai)}</span></span>${badge(i.muc_rui_ro, RISK_COLORS[i.muc_rui_ro])}</a>`).join("")
          : `<div class="p-3 text-secondary">Không tìm thấy hội viên</div>`;
        res.style.display = "block";
      }, 180);
    });
    box.addEventListener("keydown", e => {
      const links = [...res.querySelectorAll("a")];
      if (!links.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); idx = (idx + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length; links.forEach((l, i) => l.classList.toggle("active", i === idx)); }
      if (e.key === "Enter") { e.preventDefault(); location.href = (links[idx] || links[0]).href; }
    });
    document.addEventListener("click", e => { if (!e.target.closest(".header-search")) res.style.display = "none"; });
  }
});

// ---------- bảng có sắp xếp + phân trang ----------
function makeTable({ tbody, rows, render, pageSize = 25, pager, sortKey = null, sortDir = -1, head }) {
  const state = { rows, page: 0, sortKey, sortDir };
  function draw() {
    let r = state.rows.slice();
    if (state.sortKey) r.sort((a, b) => {
      const x = a[state.sortKey], y = b[state.sortKey];
      if (x === y) return 0; if (x === null || x === undefined) return 1; if (y === null || y === undefined) return -1;
      return (x > y ? 1 : -1) * state.sortDir;
    });
    const pages = Math.max(1, Math.ceil(r.length / pageSize));
    state.page = Math.min(state.page, pages - 1);
    const slice = r.slice(state.page * pageSize, (state.page + 1) * pageSize);
    setTimeout(rowsFocusable, 0);
    tbody.innerHTML = slice.length ? slice.map(render).join("") : `<tr><td colspan="20"><div class="empty-state"><i class="bi bi-inbox"></i><div class="mt-2">Không có dữ liệu phù hợp</div></div></td></tr>`;
    if (pager) {
      pager.innerHTML = `<span class="text-secondary">${vn(r.length)} khách, trang ${state.page + 1}/${pages}</span>
        <div class="btn-group btn-group-sm"><button class="btn btn-outline-secondary" aria-label="Trang trước" ${state.page ? "" : "disabled"} data-p="-1"><i class="bi bi-chevron-left"></i></button>
        <button class="btn btn-outline-secondary" aria-label="Trang sau" ${state.page < pages - 1 ? "" : "disabled"} data-p="1"><i class="bi bi-chevron-right"></i></button></div>`;
      pager.querySelectorAll("button").forEach(b => b.onclick = () => { state.page += +b.dataset.p; draw(); });
    }
  }
  if (head) head.querySelectorAll("th.sortable").forEach(th => {
    th.insertAdjacentHTML("beforeend", ' <i class="bi bi-arrow-down-up"></i>');
    th.onclick = () => {
      const k = th.dataset.key;
      state.sortDir = state.sortKey === k ? -state.sortDir : -1; state.sortKey = k;
      head.querySelectorAll("th").forEach(t => t.classList.remove("sorted")); th.classList.add("sorted");
      th.querySelector(".bi").className = "bi " + (state.sortDir < 0 ? "bi-sort-down" : "bi-sort-up");
      draw();
    };
  });
  draw();
  return { set(rows) { state.rows = rows; state.page = 0; draw(); }, redraw: draw, state };
}

// ---------- hoàn tác ----------
async function undo(id) { return api("/api/undo", id ? { id } : {}); }
function afterUndo(j) {
  sessionStorage.setItem("aura-flash", "Đã hoàn tác: " + j.undone);
  location.reload();
}
document.addEventListener("DOMContentLoaded", () => {
  const f = sessionStorage.getItem("aura-flash");
  if (f) { sessionStorage.removeItem("aura-flash"); setTimeout(() => toast(esc(f)), 250); }
});

// ---------- dòng bảng bấm được: dùng được bằng bàn phím (Tab + Enter) ----------
function rowsFocusable() {
  document.querySelectorAll(".table-click tbody tr").forEach(tr => { if (!tr.querySelector(".empty-state")) tr.tabIndex = 0; });
}
document.addEventListener("DOMContentLoaded", rowsFocusable);
window.addEventListener("scroll", () => document.querySelector(".admin-header")?.classList.toggle("scrolled", scrollY > 8), { passive: true });
document.addEventListener("keydown", e => {
  const tr = e.target.closest?.(".table-click tbody tr");
  if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); tr.click(); }
});
