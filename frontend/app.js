let csrfToken = "";
let currentUser = null;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(action, options = {}) {
  const method = options.method || "GET";
  const headers = { "Content-Type": "application/json" };
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(`api.php?action=${encodeURIComponent(action)}${options.query || ""}`, {
    method, headers, body: method === "GET" ? undefined : JSON.stringify(options.body || {})
  });
  const data = await response.json().catch(() => ({ ok: false, error: "Unexpected server response." }));
  if (!response.ok || !data.ok) throw new Error(data.error || "Request failed.");
  if (data.csrf) csrfToken = data.csrf;
  if (Object.prototype.hasOwnProperty.call(data, "user")) currentUser = data.user;
  return data;
}
function toast(message) {
  const el = $("#toast"); el.textContent = message; el.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove("show"), 3200);
}
function openModal(id) {
  if (!currentUser && ["postModal", "contactModal", "reportModal", "adminModal"].includes(id)) {
    toast("Please log in to continue."); openModal("loginModal"); return;
  }
  $("#" + id).classList.add("open");
}
function closeModals() { $$(".modal-backdrop").forEach(el => el.classList.remove("open")); }
function updateNavigation() {
  const nav = $("#navActions");
  if (!currentUser) {
    nav.innerHTML = '<button class="btn btn-quiet" data-open="loginModal">Log in</button><button class="btn btn-dark" data-open="registerModal">Create account</button>';
  } else {
    nav.innerHTML = `<span class="welcome-user">Hi, ${escapeHtml(currentUser.name.split(" ")[0])}</span>
      ${currentUser.role === "admin" ? '<button class="btn btn-outline" id="adminButton">Admin</button>' : ""}
      <button class="btn btn-dark" id="logoutButton">Log out</button>`;
    $("#logoutButton").addEventListener("click", logout);
    $("#adminButton")?.addEventListener("click", loadAdmin);
  }
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
}
function dateLabel(date) {
  if (!date) return "Date not specified";
  const d = new Date(date + "T12:00:00");
  return Number.isNaN(d.getTime()) ? date : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
async function loadListings() {
  const params = new URLSearchParams();
  const q = $("#searchInput").value.trim(), type = $("#typeFilter").value, category = $("#categoryFilter").value;
  if (q) params.set("q", q); if (type) params.set("type", type); if (category) params.set("category", category);
  const grid = $("#listingGrid"); grid.innerHTML = '<div class="empty-state">Loading listings…</div>';
  try {
    const data = await api("listings", { query: "&" + params.toString() });
    $("#resultCount").textContent = `${data.listings.length} ${data.listings.length === 1 ? "listing" : "listings"} found`;
    if (!data.listings.length) { grid.innerHTML = '<div class="empty-state">No listings match your search yet. Try another filter or post an item.</div>'; return; }
    grid.innerHTML = data.listings.map(item => `
      <article class="listing-card">
        <div class="card-top"><span class="type-pill ${escapeHtml(item.type)}">${item.type === "lost" ? "Lost item" : "Found item"}</span><span class="category-label">${escapeHtml(item.category)}</span></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="listing-description">${escapeHtml(item.description)}</p>
        <div class="card-meta"><span>⌖</span>${escapeHtml(item.location)}</div>
        <div class="card-meta"><span>◷</span>${escapeHtml(dateLabel(item.item_date))}</div>
        <div class="card-bottom"><span class="poster">Posted by ${escapeHtml(item.poster_name)}</span>
          <div class="card-actions"><button class="text-action" data-contact="${item.id}" data-title="${escapeHtml(item.title)}">Contact</button>
          <button class="text-action report" data-report="${item.id}">Report</button></div></div>
      </article>`).join("");
  } catch (e) { grid.innerHTML = `<div class="empty-state">${escapeHtml(e.message)} Check that the PHP server and database are running.</div>`; }
}
async function submitForm(form, action, success) {
  const button = $("button[type=submit],button:not([type])", form);
  if (button) button.disabled = true;
  try {
    const body = Object.fromEntries(new FormData(form).entries());
    const result = await api(action, { method: "POST", body });
    form.reset(); closeModals(); toast(result.message || success); return result;
  } catch (e) { toast(e.message); }
  finally { if (button) button.disabled = false; }
}
async function logout() {
  try { await api("logout", { method: "POST" }); currentUser = null; csrfToken = ""; await initialize(); toast("You have logged out."); }
  catch (e) { toast(e.message); }
}
async function loadAdmin() {
  openModal("adminModal");
  const target = $("#adminReports"); target.innerHTML = "Loading reports…";
  try {
    const data = await api("admin-reports");
    if (!data.reports.length) { target.innerHTML = '<div class="admin-empty">There are no open reports. Nice work!</div>'; return; }
    target.innerHTML = data.reports.map(r => `<article class="admin-report">
      <h4>${escapeHtml(r.title)} <span class="type-pill ${escapeHtml(r.type)}">${escapeHtml(r.type)}</span></h4>
      <p><b>Reason:</b> ${escapeHtml(r.reason)}<br><b>Reported by:</b> ${escapeHtml(r.reporter_name)} · ${escapeHtml(r.reported_at)}</p>
      <button class="btn btn-outline" data-keep="${r.report_id}" data-listing="${r.listing_id}">Keep listing</button>
      <button class="btn btn-dark" data-remove="${r.report_id}" data-listing="${r.listing_id}">Remove listing</button>
    </article>`).join("");
  } catch (e) { target.innerHTML = `<div class="admin-empty">${escapeHtml(e.message)}</div>`; }
}
async function moderate(reportId, listingId, decision) {
  try { const d = await api("admin-resolve", { method:"POST", body:{ report_id:reportId, listing_id:listingId, decision } }); toast(d.message); loadAdmin(); loadListings(); }
  catch(e) { toast(e.message); }
}

document.addEventListener("click", e => {
  const open = e.target.closest("[data-open]"); if (open) openModal(open.dataset.open);
  if (e.target.closest("[data-close]")) closeModals();
  const sw = e.target.closest("[data-switch]"); if (sw) { closeModals(); openModal(sw.dataset.switch); }
  if (e.target.classList.contains("modal-backdrop")) closeModals();
  const contact = e.target.closest("[data-contact]");
  if (contact) {
    if (!currentUser) { toast("Log in to contact the poster."); openModal("loginModal"); return; }
    $("#contactForm [name=listing_id]").value = contact.dataset.contact;
    $("#contactItemTitle").textContent = `Regarding: ${contact.dataset.title}`;
    openModal("contactModal");
  }
  const report = e.target.closest("[data-report]");
  if (report) { if (!currentUser) { toast("Log in to report a listing."); openModal("loginModal"); return; } $("#reportForm [name=listing_id]").value = report.dataset.report; openModal("reportModal"); }
  const keep = e.target.closest("[data-keep]"); if (keep) moderate(keep.dataset.keep, keep.dataset.listing, "keep");
  const remove = e.target.closest("[data-remove]"); if (remove) moderate(remove.dataset.remove, remove.dataset.listing, "remove");
});
$("#loginForm").addEventListener("submit", async e => { e.preventDefault(); const r = await submitForm(e.currentTarget, "login", "Welcome back!"); if (r) { currentUser = r.user; csrfToken = r.csrf; updateNavigation(); } });
$("#registerForm").addEventListener("submit", async e => { e.preventDefault(); const r = await submitForm(e.currentTarget, "register", "Your account is ready."); if (r) { currentUser = r.user; csrfToken = r.csrf; updateNavigation(); } });
$("#postForm").addEventListener("submit", async e => { e.preventDefault(); const r = await submitForm(e.currentTarget, "create-listing", "Listing posted."); if (r) loadListings(); });
$("#contactForm").addEventListener("submit", async e => { e.preventDefault(); await submitForm(e.currentTarget, "contact", "Message sent."); });
$("#reportForm").addEventListener("submit", async e => { e.preventDefault(); await submitForm(e.currentTarget, "report", "Report submitted."); });
$("#searchInput").addEventListener("input", debounce(loadListings, 250));
$("#typeFilter").addEventListener("change", loadListings); $("#categoryFilter").addEventListener("change", loadListings);
$("#clearFilters").addEventListener("click", () => { $("#searchInput").value = ""; $("#typeFilter").value = ""; $("#categoryFilter").value = ""; loadListings(); });
function debounce(fn, delay) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); }; }
async function initialize() {
  $("#year").textContent = new Date().getFullYear();
  try { const data = await api("csrf"); csrfToken = data.csrf; currentUser = data.user; }
  catch (e) { toast("Could not connect to the server. Start PHP and MySQL, then refresh."); }
  updateNavigation(); loadListings();
}
initialize();
