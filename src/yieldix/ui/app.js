/**
 * Yieldix Sovereign Cockpit Client-Side Logic.
 * Zero external libraries. Vanilla JavaScript with reactive polling and cryptographic inspector.
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentTasks = [];
  let selectedTaskId = null;
  let isBreakerTripped = false;
  let liveReportCache = null;

  // DOM Elements - Nav
  const navTabs = document.querySelectorAll('.nav-tab');
  const viewPanels = document.querySelectorAll('.view-panel');

  // DOM Elements - Pipeline & Header
  const engineStatusText = document.getElementById('engineStatusText');
  const statusDot = document.getElementById('statusDot');
  const tickerEvlp = document.getElementById('tickerEvlp');
  const tickerSpeedSla = document.getElementById('tickerSpeedSla');
  const tickerDeliverability = document.getElementById('tickerDeliverability');
  const tickerSavings = document.getElementById('tickerSavings');
  const tickerSignerKey = document.getElementById('tickerSignerKey');
  const streamLogContainer = document.getElementById('streamLogContainer');

  // Buttons
  const btnSimulateBatch = document.getElementById('btnSimulateBatch');
  const btnSimulateVoice = document.getElementById('btnSimulateVoice');
  const btnEmergencyTrip = document.getElementById('btnEmergencyTrip');
  const btnRefreshPipeline = document.getElementById('btnRefreshPipeline');

  // L2 Elements
  const draftItemsList = document.getElementById('draftItemsList');
  const l2CountSpan = document.getElementById('l2CountSpan');
  const navBadgeL2 = document.getElementById('navBadgeL2');
  const detailTaskTag = document.getElementById('detailTaskTag');
  const detailTargetCompany = document.getElementById('detailTargetCompany');
  const detailTargetPerson = document.getElementById('detailTargetPerson');
  const detailDigestBadge = document.getElementById('detailDigestBadge');
  const detailHook = document.getElementById('detailHook');
  const editCopyArea = document.getElementById('editCopyArea');
  const detailCta = document.getElementById('detailCta');
  const btnApproveDraft = document.getElementById('btnApproveDraft');
  const btnRejectDraft = document.getElementById('btnRejectDraft');
  const signatureReceipt = document.getElementById('signatureReceipt');
  const recTaskId = document.getElementById('recTaskId');
  const recDigest = document.getElementById('recDigest');
  const recSig = document.getElementById('recSig');

  // KPI Elements
  const kpiSpeedVal = document.getElementById('kpiSpeedVal');
  const kpiDeliverVal = document.getElementById('kpiDeliverVal');
  const kpiConversionVal = document.getElementById('kpiConversionVal');
  const kpiCostVal = document.getElementById('kpiCostVal');
  const breakerStatusLabel = document.getElementById('breakerStatusLabel');

  // Crypto Elements
  const verifyPublicKey = document.getElementById('verifyPublicKey');
  const verifySignature = document.getElementById('verifySignature');
  const verifyReportJson = document.getElementById('verifyReportJson');
  const btnLoadLiveReport = document.getElementById('btnLoadLiveReport');
  const btnRunVerification = document.getElementById('btnRunVerification');
  const verifyResultBox = document.getElementById('verifyResultBox');
  const verifyStatusText = document.getElementById('verifyStatusText');
  const resStateRoot = document.getElementById('resStateRoot');
  const competitorTableBody = document.getElementById('competitorTableBody');

  // Navigation Logic
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetView = tab.getAttribute('data-view');
      navTabs.forEach(t => t.classList.remove('active'));
      viewPanels.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const activePanel = document.getElementById(targetView);
      if (activePanel) activePanel.classList.add('active');
    });
  });

  // Log Helper
  function appendLog(message, level = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry log-${level}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;
    streamLogContainer.appendChild(entry);
    streamLogContainer.scrollTop = streamLogContainer.scrollHeight;
  }

  // Fetch Health
  async function fetchHealth() {
    try {
      const res = await fetch('/api/health');
      if (!res.ok) return;
      const data = await res.json();
      engineStatusText.textContent = data.status;
      if (data.status === 'HEALTHY') {
        statusDot.style.background = '#10b981';
        statusDot.style.boxShadow = '0 0 8px #10b981';
      } else {
        statusDot.style.background = '#f43f5e';
        statusDot.style.boxShadow = '0 0 8px #f43f5e';
      }
      if (data.public_key) {
        tickerSignerKey.textContent = `Ed25519: ${data.public_key.substring(0, 8)}...${data.public_key.substring(data.public_key.length - 8)}`;
      }
    } catch (err) {
      console.error('Health fetch failed:', err);
    }
  }

  // Fetch Telemetry
  async function fetchTelemetry() {
    try {
      const res = await fetch('/api/telemetry');
      if (!res.ok) return;
      const data = await res.json();
      
      // Update KPIs
      if (data.kpis) {
        tickerSpeedSla.textContent = `${data.kpis.speed_to_lead_compliance_pct}% (<60s)`;
        tickerDeliverability.textContent = `${data.kpis.deliverability_rate_pct}%`;
        kpiSpeedVal.textContent = `${data.kpis.avg_speed_to_lead_seconds}s`;
        kpiDeliverVal.textContent = `${data.kpis.deliverability_rate_pct}%`;
        kpiConversionVal.textContent = `${data.kpis.bant_conversion_rate_pct}%`;
        kpiCostVal.textContent = `$${data.kpis.cost_per_qualified_meeting_usd.toFixed(2)}`;
      }

      // Update Financials
      if (data.financial_metrics) {
        tickerEvlp.textContent = `$${data.financial_metrics.total_pipeline_evlp_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        tickerSavings.textContent = `+$${data.financial_metrics.net_revops_savings_usd.toLocaleString('en-US', { minimumFractionDigits: 0 })} / mo`;
      }

      // Update Cylinders
      if (data.cylinders) {
        const c2Queue = document.getElementById('c2QueueLen');
        if (c2Queue) c2Queue.textContent = data.cylinders.c2_speed_to_lead.queue_length;
        const c5Sent = document.getElementById('c5Sent');
        if (c5Sent) c5Sent.textContent = `${data.cylinders.c5_cold_email_l2.dispatched_today} / ${data.cylinders.c5_cold_email_l2.daily_quota}`;
        const c5Pending = document.getElementById('c5Pending');
        if (c5Pending) c5Pending.textContent = data.cylinders.c5_cold_email_l2.pending_review;
      }
    } catch (err) {
      console.error('Telemetry fetch failed:', err);
    }
  }

  // Fetch L2 Queue
  async function fetchL2Queue() {
    try {
      const res = await fetch('/api/l2-queue');
      if (!res.ok) return;
      const data = await res.json();
      currentTasks = data.pending_tasks || [];
      l2CountSpan.textContent = currentTasks.length;
      navBadgeL2.textContent = currentTasks.length;

      renderDraftsList();
    } catch (err) {
      console.error('L2 fetch failed:', err);
    }
  }

  // Render Drafts
  function renderDraftsList() {
    draftItemsList.innerHTML = '';
    if (currentTasks.length === 0) {
      draftItemsList.innerHTML = '<div class="mono text-muted" style="padding:1rem; text-align:center;">All outreach drafts approved or dispatched. Queue empty.</div>';
      clearInspector();
      return;
    }

    currentTasks.forEach((task, idx) => {
      const item = document.createElement('div');
      item.className = `draft-item ${task.task_id === selectedTaskId ? 'selected' : ''}`;
      item.innerHTML = `
        <div class="draft-item-top">
          <span class="draft-item-company">${escapeHtml(task.target_company)}</span>
          <span class="pane-tag">${task.task_id.substring(0, 10)}...</span>
        </div>
        <div class="draft-item-person">${escapeHtml(task.target_person)}</div>
      `;
      item.addEventListener('click', () => selectTask(task.task_id));
      draftItemsList.appendChild(item);
    });

    if (!selectedTaskId && currentTasks.length > 0) {
      selectTask(currentTasks[0].task_id);
    }
  }

  function selectTask(taskId) {
    selectedTaskId = taskId;
    const task = currentTasks.find(t => t.task_id === taskId);
    if (!task) return;

    // Update selection styling
    document.querySelectorAll('.draft-item').forEach(el => el.classList.remove('selected'));
    const allItems = draftItemsList.children;
    const idx = currentTasks.findIndex(t => t.task_id === taskId);
    if (allItems[idx]) allItems[idx].classList.add('selected');

    // Populate inspector
    detailTaskTag.textContent = task.task_id;
    detailTargetCompany.textContent = task.target_company;
    detailTargetPerson.textContent = `${task.target_person} (${task.target_email})`;
    detailDigestBadge.textContent = `SHA-256: ${task.content_hash.substring(0, 16)}...`;
    detailHook.textContent = task.personalized_hook;
    editCopyArea.value = task.body_text;
    detailCta.textContent = task.call_to_action;
    signatureReceipt.style.display = 'none';
  }

  function clearInspector() {
    detailTaskTag.textContent = 'NO ACTIVE TASK';
    detailTargetCompany.textContent = 'All Drafts Processed';
    detailTargetPerson.textContent = 'N/A';
    detailDigestBadge.textContent = 'SHA-256: NONE';
    detailHook.textContent = 'No pending triggers.';
    editCopyArea.value = '';
    detailCta.textContent = 'No active CTA.';
  }

  // Approve Draft
  btnApproveDraft.addEventListener('click', async () => {
    if (!selectedTaskId) return;
    try {
      const res = await fetch('/api/l2-approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: selectedTaskId,
          reviewer: 'SDR_Commander_Alpha',
          modified_body: editCopyArea.value
        })
      });
      if (!res.ok) throw new Error('Approval request failed');
      const data = await res.json();

      recTaskId.textContent = data.task_id;
      recDigest.textContent = data.hash;
      recSig.textContent = `${data.ed25519_signature.substring(0, 32)}...`;
      signatureReceipt.style.display = 'block';

      appendLog(`L2 APPROVAL: Task ${data.task_id} signed & queued. Hash: ${data.hash.substring(0, 12)}...`, 'success');

      selectedTaskId = null;
      await fetchL2Queue();
      await fetchTelemetry();
    } catch (err) {
      alert(`Approval error: ${err.message}`);
    }
  });

  // Reject Draft
  btnRejectDraft.addEventListener('click', async () => {
    if (!selectedTaskId) return;
    if (!confirm('Are you sure you want to reject this draft?')) return;
    try {
      const res = await fetch('/api/l2-reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: selectedTaskId,
          reviewer: 'SDR_Commander_Alpha',
          reason: 'Manual rejection by operator'
        })
      });
      if (!res.ok) throw new Error('Rejection request failed');
      appendLog(`L2 REJECT: Task ${selectedTaskId} rejected by operator.`, 'warning');
      selectedTaskId = null;
      await fetchL2Queue();
    } catch (err) {
      alert(`Rejection error: ${err.message}`);
    }
  });

  // Simulate Batch Leads
  btnSimulateBatch.addEventListener('click', async () => {
    appendLog('SIMULATION: Ingesting 5 incoming B2B leads across Cylinder 2 & 3...', 'info');
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leads: 5, source: 'WEB_INBOUND', company: 'Alpha Quantum Tech' })
      });
      const data = await res.json();
      appendLog(`SIMULATION COMPLETE: ${data.processed_count} leads qualified under 60s SLA.`, 'success');
      await fetchTelemetry();
    } catch (err) {
      appendLog(`Simulation failed: ${err.message}`, 'danger');
    }
  });

  // Simulate Voice Lead
  btnSimulateVoice.addEventListener('click', async () => {
    appendLog('C1 VOICE: Inbound phone call received (+90 532 111 22 33). Opus 20ms stream connecting...', 'info');
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leads: 1, source: 'INBOUND_VOICE', company: 'Sovereign Telemetry AS' })
      });
      const data = await res.json();
      appendLog('C1 VOICE: BANT qualification complete (380ms response). Lead routed to AE calendar.', 'success');
      await fetchTelemetry();
    } catch (err) {
      appendLog(`Voice simulation failed: ${err.message}`, 'danger');
    }
  });

  // Emergency Trip / Reset Circuit Breaker
  btnEmergencyTrip.addEventListener('click', async () => {
    const action = isBreakerTripped ? 'RESET' : 'TRIP';
    try {
      const res = await fetch('/api/circuit-breaker/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ component: 'C5_COLD_EMAIL', action: action })
      });
      const data = await res.json();
      isBreakerTripped = !isBreakerTripped;

      const c5Badge = document.getElementById('c5StatusBadge');
      if (isBreakerTripped) {
        btnEmergencyTrip.textContent = '🔄 Reset Breaker';
        btnEmergencyTrip.className = 'btn-action btn-emerald';
        if (c5Badge) {
          c5Badge.className = 'status-badge badge-tripped';
          c5Badge.textContent = 'SHED (TRIPPED)';
        }
        breakerStatusLabel.textContent = 'C5_COLD_EMAIL PRUNED (DELIVERABILITY GUARD)';
        breakerStatusLabel.className = 'mono text-rose';
        appendLog('CIRCUIT BREAKER: C5_COLD_EMAIL tripped & dynamically shed.', 'danger');
      } else {
        btnEmergencyTrip.textContent = '🛡️ Trip Breaker';
        btnEmergencyTrip.className = 'btn-action btn-rose';
        if (c5Badge) {
          c5Badge.className = 'status-badge badge-active';
          c5Badge.textContent = 'ACTIVE';
        }
        breakerStatusLabel.textContent = 'ALL CYLINDERS NORMAL';
        breakerStatusLabel.className = 'mono text-emerald';
        appendLog('CIRCUIT BREAKER: C5_COLD_EMAIL restored to active execution.', 'success');
      }
      await fetchHealth();
    } catch (err) {
      alert(`Circuit breaker toggle error: ${err.message}`);
    }
  });

  // Refresh Telemetry
  btnRefreshPipeline.addEventListener('click', async () => {
    await fetchTelemetry();
    await fetchHealth();
    appendLog('TELEMETRY: Real-time pipeline state refreshed.', 'info');
  });

  // Competitor Matrix
  async function fetchCompetitors() {
    try {
      const res = await fetch('/api/competitors');
      if (!res.ok) return;
      const data = await res.json();
      competitorTableBody.innerHTML = '';
      data.competitors.forEach(c => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td><strong>${escapeHtml(c.name)}</strong></td>
          <td>${escapeHtml(c.channels)}</td>
          <td>${escapeHtml(c.speed_to_lead)}</td>
          <td>${escapeHtml(c.deliverability_guard)}</td>
          <td>${escapeHtml(c.pricing_model)}</td>
          <td><span class="mini-tag">${escapeHtml(c.sla_guarantee)}</span></td>
        `;
        competitorTableBody.appendChild(row);
      });
    } catch (err) {
      console.error('Competitor fetch failed:', err);
    }
  }

  // Crypto SLA Verifier
  btnLoadLiveReport.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/sample-report');
      if (!res.ok) throw new Error('Failed to fetch sample report');
      const data = await res.json();
      liveReportCache = data;

      verifyPublicKey.value = data.public_key_hex;
      verifySignature.value = data.signature_hex;
      verifyReportJson.value = JSON.stringify(data.report_data, null, 2);
      appendLog('CRYPTO: Loaded live Ed25519 signed monthly report payload into verifier.', 'info');
    } catch (err) {
      alert(err.message);
    }
  });

  btnRunVerification.addEventListener('click', async () => {
    try {
      const sig = verifySignature.value.trim();
      const pubKey = verifyPublicKey.value.trim();
      const reportJsonStr = verifyReportJson.value.trim();

      if (!sig || !reportJsonStr) {
        alert('Please provide signature and report data JSON.');
        return;
      }

      const reportData = JSON.parse(reportJsonStr);
      const res = await fetch('/api/verify-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          signature_hex: sig,
          public_key_hex: pubKey,
          report_data: reportData
        })
      });
      const data = await res.json();

      verifyResultBox.style.display = 'block';
      if (data.valid) {
        verifyStatusText.textContent = '✅ SIGNATURE VALID (RFC 8032 Ed25519 Attested)';
        verifyStatusText.className = 'result-status text-emerald';
      } else {
        verifyStatusText.textContent = '❌ SIGNATURE INVALID / FORGERY DETECTED';
        verifyStatusText.className = 'result-status text-rose';
      }
      resStateRoot.textContent = data.state_root_sha256;
      appendLog(`CRYPTO AUDIT: Report verified. Valid: ${data.valid}. State Root: ${data.state_root_sha256.substring(0, 16)}...`, data.valid ? 'success' : 'danger');
    } catch (err) {
      alert(`Verification parse error: ${err.message}`);
    }
  });

  // Global Keyboard Shortcuts (Anti-Slop Senior Operator Flow)
  document.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      return;
    }
    
    if (e.key === '1') {
      document.querySelector('[data-view="view-pipeline"]')?.click();
    } else if (e.key === '2') {
      document.querySelector('[data-view="view-l2-studio"]')?.click();
    } else if (e.key === '3') {
      document.querySelector('[data-view="view-kpi-health"]')?.click();
    } else if (e.key === '4') {
      document.querySelector('[data-view="view-crypto-benchmark"]')?.click();
    } else if (e.key === 'a' || e.key === 'A') {
      const l2View = document.getElementById('view-l2-studio');
      if (l2View && l2View.classList.contains('active')) {
        btnApproveDraft.click();
      }
    } else if (e.key === 'r' || e.key === 'R') {
      const l2View = document.getElementById('view-l2-studio');
      if (l2View && l2View.classList.contains('active')) {
        btnRejectDraft.click();
      }
    }
  });

  // Sinusoidal Waveform Audio Spectrum Visualizer
  const voiceCanvas = document.getElementById('voiceCanvas');
  let audioSurge = 1.0;
  if (voiceCanvas) {
    const ctx = voiceCanvas.getContext('2d');
    let phase = 0;

    function renderAudioSpectrum() {
      if (!voiceCanvas) return;
      const width = voiceCanvas.width;
      const height = voiceCanvas.height;
      ctx.clearRect(0, 0, width, height);

      const grad = ctx.createLinearGradient(0, 0, width, 0);
      grad.addColorStop(0, '#06b6d4');
      grad.addColorStop(0.5, '#10b981');
      grad.addColorStop(1, '#06b6d4');

      ctx.lineWidth = 2;
      ctx.strokeStyle = grad;
      ctx.beginPath();

      const midY = height / 2;
      const freq = 0.04;
      const amp = (height * 0.32) * audioSurge;

      for (let x = 0; x < width; x++) {
        const y = midY + Math.sin(x * freq + phase) * Math.cos(x * 0.01 + phase * 0.5) * amp;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.35)';
      ctx.beginPath();
      for (let x = 0; x < width; x++) {
        const y = midY + Math.cos(x * freq * 1.5 - phase * 1.2) * (amp * 0.6);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      phase += 0.08 * audioSurge;
      if (audioSurge > 1.0) {
        audioSurge = Math.max(1.0, audioSurge - 0.03);
      }

      requestAnimationFrame(renderAudioSpectrum);
    }
    requestAnimationFrame(renderAudioSpectrum);
  }

  // Trigger surge on voice simulate button
  if (btnSimulateVoice) {
    btnSimulateVoice.addEventListener('click', () => {
      audioSurge = 2.4;
    });
  }

  // Copy to Clipboard Helpers
  function copyTextToClipboard(text, btnElement, successLabel) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      const originalText = btnElement.textContent;
      btnElement.textContent = `✅ ${successLabel}`;
      btnElement.classList.add('btn-copied');
      setTimeout(() => {
        btnElement.textContent = originalText;
        btnElement.classList.remove('btn-copied');
      }, 1800);
    });
  }

  const btnCopySignatureReceipt = document.getElementById('btnCopySignatureReceipt');
  if (btnCopySignatureReceipt) {
    btnCopySignatureReceipt.addEventListener('click', () => {
      const payload = {
        taskId: recTaskId.textContent,
        digestSha256: recDigest.textContent,
        signatureEd25519: recSig.textContent,
        standard: 'RFC 8032 & W3C VC v2.0',
        timestamp: new Date().toISOString()
      };
      copyTextToClipboard(JSON.stringify(payload, null, 2), btnCopySignatureReceipt, 'Receipt Copied!');
    });
  }

  const btnCopyVerifyCert = document.getElementById('btnCopyVerifyCert');
  if (btnCopyVerifyCert) {
    btnCopyVerifyCert.addEventListener('click', () => {
      const cert = {
        status: verifyStatusText.textContent,
        stateRootSha256: resStateRoot.textContent,
        attestationSchema: '0x7996c141703e352efdf1846b416bb5a5b5db7cf19b9195d3fa96f131a1cc0d09',
        smartContract: '0x71C8A18174415cC92067749eb3544DFFD3F87884',
        verifiedAt: new Date().toISOString()
      };
      copyTextToClipboard(JSON.stringify(cert, null, 2), btnCopyVerifyCert, 'Certificate Copied!');
    });
  }

  // Utility
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Periodic Refresh
  fetchHealth();
  fetchTelemetry();
  fetchL2Queue();
  fetchCompetitors();

  setInterval(() => {
    fetchHealth();
    fetchTelemetry();
  }, 4000);
});
