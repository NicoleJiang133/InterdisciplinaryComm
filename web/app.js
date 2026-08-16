const EXAMPLES = {
  icu: "A random-forest classifier trained on resting-state fMRI connectivity matrices predicts conversion to Alzheimer's disease with 92% accuracy, so the same connectivity-based approach should predict which ICU patients will develop sepsis from their continuous vital-sign monitoring streams.",
  kuramoto: "Kuramoto mean-field coupling of noisy oscillators predicts the onset of firefly flash synchrony, so the same coupling should predict synchronized flowering across a meadow from daily temperature records.",
  foraging: "The marginal value theorem from optimal foraging predicts when a forager leaves a depleting patch, so the same rule should predict when a translating ribosome unbinds from an mRNA from single-molecule dwell-time traces.",
};

const STAGE_ORDER = ["ingest", "retrieve", "align", "ledger", "report"];
const STAGE_LABEL = {
  ingest: "Ingest",
  retrieve: "Retrieve",
  align: "Align",
  ledger: "Ledger",
  report: "Report",
};

const state = {
  live: true,
  runId: null,
  mode: null,
  timers: {},
  ticking: null,
};

function $(id) { return document.getElementById(id); }

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function stated(value) {
  if (value == null || value === "") return null;
  return value;
}

function setMode(live) {
  state.live = live;
  $("mode-live").classList.toggle("on", live);
  $("mode-saved").classList.toggle("on", !live);
  $("mode-note").textContent = live
    ? "Live calls Paperclip and Anthropic. If either fails, a saved fixture is shown and labelled as saved."
    : "Saved replays the committed ICU fixture. It will not be presented as a live run.";
}

function banner(mode, reason) {
  const el = $("banner");
  el.hidden = false;
  if (mode === "saved") {
    el.innerHTML = "SAVED RUN — not live" + (reason ? '<span class="why">' + esc(reason) + "</span>" : "");
  } else {
    el.innerHTML = "LIVE RUN";
  }
}

function ensureStage(name) {
  let el = document.getElementById("stage-" + name);
  if (el) return el;
  el = document.createElement("section");
  el.className = "stage";
  el.id = "stage-" + name;
  el.innerHTML = '<div class="stage-head"><span class="name">' + esc(STAGE_LABEL[name]) + '</span><span class="time" id="time-' + name + '">running</span></div><div class="body" id="body-' + name + '"></div>';
  $("stages").appendChild(el);
  return el;
}

function startTimer(name) {
  ensureStage(name);
  state.timers[name] = { t0: performance.now(), running: true };
  const clock = $("time-" + name);
  if (clock) clock.textContent = "0.0s";
}

function stopTimer(name, seconds) {
  const timer = state.timers[name];
  if (timer) timer.running = false;
  const clock = $("time-" + name);
  if (clock) clock.textContent = (seconds == null ? "—" : Number(seconds).toFixed(1) + "s");
}

function tick() {
  const now = performance.now();
  for (const [name, timer] of Object.entries(state.timers)) {
    if (!timer.running) continue;
    const clock = $("time-" + name);
    if (clock) clock.textContent = ((now - timer.t0) / 1000).toFixed(1) + "s";
  }
}

function resetStages() {
  $("stages").innerHTML = "";
  state.timers = {};
  STAGE_ORDER.forEach(ensureStage);
}

function renderSlots(data) {
  ensureStage("ingest");
  stopTimer("ingest", data.seconds);
  $("body-ingest").innerHTML = (data.slots || []).map((slot) => {
    const value = stated(slot.value);
    return '<div class="slot"><div class="name">' + esc(slot.slot) + "</div>" +
      (value ? '<div class="val">' + esc(value) + "</div>" : '<div class="val null">not stated</div>') +
      "</div>";
  }).join("");
}

function appendDoc(doc) {
  ensureStage("retrieve");
  let table = document.getElementById("docs");
  if (!table) {
    $("body-retrieve").innerHTML = '<table><thead><tr><th>Doc</th><th>Source</th><th>Label</th><th>Title</th></tr></thead><tbody id="docs"></tbody></table>';
    table = document.getElementById("docs");
  }
  const label = doc.label || "unclassified";
  const tr = document.createElement("tr");
  tr.innerHTML = '<td class="doc">' + esc(doc.doc_id) + "</td><td>" + esc(doc.source) +
    '</td><td><span class="status ' + esc(label) + '">' + esc(String(label).replaceAll("_", "-")) + "</span></td><td>" +
    esc(doc.title) + "</td>";
  table.appendChild(tr);
}

function renderRetrieve(data) {
  stopTimer("retrieve", data.seconds);
  const check = data.check;
  if (!check) return;
  const note = document.createElement("p");
  note.className = "muted";
  note.textContent = "in-discipline " + check.in_discipline + " · generic " + check.generic +
    (check.below_floor ? " · source-leg floor missed" : "");
  $("body-retrieve").prepend(note);
}

function renderAlign(data) {
  ensureStage("align");
  stopTimer("align", data.seconds);
  const breaks = (data.break_points || []).map((row) =>
    "<tr><td>" + esc(row.slot) + '</td><td class="num">' + row.papers_stating + " / n=" + row.extracted +
    "</td><td>" + (row.target_states_it ? "stated" : "silent") + "</td></tr>"
  ).join("");
  const papers = (data.papers || []).map((row) =>
    '<tr><td class="doc">' + esc(row.doc_id) + '</td><td class="num">' + row.mapped +
    '</td><td class="num">' + row.unmapped + "</td><td>" + (row.admitted ? "admitted" : "held out") + "</td></tr>"
  ).join("");
  $("body-align").innerHTML =
    '<p class="muted">Unmapped slots among extracted papers. Denominator is n in every cell.</p>' +
    "<table><thead><tr><th>Slot</th><th>Stating it</th><th>Target</th></tr></thead><tbody>" +
    (breaks || '<tr><td colspan="3">none</td></tr>') + "</tbody></table>" +
    "<h3>Mapped and unmapped</h3>" +
    "<table><thead><tr><th>Doc</th><th>Mapped</th><th>Unmapped</th><th></th></tr></thead><tbody>" +
    papers + "</tbody></table>";
}

function appendEntry(entry) {
  ensureStage("ledger");
  let list = document.getElementById("entries");
  if (!list) {
    $("body-ledger").innerHTML =
      '<p class="hint">Correcting a restatement is the highest-value input this system can capture. It is stored as corrections.json in the run directory.</p>' +
      '<div id="entries"></div>';
    list = document.getElementById("entries");
  }
  const axisId = "axis-" + entry.axis;
  let group = document.getElementById(axisId);
  if (!group) {
    group = document.createElement("div");
    group.id = axisId;
    group.innerHTML = "<h3>" + esc(entry.axis) + "</h3>";
    list.appendChild(group);
  }
  const article = document.createElement("article");
  article.className = "entry";
  article.innerHTML =
    '<div class="entry-head"><span class="status ' + esc(entry.status) + '">' + esc(entry.status) + "</span>" +
    (entry.subtype ? '<span class="muted">' + esc(entry.subtype) + "</span>" : "") +
    '<span class="doc">' + esc(entry.source_doc_id) + "</span>" +
    (entry.evidence_lines ? '<span class="muted">' + esc(entry.evidence_lines) + "</span>" : "") +
    "</div>" +
    '<div class="pair"><div><h4>Source assumption</h4><p>' + esc(entry.source_assumption) + "</p></div>" +
    '<div><h4>Target restatement — editable</h4><textarea data-doc="' + esc(entry.source_doc_id) +
    '" data-axis="' + esc(entry.axis) + '">' + esc(entry.target_restatement || "") + "</textarea></div></div>";
  group.appendChild(article);
}

function renderLedger(data) {
  stopTimer("ledger", data.seconds);
}

function renderReport(data) {
  ensureStage("report");
  stopTimer("report", data.seconds);
  $("body-report").innerHTML = '<a class="report-link" href="' + esc(data.url) + '" target="_blank" rel="noopener">Open report.html</a>';
}

function handleEvent(type, data) {
  if (type === "start") {
    state.runId = data.run_id;
    state.mode = data.mode;
    banner(data.mode, data.reason);
    if (data.mode === "live") startTimer("ingest");
  }
  if (type === "fallback") {
    state.mode = "saved";
    banner("saved", data.reason);
    resetStages();
  }
  if (type === "stage") startTimer(data.name);
  if (type === "ingest") renderSlots(data);
  if (type === "doc") appendDoc(data.doc);
  if (type === "retrieve") renderRetrieve(data);
  if (type === "align") renderAlign(data);
  if (type === "entry") appendEntry(data.entry);
  if (type === "ledger") renderLedger(data);
  if (type === "report") renderReport(data);
}

function parseSse(chunk, carry) {
  const text = carry + chunk;
  const parts = text.split("\n\n");
  const rest = parts.pop();
  for (const block of parts) {
    let type = "message";
    let payload = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) type = line.slice(6).trim();
      if (line.startsWith("data:")) payload += line.slice(5).trim();
    }
    if (payload) handleEvent(type, JSON.parse(payload));
  }
  return rest;
}

async function run() {
  $("submit").disabled = true;
  $("banner").hidden = true;
  resetStages();
  if (!state.ticking) state.ticking = setInterval(tick, 200);
  const body = {
    claim: $("claim").value,
    source_discipline: $("discipline").value.trim() || null,
    live: state.live,
  };
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
      body: JSON.stringify(body),
    });
    if (!response.ok || !response.body) throw new Error("run failed: " + response.status);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let carry = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      carry = parseSse(decoder.decode(value, { stream: true }), carry);
    }
    if (carry.trim()) parseSse("\n\n", carry);
  } catch (err) {
    banner("saved", String(err));
  } finally {
    $("submit").disabled = false;
  }
}

$("mode-live").addEventListener("click", () => setMode(true));
$("mode-saved").addEventListener("click", () => setMode(false));
$("submit").addEventListener("click", run);
document.querySelector(".examples").addEventListener("click", (event) => {
  const key = event.target.getAttribute("data-example");
  if (key && EXAMPLES[key]) $("claim").value = EXAMPLES[key];
});
$("stages").addEventListener("focusout", async (event) => {
  const area = event.target;
  if (!(area instanceof HTMLTextAreaElement) || !state.runId) return;
  const payload = {
    source_doc_id: area.getAttribute("data-doc"),
    axis: area.getAttribute("data-axis"),
    target_restatement: area.value,
  };
  await fetch("/api/runs/" + state.runId + "/corrections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
});

setMode(true);
