// ── Voice samples: one shared <audio>; button shows loading / playing / progress; errors are visible.
(() => {
  const audio = new Audio();
  audio.preload = "none";
  let current = null;

  const setState = (btn, state) => {
    btn.dataset.state = state;                       // idle | loading | playing
    btn.setAttribute("aria-pressed", state === "idle" ? "false" : "true");
    const name = btn.getAttribute("aria-label").replace(/^(Play|Stop) sample of /, "");
    btn.setAttribute("aria-label", `${state === "idle" ? "Play" : "Stop"} sample of ${name}`);
    const row = btn.closest(".voice");
    row?.classList.toggle("is-playing", state !== "idle");
    if (state === "idle") { btn.style.setProperty("--progress", 0); row?.style.setProperty("--row-progress", 0); }
  };
  const stop = () => {
    if (!current) return;
    audio.pause();
    setState(current, "idle");
    current = null;
  };
  const fail = () => {
    if (!current) return;
    const card = current.closest(".voice");
    current.disabled = true;
    current.title = "Sample unavailable";
    setState(current, "idle");
    card?.querySelector(".voice-error")?.removeAttribute("hidden");
    current = null;
  };

  audio.addEventListener("playing", () => current && setState(current, "playing"));
  audio.addEventListener("waiting", () => current && setState(current, "loading"));
  audio.addEventListener("ended", stop);
  audio.addEventListener("error", fail);
  audio.addEventListener("timeupdate", () => {
    if (!current || !audio.duration) return;
    const p = audio.currentTime / audio.duration;
    current.style.setProperty("--progress", p);
    current.closest(".voice")?.style.setProperty("--row-progress", p);
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button.play");
    if (!btn || btn.disabled) return;
    if (btn === current) return stop();
    stop();
    current = btn;
    setState(btn, "loading");
    audio.src = btn.dataset.src;
    audio.play().catch((err) => (err.name === "AbortError" ? null : fail()));
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") stop(); });
})();

// ── Compare tray: selection survives navigation (localStorage), max 6.
(() => {
  const KEY = "compare-models", MAX = 6;
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; } };
  const write = (items) => { try { localStorage.setItem(KEY, JSON.stringify(items)); } catch { /* private mode */ } };
  let items = read();                                 // [{key, label}]

  // On the compare page itself, the URL is the source of truth.
  if (location.pathname === "/compare") {
    const keys = new URLSearchParams(location.search).getAll("m");
    const labels = Object.fromEntries(items.map((i) => [i.key, i.label]));
    document.querySelectorAll("th[data-key]").forEach((th) => (labels[th.dataset.key] = th.dataset.label));
    items = keys.map((k) => ({ key: k, label: labels[k] || k.split("/").pop() }));
    write(items);
  }

  const tray = document.getElementById("compare-tray");
  const navCount = document.getElementById("compare-count");
  const compareUrl = () => "/compare?" + items.map((i) => "m=" + encodeURIComponent(i.key)).join("&");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  const render = () => {
    const has = (k) => items.some((i) => i.key === k);
    document.querySelectorAll(".compare-pick").forEach((cb) => {
      cb.checked = has(cb.dataset.key);
      cb.disabled = !cb.checked && items.length >= MAX;
    });
    document.querySelectorAll(".compare-toggle").forEach((b) => {
      const on = has(b.dataset.key);
      b.setAttribute("aria-pressed", String(on));
      b.textContent = on ? "Added to compare" : "Add to compare";
    });
    if (navCount) navCount.textContent = items.length ? String(items.length) : "";
    if (!tray || location.pathname === "/compare") return;
    tray.hidden = items.length === 0;
    tray.querySelector(".tray-list").innerHTML = items
      .map((i) => `<li><span>${esc(i.label)}</span><button type="button" data-remove="${esc(i.key)}" aria-label="Remove ${esc(i.label)}">×</button></li>`)
      .join("");
    const go = tray.querySelector(".tray-go");
    go.href = compareUrl();
    go.textContent = items.length < 2 ? "Pick one more to compare" : `Compare ${items.length} models`;
    go.toggleAttribute("aria-disabled", items.length < 2);
  };

  const toggle = (key, label, on) => {
    items = items.filter((i) => i.key !== key);
    if (on && items.length < MAX) items.push({ key, label });
    write(items);
    render();
  };

  document.addEventListener("change", (e) => {
    const cb = e.target.closest(".compare-pick");
    if (cb) toggle(cb.dataset.key, cb.dataset.label, cb.checked);
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".compare-toggle");
    if (b) toggle(b.dataset.key, b.dataset.label, b.getAttribute("aria-pressed") !== "true");
    const rm = e.target.closest("[data-remove]");
    if (rm) toggle(rm.dataset.remove, "", false);
    if (e.target.closest(".tray-clear")) { items = []; write(items); render(); }
    const go = e.target.closest(".tray-go");
    if (go && go.hasAttribute("aria-disabled")) e.preventDefault();
  });
  render();

  // Compare page: "only differences" + copy link.
  const diff = document.getElementById("only-diff");
  diff?.addEventListener("change", () => document.querySelector("table.compare")?.classList.toggle("only-diff", diff.checked));
  const copy = document.getElementById("copy-link");
  copy?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); copy.textContent = "Link copied"; }
    catch { copy.textContent = "Copy the address bar link"; }
    setTimeout(() => (copy.textContent = "Copy link"), 2000);
  });
})();

// ── Copy voice ids.
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".copy-id");
  if (!b) return;
  const label = b.getAttribute("aria-label");
  try { await navigator.clipboard.writeText(b.dataset.copy); b.dataset.copied = "1"; b.setAttribute("aria-label", "Copied"); }
  catch { b.dataset.copied = "0"; b.setAttribute("aria-label", "Copy failed. Select the id and copy it manually."); }
  setTimeout(() => { delete b.dataset.copied; b.setAttribute("aria-label", label); }, 1400);
});

// ── Filters apply as soon as a dropdown or checkbox changes (text fields still use Enter / Apply).
document.addEventListener("change", (e) => {
  const el = e.target;
  const form = el.closest("form.filters");
  if (form && (el.tagName === "SELECT" || el.type === "checkbox") && !el.classList.contains("compare-pick")) {
    form.querySelector('[name="page"]')?.remove();
    form.requestSubmit();
  }
});
