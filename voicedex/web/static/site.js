// Voicedex — progressive enhancement only. Every page works without this file.
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const typing = () => /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;

// ── Voice samples: one shared <audio>; row + now-playing bar show state; J/K move, Space pauses, Esc stops.
(() => {
  const audio = new Audio();
  audio.preload = "none";
  const bar = $("#now-playing");
  const toggle = bar && $(".np-toggle", bar);
  let current = null;

  const label = (btn) => btn.getAttribute("aria-label").replace(/^(Play|Stop) sample of /, "");
  const setState = (btn, state) => {
    btn.dataset.state = state;                       // idle | loading | playing
    btn.setAttribute("aria-pressed", state === "idle" ? "false" : "true");
    btn.setAttribute("aria-label", `${state === "idle" ? "Play" : "Stop"} sample of ${label(btn)}`);
    const row = btn.closest(".voice");
    row?.classList.toggle("is-playing", state !== "idle");
    if (state === "idle") row?.style.setProperty("--row-progress", 0);
  };
  const showBar = (btn) => {
    if (!bar) return;
    const row = btn.closest(".voice");
    $(".np-name", bar).textContent = row?.dataset.name || label(btn);
    $(".np-meta", bar).textContent = row?.dataset.meta || "";
    bar.style.setProperty("--p", 0);
    toggle.classList.remove("paused");
    toggle.setAttribute("aria-label", "Pause");
    bar.hidden = false;
  };
  const stop = () => {
    if (!current) return;
    audio.pause();
    setState(current, "idle");
    current = null;
    if (bar) bar.hidden = true;
  };
  const fail = () => {
    if (!current) return;
    const row = current.closest(".voice");
    current.disabled = true;
    current.title = "Sample unavailable";
    setState(current, "idle");
    row?.querySelector(".voice-error")?.removeAttribute("hidden");
    current = null;
    if (bar) bar.hidden = true;
  };
  const play = (btn) => {
    if (!btn || btn.disabled) return;
    if (btn === current) return stop();
    stop();
    current = btn;
    setState(btn, "loading");
    showBar(btn);
    audio.src = btn.dataset.src;
    audio.play().catch((err) => (err.name === "AbortError" ? null : err.name === "NotAllowedError" ? stop() : fail()));
  };

  audio.addEventListener("playing", () => current && setState(current, "playing"));
  audio.addEventListener("waiting", () => current && setState(current, "loading"));
  audio.addEventListener("ended", stop);
  audio.addEventListener("error", fail);
  audio.addEventListener("timeupdate", () => {
    if (!current || !audio.duration) return;
    const p = audio.currentTime / audio.duration;
    current.closest(".voice")?.style.setProperty("--row-progress", p);
    bar?.style.setProperty("--p", p);
  });
  toggle?.addEventListener("click", () => {
    if (!current) return;
    if (audio.paused) { audio.play(); toggle.classList.remove("paused"); toggle.setAttribute("aria-label", "Pause"); }
    else { audio.pause(); toggle.classList.add("paused"); toggle.setAttribute("aria-label", "Play"); }
  });

  document.addEventListener("click", (e) => { const b = e.target.closest("button.play"); if (b) play(b); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") return stop();
    if (typing() || e.metaKey || e.ctrlKey || e.altKey || $("#palette")?.open) return;
    const buttons = $$("button.play:not(:disabled)");
    if (!buttons.length) return;
    if (e.key === "j" || e.key === "k") {
      e.preventDefault();
      const i = current ? buttons.indexOf(current) : -1;
      const next = buttons[e.key === "j" ? Math.min(i + 1, buttons.length - 1) : Math.max(i - 1, 0)];
      play(next);
      next.closest(".voice")?.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
    } else if (e.key === " " && current) {
      e.preventDefault();
      toggle?.click();
    }
  });
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
    $$("th[data-key]").forEach((th) => (labels[th.dataset.key] = th.dataset.label));
    items = keys.map((k) => ({ key: k, label: labels[k] || k.split("/").pop() }));
    write(items);
  }

  const tray = $("#compare-tray");
  const navCount = $("#compare-count");
  const compareUrl = () => "/compare?" + items.map((i) => "m=" + encodeURIComponent(i.key)).join("&");

  const render = () => {
    const has = (k) => items.some((i) => i.key === k);
    $$(".compare-pick").forEach((cb) => {
      cb.checked = has(cb.dataset.key);
      cb.disabled = !cb.checked && items.length >= MAX;
      cb.title = cb.disabled ? `Up to ${MAX} models` : "";
    });
    $$(".compare-toggle").forEach((b) => {
      const on = has(b.dataset.key);
      b.setAttribute("aria-pressed", String(on));
      b.textContent = on ? "Added to compare" : "Add to compare";
    });
    if (navCount) navCount.textContent = items.length ? String(items.length) : "";
    if (!tray || location.pathname === "/compare") return;
    tray.hidden = items.length === 0;
    $(".tray-list", tray).innerHTML = items
      .map((i) => `<li><span>${esc(i.label)}</span><button type="button" data-remove="${esc(i.key)}" aria-label="Remove ${esc(i.label)}">×</button></li>`)
      .join("");
    $(".tray-count", tray).textContent = `${items.length} selected`;
    const go = $(".tray-go", tray);
    go.href = compareUrl();
    go.textContent = items.length < 2 ? "Pick one more" : `Compare ${items.length}`;
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
  const diff = $("#only-diff");
  diff?.addEventListener("change", () => $("table.compare")?.classList.toggle("only-diff", diff.checked));
  const copy = $("#copy-link");
  copy?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); copy.textContent = "Link copied"; }
    catch { copy.textContent = "Copy the address bar link"; }
    setTimeout(() => (copy.textContent = "Copy link"), 2000);
  });
})();

// ── Copy buttons (ids, commands).
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".copy-btn");
  if (!b) return;
  const label = b.getAttribute("aria-label");
  try { await navigator.clipboard.writeText(b.dataset.copy); b.dataset.copied = "1"; b.setAttribute("aria-label", "Copied"); }
  catch { b.dataset.copied = "0"; b.setAttribute("aria-label", "Copy failed. Select the text and copy it manually."); }
  setTimeout(() => { delete b.dataset.copied; b.setAttribute("aria-label", label); }, 1400);
});

// ── Filters apply as soon as a dropdown or checkbox changes (text fields still use Enter / Apply).
document.addEventListener("change", (e) => {
  const el = e.target;
  const form = el.closest("form.filters, form[data-autosubmit]");
  if (form && (el.tagName === "SELECT" || el.type === "checkbox") && !el.classList.contains("compare-pick")) {
    form.querySelector('[name="page"]')?.remove();
    form.requestSubmit();
  }
});
// On phones the filter bar starts collapsed (active filters still show as removable tokens below it).
if (matchMedia("(max-width: 760px)").matches) {
  $$("details[data-collapse-sm]").forEach((d) => { d.open = false; });
}

// ── Tooltips for spectrum squares and timeline dots ("provider|name|price|note").
(() => {
  if (!matchMedia("(hover: hover)").matches) return;
  let tip = null, target = null;
  const hide = () => { tip?.remove(); tip = null; target?.classList.remove("is-tip"); target = null; };
  document.addEventListener("pointerover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (!el || el === target) return;
    hide();
    const [provider, name, price, note] = el.dataset.tip.split("|");
    tip = document.createElement("div");
    tip.className = "tip";
    tip.innerHTML = `<span>${esc(provider)}</span><b>${esc(name)}</b>${price ? `<span class="tip-price">${esc(price)}</span>` : ""}${note ? `<span class="tip-end">${esc(note)}</span>` : ""}`;
    document.body.append(tip);
    target = el;
    el.classList.add("is-tip");
    const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
    const left = Math.min(Math.max(8, r.left + r.width / 2 - t.width / 2), innerWidth - t.width - 8);
    const top = r.top - t.height - 10 < 8 ? r.bottom + 10 : r.top - t.height - 10;
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  });
  document.addEventListener("pointerout", (e) => { if (target && !target.contains(e.relatedTarget)) hide(); });
  addEventListener("scroll", hide, { passive: true });
})();

// ── Stat tickers: count up once on first view (final value is already in the HTML).
(() => {
  const els = $$("[data-count]");
  if (!els.length || reduceMotion || document.hidden || !("IntersectionObserver" in window)) return;
  const fmt = new Intl.NumberFormat("en-US");
  const io = new IntersectionObserver((entries) => entries.forEach((en) => {
    if (!en.isIntersecting) return;
    io.unobserve(en.target);
    const el = en.target, end = +el.dataset.count, t0 = performance.now(), dur = 700;
    el.style.minWidth = `${el.getBoundingClientRect().width}px`;
    // Browsers pause animation frames in background tabs; always land on the true value.
    const settle = () => (el.textContent = fmt.format(end));
    setTimeout(settle, dur + 150);
    document.addEventListener("visibilitychange", settle, { once: true });
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur), eased = 1 - Math.pow(2, -10 * k);
      el.textContent = fmt.format(Math.round(end * (k === 1 ? 1 : eased)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }), { threshold: 0.6 });
  els.forEach((el) => io.observe(el));
})();

// ── ⌘K palette: models, providers, languages and features. Index is fetched once, on first open.
(() => {
  const dlg = $("#palette");
  if (!dlg || !dlg.showModal) return;
  const input = $("#pal-q"), list = $("#pal-list"), status = $(".pal-status", dlg);
  const TYPE = { stt: "Speech-to-text", tts: "Text-to-speech", sts: "Realtime" };
  const FEATURES = {
    word_timestamps: "Word timestamps", speaker_diarization: "Speaker diarization", punctuation: "Punctuation",
    profanity_filter: "Profanity filter", custom_vocabulary: "Custom vocabulary", language_detection: "Language detection",
    translation: "Translation", sentiment: "Sentiment", pii_redaction: "PII redaction", summarization: "Summarization",
    topic_detection: "Topic detection", emotion: "Emotion control", voice_cloning: "Voice cloning", voice_design: "Voice design",
    ssml: "SSML", phoneme_input: "Phoneme input", prosody_control: "Speed / prosody control", style_control: "Style control",
    multi_speaker: "Multi-speaker",
  };
  // Shown before anything is typed: every section is reachable from here (the phone header shows only Models/Voices).
  const PAGES = [
    { kind: "Go to", main: "Models", sub: "Filter, sort by price, compare", url: "/models" },
    { kind: "Go to", main: "Voices", sub: "Browse and play samples", url: "/voices" },
    { kind: "Go to", main: "Providers", sub: "Every provider, including retired ones", url: "/#providers" },
    { kind: "Go to", main: "Compare", sub: "Models side by side", url: "/compare" },
    { kind: "Go to", main: "API docs", sub: "Free REST API, no key", url: "/docs" },
  ];
  let index = null, loading = null, shown = [], sel = 0;

  const load = () => loading ??= Promise.all([
    fetch("/v1/providers").then((r) => r.json()),
    fetch("/v1/models?limit=500").then((r) => r.json()),
  ]).then(([providers, models]) => {
    const names = Object.fromEntries(providers.map((p) => [p.provider_id, p.display_name]));
    let langName = (c) => c;
    try { const dn = new Intl.DisplayNames(["en"], { type: "language" }); langName = (c) => dn.of(c) || c; } catch { /* old browser */ }
    const langs = new Map();
    for (const m of models.data) for (const l of m.languages) if (l !== "*") { const b = l.split("-")[0].toLowerCase(); langs.set(b, (langs.get(b) || 0) + 1); }
    index = [
      ...providers.map((p) => ({ kind: "Provider", main: p.display_name, sub: p.status === "active" ? `${p.model_count} models` : "No longer available", url: `/providers/${p.provider_id}`, hay: `${p.display_name} ${p.provider_id}` })),
      ...models.data.map((m) => ({ kind: TYPE[m.type] ? m.type.toUpperCase().replace("STS", "S2S") : m.type, main: m.model_id, sub: `${names[m.provider_id] || m.provider_id}, ${m.display_name}`, end: m.eol_date ? `ends ${m.eol_date}` : "", url: `/models/${m.provider_id}/${m.type}/${m.model_id}`, hay: `${m.model_id} ${m.display_name} ${names[m.provider_id] || ""} ${m.provider_id}` })),
      ...[...langs].map(([code, n]) => ({ kind: "Language", main: langName(code), sub: `${n} models`, url: `/models?language=${code}`, hay: `${langName(code)} ${code}` })),
      ...Object.entries(FEATURES).map(([k, v]) => ({ kind: "Feature", main: v, sub: "Models that list it", url: `/models?capability=${k}`, hay: `${v} ${k.replace(/_/g, " ")}` })),
    ].map((it) => ({ ...it, hay: it.hay.toLowerCase() }));
  }).catch(() => { index = []; status.textContent = "Couldn't load the index"; });

  const score = (it, q, terms) => {
    if (!terms.every((t) => it.hay.includes(t))) return -1;
    const main = it.main.toLowerCase();
    return (main === q ? 100 : 0) + (main.startsWith(q) ? 50 : 0) + (it.kind === "Provider" ? 10 : 0) - main.length / 100;
  };
  const search = () => {
    const q = input.value.trim().toLowerCase();
    const terms = q.split(/\s+/).filter(Boolean);
    if (!index && !terms.length) { shown = PAGES; sel = 0; draw(); return; }
    if (!index) { list.innerHTML = `<li class="pl-empty"><span class="loader loader-sm" aria-hidden="true"><i></i><i></i><i></i><i></i></span> Loading the catalog…</li>`; return; }
    shown = terms.length
      ? index.map((it) => [score(it, q, terms), it]).filter(([s]) => s >= 0).sort((a, b) => b[0] - a[0]).slice(0, 40).map(([, it]) => it)
      : [...PAGES, ...index.filter((it) => it.kind === "Provider" && it.sub !== "No longer available")];
    if (terms.length) shown.push({ kind: "Search", main: `Everything matching “${input.value.trim()}”`, sub: "voices included", url: `/search?q=${encodeURIComponent(input.value.trim())}` });
    sel = 0;
    status.textContent = terms.length ? `${shown.length - 1} results` : "";
    draw();
  };
  const draw = () => {
    list.innerHTML = shown.length ? shown.map((it, i) => `<li role="option" id="pl-${i}" data-i="${i}" aria-selected="${i === sel}">
      <span class="pl-kind">${esc(it.kind)}</span><span class="pl-main">${esc(it.main)}</span><span class="pl-sub">${esc(it.sub)}</span>${it.end ? `<span class="pl-end">${esc(it.end)}</span>` : ""}</li>`).join("")
      : `<li class="pl-empty">No matches</li>`;
    input.setAttribute("aria-activedescendant", shown.length ? `pl-${sel}` : "");
    $('[aria-selected="true"]', list)?.scrollIntoView({ block: "nearest" });
  };
  const open = (seed = "") => {
    if (dlg.open) return;
    dlg.showModal();
    input.value = seed;
    input.focus();
    search();
    load().then(() => dlg.open && search());
  };
  const go = (i) => { if (shown[i]) location.href = shown[i].url; };

  input.addEventListener("input", search);
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, shown.length - 1); draw(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); draw(); }
    else if (e.key === "Enter") { e.preventDefault(); go(sel); }
  });
  list.addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) go(+li.dataset.i); });
  list.addEventListener("pointermove", (e) => { const li = e.target.closest("li[data-i]"); if (li && +li.dataset.i !== sel) { sel = +li.dataset.i; draw(); } });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });

  // Header and hero search fields open the palette (they still work as plain forms without JS).
  $$("[data-palette-trigger]").forEach((form) => {
    const field = $("input", form);
    form.addEventListener("submit", (e) => { e.preventDefault(); open(field.value); });
    field.addEventListener("focus", () => { const v = field.value; field.blur(); open(v); });
    form.addEventListener("click", () => open(field.value));
  });
  addEventListener("keydown", (e) => {
    if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing())) { e.preventDefault(); open(); }
  });
  addEventListener("pagehide", () => dlg.open && dlg.close());
})();

// ── Cross-page continuity: a model link morphs into the model page title (Chrome/Safari; others just navigate).
addEventListener("pageswap", (e) => {
  const url = e.activation?.entry?.url;
  if (!e.viewTransition || !url) return;
  const path = new URL(url).pathname;
  if (!path.startsWith("/models/")) return;
  const link = $$(`a[href="${CSS.escape(path)}"]`).find((a) => a.querySelector("code") && a.getBoundingClientRect().height);
  if (link) link.querySelector("code").style.viewTransitionName = "model-title";
});

// ── Searchable picker: long <select data-searchable="noun"> (languages, providers) gets a type-to-filter combobox.
// The real <select> stays in the form (hidden) and still drives submission; phones keep the native picker.
(() => {
  if (!matchMedia("(pointer: fine)").matches) return;
  let uid = 0;
  $$("select[data-searchable]").forEach((select) => {
    const options = [...select.options].map((o) => ({ value: o.value, text: o.text }));
    const anyText = options.find((o) => o.value === "")?.text || "Any";
    const noun = select.dataset.searchable || "language";
    const id = `combo-${++uid}`;
    const wrap = document.createElement("span");
    wrap.className = "combo";
    wrap.innerHTML = `<input type="text" class="combo-input" role="combobox" aria-expanded="false" aria-controls="${id}" aria-autocomplete="list" autocomplete="off" spellcheck="false"><ul class="combo-list" id="${id}" role="listbox" hidden></ul>`;
    select.before(wrap);
    select.hidden = true;
    const input = $("input", wrap), list = $("ul", wrap);
    const currentText = () => (select.value ? select.options[select.selectedIndex].text : "");
    input.placeholder = select.value ? currentText() : anyText;
    input.value = currentText();
    let shown = [], active = 0;

    const render = () => {
      const q = input.value.trim().toLowerCase();
      const filtering = q && q !== currentText().toLowerCase();
      shown = filtering
        ? options.filter((o) => o.value && o.text.toLowerCase().includes(q))
            .sort((a, b) => b.text.toLowerCase().startsWith(q) - a.text.toLowerCase().startsWith(q))
        : options;
      active = Math.max(0, shown.findIndex((o) => o.value === select.value));
      if (filtering) active = 0;
      list.innerHTML = shown.length
        ? shown.map((o, i) => {
            const label = filtering ? esc(o.text).replace(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "i"), "<mark>$1</mark>") : esc(o.text);
            return `<li role="option" id="${id}-${i}" data-i="${i}" aria-selected="${i === active}" class="${o.value === select.value ? "current" : ""}">${label}</li>`;
          }).join("")
        : `<li class="combo-empty">No ${esc(noun)} matches “${esc(input.value.trim())}”</li>`;
      input.setAttribute("aria-activedescendant", shown.length ? `${id}-${active}` : "");
      list.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    };
    const open = () => { if (!list.hidden) return; list.hidden = false; input.setAttribute("aria-expanded", "true"); render(); };
    const close = (restore = true) => {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      if (restore) input.value = currentText();
    };
    const pick = (o) => {
      close(false);
      input.value = o.value ? o.text : "";
      input.placeholder = o.value ? o.text : anyText;
      if (select.value === o.value) return;
      select.value = o.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));   // filters auto-submit on change
    };
    const move = (d) => {
      if (!shown.length) return;
      active = (active + d + shown.length) % shown.length;
      $$("li[role=option]", list).forEach((li, i) => li.setAttribute("aria-selected", String(i === active)));
      input.setAttribute("aria-activedescendant", `${id}-${active}`);
      list.children[active]?.scrollIntoView({ block: "nearest" });
    };

    input.addEventListener("focus", () => { input.select(); open(); });
    input.addEventListener("click", open);
    input.addEventListener("input", () => { open(); render(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); list.hidden ? open() : move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") { e.preventDefault(); if (!list.hidden && shown[active]) pick(shown[active]); }
      else if (e.key === "Escape") { if (!list.hidden) { e.preventDefault(); e.stopPropagation(); close(); } }
      else if (e.key === "Tab") close();
    });
    list.addEventListener("mousedown", (e) => e.preventDefault());       // keep focus in the input
    list.addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) pick(shown[+li.dataset.i]); });
    list.addEventListener("pointermove", (e) => {
      const li = e.target.closest("li[data-i]");
      if (li && +li.dataset.i !== active) { active = +li.dataset.i; move(0); }
    });
    input.addEventListener("blur", () => close());
  });
})();

// ── Clean filter URLs: drop empty fields on submit (?type=stt&language=hi, not …&provider=&status=).
document.addEventListener("formdata", (e) => {
  if (!e.target.matches("form.filters, form[data-autosubmit]")) return;
  for (const [k, v] of [...e.formData]) if (v === "") e.formData.delete(k);
});

// ── Coverage map: show as many language columns as fit (no sideways scroll on desktop; phones still scroll).
(() => {
  const wrap = $(".map-scroll"), table = wrap && $("table.map", wrap);
  if (!table) return;
  const style = document.createElement("style");
  document.head.append(style);
  const fit = () => {
    style.textContent = "";
    if (innerWidth <= 760) return;                       // phones: scroll the full map
    const first = $("tbody th", table)?.getBoundingClientRect().width || 0;
    const total = $("td.map-total", table)?.getBoundingClientRect().width || 0;
    const cell = 20;                                     // 18px cell + 2px spacing
    const cols = $$("thead th.map-lang", table).length;
    const fitCols = Math.max(12, Math.min(cols, Math.floor((wrap.clientWidth - first - total - 12) / cell)));
    if (fitCols < cols) style.textContent = `.map tr > :nth-child(n+${fitCols + 2}):not(.map-total) { display: none; }`;
    const note = $("#coverage-cols");
    if (note) note.textContent = String(fitCols);
  };
  fit();
  addEventListener("resize", fit);
})();
