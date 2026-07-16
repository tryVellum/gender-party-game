const socket = io({
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 10000,
});

const connectionStatusElement = document.getElementById("connection-status");
const serverMessageElement = document.getElementById("server-message");

socket.on("connect", () => {
  if (connectionStatusElement) {
    connectionStatusElement.textContent = "Подключено";
  }
});

socket.on("disconnect", () => {
  if (connectionStatusElement) {
    connectionStatusElement.textContent = "Соединение потеряно";
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