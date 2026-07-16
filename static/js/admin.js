const openRatingButton = document.getElementById("open-rating-button");
const finalRoundButton = document.getElementById("final-round-button");
const fullscreenButton = document.getElementById("fullscreen-button");
const ratingModal = document.getElementById("rating-modal");
const ratingTableBody = document.getElementById("rating-table-body");
const closeRatingElements = document.querySelectorAll("[data-close-rating]");
const adminBoard = document.getElementById("admin-board");

const playerLinkButton = document.getElementById("player-link-button");
const playerLinkModal = document.getElementById("player-link-modal");
const playerLinkQrImage = document.getElementById("player-link-qr-image");
const playerLinkUrl = document.getElementById("player-link-url");
const copyPlayerLinkButton = document.getElementById("copy-player-link-button");
const playerLinkStatus = document.getElementById("player-link-status");
const closePlayerLinkElements = document.querySelectorAll("[data-close-player-link]");

const questionModal = document.getElementById("question-modal");
const adminQuestionCard = document.getElementById("admin-question-card");
const adminQuestionCategory = document.getElementById("admin-question-category");
const adminQuestionTitle = document.getElementById("admin-question-title");
const adminQuestionImageWrap = document.getElementById("admin-question-image-wrap");
const adminQuestionImage = document.getElementById("admin-question-image");
const adminQuestionOptions = document.getElementById("admin-question-options");

const finalModal = document.getElementById("final-modal");
const finalCard = document.getElementById("final-card");
const finalTitle = document.getElementById("final-title");
const finalAdminChoices = document.getElementById("final-admin-choices");
const boyVotesCount = document.getElementById("boy-votes-count");
const girlVotesCount = document.getElementById("girl-votes-count");
const finalHint = document.getElementById("final-hint");

const secretModal = document.getElementById("secret-modal");
const secretAdminNamesBody = document.getElementById("secret-admin-names-body");

const resetGameButton = document.getElementById("reset-game-button");

let isFinalRevealing = false;
let isFinalRevealed = false;
let currentQuestion = null;
let isClosingQuestion = false;
let currentPlayerLink = "";


async function openPlayerLinkModal() {
  playerLinkModal.classList.remove("hidden");

  playerLinkQrImage.src = "";
  playerLinkUrl.textContent = "Загрузка ссылки...";
  playerLinkUrl.href = "#";
  playerLinkStatus.textContent = "";

  try {
    const response = await fetchWithTimeout("/api/admin/player-link");
    const data = await response.json();

    if (!response.ok) {
      playerLinkStatus.textContent = data.message || "Не удалось получить ссылку подключения.";
      return;
    }

    currentPlayerLink = data.url;

    playerLinkQrImage.src = data.qr_data_uri;
    playerLinkUrl.textContent = data.url;
    playerLinkUrl.href = data.url;
  } catch (error) {
    playerLinkStatus.textContent = "Не удалось получить ссылку подключения. Проверьте сервер.";
  }
}

function closePlayerLinkModal() {
  playerLinkModal.classList.add("hidden");
}

async function copyPlayerLink() {
  if (!currentPlayerLink) {
    return;
  }

  try {
    await navigator.clipboard.writeText(currentPlayerLink);
    playerLinkStatus.textContent = "Ссылка скопирована.";
  } catch (error) {
    playerLinkStatus.textContent = "Не удалось скопировать автоматически. Скопируйте ссылку вручную.";
  }
}

function updateFullscreenButtonText() {
  if (!fullscreenButton) {
    return;
  }

  const isFullscreen = Boolean(document.fullscreenElement);

  fullscreenButton.setAttribute(
    "aria-label",
    isFullscreen ? "Выйти из полноэкранного режима" : "На весь экран",
  );

  fullscreenButton.setAttribute(
    "title",
    isFullscreen ? "Выйти из полноэкранного режима" : "На весь экран",
  );

  fullscreenButton.classList.toggle("is-fullscreen", isFullscreen);
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }

    updateFullscreenButtonText();
  } catch (error) {
    alert("Не удалось переключить полноэкранный режим. Попробуйте нажать F11.");
  }
}

function openRatingModal() {
  ratingModal.classList.remove("hidden");
  socket.emit("admin_request_rating");
}

function closeRatingModal() {
  ratingModal.classList.add("hidden");
}

function renderRating(players) {
  if (!players.length) {
    ratingTableBody.innerHTML = `
      <tr>
        <td colspan="3">Пока нет игроков</td>
      </tr>
    `;
    return;
  }

  ratingTableBody.innerHTML = players
    .map((player, index) => {
      const statusClass = player.connected ? "online" : "offline";
      const statusTitle = player.connected ? "Онлайн" : "Нет связи";

      return `
        <tr>
          <td>${index + 1}</td>
          <td>
            <span class="player-status-dot ${statusClass}" title="${statusTitle}"></span>
            ${player.nickname}
          </td>
          <td>${player.score}</td>
        </tr>
      `;
    })
    .join("");
}

function renderBoard(board, allQuestionsUsed) {
  adminBoard.innerHTML = "";

  board.forEach((row) => {
    const categoryCell = document.createElement("div");
    categoryCell.className = "board-cell category-cell";
    categoryCell.textContent = row.category;
    adminBoard.appendChild(categoryCell);

    row.questions.forEach((question) => {
      const questionCell = document.createElement("button");
      questionCell.type = "button";
      questionCell.className = "board-cell question-cell";

      if (!question) {
        questionCell.textContent = "—";
        questionCell.disabled = true;
        questionCell.classList.add("used");
        adminBoard.appendChild(questionCell);
        return;
      }

      questionCell.textContent = String(question.points);
      questionCell.dataset.questionId = question.id;

      if (question.is_used) {
        questionCell.disabled = true;
        questionCell.classList.add("used");
      }

      questionCell.addEventListener("click", () => {
        openQuestion(question.id);
      });

      adminBoard.appendChild(questionCell);
    });
  });

  finalRoundButton.disabled = !allQuestionsUsed;
}

function renderAdminQuestionImage(question, visible = true) {
  const imageUrl = visible && question ? question.image_url : null;

  adminQuestionCard.classList.toggle("has-question-image", Boolean(imageUrl));

  if (!imageUrl) {
    adminQuestionImageWrap.classList.add("hidden");
    adminQuestionImage.removeAttribute("src");
    adminQuestionImage.alt = "";
    return;
  }

  adminQuestionImage.src = imageUrl;
  adminQuestionImage.alt = `Иллюстрация к вопросу: ${question.question}`;
  adminQuestionImageWrap.classList.remove("hidden");
}

function updateAdminQuestionTitleScale(questionText = "") {
  const textLength = questionText.trim().length;

  adminQuestionTitle.classList.toggle("long-question-title", textLength > 140);
  adminQuestionTitle.classList.toggle("very-long-question-title", textLength > 260);
}

function renderAdminQuestionCard(question, auction = null, winner = null) {
  currentQuestion = question;

  questionModal.classList.remove("hidden");
  adminQuestionCard.classList.toggle("auction-question-card", Boolean(question.is_auction));
  renderAdminQuestionImage(question, !question.is_auction || Boolean(winner));

  adminQuestionCategory.textContent = `${question.category} · ${question.points} баллов`;
  updateAdminQuestionTitleScale(question.question || "");

  if (question.is_auction) {
  adminQuestionTitle.textContent = winner && question.question
    ? question.question
    : "АУКЦИОН";

  if (winner) {
    adminQuestionOptions.innerHTML = `
      <div class="auction-admin-text">
        <p>Вопрос достался игроку:</p>
        <strong>${winner.nickname}</strong>
        <p>Ставка: ${winner.bid}</p>
        <p class="small-note">После ответа победителя нажмите на карточку, чтобы закрыть вопрос.</p>
      </div>
    `;
    return;
  }

    const bidsCount = auction ? auction.bids_count : 0;
    const participantsCount = auction ? auction.participants_count : 0;
    const progressPercent = participantsCount > 0
      ? Math.round((bidsCount / participantsCount) * 100)
      : 0;

    adminQuestionOptions.innerHTML = `
      <div class="auction-admin-text">
        <p>Игроки делают ставки</p>
        <strong>${bidsCount} / ${participantsCount}</strong>
        <div class="auction-progress">
          <div class="auction-progress-fill" style="width: ${progressPercent}%"></div>
        </div>
      </div>
    `;
    return;
  }

  adminQuestionTitle.textContent = question.question;

  if (question.type === "choice") {
    adminQuestionOptions.innerHTML = question.options
      .map((option) => `<div class="admin-option-preview">${option}</div>`)
      .join("");
    return;
  }

  adminQuestionOptions.innerHTML = `
    <div class="admin-option-preview text-question-preview">
      Текстовый ответ
    </div>
  `;
}

function hideAdminQuestionCard() {
  currentQuestion = null;
  questionModal.classList.add("hidden");
  adminQuestionCard.classList.remove("auction-question-card");
  renderAdminQuestionImage(null);
  adminQuestionCategory.textContent = "";
  adminQuestionTitle.textContent = "";
  updateAdminQuestionTitleScale();
  adminQuestionOptions.innerHTML = "";
}

function showFinalModal(counts = { boy: 0, girl: 0 }) {
  finalModal.classList.remove("hidden");
  isFinalRevealed = false;

  finalCard.classList.remove("final-reveal-card", "final-reveal-girl");
  finalTitle.textContent = "Кто родится?";
  finalAdminChoices.classList.remove("hidden");
  finalHint.textContent = "Нажмите на карточку, чтобы раскрыть ответ";
  updateFinalCounts(counts);
}

function updateFinalCounts(counts) {
  boyVotesCount.textContent = String(counts.boy || 0);
  girlVotesCount.textContent = String(counts.girl || 0);
}

function showFinalDrumroll() {
  finalTitle.textContent = "Барабанная дробь...";
  finalAdminChoices.classList.add("hidden");
  finalHint.textContent = "";
  finalCard.classList.add("final-drumroll-card");
}

function showFinalReveal(actualGender = "boy") {
  finalCard.classList.remove("final-drumroll-card");
  isFinalRevealed = true;

  const isGirl = actualGender === "girl";

  finalCard.classList.add("final-reveal-card");
  finalCard.classList.toggle("final-reveal-girl", isGirl);
  finalTitle.textContent = isGirl ? "ДЕВОЧКА!" : "МАЛЬЧИК!";
  finalAdminChoices.classList.add("hidden");
  finalHint.textContent = "Нажмите, чтобы перейти к секретному раунду";

  if (typeof window.launchGenderConfetti === "function") {
    window.launchGenderConfetti();
  }
}

function renderSecretNames(names) {
  names = [...names].sort((first, second) => {
    return Number(second.rating) - Number(first.rating);
  });

  if (!names.length) {
    secretAdminNamesBody.innerHTML = `
      <tr>
        <td colspan="2">Пока нет имён</td>
      </tr>
    `;
    return;
  }

  secretAdminNamesBody.innerHTML = names
    .map((item) => {
      return `
        <tr>
          <td>${item.display_name}</td>
          <td>${item.rating}</td>
        </tr>
      `;
    })
    .join("");
}

function showSecretModal(names = []) {
  finalModal.classList.add("hidden");
  secretModal.classList.remove("hidden");
  renderSecretNames(names);
}

async function startSecretRound() {
  const response = await fetchWithTimeout("/api/admin/secret/start", {
    method: "POST",
  });

  const data = await response.json();

  if (!response.ok) {
    alert(data.message || "Не удалось начать секретный раунд.");
    return;
  }

  showSecretModal(data.names || []);
}

async function startFinalRound() {
  const response = await fetchWithTimeout("/api/admin/final/start", {
    method: "POST",
  });

  const data = await response.json();

  if (!response.ok) {
    alert(data.message || "Не удалось начать финальный раунд.");
    return;
  }

  showFinalModal(data.counts);
}

async function resetGame() {
  const confirmed = window.confirm(
    "Сбросить игру полностью? Будут удалены игроки, баллы, ответы, ставки, финальные голоса и имена. Начнётся новая игра."
  );

  if (!confirmed) {
    return;
  }

  const response = await fetchWithTimeout("/api/admin/game/reset", {
    method: "POST",
  });

  const data = await response.json();

  if (!response.ok) {
    alert(data.message || "Не удалось сбросить игру.");
    return;
  }

  hideAdminQuestionCard();
  finalModal.classList.add("hidden");
  secretModal.classList.add("hidden");

  renderBoard(data.board || [], Boolean(data.all_questions_used));
  renderRating(data.players || []);
}

async function revealFinalRound() {
  if (isFinalRevealing || isFinalRevealed) {
    return;
  }

  isFinalRevealing = true;
  showFinalDrumroll();

  window.setTimeout(async () => {
    try {
      const response = await fetchWithTimeout("/api/admin/final/reveal", {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        alert(data.message || "Не удалось раскрыть финальный ответ.");
        return;
      }

      showFinalReveal(data.answer);
    } finally {
      isFinalRevealing = false;
    }
  }, 2000);
}

async function loadCurrentGameState() {
  const response = await fetchWithTimeout("/api/game-state");

  if (!response.ok) {
    return;
  }

  const data = await response.json();

  if (!data.question || !data.state || !data.state.question_open) {
    return;
  }

  if (data.state.current_phase === "auction_bidding") {
    renderAdminQuestionCard(data.question, data.auction || null);
    return;
  }

  if (data.state.current_phase === "auction_question") {
    renderAdminQuestionCard(
      data.question,
      null,
      data.auction_winner || null,
    );
    return;
  }

  renderAdminQuestionCard(data.question);
}

async function loadBoard() {
  const response = await fetchWithTimeout("/api/admin/board");

  if (!response.ok) {
    adminBoard.innerHTML = `
      <div class="board-loading">Не удалось загрузить игровое поле.</div>
    `;
    return;
  }

  const data = await response.json();
  renderBoard(data.board, data.all_questions_used);

  await loadCurrentGameState();
}

async function openQuestion(questionId) {
  const response = await fetchWithTimeout(`/api/admin/questions/${encodeURIComponent(questionId)}/open`, {
    method: "POST",
  });

  const data = await response.json();

  if (!response.ok) {
    if (data.error === "question_already_open") {
      await loadCurrentGameState();
      return;
    }

    alert(data.message || "Не удалось открыть вопрос.");
    return;
  }

  renderAdminQuestionCard(data.question, data.auction || null);
}

async function closeCurrentQuestion() {
  if (isClosingQuestion) {
    return;
  }

  if (!currentQuestion) {
    await loadCurrentGameState();

    if (!currentQuestion) {
      alert("Сейчас нет открытой карточки вопроса. Обновляю состояние игры.");
      return;
    }
  }

  isClosingQuestion = true;

  try {
    const response = await fetchWithTimeout("/api/admin/questions/current/close", {
      method: "POST",
    });

    const data = await response.json();

    if (!response.ok) {
      if (data.error === "no_open_question") {
        hideAdminQuestionCard();
        await loadBoard();
        return;
      }

      alert(data.message || "Не удалось закрыть вопрос.");
      return;
    }

    hideAdminQuestionCard();
    renderBoard(data.board, data.all_questions_used);
    renderRating(data.players || []);
  } catch (error) {
    alert("Не удалось закрыть вопрос. Проверьте, запущен ли сервер, и обновите страницу администратора.");
  } finally {
    isClosingQuestion = false;
  }
}

async function fetchWithTimeout(url, options = {}) {
  const timeoutMs = options.timeoutMs || 8000;
  const controller = new AbortController();

  const timeoutId = window.setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    const { timeoutMs: _timeoutMs, ...fetchOptions } = options;

    return await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

if (playerLinkButton) {
  playerLinkButton.addEventListener("click", openPlayerLinkModal);
}

closePlayerLinkElements.forEach((element) => {
  element.addEventListener("click", closePlayerLinkModal);
});

if (copyPlayerLinkButton) {
  copyPlayerLinkButton.addEventListener("click", copyPlayerLink);
}

if (fullscreenButton) {
  fullscreenButton.addEventListener("click", toggleFullscreen);
}

document.addEventListener("fullscreenchange", updateFullscreenButtonText);

if (openRatingButton) {
  openRatingButton.addEventListener("click", openRatingModal);
}

if (finalRoundButton) {
  finalRoundButton.addEventListener("click", startFinalRound);
}

if (adminQuestionCard) {
  adminQuestionCard.addEventListener("click", closeCurrentQuestion);
}

if (resetGameButton) {
  resetGameButton.addEventListener("click", resetGame);
}

if (finalCard) {
  finalCard.addEventListener("click", () => {
    if (isFinalRevealed) {
      startSecretRound();
      return;
    }

    revealFinalRound();
  });
}

closeRatingElements.forEach((element) => {
  element.addEventListener("click", closeRatingModal);
});

socket.on("rating_updated", (data) => {
  renderRating(data.players || []);
});

socket.on("board_updated", (data) => {
  renderBoard(data.board || [], Boolean(data.all_questions_used));
});

socket.on("question_opened", (data) => {
  if (data.question) {
    renderAdminQuestionCard(data.question);
  }
});

socket.on("question_closed", (data) => {
  hideAdminQuestionCard();
  renderBoard(data.board || [], Boolean(data.all_questions_used));
});

socket.on("connect", () => {
  socket.emit("admin_request_board");
  loadCurrentGameState();
});

socket.on("auction_started", (data) => {
  if (!data.auction) {
    return;
  }

  renderAdminQuestionCard(
    {
      id: data.auction.question_id,
      category: "Аукцион",
      points: "",
      is_auction: true,
    },
    data.auction,
  );
});

socket.on("auction_progress_updated", (data) => {
  if (!currentQuestion || !currentQuestion.is_auction) {
    return;
  }

  renderAdminQuestionCard(currentQuestion, data.auction);
});

socket.on("auction_winner_selected", (data) => {
  if (!currentQuestion || !currentQuestion.is_auction) {
    return;
  }

  renderAdminQuestionCard(currentQuestion, null, data.winner);
});

socket.on("final_started", (data) => {
  showFinalModal(data.counts || { boy: 0, girl: 0 });
});

socket.on("final_vote_updated", (data) => {
  updateFinalCounts(data.counts || { boy: 0, girl: 0 });
});

socket.on("final_revealed", (data) => {
  showFinalReveal(data.answer);
});

socket.on("secret_started", (data) => {
  showSecretModal(data.names || []);
});

socket.on("baby_names_updated", (data) => {
  if (!secretModal.classList.contains("hidden")) {
    renderSecretNames(data.names || []);
  }
});

async function refreshAdminStateAfterIdle() {
  try {
    if (!socket.connected) {
      socket.connect();
    }

    await loadBoard();
    socket.emit("admin_request_rating");
  } catch (error) {
    console.warn("Не удалось обновить состояние админки после простоя.", error);
  }
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refreshAdminStateAfterIdle();
  }
});

window.addEventListener("focus", () => {
  refreshAdminStateAfterIdle();
});

loadBoard();
if (adminQuestionImage) {
  adminQuestionImage.addEventListener("error", () => {
    adminQuestionImageWrap.classList.add("hidden");
    adminQuestionCard.classList.remove("has-question-image");
  });
}
