const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---- Tabs -------------------------------------------------------------
$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#panel-${tab.dataset.tab}`).classList.add("active");
  });
});

// ---- Status -------------------------------------------------------------
async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const count = data.collection?.points_count ?? 0;
    $("#statusPill").textContent = `${data.llm_provider || "no LLM"} · ${count.toLocaleString()} chunks indexed`;
  } catch (e) {
    $("#statusPill").textContent = "status unavailable";
  }
}

// ---- Pipeline tracker (shared by Sources ingest + Chat) ------------------
function renderTracker(container, stages) {
  container.innerHTML = stages.map((s) => {
    const icon = s.status === "done" ? "✓" : s.status === "error" ? "!" : "";
    const meta = s.metaLine ? `<div class="stage-meta">${esc(s.metaLine)}</div>` : "";
    return `<div class="stage ${s.status}"><div class="stage-icon">${icon}</div><div><div class="stage-name">${esc(s.label)}</div>${meta}</div></div>`;
  }).join("");
}

function streamSSE(url, options, onEvent) {
  return fetch(url, options).then(async (res) => {
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        const line = part.split("\n").find((l) => l.startsWith("data: "));
        if (line) onEvent(JSON.parse(line.slice(6)));
      }
    }
  });
}

// ---- Sources --------------------------------------------------------------
const SOURCE_LABELS = {
  "01_selenium_framework": "Selenium framework", "02_playwright_framework": "Playwright framework",
  "03_test_cases": "Test cases", "05_company_docs": "Company docs", "07_meeting_notes": "Meeting notes",
  "08_lucid_charts": "Lucid charts", "09_prd_srs_brd_frd": "PRD / SRS / BRD / FRD", "10_jenkins_logs": "Jenkins logs",
};
const INGEST_STAGE_LABELS = { read: "Read source", chunk: "Chunk", embed: "Embed (bge-m3)", index: "Index in Qdrant" };

async function loadSources() {
  const res = await fetch("/api/sources");
  const data = await res.json();
  const list = $("#sourceList");
  list.innerHTML = data.sources.map((s) => sourceCardHTML(s)).join("");
  data.sources.forEach((s) => wireSourceCard(s.key));
}

function sourceCardHTML(s) {
  const label = SOURCE_LABELS[s.key] || s.key;
  const uploadUI = s.key === "03_test_cases" ? testCaseUploadHTML() : "";
  const ingestBtn = s.key === "03_test_cases" ? "" : `<button class="btn" data-ingest="${s.key}">Ingest</button>`;
  return `<div class="source-card" id="card-${s.key}">
    <div class="info">
      <div class="source-key"><span class="badge">${s.source_type}</span>${esc(label)}</div>
      <div class="source-meta">${s.file_count} file(s) in data_sources/${s.key}/ · ${s.indexed_chunks} chunk(s) indexed</div>
      ${uploadUI}
      <div class="source-progress" id="progress-${s.key}" style="display:none"></div>
    </div>
    ${ingestBtn}
  </div>`;
}

function testCaseUploadHTML() {
  return `<div class="upload-row" style="margin-top:8px">
    <label class="file-label">Choose CSV/XLSX<input type="file" id="tcFile" accept=".csv,.xlsx,.xls"></label>
    <span id="tcFileName" style="font-size:12px;color:var(--ink-soft)"></span>
  </div>
  <div class="tc-preview" id="tcPreview" style="display:none">
    <div class="label">Text columns (embedded)</div>
    <div class="col-picker" id="tcTextCols"></div>
    <div class="label">Metadata columns (filterable, not embedded)</div>
    <div class="col-picker" id="tcMetaCols"></div>
    <button class="btn" id="tcIngest" style="margin-top:8px">Start ingestion</button>
  </div>`;
}

function wireSourceCard(key) {
  if (key === "03_test_cases") {
    wireTestCaseUpload();
    return;
  }
  const btn = document.querySelector(`[data-ingest="${key}"]`);
  if (!btn) return;
  btn.addEventListener("click", () => runIngest(key));
}

function runIngest(key) {
  const btn = document.querySelector(`[data-ingest="${key}"]`);
  const progress = $(`#progress-${key}`);
  const stages = { read: { status: "" }, chunk: { status: "" }, embed: { status: "" }, index: { status: "" } };
  progress.style.display = "block";
  if (btn) btn.disabled = true;

  const render = () => {
    progress.innerHTML = Object.entries(INGEST_STAGE_LABELS).map(([k, label]) => {
      const st = stages[k];
      const icon = st.status === "done" ? "✓" : st.status === "error" ? "!" : st.status === "progress" ? "…" : "";
      return `${icon ? icon + " " : "• "}${label}${st.detail ? ": " + st.detail : ""}`;
    }).join("\n");
  };
  render();

  streamSSE(`/api/sources/${key}/ingest/stream`, {}, (event) => {
    if (event.stage === "error") {
      progress.textContent = `Error: ${event.detail.message}`;
      if (btn) btn.disabled = false;
      return;
    }
    const st = stages[event.stage];
    if (!st) return;
    st.status = event.status;
    if (event.stage === "chunk" && event.status === "done") st.detail = `${event.detail.total} chunks`;
    if (event.stage === "embed" && event.status === "progress") st.detail = `${event.detail.done}/${event.detail.total}`;
    if (event.stage === "embed" && event.status === "done") st.detail = `${event.detail.total} done`;
    if (event.stage === "index" && event.status === "done") st.detail = `${event.detail.points_count} total chunks in index`;
    render();
    if (event.stage === "index" && event.status === "done") {
      if (btn) btn.disabled = false;
      loadSources();
      refreshStatus();
    }
  }).catch((e) => {
    progress.textContent = `Error: ${e.message}`;
    if (btn) btn.disabled = false;
  });
}

// ---- Test case upload (needs column selection before ingest) --------------
let tcState = { uploadId: null, columns: [], textCols: new Set(), metaCols: new Set() };

function wireTestCaseUpload() {
  const fileInput = $("#tcFile");
  if (!fileInput) return;
  fileInput.addEventListener("change", async () => {
    if (!fileInput.files.length) return;
    const file = fileInput.files[0];
    $("#tcFileName").textContent = file.name;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/test_cases/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      tcState = { uploadId: data.upload_id, columns: data.columns, textCols: new Set(), metaCols: new Set() };
      renderColumnPicker();
      $("#tcPreview").style.display = "block";
    } catch (e) {
      $("#tcFileName").textContent = `Error: ${e.message}`;
    }
  });
}

function renderColumnPicker() {
  const render = (containerId, set, other) => {
    $(containerId).innerHTML = tcState.columns.map((c) =>
      `<div class="col-chip${set.has(c) ? " text" : ""}" data-col="${esc(c)}">${esc(c)}</div>`
    ).join("");
    $$(`${containerId} .col-chip`).forEach((chip) => {
      chip.addEventListener("click", () => {
        const col = chip.dataset.col;
        if (set.has(col)) set.delete(col); else { set.add(col); other.delete(col); }
        renderColumnPicker();
      });
    });
  };
  render("#tcTextCols", tcState.textCols, tcState.metaCols);
  render("#tcMetaCols", tcState.metaCols, tcState.textCols);
  $$("#tcTextCols .col-chip").forEach((c) => c.classList.toggle("text", tcState.textCols.has(c.dataset.col)));
  $$("#tcMetaCols .col-chip").forEach((c) => c.classList.toggle("meta", tcState.metaCols.has(c.dataset.col)));

  $("#tcIngest").onclick = () => {
    if (tcState.textCols.size === 0) { alert("Select at least one text column."); return; }
    const params = new URLSearchParams({
      upload_id: tcState.uploadId,
      text_cols: [...tcState.textCols].join(","),
      meta_cols: [...tcState.metaCols].join(","),
    });
    const btn = $("#tcIngest");
    btn.disabled = true;
    const progress = $("#progress-03_test_cases");
    progress.style.display = "block";
    const stages = { read: { status: "" }, chunk: { status: "" }, embed: { status: "" }, index: { status: "" } };
    const render2 = () => {
      progress.innerHTML = Object.entries(INGEST_STAGE_LABELS).map(([k, label]) => {
        const st = stages[k];
        const icon = st.status === "done" ? "✓" : st.status === "error" ? "!" : st.status === "progress" ? "…" : "";
        return `${icon ? icon + " " : "• "}${label}${st.detail ? ": " + st.detail : ""}`;
      }).join("\n");
    };
    streamSSE(`/api/test_cases/ingest/stream?${params}`, {}, (event) => {
      if (event.stage === "error") { progress.textContent = `Error: ${event.detail.message}`; btn.disabled = false; return; }
      const st = stages[event.stage];
      if (!st) return;
      st.status = event.status;
      if (event.stage === "chunk" && event.status === "done") st.detail = `${event.detail.total} chunks`;
      if (event.stage === "embed" && event.status === "progress") st.detail = `${event.detail.done}/${event.detail.total}`;
      if (event.stage === "embed" && event.status === "done") st.detail = `${event.detail.total} done`;
      if (event.stage === "index" && event.status === "done") st.detail = `${event.detail.points_count} total chunks in index`;
      render2();
      if (event.stage === "index" && event.status === "done") { btn.disabled = false; loadSources(); refreshStatus(); }
    }).catch((e) => { progress.textContent = `Error: ${e.message}`; btn.disabled = false; });
  };
}

// ---- Chat -----------------------------------------------------------------
let chatMode = "answer";
const activeSourceFilters = new Set();

$$(".mode-chip").forEach((chip) => chip.addEventListener("click", () => {
  $$(".mode-chip").forEach((c) => c.classList.remove("active"));
  chip.classList.add("active");
  chatMode = chip.dataset.mode;
}));

$$(".filter-chip").forEach((chip) => chip.addEventListener("click", () => {
  chip.classList.toggle("active");
  const t = chip.dataset.type;
  if (activeSourceFilters.has(t)) activeSourceFilters.delete(t); else activeSourceFilters.add(t);
}));

const CHAT_STAGE_LABELS = { rewrite: "Rewrite query", hybrid_search: "Dense + sparse search", fuse: "RRF fuse", rerank: "Re-rank (cross-encoder)", answer: "Generate answer" };

$("#chatSend").addEventListener("click", sendChat);
$("#chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });

function sendChat() {
  const query = $("#chatInput").value.trim();
  if (!query) return;
  const trackerCard = $("#chatTrackerCard");
  const answerCard = $("#answerCard");
  trackerCard.style.display = "block";
  answerCard.style.display = "none";
  $("#chatSend").disabled = true;

  const stageOrder = ["rewrite", "hybrid_search", "fuse", "rerank", "answer"];
  const stages = stageOrder.map((key) => ({ key, label: CHAT_STAGE_LABELS[key], status: "" }));
  renderTracker($("#chatTrackerStages"), stages);

  streamSSE("/api/chat/stream", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, mode: chatMode, source_types: [...activeSourceFilters] }),
  }, (event) => {
    const stage = stages.find((s) => s.key === event.stage);
    if (stage) {
      stage.status = event.status;
      if (event.stage === "rewrite") stage.metaLine = event.detail.rewrites.join(" · ") || "(no rewrites)";
      if (event.stage === "hybrid_search") stage.metaLine = `${event.detail.dense_top.length} dense · ${event.detail.sparse_top.length} sparse hits`;
      if (event.stage === "fuse") stage.metaLine = `${event.detail.fused_top.length} fused candidates`;
      if (event.stage === "rerank") stage.metaLine = `top ${event.detail.after.length} selected`;
      renderTracker($("#chatTrackerStages"), stages);
    }
    if (event.stage === "answer") {
      $("#chatSend").disabled = false;
      if (event.status === "error") {
        answerCard.style.display = "block";
        $("#answerText").textContent = event.detail.message;
        $("#citationList").innerHTML = "";
        return;
      }
      answerCard.style.display = "block";
      $("#answerText").textContent = event.detail.answer;
      $("#citationList").innerHTML = event.detail.citations.map((c) =>
        `<div class="citation-item"><span class="cite-label">[Chunk ${c.chunk_number}]</span> ${esc(c.citation)} <span style="color:var(--ink-soft)">(${esc(c.source_type)})</span><div style="margin-top:4px;color:var(--ink-soft)">${esc(c.text_preview)}…</div></div>`
      ).join("");
    }
  }).catch((e) => {
    $("#chatSend").disabled = false;
    trackerCard.style.display = "none";
    answerCard.style.display = "block";
    $("#answerText").textContent = `Error: ${e.message}`;
    $("#citationList").innerHTML = "";
  });
}

// ---- Chunks -----------------------------------------------------------------
async function loadChunks() {
  const params = new URLSearchParams({ limit: "50" });
  const search = $("#chunkSearch").value.trim();
  const sourceType = $("#chunkSourceType").value;
  if (search) params.set("search", search);
  if (sourceType) params.set("source_type", sourceType);
  const res = await fetch(`/api/chunks?${params}`);
  const data = await res.json();
  $("#chunkList").innerHTML = data.points.map((p) => `
    <div class="chunk-item${p.cited ? " cited" : ""}">
      <div class="chunk-head"><span>${esc(p.payload.source_type)} · ${esc(p.payload.source_name)} · ${esc(p.payload.chunk_id)}</span></div>
      <div>${esc(p.text.slice(0, 300))}${p.text.length > 300 ? "…" : ""}</div>
    </div>`).join("") || `<div class="source-meta">No chunks found.</div>`;
}
$("#chunkRefresh").addEventListener("click", loadChunks);

// ---- Init -------------------------------------------------------------------
refreshStatus();
loadSources();
loadChunks();
