// ---------------------------------------------------------------------
// Advanced RAG Explorer — frontend. Vanilla JS, no build step.
// ---------------------------------------------------------------------

const state = {
  uploadId: null,
  columns: [],
  textCols: new Set(),
  metaCols: new Set(),
  chunkOffset: null,
  lastCitedIds: [],
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---- Tabs --------------------------------------------------------------

const INGEST_STAGES = [
  { key: "read", label: "Read file" },
  { key: "build_docs", label: "Build docs" },
  { key: "chunk", label: "Chunk" },
  { key: "embed", label: "Embed (bge-m3)" },
  { key: "index", label: "Index (Qdrant)" },
];
const CHAT_STAGES = [
  { key: "rewrite", label: "Rewrite query" },
  { key: "hybrid_search", label: "Dense + sparse search" },
  { key: "fuse", label: "RRF fuse" },
  { key: "rerank", label: "Re-rank (cross-encoder)" },
  { key: "answer", label: "Generate answer" },
];

function switchTab(tab) {
  $$(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${tab}`));
  if (tab === "ingest") renderTracker(INGEST_STAGES, {});
  if (tab === "chat") renderTracker(CHAT_STAGES, {});
  if (tab === "chunks") loadChunkFilters().then(() => loadChunks(true));
}
$$(".tab-btn").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

// ---- Status pill ---------------------------------------------------------

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const pill = $("#statusPill");
    const has = data.collection && data.collection.exists;
    pill.innerHTML = `<span class="led ${has ? "" : "off"}"></span> ${data.llm_provider || "no LLM key"} · ${has ? data.collection.points_count + " chunks indexed" : "no collection yet"}`;
  } catch (e) { /* server still warming up */ }
}
refreshStatus();
setInterval(refreshStatus, 8000);

// ---- Tracker -------------------------------------------------------------

function renderTracker(stages, statusMap, title) {
  $("#trackerTitle").textContent = title || "Pipeline";
  $("#trackerStages").innerHTML = stages.map((s) => {
    const st = statusMap[s.key];
    const cls = st ? st.status : "";
    const icon = cls === "done" ? "✓" : cls === "error" ? "!" : "";
    const meta = st && st.metaLine ? `<div class="stage-meta">${esc(st.metaLine)}</div>` : "";
    return `<div class="stage ${cls}"><div class="stage-icon">${icon}</div><div class="stage-label"><div class="stage-name">${esc(s.label)}</div>${meta}</div></div>`;
  }).join("");
}

// ---- Upload ---------------------------------------------------------------

const dropzone = $("#dropzone");
const fileInput = $("#fileInput");
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault(); dropzone.classList.remove("drag");
  if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; handleFile(e.dataTransfer.files[0]); }
});
fileInput.addEventListener("change", () => { if (fileInput.files.length) handleFile(fileInput.files[0]); });

async function handleFile(file) {
  $("#dropzoneLabel").textContent = `Uploading ${file.name}…`;
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    state.uploadId = data.upload_id;
    state.columns = data.columns;
    $("#dropzoneLabel").textContent = `${file.name} — ${data.row_count.toLocaleString()} rows, ${data.columns.length} columns`;
    renderPreview(data);
  } catch (e) {
    $("#dropzoneLabel").textContent = `Error: ${e.message}. Click to try again.`;
  }
}

function renderPreview(data) {
  $("#previewCard").style.display = "block";
  $("#previewSub").textContent = `${data.row_count.toLocaleString()} rows · dtypes: ` +
    Object.entries(data.dtypes).map(([c, t]) => `${c}(${t})`).join(", ");

  const cols = data.columns;
  const thead = `<tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>`;
  const rows = data.preview_rows.map((r) => `<tr>${cols.map((c) => `<td>${esc(r[c])}</td>`).join("")}</tr>`).join("");
  $("#previewTable").innerHTML = thead + rows;

  const likelyText = ["title", "summary", "steps", "expected", "tags", "preconditions", "test_data", "description"];
  const likelyMeta = ["id", "jira_id", "priority", "module", "status", "test_type", "sprint"];
  state.textCols = new Set(cols.filter((c) => likelyText.includes(c.toLowerCase())));
  state.metaCols = new Set(cols.filter((c) => likelyMeta.includes(c.toLowerCase())));

  $("#textColPicker").innerHTML = cols.map((c) => chipHtml(c, "text")).join("");
  $("#metaColPicker").innerHTML = cols.map((c) => chipHtml(c, "meta")).join("");
  $$("#textColPicker .chip").forEach((el) => el.addEventListener("click", () => toggleChip(el, "text")));
  $$("#metaColPicker .chip").forEach((el) => el.addEventListener("click", () => toggleChip(el, "meta")));
}

function chipHtml(col, kind) {
  const set = kind === "text" ? state.textCols : state.metaCols;
  const cls = set.has(col) ? `on-${kind}` : "";
  return `<div class="chip ${cls}" data-col="${esc(col)}">${esc(col)}</div>`;
}
function toggleChip(el, kind) {
  const set = kind === "text" ? state.textCols : state.metaCols;
  const col = el.dataset.col;
  if (set.has(col)) { set.delete(col); el.classList.remove(`on-${kind}`); }
  else { set.add(col); el.classList.add(`on-${kind}`); }
}

$("#startIngestBtn").addEventListener("click", startIngest);

function startIngest() {
  if (!state.textCols.size) { alert("Pick at least one text column."); return; }
  switchTab("ingest");
  $("#ingestStages").innerHTML = "";
  const params = new URLSearchParams({
    upload_id: state.uploadId,
    text_cols: Array.from(state.textCols).join(","),
    meta_cols: Array.from(state.metaCols).join(","),
  });
  const es = new EventSource(`/api/ingest/stream?${params.toString()}`);
  const statusMap = {};

  es.onmessage = (evt) => {
    const event = JSON.parse(evt.data);
    handleIngestEvent(event, statusMap);
    if (event.stage === "index" || event.stage === "error") { es.close(); refreshStatus(); }
  };
  es.onerror = () => { es.close(); };
}

function handleIngestEvent(event, statusMap) {
  const { stage, status, detail } = event;
  if (stage === "error") {
    appendIngestCard(`<div class="card"><h2 style="color:var(--red)">Error</h2><div>${esc(detail.message)}</div></div>`, true);
    return;
  }

  let metaLine = "";
  if (stage === "read") metaLine = `${detail.rows} rows`;
  if (stage === "build_docs") metaLine = `${detail.docs} docs`;
  if (stage === "chunk") metaLine = `${detail.total} chunks`;
  if (stage === "embed") metaLine = status === "progress" ? `${detail.done}/${detail.total}` : `${detail.total} embedded`;
  if (stage === "index") metaLine = `${detail.points_count} points`;

  statusMap[stage] = { status: status === "progress" ? "active" : "done", metaLine };
  renderTracker(INGEST_STAGES, statusMap);

  if (stage === "chunk" && status === "done") renderChunkStageCard(detail);
  if (stage === "embed") renderEmbedStageCard(detail, status);
  if (stage === "index" && status === "done") renderIndexStageCard(detail);
}

function appendIngestCard(html, replaceLast) {
  const wrap = $("#ingestStages");
  const div = document.createElement("div");
  div.innerHTML = html;
  wrap.appendChild(div.firstElementChild);
}

function renderChunkStageCard(d) {
  const maxCount = Math.max(1, ...d.histogram.map((h) => h.count));
  const hist = d.histogram.map((h) => `
    <div class="hist-col">
      <div class="hist-bar" style="height:${Math.max(4, (h.count / maxCount) * 80)}px">
        <div class="fill" style="height:100%"></div>
      </div>
      <div class="hist-label">${h.bucket}<br>${h.count}</div>
    </div>`).join("");

  const samples = d.samples.map((s) => {
    let text = esc(s.text);
    if (s.overlap_chars > 0) {
      const cut = esc(s.text.slice(0, s.overlap_chars));
      text = `<span class="overlap-hl">${cut}</span>${esc(s.text.slice(s.overlap_chars))}`;
    }
    return `<div class="chunk-sample">
      <div class="hdr"><span>${esc(s.chunk_id)} · row ${s.row_index}</span><span>${s.char_len} chars${s.overlap_chars ? " · " + s.overlap_chars + " overlap" : ""}</span></div>
      <pre>${text}</pre>
    </div>`;
  }).join("");

  appendIngestCard(`
    <div class="card">
      <h2>Chunk</h2>
      <div class="sub">${d.total} chunks · avg ${d.avg_chars} chars (min ${d.min_chars}, max ${d.max_chars})</div>
      <div class="hist-wrap">${hist}</div>
      <h4>Sample chunks (coral = overlap carried from previous chunk)</h4>
      ${samples}
    </div>`);
}

let embedCardInserted = false;
function renderEmbedStageCard(d, status) {
  let card = $("#embed-card");
  if (!card) {
    appendIngestCard(`<div class="card" id="embed-card"><h2>Embed</h2><div class="sub" id="embed-sub"></div>
      <div class="progress-bar"><div class="progress-fill" id="embed-progress" style="width:0%"></div></div>
      <h4>Dense vector preview (first 8 dims)</h4><div class="dims-row" id="embed-dense"></div>
      <h4>Sparse — top 5 tokens by weight</h4><div id="embed-sparse"></div>
    </div>`);
    card = $("#embed-card");
  }
  const pct = Math.round((d.done / d.total) * 100) || (status === "done" ? 100 : 0);
  $("#embed-sub").textContent = status === "done" ? `${d.total} chunks embedded (dim=${d.dim})` : `${d.done}/${d.total}`;
  $("#embed-progress").style.width = `${pct}%`;
  if (d.dense_preview && d.dense_preview.length) {
    $("#embed-dense").innerHTML = d.dense_preview.map((v) => `<span>${v.toFixed(4)}</span>`).join("");
  }
  if (d.sparse_preview && d.sparse_preview.length) {
    $("#embed-sparse").innerHTML = d.sparse_preview.map((t) => `<div class="token-row"><span>${esc(t.token)}</span><span>${t.weight}</span></div>`).join("");
  }
}

function renderIndexStageCard(d) {
  appendIngestCard(`<div class="card">
    <h2>Index</h2>
    <div class="sub">Qdrant collection <b>${esc(d.collection)}</b> — ${d.mode} mode${d.path ? " · " + esc(d.path) : ""}</div>
    <table class="mini">
      <tr><th>Points</th><td>${d.points_count}</td></tr>
      <tr><th>Status</th><td>${esc(d.status)}</td></tr>
      <tr><th>Total pipeline time</th><td>${d.total_elapsed_ms} ms</td></tr>
    </table>
  </div>`);
}

// ---- Chunks viewer ---------------------------------------------------------

async function loadChunkFilters() {
  const res = await fetch("/api/chunks/filters");
  const data = await res.json();
  const modSel = $("#filterModule"), prSel = $("#filterPriority");
  if (modSel.dataset.loaded) return;
  data.modules.forEach((m) => modSel.insertAdjacentHTML("beforeend", `<option value="${esc(m)}">${esc(m)}</option>`));
  data.priorities.forEach((p) => prSel.insertAdjacentHTML("beforeend", `<option value="${esc(p)}">${esc(p)}</option>`));
  modSel.dataset.loaded = "1";
}

async function loadChunks(reset) {
  if (reset) { state.chunkOffset = null; $("#chunkGrid").innerHTML = ""; }
  const params = new URLSearchParams({ limit: 30 });
  if (state.chunkOffset != null) params.set("offset", state.chunkOffset);
  const search = $("#chunkSearch").value.trim();
  const module = $("#filterModule").value;
  const priority = $("#filterPriority").value;
  const jira = $("#filterJira").value.trim();
  if (search) params.set("search", search);
  if (module) params.set("module", module);
  if (priority) params.set("priority", priority);
  if (jira) params.set("jira_id", jira);

  const res = await fetch(`/api/chunks?${params.toString()}`);
  const data = await res.json();
  state.chunkOffset = data.next_offset;
  $("#chunkLoadMore").style.display = data.next_offset != null ? "inline-block" : "none";

  if (!data.points.length && reset) {
    $("#chunkGrid").innerHTML = `<div class="empty-state">No chunks indexed yet — go to Upload → Ingest first.</div>`;
    return;
  }
  const html = data.points.map(renderChunkCard).join("");
  $("#chunkGrid").insertAdjacentHTML("beforeend", html);
}

function renderChunkCard(p) {
  const tags = Object.entries(p.payload).slice(0, 6).map(([k, v]) => `<span class="tag">${esc(k)}: ${esc(v)}</span>`).join("");
  const dense = (p.dense_preview || []).map((v) => v.toFixed(3)).join(", ");
  const sparse = (p.sparse_preview || []).map((t) => `${t.token_id}:${t.weight}`).join(", ");
  return `<div class="chunk-card ${p.cited ? "cited" : ""}">
    <div class="id">#${p.id} ${p.cited ? "· cited in last answer" : ""}</div>
    <div class="meta-tags">${tags}</div>
    <div class="text">${esc(p.text)}</div>
    <details><summary>vectors</summary>
      <div style="margin-top:6px"><b>dense[:8]</b>: ${dense}</div>
      <div><b>sparse top5 (ids)</b>: ${sparse}</div>
    </details>
  </div>`;
}

$("#chunkSearchBtn").addEventListener("click", () => loadChunks(true));
$("#chunkSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") loadChunks(true); });
$("#filterModule").addEventListener("change", () => loadChunks(true));
$("#filterPriority").addEventListener("change", () => loadChunks(true));
$("#chunkLoadMore").addEventListener("click", () => loadChunks(false));

// ---- Chat -------------------------------------------------------------

$("#chatSendBtn").addEventListener("click", sendChat);
$("#chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });

function appendUserMsg(text) {
  $("#chatLog").querySelector(".empty-state")?.remove();
  $("#chatLog").insertAdjacentHTML("beforeend", `<div class="msg user"><div class="role">You</div><div class="bubble">${esc(text)}</div></div>`);
  scrollChatToBottom();
}

function appendAssistantMsg() {
  const id = "msg-" + Date.now();
  $("#chatLog").insertAdjacentHTML("beforeend", `<div class="msg assistant"><div class="role">Assistant</div><div class="bubble" id="${id}">Thinking…</div></div>`);
  scrollChatToBottom();
  return id;
}
function scrollChatToBottom() { const log = $("#chatLog"); log.scrollTop = log.scrollHeight; }

async function sendChat() {
  const input = $("#chatInput");
  const query = input.value.trim();
  if (!query) return;
  input.value = "";
  appendUserMsg(query);
  const bubbleId = appendAssistantMsg();
  const bubble = document.getElementById(bubbleId);

  switchTab("chat");
  const statusMap = {};
  renderTracker(CHAT_STAGES, statusMap, "Pipeline");

  let trace = { rewrites: [], dense: [], sparse: [], fused: [], before: [], after: [] };

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      bubble.innerHTML = `<span style="color:var(--red)">${esc(data.error || "Request failed")}</span>`;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        const line = part.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const event = JSON.parse(line.slice(6));
        handleChatEvent(event, statusMap, trace, bubble);
      }
    }
  } catch (e) {
    bubble.innerHTML = `<span style="color:var(--red)">${esc(e.message)}</span>`;
  }
}

function handleChatEvent(event, statusMap, trace, bubble) {
  const { stage, status, detail } = event;
  if (stage === "error") {
    bubble.innerHTML = `<span style="color:var(--red)">${esc(detail.message)}</span>`;
    return;
  }

  let metaLine = "";
  if (stage === "rewrite") { trace.rewrites = detail.rewrites; metaLine = `${detail.rewrites.length} rewrites`; }
  if (stage === "hybrid_search") { trace.dense = detail.dense_top; trace.sparse = detail.sparse_top; metaLine = `${detail.dense_top.length} + ${detail.sparse_top.length} hits`; }
  if (stage === "fuse") { trace.fused = detail.fused_top; metaLine = `${detail.fused_top.length} fused`; }
  if (stage === "rerank") { trace.before = detail.before; trace.after = detail.after; metaLine = `top ${detail.after.length}`; }
  if (stage === "answer") metaLine = detail.mode;

  statusMap[stage] = { status: "done", metaLine };
  renderTracker(CHAT_STAGES, statusMap, "Pipeline");

  if (stage === "answer") renderFinalAnswer(bubble, trace, detail);
  else renderTraceInProgress(bubble, trace);
}

function renderTraceInProgress(bubble, trace) {
  bubble.innerHTML = `<i style="color:var(--ink-soft)">Working through the pipeline…</i>` + traceHtml(trace);
}

function traceHtml(trace) {
  const rewrites = trace.rewrites.length
    ? `<h4 style="margin:10px 0 4px;font-size:11px;text-transform:uppercase;color:var(--ink-soft)">Query rewrites</h4>` +
      trace.rewrites.map((r) => `<div class="tag" style="display:inline-block;margin:2px 4px 2px 0">${esc(r)}</div>`).join("")
    : "";

  const rankCol = (title, list) => `<div><h5>${title}</h5>${list.slice(0, 5).map((p) =>
    `<div style="font-size:11px;margin-bottom:4px"><b>#${p.rank}</b> id ${p.id} (${p.score ?? "—"})<br><span style="color:var(--ink-soft)">${esc(p.text_preview.slice(0, 70))}…</span></div>`).join("")}</div>`;

  const hybrid = (trace.dense.length || trace.sparse.length)
    ? `<h4 style="margin:14px 0 4px;font-size:11px;text-transform:uppercase;color:var(--ink-soft)">Dense vs Sparse vs Fused (top 5)</h4>
       <div class="rank-cols">${rankCol("Dense", trace.dense)}${rankCol("Sparse", trace.sparse)}${rankCol("RRF Fused", trace.fused)}</div>`
    : "";

  const rerank = trace.after.length
    ? `<h4 style="margin:14px 0 4px;font-size:11px;text-transform:uppercase;color:var(--ink-soft)">Re-rank: before → after</h4>
       <table class="rank-table"><tr><th>Before rank</th><th>After score</th><th>Chunk</th></tr>
       ${trace.after.map((p) => `<tr><td>#${p.rank}</td><td>${p.rerank_score}</td><td>${esc(p.text_preview.slice(0, 60))}…</td></tr>`).join("")}
       </table>`
    : "";

  return `<div class="trace-block">${rewrites}${hybrid}${rerank}</div>`;
}

function renderFinalAnswer(bubble, trace, detail) {
  let answerHtml = esc(detail.answer).replace(/\n/g, "<br>").replace(/\[Chunk (\d+)\]/g, '<span class="citation-tag">Chunk $1</span>');
  const citations = detail.citations.map((c) => `<div class="tag" style="display:inline-block;margin:2px 4px 2px 0">#${c.chunk_number}: ${esc(c.meta.jira_id || c.meta.chunk_id || c.id)}</div>`).join("");

  const traceId = "trace-" + Date.now();
  bubble.innerHTML = `
    <div class="mode-badge ${detail.mode === "generate" ? "generate" : ""}">${detail.mode === "generate" ? "Generated new test case" : "Grounded answer"}</div>
    <p>${answerHtml}</p>
    <div style="margin-top:8px">${citations}</div>
    <div class="trace-toggle" onclick="document.getElementById('${traceId}').style.display = document.getElementById('${traceId}').style.display==='none' ? 'block' : 'none'">▸ show pipeline trace (${detail.total_elapsed_ms} ms)</div>
    <div id="${traceId}" style="display:none">${traceHtml(trace)}</div>
  `;
  scrollChatToBottom();
}
