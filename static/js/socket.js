const socket = io({
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 10000,
});

const connectionStatusElement = document.getElementById("connection-status");
const serverMessageElement = document.getElementById("server-message");

let serverClockOffsetMs = 0;
let bestTimeSyncRttMs = Number.POSITIVE_INFINITY;
let timeSyncBurstTimeoutIds = [];

function clearTimeSyncBurst() {
  timeSyncBurstTimeoutIds.forEach((timeoutId) => {
    window.clearTimeout(timeoutId);
  });
  timeSyncBurstTimeoutIds = [];
}

function requestServerTimeSync() {
  if (!socket.connected) {
    return;
  }

  socket.emit("time_sync_request", {
    client_sent_at_ms: Date.now(),
  });
}

function startTimeSyncBurst() {
  clearTimeSyncBurst();
  bestTimeSyncRttMs = Number.POSITIVE_INFINITY;

  [0, 180, 420, 800, 1300].forEach((delayMs) => {
    const timeoutId = window.setTimeout(requestServerTimeSync, delayMs);
    timeSyncBurstTimeoutIds.push(timeoutId);
  });
}

function getSynchronizedServerTimeMs() {
  return Date.now() + serverClockOffsetMs;
}

function scheduleAtServerTime(targetServerTimeMs, callback) {
  const target = Number(targetServerTimeMs);

  if (!Number.isFinite(target)) {
    callback();
    return null;
  }

  const delayMs = Math.max(0, target - getSynchronizedServerTimeMs());
  return window.setTimeout(callback, delayMs);
}

window.getSynchronizedServerTimeMs = getSynchronizedServerTimeMs;
window.scheduleAtServerTime = scheduleAtServerTime;

socket.on("connect", () => {
  if (connectionStatusElement) {
    connectionStatusElement.textContent = "Подключено";
  }

  startTimeSyncBurst();
});

socket.on("disconnect", () => {
  clearTimeSyncBurst();

  if (connectionStatusElement) {
    connectionStatusElement.textContent = "Соединение потеряно";
  }
});

socket.on("time_sync_response", (data) => {
  const clientSentAtMs = Number(data && data.client_sent_at_ms);
  const serverTimeMs = Number(data && data.server_time_ms);
  const clientReceivedAtMs = Date.now();

  if (!Number.isFinite(clientSentAtMs) || !Number.isFinite(serverTimeMs)) {
    return;
  }

  const roundTripTimeMs = Math.max(0, clientReceivedAtMs - clientSentAtMs);
  const clientMidpointMs = clientSentAtMs + (roundTripTimeMs / 2);
  const measuredOffsetMs = serverTimeMs - clientMidpointMs;

  if (roundTripTimeMs <= bestTimeSyncRttMs) {
    bestTimeSyncRttMs = roundTripTimeMs;
    serverClockOffsetMs = measuredOffsetMs;
  }
});

window.setInterval(() => {
  requestServerTimeSync();
}, 30000);

window.addEventListener("focus", () => {
  startTimeSyncBurst();
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    startTimeSyncBurst();
  }
});

socket.on("server_message", (data) => {
  if (serverMessageElement) {
    serverMessageElement.textContent = data.message;
  }
});

let lastConfettiLaunchTime = 0;

function launchGenderConfetti() {
  const now = Date.now();

  if (now - lastConfettiLaunchTime < 1500) {
    return;
  }

  lastConfettiLaunchTime = now;

  const existingLayer = document.querySelector(".confetti-layer");

  if (existingLayer) {
    existingLayer.remove();
  }

  const layer = document.createElement("div");
  layer.className = "confetti-layer";

  const colors = [
    "#7ec8ff",
    "#ff9acb",
    "#ffffff",
    "#ffd36e",
    "#b8e7ff",
    "#ffc7df",
  ];

  for (let index = 0; index < 90; index += 1) {
    const piece = document.createElement("span");

    const size = 6 + Math.random() * 8;
    const left = Math.random() * 100;
    const delay = Math.random() * 0.8;
    const duration = 2.4 + Math.random() * 1.8;
    const drift = -80 + Math.random() * 160;
    const rotation = Math.random() * 720;

    piece.className = "confetti-piece";
    piece.style.left = `${left}%`;
    piece.style.width = `${size}px`;
    piece.style.height = `${size * 1.4}px`;
    piece.style.backgroundColor = colors[index % colors.length];
    piece.style.animationDelay = `${delay}s`;
    piece.style.animationDuration = `${duration}s`;
    piece.style.setProperty("--confetti-drift", `${drift}px`);
    piece.style.setProperty("--confetti-rotation", `${rotation}deg`);

    layer.appendChild(piece);
  }

  document.body.appendChild(layer);

  window.setTimeout(() => {
    layer.remove();
  }, 5200);
}

window.launchGenderConfetti = launchGenderConfetti;
