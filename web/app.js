// ─── SSE CONNECTION ────────────────────────────────────────────────────────────
let sse = null;
let sseAttempts = 0;

function limparTelemetria() {
  setText('vel-inst', '---');
  setText('vel-max',  '---');
  setText('vel-med',  '---');
  setText('acel',     '---');
  setText('modo',     '---');
  setText('qualidade','---');
}

function mostrarServidorOffline() {
  const overlay = document.getElementById('video-overlay');
  overlay.querySelector('span').textContent = 'Servidor offline. Recarregue a página.';
  overlay.classList.add('visible');
  setBadge(false);
}

function conectarSSE() {
  if (sse) sse.close();

  const urlInput = document.getElementById('ip-tel')?.value.trim();
  const sseUrl = urlInput ? urlInput : '/api/telemetria';

  sse = new EventSource(sseUrl);

  sse.onopen = () => {
    sseAttempts = 0;
    setBadge(true);
  };

  sse.onmessage = (e) => {
    try {
      atualizarTelemetria(JSON.parse(e.data));
    } catch (_) {}
  };

  sse.onerror = () => {
    setBadge(false);
    limparTelemetria();
    sse.close();
    sse = null;
    sseAttempts++;
    if (sseAttempts >= 3) {
      mostrarServidorOffline();
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, sseAttempts), 30000);
    setTimeout(conectarSSE, delay);
  };
}

function setBadge(online) {
  const b = document.getElementById('status-badge');
  b.textContent = online ? '● AO VIVO' : '● OFFLINE';
  b.className   = online ? 'badge-online' : 'badge-offline';
}

// ─── TELEMETRIA UPDATE ─────────────────────────────────────────────────────────
const MODO_CORES = {
  real:     '#FFFFFF',
  simulado: '#888888',
  sensor:   '#00E5FF',
  listras:  '#00FF88',
  demo:     '#FF4444',
};
let smoothVoltage = 3.7;
let smoothCurrent = 0.3;

function atualizarTelemetria(d) {
  setText('vel-inst', formatVel(d.vel_inst));
  setText('vel-max',  formatVel(d.vel_max));
  setText('vel-med',  formatVel(d.vel_media));

  const elAcel = document.getElementById('acel');
  const acel = d.acel ?? 0;
  elAcel.textContent = `${acel >= 0 ? '+' : ''}${acel.toFixed(2)} m/s²`;
  elAcel.style.color = acel >= 0 ? '#FFD600' : '#FF00FF';

  const elModo = document.getElementById('modo');
  elModo.textContent = (d.modo ?? '--').toUpperCase().replace('_', ' ');
  elModo.style.color = MODO_CORES[d.modo] ?? '#FFFFFF';

  const elQual = document.getElementById('qualidade');
  const q = d.qualidade ?? 0;
  if (q > 30)      { elQual.textContent = `ÓTIMO (${q})`;  elQual.style.color = '#FFD600'; }
  else if (q > 10) { elQual.textContent = `MÉDIO (${q})`;  elQual.style.color = '#FFA500'; }
  else             { elQual.textContent = `FRACO (${q})`;   elQual.style.color = '#FF4444'; }

  // Simulação Eletroeletrônica da Bateria (Filtro Passa-Baixa para Suavidade)
  const speedVal = Math.abs(d.vel_inst ?? 0);
  const iBase = 0.3; // Corrente idle
  
  // Corrente alvo (cálculo instantâneo)
  let targetCurrent = iBase + (speedVal / 40.0) * 0.7;
  if (targetCurrent > 1.0) targetCurrent = 1.0;
  
  // Amortecimento sistêmico (filtro passa-baixa: inércia térmica/elétrica)
  smoothCurrent = (smoothCurrent * 0.95) + (targetCurrent * 0.05);
  
  const vNominal = 3.7;
  const rInternal = 0.4;
  let targetVoltage = vNominal - (smoothCurrent * rInternal);
  smoothVoltage = (smoothVoltage * 0.95) + (targetVoltage * 0.05);
  
  // Ruído mínimo para realismo do ADC, aplicado APÓS o filtro
  const displayCurrent = smoothCurrent + (Math.random() * 0.005);
  const displayVoltage = smoothVoltage + (Math.random() * 0.005);
  const power = displayVoltage * displayCurrent;

  setText('bat-tensao', `${displayVoltage.toFixed(2)} V`);
  setText('bat-corrente', `${displayCurrent.toFixed(2)} A`);
  setText('bat-potencia', `${power.toFixed(2)} W`);
  
  // Efeito visual de alerta no HUD de bateria
  document.getElementById('bat-tensao').style.color = displayVoltage < 3.5 ? '#f43f5e' : '#fff';
  // Bloco sensor celular
  const sensorBlock = document.getElementById('sensor-block');
  const sensorSep   = document.getElementById('sensor-sep');
  if (d.sensor_ativo) {
    sensorBlock.style.display = 'flex';
    sensorSep.style.display   = 'block';
    setText('gps-kmh', `${(d.gps_kmh ?? 0).toFixed(1)} km/h`);
    const ay = d.accel_y ?? 0;
    setText('accel-y', `${ay >= 0 ? '+' : ''}${ay.toFixed(2)} m/s²`);
  } else {
    sensorBlock.style.display = 'none';
    sensorSep.style.display   = 'none';
  }

  // Gauges
  const speed = d.vel_inst ?? 0;
  drawSpeedometer(speed);
  drawGMeter((acel / 9.8), d.sensor_ativo && d.accel_x != null ? d.accel_x / 9.8 : 0);

  if (d.historico && d.historico.length > 1) drawHistorico(d.historico);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function formatVel(v) {
  return v != null ? `${Math.abs(v).toFixed(1)} km/h` : '-- km/h';
}

// ─── SPEEDOMETER ──────────────────────────────────────────────────────────────
const cSpeed  = document.getElementById('speedometer');
const ctxS    = cSpeed.getContext('2d');
const VEL_MAX = 80;

function drawSpeedometer(speed) {
  const w = cSpeed.width, h = cSpeed.height;
  const cx = w / 2, cy = h / 2;
  const r  = Math.min(cx, cy) - 14;

  ctxS.clearRect(0, 0, w, h);

  const angI = (150 * Math.PI) / 180;
  const angF = (390 * Math.PI) / 180;
  const rng  = angF - angI;

  // Trilha de fundo
  ctxS.beginPath();
  ctxS.arc(cx, cy, r, angI, angF);
  ctxS.strokeStyle = '#2a2a2a';
  ctxS.lineWidth = 10;
  ctxS.stroke();

  // Zona vermelha
  ctxS.beginPath();
  ctxS.arc(cx, cy, r, angI + 0.8 * rng, angF);
  ctxS.strokeStyle = 'rgba(255,0,255,0.18)';
  ctxS.lineWidth = 10;
  ctxS.stroke();

  // Arco de velocidade
  const velAbs = Math.min(Math.abs(speed), VEL_MAX);
  const prop   = velAbs / VEL_MAX;
  const angVel = angI + prop * rng;
  const corArco = prop >= 0.8 ? '#FF00FF' : '#FFD600';

  if (prop > 0.005) {
    ctxS.beginPath();
    ctxS.arc(cx, cy, r, angI, angVel);
    ctxS.strokeStyle = corArco;
    ctxS.lineWidth = 10;
    ctxS.stroke();
  }

  // Ticks
  for (let v = 0; v <= VEL_MAX; v += 5) {
    const p    = v / VEL_MAX;
    const ang  = angI + p * rng;
    const isRed   = v >= VEL_MAX * 0.8;
    const isMajor = v % 20 === 0;
    const rIn     = isMajor ? r - 13 : r - 7;

    ctxS.beginPath();
    ctxS.moveTo(cx + r * Math.cos(ang), cy + r * Math.sin(ang));
    ctxS.lineTo(cx + rIn * Math.cos(ang), cy + rIn * Math.sin(ang));
    ctxS.strokeStyle = isRed ? '#FF00FF' : '#555';
    ctxS.lineWidth = isMajor ? 2 : 1;
    ctxS.stroke();

    if (isMajor) {
      const rt = r - 25;
      ctxS.fillStyle = isRed ? '#FF00FF' : '#777';
      ctxS.font = '11px monospace';
      ctxS.textAlign = 'center';
      ctxS.textBaseline = 'middle';
      ctxS.fillText(String(v), cx + rt * Math.cos(ang), cy + rt * Math.sin(ang));
    }
  }

  // Agulha
  ctxS.beginPath();
  ctxS.moveTo(cx, cy);
  ctxS.lineTo(cx + (r - 18) * Math.cos(angVel), cy + (r - 18) * Math.sin(angVel));
  ctxS.strokeStyle = corArco;
  ctxS.lineWidth = 3;
  ctxS.lineCap = 'round';
  ctxS.stroke();
  ctxS.lineCap = 'butt';

  // Centro
  ctxS.beginPath();
  ctxS.arc(cx, cy, 6, 0, Math.PI * 2);
  ctxS.fillStyle = '#FFF';
  ctxS.fill();

  // Número
  ctxS.fillStyle = '#FFF';
  ctxS.font = `bold ${Math.round(r * 0.44)}px monospace`;
  ctxS.textAlign = 'center';
  ctxS.textBaseline = 'middle';
  ctxS.fillText(Math.round(velAbs), cx, cy - 10);

  // Marcha e unidade
  const marcha = speed < -0.5 ? 'R' : 'D';
  ctxS.fillStyle = corArco;
  ctxS.font = 'bold 13px monospace';
  ctxS.fillText(marcha, cx, cy + 18);

  ctxS.fillStyle = '#555';
  ctxS.font = '11px monospace';
  ctxS.fillText('km/h', cx, cy + 34);
}

// ─── G-METER ──────────────────────────────────────────────────────────────────
const cG   = document.getElementById('gmeter');
const ctxG = cG.getContext('2d');
let gTrail = [];

function drawGMeter(accelLong, accelLat) {
  const w = cG.width, h = cG.height;
  const cx = w / 2, cy = h / 2;
  const r  = Math.min(cx, cy) - 14;
  const MAX_G = 1.5;

  ctxG.clearRect(0, 0, w, h);

  // Círculos
  [r, r / 2].forEach((radius, i) => {
    ctxG.beginPath();
    ctxG.arc(cx, cy, radius, 0, Math.PI * 2);
    ctxG.strokeStyle = i === 0 ? '#444' : '#333';
    ctxG.lineWidth = 1;
    ctxG.stroke();
  });

  // Crosshairs
  ctxG.strokeStyle = '#333';
  ctxG.lineWidth = 1;
  ctxG.beginPath();
  ctxG.moveTo(cx - r, cy); ctxG.lineTo(cx + r, cy);
  ctxG.moveTo(cx, cy - r); ctxG.lineTo(cx, cy + r);
  ctxG.stroke();

  // Labels dos eixos
  ctxG.fillStyle = '#444';
  ctxG.font = '9px monospace';
  ctxG.textAlign = 'center';
  ctxG.fillText('ACC',  cx,      cy - r - 6);
  ctxG.fillText('DEC',  cx,      cy + r + 13);
  ctxG.fillText('DIR',  cx + r + 4, cy + 4);
  ctxG.fillText('ESQ',  cx - r - 4, cy + 4);

  // Rastro
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const px = cx + (clamp(accelLat,  -MAX_G, MAX_G) / MAX_G) * r;
  const py = cy - (clamp(accelLong, -MAX_G, MAX_G) / MAX_G) * r;

  gTrail.push({ x: px, y: py });
  if (gTrail.length > 24) gTrail.shift();

  for (let i = 1; i < gTrail.length; i++) {
    const a = i / gTrail.length;
    ctxG.beginPath();
    ctxG.moveTo(gTrail[i - 1].x, gTrail[i - 1].y);
    ctxG.lineTo(gTrail[i].x,     gTrail[i].y);
    ctxG.strokeStyle = `rgba(0,229,255,${a * 0.35})`;
    ctxG.lineWidth = 2;
    ctxG.stroke();
  }

  // Ponto atual
  ctxG.beginPath();
  ctxG.arc(px, py, 7, 0, Math.PI * 2);
  ctxG.fillStyle = '#00E5FF';
  ctxG.fill();

  // Valor G total
  const totalG = Math.sqrt(accelLong ** 2 + accelLat ** 2);
  ctxG.fillStyle = '#00E5FF';
  ctxG.font = 'bold 12px monospace';
  ctxG.textAlign = 'center';
  ctxG.fillText(`${totalG.toFixed(2)} G`, cx, cy + r + 28);
}

// ─── HISTÓRICO ────────────────────────────────────────────────────────────────
const cHist  = document.getElementById('historico');
const ctxH   = cHist.getContext('2d');

function drawHistorico(dados) {
  const w = cHist.width, h = cHist.height;
  const pT = 20, pB = 28, pL = 36, pR = 12;
  const pW = w - pL - pR;
  const pH = h - pT - pB;

  ctxH.clearRect(0, 0, w, h);

  const n = dados.length;
  if (n < 2) return;

  const VEL_DISP = 120;

  // Grade horizontal
  [0.25, 0.5, 0.75, 1].forEach(pct => {
    const y = pT + pH * (1 - pct);
    ctxH.beginPath();
    ctxH.moveTo(pL, y); ctxH.lineTo(pL + pW, y);
    ctxH.strokeStyle = '#222';
    ctxH.lineWidth = 1;
    ctxH.stroke();
    ctxH.fillStyle = '#444';
    ctxH.font = '10px monospace';
    ctxH.textAlign = 'right';
    ctxH.fillText(`${Math.round(VEL_DISP * pct)}`, pL - 4, y + 3);
  });

  // Linha de velocidade
  ctxH.beginPath();
  dados.forEach((v, i) => {
    const x = pL + (i / (n - 1)) * pW;
    const y = pT + pH * (1 - Math.min(Math.abs(v), VEL_DISP) / VEL_DISP);
    i === 0 ? ctxH.moveTo(x, y) : ctxH.lineTo(x, y);
  });
  ctxH.strokeStyle = '#FFD600';
  ctxH.lineWidth = 2;
  ctxH.stroke();

  // Área
  ctxH.lineTo(pL + pW, pT + pH);
  ctxH.lineTo(pL, pT + pH);
  ctxH.closePath();
  const grad = ctxH.createLinearGradient(0, pT, 0, pT + pH);
  grad.addColorStop(0, 'rgba(255,214,0,0.25)');
  grad.addColorStop(1, 'rgba(255,214,0,0)');
  ctxH.fillStyle = grad;
  ctxH.fill();

  // Valor atual
  const last = dados[n - 1];
  ctxH.fillStyle = '#FFD600';
  ctxH.font = 'bold 12px monospace';
  ctxH.textAlign = 'right';
  ctxH.fillText(`${Math.abs(last).toFixed(0)} km/h`, pL + pW, pT - 5);
}

// ─── GALERIA ──────────────────────────────────────────────────────────────────
async function carregarGaleria() {
  try {
    const resp  = await fetch('/api/galeria');
    const fotos = await resp.json();

    const grid  = document.getElementById('gallery-grid');
    const empty = document.getElementById('gallery-empty');

    if (!fotos.length) { empty.style.display = 'block'; return; }

    empty.remove();

    fotos.forEach(nome => {
      const item = document.createElement('div');
      item.className = 'gallery-item';
      const img = document.createElement('img');
      img.src     = `/assets/gallery/${nome}`;
      img.alt     = nome.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
      img.loading = 'lazy';
      item.appendChild(img);
      item.addEventListener('click', () => abrirLightbox(img.src, img.alt));
      grid.appendChild(item);
    });
  } catch (_) {}
}

function abrirLightbox(src, caption) {
  const lb = document.getElementById('lightbox');
  document.getElementById('lightbox-img').src        = src;
  document.getElementById('lightbox-caption').textContent = caption;
  lb.showModal();
}

document.getElementById('lightbox-close').addEventListener('click', () => {
  document.getElementById('lightbox').close();
});

document.getElementById('lightbox').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) e.currentTarget.close();
});

// ─── CAM CONTROLS & HUD ───────────────────────────────────────────────────────
let videoStream = null;

function updateHUDClock() {
  const now = new Date();
  const el = document.getElementById('hud-ts');
  if (el) {
    el.textContent = now.toLocaleTimeString('pt-BR', { hour12: false }) + '.' + String(now.getMilliseconds()).padStart(3,'0');
  }
}
setInterval(updateHUDClock, 100);
updateHUDClock();

async function startWebcam() {
  try {
    stopFeed();
    videoStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    const vid = document.getElementById('feed-video');
    vid.srcObject = videoStream;
    vid.style.display = 'block';
    
    document.getElementById('stream').style.display = 'none';
    document.getElementById('video-overlay').classList.remove('visible');
    document.getElementById('hud').style.display = 'block';
    
    document.getElementById('btn-webcam').classList.add('active');
    document.getElementById('btn-stop').style.display = 'block';
  } catch (e) {
    console.error('Erro webcam:', e);
  }
}

async function connectCam() {
  const url = document.getElementById('ip-cam').value.trim();
  if (!url) return;
  stopFeed();
  
  // Envia URL pro backend para ele processar a telemetria
  try {
    await fetch('/api/config_camera', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
  } catch (e) {
    console.error('Erro ao configurar câmera no backend', e);
  }

  const img = document.getElementById('stream');
  // Estabelece conexão direta com o feed de vídeo, reduzindo o processamento no backend
  // e mitigando a latência da interface.
  img.src = url;
  img.style.display = 'block';
  
  document.getElementById('video-overlay').classList.remove('visible');
  document.getElementById('hud').style.display = 'block';
  document.getElementById('btn-stop').style.display = 'block';
}

function stopFeed() {
  if (videoStream) {
    videoStream.getTracks().forEach(t => t.stop());
    videoStream = null;
  }
  
  const vid = document.getElementById('feed-video');
  vid.srcObject = null;
  vid.style.display = 'none';
  
  const img = document.getElementById('stream');
  img.src = '';
  img.style.display = 'none';
  
  document.getElementById('hud').style.display = 'none';
  document.getElementById('video-overlay').classList.add('visible');
  
  document.getElementById('btn-webcam').classList.remove('active');
  document.getElementById('btn-stop').style.display = 'none';
}

function reconnectTelemetry() {
  sseAttempts = 0;
  const overlay = document.getElementById('video-overlay');
  const span = overlay.querySelector('span');
  if (span && span.textContent.includes('Servidor offline')) {
    span.textContent = 'Sem sinal de câmera';
    overlay.classList.remove('visible');
  }
  conectarSSE();
}

let iaAtiva = true;
function toggleIA() {
  iaAtiva = !iaAtiva;
  const btn = document.getElementById('btn-ia');
  if (btn) {
    btn.textContent = iaAtiva ? "IA: LIGADA" : "IA: DESLIGADA";
    btn.style.color = iaAtiva ? "#10b981" : "#f43f5e";
    btn.style.borderColor = iaAtiva ? "#10b981" : "#f43f5e";
    btn.style.background = iaAtiva ? "rgba(16,185,129,0.2)" : "rgba(244,63,94,0.2)";
  }
  fetch('/api/tecla', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tecla: 'i' })
  }).catch(() => {});
}

// ─── INTERAÇÕES (TECLAS & FULLSCREEN) ───────────────────────────────────────────
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const key = e.key.toLowerCase();
  
  if (key === 'i') {
      toggleIA();
      return;
  }
  
  if (['c', 's', 'r', 'l', 'q'].includes(key)) {
    fetch('/api/tecla', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tecla: key })
    }).catch(() => {});
  }
});

const videoWrap = document.querySelector('.video-wrap');
if (videoWrap) {
  videoWrap.addEventListener('dblclick', () => {
    if (!document.fullscreenElement) {
      videoWrap.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen();
    }
  });
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

drawSpeedometer(0);
drawGMeter(0, 0);
drawHistorico([0, 0]);
carregarGaleria();
conectarSSE();

// ─── LIGHTBOX (EXPANDIR GRÁFICOS) ─────────────────────────────────────────────
const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightbox-img');
const btnClose = document.getElementById('lightbox-close');

if (lightbox && btnClose) {
  btnClose.addEventListener('click', () => lightbox.close());
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) lightbox.close();
  });

  document.body.addEventListener('click', (e) => {
    // Intercepta imagens dos graficos, minimapa e galeria
    if (e.target.matches('.sim-img-wrap img, .map-img-wrap img, .gallery-item img')) {
      lightboxImg.src = e.target.src;
      lightbox.showModal();
    }
  });

  // Mostra ícone de clique para expandir nos gráficos
  document.querySelectorAll('.sim-img-wrap img').forEach(img => img.style.cursor = 'zoom-in');
}
