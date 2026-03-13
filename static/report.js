function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function truncate(str, max) {
  if (!str) return "";
  return str.length > max ? str.slice(0, max) + "…" : str;
}

function renderRunReport(run, container) {
  if (!container) return;
  if (!run || !run.run_id) { container.innerHTML = ""; return; }

  const cases = run.cases || [];
  const total = cases.length;
  const passed = cases.filter(c => c.evaluation ? c.evaluation.pass : c.status === "completed").length;
  const passRate = total > 0 ? Math.round((passed / total) * 100) : 0;
  const latencies = cases.map(c => c.latency_ms).filter(Boolean);
  const avgLatency = latencies.length
    ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : null;

  let duration = "";
  if (run.started_at && run.ended_at) {
    const ms = new Date(run.ended_at) - new Date(run.started_at);
    duration = Math.round(ms / 1000) + "s";
  }

  const statClass = passRate >= 80 ? "stat-good" : passRate >= 50 ? "stat-warn" : "stat-bad";
  const statusBadge = `<span class="status-badge status-${run.status}">${run.status}</span>`;

  const summary = `
    <div class="report-summary">
      <div class="report-meta">
        <span><b>Run:</b> ${escapeHtml(run.run_id)}</span>
        <span><b>Mode:</b> ${escapeHtml(run.mode || "dataset")}</span>
        ${run.agent ? `<span><b>Agent:</b> ${escapeHtml(run.agent)}</span>` : ""}
        ${run.dataset_id && run.mode !== "agent" ? `<span><b>Dataset:</b> ${escapeHtml(run.dataset_id)}</span>` : ""}
        <span><b>Status:</b> ${statusBadge}</span>
        ${run.mode === "agent" ? `<span><b>Turns:</b> ${total}${run.max_turns ? " / " + run.max_turns : ""}</span>` : ""}
        ${duration ? `<span><b>Duration:</b> ${duration}</span>` : ""}
      </div>
      <div class="report-stats">
        ${run.mode === "agent"
          ? `<span class="${statClass}">${passed}/${total} turns responded (${passRate}%)</span>`
          : `<span class="${statClass}">${passed}/${total} passed (${passRate}%)`}
        ${avgLatency ? `<span class="stat-info">Avg latency: ${(avgLatency / 1000).toFixed(1)}s</span>` : ""}
        ${passed < total ? `<span class="stat-bad">${total - passed} failed</span>` : ""}
      </div>
      ${run.custom_system_prompt ? `
        <div class="prompt-preview">
          <b>Prompt used:</b> ${escapeHtml(truncate(run.custom_system_prompt, 200))}
        </div>` : ""}
    </div>`;

  // Agent mode → show as chat conversation; dataset mode → table
  let body;
  if (run.mode === "agent") {
    body = renderConversationThread(cases, run.auto_eval);
  } else {
    const rows = cases.map(c => {
      const evalPass = c.evaluation ? c.evaluation.pass : c.status === "completed";
      const icon = c.error ? "⚠️" : evalPass ? "✅" : "❌";
      const latency = c.latency_ms ? (c.latency_ms / 1000).toFixed(1) + "s" : "—";
      const userMsg = escapeHtml(c.user_message || c.case_id || "");
      const botMsgFull = (c.actual && c.actual.bot_message) || c.error || "";
      const botMsg = escapeHtml(botMsgFull);

      let checks = "";
      if (c.evaluation && c.evaluation.checks && c.evaluation.checks.length) {
        checks = c.evaluation.checks.map(ch =>
          `<span class="${ch.pass ? "check-pass" : "check-fail"}">${ch.pass ? "✓" : "✗"} ${escapeHtml(ch.type)}: "${escapeHtml(ch.value)}"</span>`
        ).join("<br>");
      }
      if (c.evaluation && c.evaluation.llm_judge) {
        const j = c.evaluation.llm_judge;
        const jCls = j.pass === true ? "check-pass" : j.pass === false ? "check-fail" : "check-skip";
        checks += `${checks ? "<br>" : ""}<span class="${jCls}">🤖 ${escapeHtml(j.reason || (j.pass ? "pass" : "fail"))}</span>`;
      }

      return `<tr class="${evalPass ? "row-pass" : "row-fail"}">
        <td style="font-size:16px">${icon}</td>
        <td class="cell-id">${escapeHtml(c.case_id || "")}</td>
        <td class="cell-latency">${latency}</td>
        <td class="cell-msg" title="${escapeHtml(userMsg)}">${truncate(userMsg, 55)}</td>
        <td class="cell-msg" title="${escapeHtml(botMsgFull)}">${truncate(botMsg, 80)}</td>
        <td class="cell-checks">${checks || "<span style='color:#9ca3af'>—</span>"}</td>
      </tr>`;
    }).join("");

    body = total > 0 ? `
      <table class="report-table">
        <thead><tr>
          <th></th><th>Case / Turn</th><th>Latency</th><th>Message Sent</th><th>Bot Response</th><th>Checks</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>` : `<p style="color:#6b7280;font-size:13px">No cases yet.</p>`;

    body += renderAutoEval(run.auto_eval);
  }

  container.innerHTML = summary + body;
}

function renderConversationThread(cases, autoEval) {
  if (!cases || cases.length === 0) {
    return `<p style="color:#6b7280;font-size:13px">No turns yet.</p>`;
  }

  // Build a turn-keyed map for auto_eval per-turn lookups
  const evalByTurn = {};
  if (autoEval && autoEval.turns) {
    autoEval.turns.forEach(t => { evalByTurn[t.turn] = t; });
  }

  const turnHtml = cases.map((c, i) => {
    const turn = c.turn || (i + 1);
    const userMsg = c.user_message || c.case_id || "(no message)";
    const botMsgRaw = (c.actual && c.actual.bot_message) || "";
    const isError = !botMsgRaw || c.error;
    const latency = c.latency_ms ? (c.latency_ms / 1000).toFixed(1) + "s" : null;
    const te = evalByTurn[turn];

    const turnEvalHtml = te
      ? `<div class="conv-turn-eval">
          <span class="${te.pass ? "check-pass" : "check-fail"}">${te.pass ? "✓" : "✗"}</span>
          ${escapeHtml(te.reason || "")}
         </div>`
      : "";

    const latencyHtml = latency
      ? `<span class="hint" style="align-self:flex-end;padding-bottom:2px">${latency}</span>`
      : "";

    return `
      <div class="conv-turn">
        <span class="conv-turn-label">Turn ${turn}</span>
        <div class="conv-bubble-row user-row">
          <div class="conv-avatar user-avatar">U</div>
          <div class="conv-bubble user-bubble">${escapeHtml(userMsg)}</div>
        </div>
        <div class="conv-bubble-row">
          <div class="conv-avatar bot-avatar">B</div>
          ${latencyHtml}
          <div class="conv-bubble bot-bubble${isError ? " error-bubble" : ""}">
            ${isError
              ? escapeHtml(c.error || "No response (timeout)")
              : escapeHtml(botMsgRaw)}
          </div>
        </div>
        ${turnEvalHtml}
      </div>
      ${i < cases.length - 1 ? `<hr class="conv-turn-divider" />` : ""}`;
  }).join("");

  const overallEval = autoEval
    ? `<div class="auto-eval-panel">
        <h3>AI Evaluation</h3>
        <div class="auto-eval-verdict ${autoEval.overall_verdict === "pass" ? "verdict-pass" : "verdict-fail"}">
          ${autoEval.overall_verdict === "pass" ? "✅" : "❌"}
          ${escapeHtml(autoEval.overall_reason || "")}
        </div>
      </div>`
    : "";

  return `<div class="conv-thread">${turnHtml}</div>${overallEval}`;
}

function renderAutoEval(autoEval) {
  if (!autoEval) return "";
  const verdict = autoEval.overall_verdict === "pass";
  const turnRows = (autoEval.turns || []).map(t =>
    `<tr>
      <td style="white-space:nowrap">Turn ${t.turn}</td>
      <td><span class="${t.pass ? "check-pass" : "check-fail"}">${t.pass ? "✅ Pass" : "❌ Fail"}</span></td>
      <td style="font-size:12px;color:#4b5563">${escapeHtml(t.reason || "")}</td>
    </tr>`
  ).join("");

  return `
    <div class="auto-eval-panel">
      <h3>AI Evaluation</h3>
      <div class="auto-eval-verdict ${verdict ? "verdict-pass" : "verdict-fail"}">
        ${verdict ? "✅" : "❌"} ${escapeHtml(autoEval.overall_reason || "")}
      </div>
      ${turnRows ? `
        <table class="report-table" style="margin-top:8px">
          <thead><tr><th>Turn</th><th>Result</th><th>Reason</th></tr></thead>
          <tbody>${turnRows}</tbody>
        </table>` : ""}
    </div>`;
}
