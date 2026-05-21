let CONTENT_TYPES = {};
let selectedType  = null;
let lastResult    = null;
let lastStyle     = "cinematic";

// ── Bootstrap ─────────────────────────────────────────────────────────────────

async function init() {
  const res = await fetch("/api/content-types");
  CONTENT_TYPES = await res.json();
  renderTypeGrid();
}

// ── Type grid ─────────────────────────────────────────────────────────────────

function renderTypeGrid() {
  const grid = document.getElementById("type-grid");
  grid.innerHTML = "";
  Object.entries(CONTENT_TYPES).forEach(([key, ct]) => {
    const btn = document.createElement("button");
    btn.id = `type-btn-${key}`;
    const active = selectedType === key;
    btn.className = [
      "type-card relative p-3 rounded-xl border text-left transition-all",
      "hover:border-violet-500/50 hover:text-white",
      active
        ? "bg-violet-600/20 border-violet-500 text-white"
        : "bg-[#1a1a2e] border-white/10 text-gray-400",
    ].join(" ");
    btn.innerHTML = `
      <div class="text-2xl mb-1">${ct.icon || "📄"}</div>
      <div class="text-xs font-semibold leading-tight">${ct.label}</div>
      ${ct.is_video
        ? '<div class="absolute top-2 right-2 w-2 h-2 rounded-full bg-violet-500"></div>'
        : ""}
    `;
    btn.onclick = () => selectType(key);
    grid.appendChild(btn);
  });
}

function selectType(key) {
  selectedType = key;
  renderTypeGrid();
  renderForm(key);
}

// ── Form ──────────────────────────────────────────────────────────────────────

function renderForm(key) {
  const ct = CONTENT_TYPES[key];
  hide("form-placeholder");
  show("form-container");

  document.getElementById("form-icon").textContent  = ct.icon || "📄";
  document.getElementById("form-title").textContent = ct.label;

  const fieldsEl = document.getElementById("form-fields");
  fieldsEl.innerHTML = "";

  ct.variables.forEach((v) => {
    const wrap = document.createElement("div");
    wrap.className = "space-y-1";

    const label = document.createElement("label");
    label.className = "block text-xs font-medium text-gray-400";
    label.textContent = v.label;
    label.htmlFor = `field-${v.name}`;
    wrap.appendChild(label);

    let input;
    if (v.type === "select") {
      input = document.createElement("select");
      input.className = fieldClass();
      v.options.forEach((opt) => {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        input.appendChild(o);
      });
    } else if (v.type === "textarea") {
      input = document.createElement("textarea");
      input.rows = 3;
      input.placeholder = v.placeholder || "";
      input.className = fieldClass() + " resize-none";
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.placeholder = v.placeholder || "";
      input.className = fieldClass();
    }
    input.id   = `field-${v.name}`;
    input.name = v.name;
    wrap.appendChild(input);
    fieldsEl.appendChild(wrap);
  });

  document.getElementById("generate-form").onsubmit = handleSubmit;

  // Animate in
  const card = document.querySelector("#form-container > div");
  card.classList.remove("fade-in");
  void card.offsetWidth;
  card.classList.add("fade-in");
}

function fieldClass() {
  return [
    "w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2.5",
    "text-sm text-white placeholder-gray-600",
    "focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500/50",
    "transition",
  ].join(" ");
}

// ── Generate content ──────────────────────────────────────────────────────────

async function handleSubmit(e) {
  e.preventDefault();
  const variables = {};
  new FormData(document.getElementById("generate-form")).forEach((val, key) => {
    variables[key] = val;
  });
  lastStyle = variables.visual_style || "cinematic";

  showLoading("Generating konten dengan AI…");

  try {
    const res  = await fetch("/api/generate", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ content_type: selectedType, variables }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    lastResult = data;
    showResult(data, CONTENT_TYPES[selectedType]);
  } catch (err) {
    showError(err.message);
  }
}

// ── Display results ───────────────────────────────────────────────────────────

function showResult(data, ct) {
  hide("result-empty");
  hide("result-loading");
  show("result-content");

  document.getElementById("result-type-label").textContent = ct.label;
  document.getElementById("result-title").textContent      = data.title || "—";

  if (ct.is_video) {
    hide("text-result-area");
    show("video-result-area");
    fillVideoResult(data);
  } else {
    hide("video-result-area");
    show("text-result-area");
    fillTextResult(data);
  }

  document.getElementById("frames-container").innerHTML = "";
  hide("frames-loading");

  const rc = document.getElementById("result-content");
  rc.classList.remove("fade-in");
  void rc.offsetWidth;
  rc.classList.add("fade-in");
}

function fillTextResult(data) {
  setText("main-content-text", data.main_content || data.content || "");
  setText("alt1-text", data.alternative_1 || "—");
  setText("alt2-text", data.alternative_2 || "—");
  setText("best-time", data.best_posting_time || "—");

  const tips = document.getElementById("eng-tips");
  tips.innerHTML = "";
  (data.engagement_tips || []).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    tips.appendChild(li);
  });

  renderTags("hashtags-text", data.hashtags);
}

function fillVideoResult(data) {
  setText("hook-text",   data.hook        || "—");
  setText("script-text", data.full_script || "—");
  setText("caption-text",data.caption     || "—");
  setText("cta-text",    data.cta         || "—");
  renderTags("video-hashtags", data.hashtags);

  const list = document.getElementById("scenes-list");
  list.innerHTML = "";
  (data.scenes || []).forEach((sc) => {
    const card = document.createElement("div");
    card.className = "bg-black/20 rounded-xl p-4 border border-white/5";
    card.innerHTML = `
      <div class="flex items-center gap-2 mb-2">
        <span class="text-xs font-bold bg-violet-600/30 text-violet-300 px-2 py-0.5 rounded">
          Scene ${sc.id}
        </span>
        <span class="text-xs text-gray-500">${sc.time_range || ""}</span>
      </div>
      <p class="text-sm text-gray-300 mb-2">
        <span class="text-gray-500 text-xs font-medium block mb-0.5">VISUAL</span>
        ${esc(sc.visual_description || "")}
      </p>
      <p class="text-sm text-gray-300 mb-3">
        <span class="text-gray-500 text-xs font-medium block mb-0.5">NARASI</span>
        ${esc(sc.narration || "")}
      </p>
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div class="bg-green-900/20 border border-green-700/30 rounded-lg p-2.5">
          <span class="text-green-400 font-bold">▶ START FRAME</span>
          <p class="text-gray-400 mt-1 leading-relaxed">
            ${esc((sc.start_frame || "").substring(0, 130))}${(sc.start_frame || "").length > 130 ? "…" : ""}
          </p>
        </div>
        <div class="bg-red-900/20 border border-red-700/30 rounded-lg p-2.5">
          <span class="text-red-400 font-bold">⏹ END FRAME</span>
          <p class="text-gray-400 mt-1 leading-relaxed">
            ${esc((sc.end_frame || "").substring(0, 130))}${(sc.end_frame || "").length > 130 ? "…" : ""}
          </p>
        </div>
      </div>
    `;
    list.appendChild(card);
  });
}

// ── Generate frame images ─────────────────────────────────────────────────────

async function generateFrames() {
  if (!lastResult) return;

  document.getElementById("frames-container").innerHTML = "";
  show("frames-loading");
  document.getElementById("generate-frames-btn").disabled = true;

  const scenes = lastResult.scenes || [];
  let frames = scenes.map((s) => ({
    start_frame: s.start_frame || lastResult.video_start_frame || "",
    end_frame:   s.end_frame   || lastResult.video_end_frame   || "",
    scene_num:   s.id,
  }));

  if (!frames.length) {
    frames = [{
      start_frame: lastResult.video_start_frame || "",
      end_frame:   lastResult.video_end_frame   || "",
      scene_num:   null,
    }];
  }

  try {
    const res  = await fetch("/api/generate-frames", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ frames, style: lastStyle, title: lastResult.title || "" }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    hide("frames-loading");
    renderFrames(data.frames);
  } catch (err) {
    hide("frames-loading");
    document.getElementById("frames-container").innerHTML =
      `<p class="text-red-400 text-sm p-4">Error: ${esc(err.message)}</p>`;
  } finally {
    document.getElementById("generate-frames-btn").disabled = false;
  }
}

function renderFrames(frames) {
  const container = document.getElementById("frames-container");
  container.innerHTML = "";

  frames.forEach((f, idx) => {
    const wrap  = document.createElement("div");
    wrap.className = "fade-in";
    const label = f.scene_num != null ? `Scene ${f.scene_num}` : "Video Frame";

    wrap.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="text-xs font-bold bg-white/5 border border-white/10 text-gray-400 px-3 py-1 rounded-full">
          ${label}
        </span>
        <div class="flex-1 h-px bg-white/5"></div>
      </div>
      <div class="frame-pair">
        <div class="rounded-xl overflow-hidden border border-green-700/40 shadow-xl">
          <div class="flex items-center justify-between px-3 py-2 bg-green-900/30 border-b border-green-700/30">
            <span class="text-xs font-bold text-green-400">▶ START FRAME</span>
            <button onclick="dlFrame('start','${idx}')"
              class="text-xs text-gray-500 hover:text-white transition px-2 py-0.5 rounded bg-white/5 hover:bg-white/10">
              ⬇ Download
            </button>
          </div>
          <img id="img-start-${idx}" src="data:image/png;base64,${f.start_frame}"
               class="w-full block" alt="Start Frame ${label}" />
          <div class="px-3 py-2 bg-black/20">
            <p class="text-xs text-gray-500 leading-relaxed line-clamp-2">
              ${esc((f.start_description || "").substring(0, 110))}…
            </p>
          </div>
        </div>
        <div class="rounded-xl overflow-hidden border border-red-700/40 shadow-xl">
          <div class="flex items-center justify-between px-3 py-2 bg-red-900/30 border-b border-red-700/30">
            <span class="text-xs font-bold text-red-400">⏹ END FRAME</span>
            <button onclick="dlFrame('end','${idx}')"
              class="text-xs text-gray-500 hover:text-white transition px-2 py-0.5 rounded bg-white/5 hover:bg-white/10">
              ⬇ Download
            </button>
          </div>
          <img id="img-end-${idx}" src="data:image/png;base64,${f.end_frame}"
               class="w-full block" alt="End Frame ${label}" />
          <div class="px-3 py-2 bg-black/20">
            <p class="text-xs text-gray-500 leading-relaxed line-clamp-2">
              ${esc((f.end_description || "").substring(0, 110))}…
            </p>
          </div>
        </div>
      </div>
    `;
    container.appendChild(wrap);
  });
}

function dlFrame(type, idx) {
  const img = document.getElementById(`img-${type}-${idx}`);
  if (!img) return;
  const a = document.createElement("a");
  a.href     = img.src;
  a.download = `${type}_frame_scene${idx}.png`;
  a.click();
}

// ── Copy ──────────────────────────────────────────────────────────────────────

function copyContent() {
  if (!lastResult) return;
  const text =
    lastResult.main_content ||
    lastResult.full_script  ||
    lastResult.content      ||
    JSON.stringify(lastResult, null, 2);
  navigator.clipboard.writeText(text).then(() => {
    const btn  = document.getElementById("copy-btn");
    const orig = btn.innerHTML;
    btn.innerHTML = "✓ Copied!";
    btn.classList.add("text-green-400");
    setTimeout(() => { btn.innerHTML = orig; btn.classList.remove("text-green-400"); }, 2000);
  });
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function showLoading(msg) {
  hide("result-empty");
  hide("result-content");
  show("result-loading");
  document.getElementById("loading-msg").textContent = msg;
}

function showError(msg) {
  hide("result-loading");
  show("result-empty");
  document.getElementById("result-empty").innerHTML = `
    <div class="text-5xl mb-4">❌</div>
    <h3 class="text-lg font-bold text-red-400 mb-2">Error</h3>
    <p class="text-gray-500 text-sm max-w-sm">${esc(msg)}</p>
    <button onclick="location.reload()"
      class="mt-4 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm text-gray-400 hover:text-white transition">
      Coba Lagi
    </button>
  `;
}

function show(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hide(id) { document.getElementById(id)?.classList.add("hidden"); }
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val || ""; }
function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderTags(containerId, tags) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = "";
  (tags || []).forEach((tag) => {
    const span = document.createElement("span");
    span.className =
      "px-2 py-0.5 text-xs bg-violet-600/20 text-violet-300 border border-violet-500/20 rounded-full";
    span.textContent = tag;
    el.appendChild(span);
  });
}

init();
