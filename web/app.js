"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const view = params.get("view") === "dashboard" ? "dashboard" : "phone";
  const isPhone = view === "phone";
  const deviceName = (id) => id === "edge1" ? "HP A" : "HP B";
  const validBroker = (value) => {
    try {
      const url = new URL(value);
      return url.protocol === "wss:" || (url.protocol === "ws:" && ["localhost","127.0.0.1"].includes(url.hostname));
    } catch { return false; }
  };
  const id = () => crypto.randomUUID().replaceAll("-", "");
  const escape = (text) => String(text).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const labels = { OFFLINE:"Offline", MONITORING:"Memantau", OBSERVING:"Observasi", PAUSED:"Dijeda", CHECK_BUDDY:"Perlu dicek", AWAITING_REPLY:"Menunggu", SAFE:"Aman", NEED_HELP:"Perlu bantuan", NO_RESPONSE:"Belum dijawab", CLOSED:"Selesai" };
  const eventLabels = {CHECK_BUDDY:"CHECK YOUR BUDDY", AWAITING_REPLY:"ARE YOU OK?", SAFE:"I'M SAFE", NEED_HELP:"NEED HELP", NO_RESPONSE:"NO RESPONSE", CLOSED:"Pengecekan selesai"};
  const actionLabels = {REQUEST_STATUS:"REQUEST STATUS ↗", SAFE:"I'M SAFE ✓", NEED_HELP:"NEED HELP", ACKNOWLEDGE:"Sudah ditindaklanjuti"};
  let client = null, connected = false, starting = false, active = false;
  let actor = "dashboard", project = "", bootId = "", sequence = 0, sent = 0;
  let state = null, lastState = 0, serverOffset = 0, eventSignature = "";
  let samples = [], lastSample = 0, lastAcceptedSample = 0, sensorStartedAt = 0;
  let accelCount = 0, gyroCount = 0, motionCount = 0, wakeLock = null, audio = null;
  const pending = new Map(), notices = new Map(), history = {edge1:[],edge2:[]};
  const emptyEvents = $("events").innerHTML;
  let lastSequences = {}, logLines = [];

  document.body.classList.add(view);
  $(isPhone ? "phoneLink" : "dashboardLink").classList.add("active");
  $("roleLabel").hidden = !isPhone;
  $("sensorPanel").hidden = !isPhone;
  if (!isPhone) {
    $("startButton").innerHTML = 'Hubungkan dashboard <span>↗</span>';
    $("sensorHint").textContent = "Dashboard memantau kedua HP. Jalankan detector Python di laptop, lalu hubungkan ke ID kelompok yang sama.";
  }
  if (params.get("role") === "edge2") $("role").value = "edge2";
  if (/^[A-Za-z0-9_-]{1,80}$/.test(params.get("project") || "")) $("project").value = params.get("project");
  if (validBroker(params.get("broker"))) $("broker").value = params.get("broker");
  ["edge1", "edge2"].forEach((device) => {
    const node = document.createElement("article");
    node.className = "device-card";
    node.innerHTML = `<div class="device-top"><div class="device-name"><span class="device-avatar">${device === "edge1" ? "A" : "B"}</span><div><h3>${deviceName(device)}</h3><p>${device === "edge1" ? "Pengguna pertama" : "Pengguna kedua"}</p></div></div><span id="${device}-status" class="status-label">Offline</span></div><div class="device-numbers"><div><span class="metric-label">RMS GERAKAN</span><span id="${device}-rms" class="metric-value">—</span><span class="metric-unit">m/s²</span></div><div><span class="metric-label">TOTAL ROTASI</span><span id="${device}-rotation" class="metric-value">—</span><span class="metric-unit">rad</span></div></div><svg class="sparkline" viewBox="0 0 260 45" preserveAspectRatio="none" aria-label="Riwayat intensitas gerakan"><polyline id="${device}-chart" points=""></polyline></svg><div class="device-foot"><span id="${device}-source">Belum ada sensor</span><span id="${device}-peak">Peak —</span></div>`;
    $("devices").append(node);
  });

  function log(message) {
    logLines.unshift(`${new Date().toLocaleTimeString("id-ID")} · ${message}`);
    logLines = logLines.slice(0, 60);
    $("log").replaceChildren(...logLines.map((line) => {
      const node = document.createElement("li"); node.textContent = line; return node;
    }));
  }
  function notice(message, good = false) {
    $("notice").hidden = !message;
    $("notice").textContent = message;
    $("notice").classList.toggle("good", good);
  }
  function liveService() {
    return connected && state?.service === "ONLINE" && performance.now() - lastState < 5000;
  }
  function tone() {
    if (navigator.vibrate) navigator.vibrate([180, 80, 180]);
    if (!audio || audio.state !== "running") return;
    const oscillator = audio.createOscillator(), gain = audio.createGain();
    oscillator.frequency.value = 660;
    gain.gain.setValueAtTime(0.08, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.35);
    oscillator.connect(gain); gain.connect(audio.destination);
    oscillator.start(); oscillator.stop(audio.currentTime + 0.35);
  }
  function rememberLinks() {
    ["phone", "dashboard"].forEach((mode) => {
      const query = new URLSearchParams({view:mode,project:$("project").value,broker:$("broker").value});
      $(mode === "phone" ? "phoneLink" : "dashboardLink").href = "?" + query;
    });
  }
  function lockSetup(lock) {
    document.body.classList.toggle("session-active",lock);
    $("setupForm").querySelectorAll("input,select").forEach((input) => input.disabled = lock);
    $("startButton").hidden = lock;
    $("stopButton").hidden = !lock;
    document.querySelector(".setup-panel").classList.toggle("connected", lock);
  }

  async function start(event) {
    event?.preventDefault();
    if (active || starting) return;
    if (!$("setupForm").reportValidity()) return;
    const broker = $("broker").value.trim();
    // ws:// is accepted exclusively for a loopback development broker.
    if (!validBroker(broker)) { notice("Gunakan MQTT WebSocket TLS dengan alamat wss://."); return; }
    if (typeof mqtt === "undefined") { notice("MQTT.js belum tersedia. Periksa folder web/vendor."); return; }
    if (isPhone && (!window.isSecureContext || typeof DeviceMotionEvent === "undefined")) {
      notice("Sensor memerlukan browser HP yang mendukung DeviceMotion dan halaman HTTPS. HTTP IP laptop hanya untuk dashboard."); return;
    }
    starting = true;
    $("startButton").disabled = true;
    try {
      // Permission must be requested directly from the user's click, before unrelated awaits.
      if (isPhone && typeof DeviceMotionEvent.requestPermission === "function") {
        if (await DeviceMotionEvent.requestPermission() !== "granted") throw new Error("Izin sensor gerak ditolak.");
      }
      actor = isPhone ? $("role").value : "dashboard";
      project = $("project").value.trim();
      bootId = id(); sequence = 0; sent = 0; accelCount = gyroCount = motionCount = 0;
      samples = []; lastSample = lastAcceptedSample = 0;
      state = null; lastState = 0; eventSignature = "";
      notices.clear(); history.edge1 = []; history.edge2 = []; lastSequences = {};
      active = true; sensorStartedAt = performance.now();
      notice(""); lockSetup(true); rememberLinks();
      try {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (Audio && isPhone) { audio = new Audio(); audio.resume().catch(() => {}); }
      } catch { /* Visual alerts remain available. */ }
      if (isPhone) {
        window.addEventListener("devicemotion", onMotion);
        if (navigator.wakeLock) navigator.wakeLock.request("screen").then((lock) => wakeLock = lock).catch(() => {});
        $("heroDescription").textContent = `${deviceName(actor)} siap saling menjaga. Selamat melangkah!`;
        $("sessionLabel").textContent = `${deviceName(actor)} / LIVE CHECK-IN`;
      }
      client = mqtt.connect(broker, {
        clientId:`bc-${actor}-${id().slice(0,12)}`, protocolVersion:4,
        username:$("username").value || undefined, password:$("password").value || undefined,
        reconnectPeriod:2500, connectTimeout:10000, clean:true, queueQoSZero:false,
      });
      client.on("connect", () => {
        connected = true;
        client.subscribe([`buddycheck/${project}/state`,`buddycheck/${project}/receipts/${actor}`], {qos:1}, (error) => {
          if (error) notice("Gagal subscribe: " + error.message);
        });
        samples = []; lastSample = lastAcceptedSample = 0;
        notice(""); log(`MQTT tersambung · ${actor === "dashboard" ? "Dashboard" : deviceName(actor)} · ${project}`);
        refresh();
      });
      client.on("offline", () => { connected = false; refresh(); log("MQTT terputus. Mencoba menyambung kembali."); });
      client.on("close", () => { connected = false; refresh(); });
      client.on("error", (error) => { notice("Koneksi MQTT: " + error.message); log("MQTT: " + error.message); });
      client.on("message", receive);
      refresh();
    } catch (error) { stop(); notice(error.message); }
    finally { starting = false; $("startButton").disabled = false; }
  }

  function stop() {
    active = connected = false;
    window.removeEventListener("devicemotion", onMotion);
    samples = []; lastSample = 0;
    if (client) { client.end(true); client = null; }
    if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
    if (audio) { audio.close().catch(() => {}); audio = null; }
    pending.forEach((entry) => clearTimeout(entry.timer)); pending.clear();
    lockSetup(false); eventSignature = "";
    refresh(); log("Koneksi dihentikan.");
  }

  function onMotion(event) {
    if (!active || document.hidden) return;
    motionCount++;
    const a = event.accelerationIncludingGravity, r = event.rotationRate;
    const valid = (array) => array.every((value) => typeof value === "number" && Number.isFinite(value));
    const hasA = a && valid([a.x,a.y,a.z]), hasR = r && valid([r.alpha,r.beta,r.gamma]);
    if (hasA) accelCount++;
    if (hasR) gyroCount++;
    if (!hasA || !hasR) return;
    const now = performance.now();
    if (now - lastAcceptedSample < 45) return;
    if (lastAcceptedSample && now - lastAcceptedSample > 500) samples = [];
    lastSample = lastAcceptedSample = now;
    samples.push({time:now,accel:[a.x,a.y,a.z],gyro:[r.alpha,r.beta,r.gamma].map((value) => value * Math.PI / 180)});
    if (samples.length > 60) samples.shift();
    if (samples.length < 4 || now - samples[0].time < 1000) return;
    const features = BuddyCore.features(samples);
    samples = [];
    if (!connected || features.window_ms > 3000) return;
    const payload = {device_id:actor,boot_id:bootId,sequence:sequence++,sent_at_ms:Date.now(),source:"physical",...features};
    client.publish(`buddycheck/${project}/edge/${actor}/telemetry`, JSON.stringify(payload), {qos:1,retain:false}, (error) => {
      if (error) log("Pengiriman sensor gagal: " + error.message);
      else sent++;
    });
  }

  function receive(topic, bytes) {
    let payload;
    try { payload = JSON.parse(bytes.toString()); } catch { return; }
    if (!payload || typeof payload !== "object") return;
    if (topic.endsWith(`/receipts/${actor}`)) {
      const entry = pending.get(payload.command_id);
      if (!entry) return;
      clearTimeout(entry.timer); pending.delete(payload.command_id);
      notice(payload.ok ? "Perintah diterima detector." : `Perintah ditolak: ${payload.reason || "Periksa status kejadian."}`, !!payload.ok);
      eventSignature = ""; renderEvents(); return;
    }
    if (topic !== `buddycheck/${project}/state`) return;
    if (payload.service === "OFFLINE") {
      state = {...state,service:"OFFLINE"};
      eventSignature = ""; log("Detector berhenti atau terputus."); refresh(); return;
    }
    if (payload.service !== "ONLINE" || !Number.isFinite(payload.at_ms) || !payload.devices || !Array.isArray(payload.events)) return;
    if (Math.abs(Date.now() - payload.at_ms) > 15000) { notice("State detector kedaluwarsa atau jam perangkat berbeda. Jalankan detector dan sinkronkan jam laptop/HP."); return; }
    if (state?.session_id && state.session_id !== payload.session_id) {
      notices.clear(); log("Detector memulai sesi baru; riwayat sebelumnya berakhir.");
    }
    state = payload; lastState = performance.now(); serverOffset = payload.at_ms - Date.now();
    ["edge1","edge2"].forEach((device) => {
      const reading = payload.devices[device]?.telemetry;
      if (!reading || !Number.isFinite(reading.motion_rms)) return;
      const key = `${reading.boot_id}-${reading.sequence}`;
      if (key !== lastSequences[device]) {
        lastSequences[device] = key;
        history[device].push(reading.motion_rms); history[device] = history[device].slice(-35);
      }
    });
    for (const event of payload.events.slice(-50)) {
      if (!event || !event.event_id || !eventLabels[event.status]) continue;
      const previous = notices.get(event.event_id);
      if (previous !== event.status) {
        notices.set(event.event_id,event.status);
        const relevant = isPhone && (
          (event.buddy === actor && ["CHECK_BUDDY","SAFE","NEED_HELP","NO_RESPONSE"].includes(event.status)) ||
          (event.subject === actor && event.status === "AWAITING_REPLY")
        );
        if (relevant) { tone(); log(`${eventLabels[event.status]} · ${deviceName(event.subject)}`); }
      }
    }
    refresh();
  }

  function refresh() {
    const live = liveService();
    $("connectionBadge").classList.toggle("online", connected);
    $("connectionBadge").innerHTML = `<i></i>${connected ? "MQTT terhubung" : active ? "Menghubungkan…" : "Belum terhubung"}`;
    $("detectorStatus").innerHTML = `<i class="status-dot ${live ? "online" : ""}"></i>${live ? (state.armed ? "Detector aktif" : "Deteksi dijeda · konfirmasi tetap aktif") : connected ? "Detector offline / belum menerima heartbeat" : "Detector belum terhubung"}`;
    $("updateTime").textContent = live ? `Diperbarui ${new Date(state.at_ms).toLocaleTimeString("id-ID")}` : "Menunggu data terbaru";
    const onlineCount = live ? Object.values(state.devices).filter((device) => device.online).length : 0;
    $("pairCaption").textContent = `${onlineCount}/2 perangkat aktif`;
    $("pairDot").classList.toggle("online",onlineCount === 2);
    $("monitorButton").disabled = !live || pending.size > 0;
    $("monitorButton").textContent = state?.armed === false ? "Lanjutkan deteksi" : "Jeda deteksi";
    if (live && state.config) $("thresholdInfo").textContent = `Peak ≥ ${state.config.impact_peak} m/s² · Diam ${state.config.still_seconds} detik`;
    ["edge1","edge2"].forEach((device) => {
      const data = state?.devices?.[device], reading = data?.telemetry;
      const status = live ? data?.status || "OFFLINE" : "OFFLINE";
      const tag = $(`${device}-status`);
      tag.textContent = labels[status] || status;
      tag.className = `status-label ${["MONITORING","SAFE"].includes(status) ? "good" : ["NEED_HELP","NO_RESPONSE"].includes(status) ? "danger" : ["OBSERVING","CHECK_BUDDY","AWAITING_REPLY"].includes(status) ? "warning" : ""}`;
      $(`${device}-rms`).textContent = Number.isFinite(reading?.motion_rms) ? reading.motion_rms.toFixed(2) : "—";
      $(`${device}-rotation`).textContent = Number.isFinite(reading?.rotation_rad) ? reading.rotation_rad.toFixed(2) : "—";
      $(`${device}-peak`).textContent = Number.isFinite(reading?.accel_peak) ? `Peak ${reading.accel_peak.toFixed(1)} m/s²` : "Peak —";
      $(`${device}-source`).textContent = reading ? `${reading.source === "physical" ? "Sensor fisik" : "SIMULASI"}${status === "OFFLINE" ? " · data terakhir" : ` · ${reading.sample_count} sampel`}` : "Belum ada sensor";
      const values = history[device], max = Math.max(2,...values);
      $(`${device}-chart`).setAttribute("points",values.map((value,index) => `${index * 260 / 34},${42 - value / max * 36}`).join(" "));
    });
    if (isPhone) {
      $("accelCount").textContent = `${accelCount} sampel`;
      $("gyroCount").textContent = `${gyroCount} sampel`;
      $("sentCount").textContent = `${sent} pesan`;
      let sensorMessage = "Sensor belum dimulai.";
      if (active) {
        sensorMessage = "Menunggu pembacaan accelerometer & gyroscope…";
        if (document.hidden) sensorMessage = "Tab tidak aktif; pembacaan sensor dijeda. Buka kembali tab ini.";
        else if (performance.now() - sensorStartedAt > 4000) {
          if (!motionCount) sensorMessage = "Tidak ada event sensor. Cek izin sensor gerak, HTTPS, dan dukungan HP.";
          else if (!accelCount) sensorMessage = "Accelerometer tidak tersedia atau belum diberi izin.";
          else if (!gyroCount) sensorMessage = "Gyroscope tidak tersedia. Cek spesifikasi HP atau gunakan Termux:API.";
          else if (!lastSample || performance.now() - lastSample > 3000) sensorMessage = "Pembacaan sensor berhenti. Pastikan layar dan tab tetap aktif.";
          else sensorMessage = connected ? "Dua sensor aktif · mengirim tiap ±1 detik." : "Sensor aktif · menunggu koneksi MQTT.";
        }
      }
      $("sensorStatus").textContent = sensorMessage;
    }
    renderEvents();
  }

  function renderEvents() {
    const events = (state?.events || []).filter((event) => event && eventLabels[event.status]).slice(-50).reverse();
    const live = liveService();
    const signature = JSON.stringify([events,live,pending.size,actor]);
    if (signature === eventSignature) return;
    eventSignature = signature;
    $("eventCount").textContent = `${events.length} kejadian`;
    if (!events.length) { $("events").innerHTML = emptyEvents; return; }
    $("events").replaceChildren(...events.map((event) => {
      const card = document.createElement("article");
      const severity = ["NEED_HELP","NO_RESPONSE"].includes(event.status) ? "danger" : ["CHECK_BUDDY","AWAITING_REPLY"].includes(event.status) ? "warning" : "";
      card.className = `event-card ${severity}`;
      let explanation = `${deviceName(event.subject)} perlu dicek oleh ${deviceName(event.buddy)}.`;
      if (event.status === "AWAITING_REPLY") explanation = event.subject === actor ? "Temanmu meminta kabar. Bagaimana kondisimu sekarang?" : `Permintaan terkirim ke ${deviceName(event.subject)}. Menunggu jawaban pengguna.`;
      if (event.status === "SAFE") explanation = `${deviceName(event.subject)} sudah mengonfirmasi bahwa dirinya aman.`;
      if (event.status === "NEED_HELP") explanation = `${deviceName(event.subject)} meminta bantuan. Hubungi atau periksa langsung kondisi temanmu.`;
      if (event.status === "NO_RESPONSE") explanation = "Belum ada konfirmasi sampai batas waktu. Periksa koneksi dan hubungi temanmu; kondisi belum diketahui.";
      if (event.status === "CLOSED") explanation = "Teman sudah menandai kejadian ini sebagai ditindaklanjuti.";
      card.innerHTML = `<div class="event-top"><h3>${escape(eventLabels[event.status])}</h3><span class="event-time">${escape(deviceName(event.subject))} · ${escape(new Date(event.created_at_ms).toLocaleTimeString("id-ID"))}</span></div><p>${escape(explanation)}</p><span class="event-source">${event.source === "physical" ? "SENSOR FISIK" : "SIMULASI"} · ${escape(event.event_id.slice(0,8))}</span>${event.expires_at_ms ? `<p class="event-countdown" data-expires="${Number(event.expires_at_ms)}"></p>` : ""}`;
      const actions = BuddyCore.actions(event,actor);
      if (isPhone && actions.length) {
        const buttons = document.createElement("div"); buttons.className = "event-actions";
        actions.forEach((action) => {
          const button = document.createElement("button");
          button.type = "button"; button.className = `button ${action === "SAFE" ? "safe" : action === "NEED_HELP" ? "danger" : "primary"}`;
          button.textContent = actionLabels[action]; button.disabled = !live || pending.size > 0;
          button.addEventListener("click",() => send(action,event.event_id)); buttons.append(button);
        });
        card.append(buttons);
      } else if (!isPhone && ["CHECK_BUDDY","AWAITING_REPLY"].includes(event.status)) {
        const hint = document.createElement("p"); hint.textContent = "Konfirmasi dilakukan oleh pengguna melalui halaman HP Edge."; card.append(hint);
      }
      if (!live && actions.length) { const hint = document.createElement("p"); hint.textContent = "Menunggu detector tersambung kembali."; card.append(hint); }
      return card;
    }));
  }

  function send(action,eventId = "") {
    if (!liveService() || pending.size) { notice("Tunggu koneksi detector dan konfirmasi perintah sebelumnya."); return; }
    const commandId = id();
    const timer = setTimeout(() => {
      pending.delete(commandId); notice("Belum ada konfirmasi detector. Periksa koneksi dan status kejadian sebelum mencoba lagi."); eventSignature = ""; refresh();
    },8000);
    pending.set(commandId,{timer});
    client.publish(`buddycheck/${project}/commands/${actor}`,JSON.stringify({command_id:commandId,action,actor,event_id:eventId,sent_at_ms:Date.now()}),{qos:1,retain:false},(error) => {
      if (!error) return;
      clearTimeout(timer); pending.delete(commandId); notice("Pengiriman perintah gagal: " + error.message); eventSignature = ""; refresh();
    });
    notice("Mengirim perintah; menunggu konfirmasi detector…");
    log(`Mengirim ${action}`); eventSignature = ""; refresh();
  }

  $("setupForm").addEventListener("submit",start);
  $("stopButton").addEventListener("click",stop);
  $("monitorButton").addEventListener("click",() => send(state?.armed ? "DISARM" : "ARM"));
  $("clearLog").addEventListener("click",() => { logLines = []; $("log").replaceChildren(); });
  $("project").addEventListener("change",rememberLinks);
  $("broker").addEventListener("change",rememberLinks);
  document.addEventListener("visibilitychange",() => {
    samples = []; lastAcceptedSample = 0;
    if (isPhone && active && !document.hidden && navigator.wakeLock) navigator.wakeLock.request("screen").then((lock) => wakeLock = lock).catch(() => {});
  });
  window.addEventListener("pagehide",() => { if (active) stop(); });
  setInterval(() => {
    refresh();
    document.querySelectorAll("[data-expires]").forEach((node) => {
      const seconds = Math.max(0,Math.ceil((Number(node.dataset.expires) - Date.now() - serverOffset) / 1000));
      node.textContent = liveService() ? `Batas konfirmasi: ${seconds} detik` : "Batas waktu belum tersinkron dengan detector.";
    });
  },500);
  const setupController = new AbortController();
  const setupTimeout = setTimeout(() => setupController.abort(),3000);
  fetch("./config.json",{signal:setupController.signal}).then((response) => response.ok ? response.json() : null).then((config) => {
    if (!config || active || starting) return;
    if (!params.has("project")) $("project").value = config.project_id || "";
    if (!params.has("broker") && config.websocket_url) $("broker").value = config.websocket_url;
    rememberLinks();
    // Sensor permission is always requested through a user click on the phone.
  }).catch(() => {}).finally(() => clearTimeout(setupTimeout));
  refresh();
})();
