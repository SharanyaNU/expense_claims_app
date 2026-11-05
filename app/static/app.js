// Expense Claims Portal UI. Plain JavaScript, no build step.

const state = { employees: [], categories: [], me: null };

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Employee-Id": String(state.me.id), ...(options.headers || {}) },
  });
  const body = res.status === 204 ? null : await res.json();
  if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Request failed");
  return body;
}

function toast(message, kind = "ok") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = kind;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), 4000);
}

const money = (n) => `$${Number(n).toFixed(2)}`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function flagsHtml(flags) {
  if (!flags.length) return '<span class="ok-badge">Within policy</span>';
  return `<ul class="flags">${flags.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`;
}

// ---- tabs -----------------------------------------------------------------
document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll("main > section").forEach((s) => (s.hidden = s.id !== `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "approvals") loadInbox();
  })
);

// ---- my claims ------------------------------------------------------------
const form = document.getElementById("claim-form");

function selectedCategory() {
  return state.categories.find((c) => c.code === form.category_code.value);
}

function updatePolicyHint() {
  const cat = selectedCategory();
  if (!cat) return;
  document.getElementById("attendees-field").hidden = !cat.requires_attendees;
  const monthly = cat.monthly_limit ? `, ${money(cat.monthly_limit)} a month` : "";
  const receipt = cat.receipt_required_over > 0 ? `receipt over ${money(cat.receipt_required_over)}` : "receipt always";
  document.getElementById("policy-hint").textContent =
    `Policy: up to ${money(cat.limit_per_claim)} per claim${monthly}; ${receipt}${cat.requires_attendees ? "; list attendees" : ""}.`;
}
form.category_code.addEventListener("change", updatePolicyHint);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  try {
    const claim = await api("/claims", {
      method: "POST",
      body: JSON.stringify({ ...data, amount: Number(data.amount), has_receipt: form.has_receipt.checked, attendees: data.attendees || null }),
    });
    form.reset();
    updatePolicyHint();
    toast(claim.policy_flags.length ? `Draft #${claim.id} saved with ${claim.policy_flags.length} policy flag(s)` : `Draft #${claim.id} saved`);
    loadMyClaims();
  } catch (err) {
    toast(err.message, "error");
  }
});

async function loadMyClaims() {
  const rows = await api("/claims");
  document.querySelector("[data-testid=my-claims] tbody").innerHTML = rows.length
    ? rows.map((c) => `
      <tr data-testid="claim-row-${c.id}">
        <td>${c.id}</td><td>${c.expense_date}</td><td>${esc(c.category_name)}</td><td>${esc(c.merchant)}</td>
        <td class="num">${money(c.amount)}</td>
        <td><span class="status ${c.status}" data-testid="claim-status-${c.id}">${c.status}</span></td>
        <td>${flagsHtml(c.policy_flags)}</td>
        <td>${c.status === "draft" ? `<button data-submit="${c.id}" data-testid="submit-${c.id}">Submit</button>` : ""}</td>
      </tr>`).join("")
    : '<tr><td colspan="8" class="empty">No claims yet.</td></tr>';
}

document.querySelector("[data-testid=my-claims]").addEventListener("click", async (e) => {
  const id = e.target.dataset.submit;
  if (!id) return;
  try {
    await api(`/claims/${id}/submit`, { method: "POST" });
    toast(`Claim #${id} submitted for approval`);
    loadMyClaims();
  } catch (err) {
    toast(err.message, "error");
  }
});

// ---- approvals ------------------------------------------------------------
async function loadInbox() {
  const box = document.getElementById("inbox");
  const note = document.getElementById("approvals-note");
  if (state.me.role !== "manager") {
    note.textContent = "Only managers approve claims. Switch 'Acting as' to a manager.";
    box.innerHTML = "";
    return;
  }
  note.textContent = "";
  const rows = await api("/approvals/inbox");
  box.innerHTML = rows.length
    ? rows.map((c) => `
      <article class="card" data-testid="inbox-claim-${c.id}">
        <div class="card-head"><strong>#${c.id} ${esc(c.employee_name)}</strong><span>${money(c.amount)}</span></div>
        <p>${esc(c.category_name)} at ${esc(c.merchant)} on ${c.expense_date}: ${esc(c.description)}</p>
        ${c.attendees ? `<p class="hint">Attendees: ${esc(c.attendees)}</p>` : ""}
        <p class="hint">Receipt: ${c.has_receipt ? "yes" : "no"}</p>
        ${flagsHtml(c.policy_flags)}
        <div class="ai" data-testid="ai-review-${c.id}">${c.ai_review ? aiHtml(c.ai_review) : ""}</div>
        <textarea placeholder="Comment (required to reject)" data-comment="${c.id}" data-testid="comment-${c.id}"></textarea>
        <div class="actions">
          <button data-ai="${c.id}" class="secondary" data-testid="ai-btn-${c.id}">AI review</button>
          <button data-decide="rejected" data-id="${c.id}" class="danger" data-testid="reject-${c.id}">Reject</button>
          <button data-decide="approved" data-id="${c.id}" data-testid="approve-${c.id}">Approve</button>
        </div>
      </article>`).join("")
    : '<p class="empty" data-testid="inbox-empty">Nothing waiting for you.</p>';
}

function aiHtml(r) {
  if (!r.available) return `<p class="hint">${esc(r.message)}</p>`;
  if (r.error) return `<p class="hint">${esc(r.error)}</p>`;
  return `<p><strong>AI recommends: ${esc(r.recommendation)}</strong> (risk ${esc(r.risk)})</p>
    <ul>${(r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${r.question_for_employee ? `<p class="hint">Ask: ${esc(r.question_for_employee)}</p>` : ""}`;
}

document.getElementById("inbox").addEventListener("click", async (e) => {
  const { decide, id, ai } = e.target.dataset;
  try {
    if (ai) {
      e.target.disabled = true;
      e.target.textContent = "Reviewing…";
      const result = await api(`/claims/${ai}/ai-review`, { method: "POST" });
      document.querySelector(`[data-testid=ai-review-${ai}]`).innerHTML = aiHtml(result);
      e.target.disabled = false;
      e.target.textContent = "AI review";
    } else if (decide) {
      const comment = document.querySelector(`[data-comment="${id}"]`).value.trim() || null;
      await api(`/claims/${id}/decision`, { method: "POST", body: JSON.stringify({ decision: decide, comment }) });
      toast(`Claim #${id} ${decide}`);
      loadInbox();
    }
  } catch (err) {
    toast(err.message, "error");
    if (ai) { e.target.disabled = false; e.target.textContent = "AI review"; }
  }
});

// ---- start ----------------------------------------------------------------
async function init() {
  state.employees = await (await fetch("/api/employees")).json();
  state.categories = await (await fetch("/api/categories")).json();
  const picker = document.getElementById("acting-as");
  picker.innerHTML = state.employees.map((e) => `<option value="${e.id}">${esc(e.full_name)} (${e.role})</option>`).join("");
  picker.value = "2";
  state.me = state.employees.find((e) => e.id === 2);
  picker.addEventListener("change", () => {
    state.me = state.employees.find((e) => e.id === Number(picker.value));
    loadMyClaims();
    if (!document.getElementById("tab-approvals").hidden) loadInbox();
  });
  form.category_code.innerHTML = state.categories.map((c) => `<option value="${c.code}">${esc(c.name)}</option>`).join("");
  form.expense_date.max = new Date().toISOString().slice(0, 10);
  updatePolicyHint();
  loadMyClaims();
}

init();
