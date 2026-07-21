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
const finalResetGameButton = document.getElementById("final-reset-game-button");
const secretResetGameButton = document.getElementById("secret-reset-game-button");

const drumrollAudio = document.getElementById("admin-drumroll-audio");
const babyLaughterAudio = document.getElementById("admin-baby-laughter-audio");
const auctionAudio = document.getElementById("admin-auction-audio");

let isFinalRevealing = false;
let isFinalRevealed = false;
let currentQuestion = null;
let isClosingQuestion = false;
let currentPlayerLink = "";
let activeFinalSequenceId = null;
let drumrollStartTimeoutId = null;
let finalRevealTimeoutId = null;
let lastBabySoundSequenceId = null;
let audioUnlocked = false;
let activeAnswerRevealSequenceId = null;
let answerRevealAdminTimeoutId = null;
let answerRevealFinishTimeoutId = null;
let answerRevealInProgress = false;
let lastBoard = [];
let lastAllQuestionsUsed = false;
let adminStateRefreshInProgress = false;


function getServerNowMs() {
  if (typeof window.getSynchronizedServerTimeMs === "function") {
    return window.getSynchronizedServerTimeMs();
  }

  return Date.now();
}

function scheduleForServerTime(targetServerTimeMs, callback) {
  if (typeof window.scheduleAtServerTime === "function") {
    return window.scheduleAtServerTime(targetServerTimeMs, callback);
  }

  return window.setTimeout(
    callback,
    Math.max(0, Number(targetServerTimeMs) - Date.now()),
  );
}

function stopAudio(audio, reset = true) {
  if (!audio) {
    return;
  }

  audio.pause();

  if (reset) {
    try {
      audio.currentTime = 0;
    } catch (error) {
      console.warn("Не удалось сбросить аудиодорожку.", error);
    }
  }
}

async function playAudio(audio, { loop = false, offsetSeconds = 0 } = {}) {
  if (!audio) {
    return;
  }

  audio.loop = loop;

  try {
    audio.currentTime = Math.max(0, Number(offsetSeconds) || 0);
    await audio.play();
  } catch (error) {
    console.warn("Браузер заблокировал воспроизведение звука.", error);
  }
}

async function unlockAdminAudio() {
  if (audioUnlocked) {
    return;
  }

  const audioElements = [drumrollAudio, babyLaughterAudio, auctionAudio].filter(Boolean);

  try {
    await Promise.all(audioElements.map(async (audio) => {
      const previousMuted = audio.muted;
      audio.muted = true;

      try {
        await audio.play();
      } finally {
        audio.pause();
        audio.currentTime = 0;
        audio.muted = previousMuted;
      }
    }));

    audioUnlocked = true;
  } catch (error) {
    console.warn("Предварительная активация звука не выполнена.", error);
  }
}

function playAuctionSound() {
  if (!auctionAudio || !auctionAudio.paused) {
    return;
  }

  playAudio(auctionAudio, { loop: true });
}

function stopAuctionSound() {
  stopAudio(auctionAudio);
}

function clearFinalSequenceTimers() {
  if (drumrollStartTimeoutId !== null) {
    window.clearTimeout(drumrollStartTimeoutId);
    drumrollStartTimeoutId = null;
  }

  if (finalRevealTimeoutId !== null) {
    window.clearTimeout(finalRevealTimeoutId);
    finalRevealTimeoutId = null;
  }
}

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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function clearAnswerRevealTimers() {
  if (answerRevealAdminTimeoutId !== null) {
    window.clearTimeout(answerRevealAdminTimeoutId);
    answerRevealAdminTimeoutId = null;
  }

  if (answerRevealFinishTimeoutId !== null) {
    window.clearTimeout(answerRevealFinishTimeoutId);
    answerRevealFinishTimeoutId = null;
  }
}

function finishAdminAnswerReveal(sequenceId = null) {
  if (
    sequenceId
    && activeAnswerRevealSequenceId
    && sequenceId !== activeAnswerRevealSequenceId
  ) {
    return;
  }

  clearAnswerRevealTimers();
  answerRevealInProgress = false;
  activeAnswerRevealSequenceId = null;

  if (questionModal && !questionModal.classList.contains("hidden")) {
    hideAdminQuestionCard();
  }

  renderBoard(lastBoard, lastAllQuestionsUsed);
}

function showAdminAnswerReveal(answerReveal) {
  if (!answerReveal || !answerReveal.sequence_id) {
    return;
  }

  const sequenceId = String(answerReveal.sequence_id);
  const adminRevealUntilMs = Number(answerReveal.admin_reveal_until_ms);
  const playerRevealUntilMs = Number(answerReveal.player_reveal_until_ms);
  const nowMs = getServerNowMs();

  clearAnswerRevealTimers();
  activeAnswerRevealSequenceId = sequenceId;
  answerRevealInProgress = Number.isFinite(playerRevealUntilMs)
    ? playerRevealUntilMs > nowMs
    : true;
  currentQuestion = null;
  stopAuctionSound();

  if (!Number.isFinite(adminRevealUntilMs) || adminRevealUntilMs > nowMs) {
    questionModal.classList.remove("hidden");
    adminQuestionCard.classList.remove("auction-question-card");
    renderAdminQuestionImage(null);
    adminQuestionCategory.textContent = "Ответы зафиксированы";
    adminQuestionTitle.textContent = "Правильный ответ";
    updateAdminQuestionTitleScale("Правильный ответ");
    adminQuestionOptions.innerHTML = `
      <div class="admin-option-preview text-question-preview correct-answer-preview">
        ${escapeHtml(answerReveal.correct_answer || "—")}
      </div>
    `;
    const remainingPlayerSeconds = Number.isFinite(playerRevealUntilMs)
      ? Math.max(0, Math.ceil((playerRevealUntilMs - nowMs) / 1000))
      : 10;
    const hint = document.querySelector("#admin-question-card .question-close-hint");
    if (hint) {
      hint.textContent = `Игроки видят ответ ещё ${remainingPlayerSeconds} сек.`;
    }

    const adminRemainingMs = Number.isFinite(adminRevealUntilMs)
      ? Math.max(0, adminRevealUntilMs - nowMs)
      : 5000;

    answerRevealAdminTimeoutId = window.setTimeout(() => {
      answerRevealAdminTimeoutId = null;
      hideAdminQuestionCard();
    }, adminRemainingMs);
  } else {
    hideAdminQuestionCard();
  }

  renderBoard(lastBoard, lastAllQuestionsUsed);

  const finishRemainingMs = Number.isFinite(playerRevealUntilMs)
    ? Math.max(0, playerRevealUntilMs - nowMs)
    : 10000;

  answerRevealFinishTimeoutId = window.setTimeout(() => {
    answerRevealFinishTimeoutId = null;
    finishAdminAnswerReveal(sequenceId);
  }, finishRemainingMs);
}

function renderBoard(board, allQuestionsUsed) {
  lastBoard = Array.isArray(board) ? board : [];
  lastAllQuestionsUsed = Boolean(allQuestionsUsed);
  adminBoard.innerHTML = "";

  lastBoard.forEach((row) => {
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
      } else if (answerRevealInProgress) {
        questionCell.disabled = true;
        questionCell.classList.add("temporarily-disabled");
        questionCell.title = "Дождитесь окончания показа правильного ответа";
      }

      questionCell.addEventListener("click", () => {
        openQuestion(question.id);
      });

      adminBoard.appendChild(questionCell);
    });
  });

  finalRoundButton.disabled = !lastAllQuestionsUsed || answerRevealInProgress;
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
  if (currentQuestion && currentQuestion.is_auction) {
    stopAuctionSound();
  }

  currentQuestion = null;
  questionModal.classList.add("hidden");
  adminQuestionCard.classList.remove("auction-question-card");
  renderAdminQuestionImage(null);
  adminQuestionCategory.textContent = "";
  adminQuestionTitle.textContent = "";
  updateAdminQuestionTitleScale();
  adminQuestionOptions.innerHTML = "";
  const hint = document.querySelector("#admin-question-card .question-close-hint");
  if (hint) {
    hint.textContent = "Нажмите на карточку, чтобы закрыть вопрос";
  }
}

function showFinalModal(counts = { boy: 0, girl: 0 }) {
  clearFinalSequenceTimers();
  activeFinalSequenceId = null;
  isFinalRevealing = false;
  isFinalRevealed = false;

  stopAudio(drumrollAudio);
  stopAudio(babyLaughterAudio);

  finalModal.classList.remove("hidden");
  finalCard.classList.remove("final-drumroll-card", "final-reveal-card");
  finalTitle.textContent = "Кто родится?";
  finalAdminChoices.classList.remove("hidden");
  finalHint.textContent = "Нажмите на карточку, чтобы раскрыть ответ";
  updateFinalCounts(counts);
}

function updateFinalCounts(counts) {
  boyVotesCount.textContent = String(counts.boy || 0);
  girlVotesCount.textContent = String(counts.girl || 0);
}

function showFinalDrumroll(schedule = null) {
  finalModal.classList.remove("hidden");
  finalCard.classList.remove("final-reveal-card");
  finalCard.classList.add("final-drumroll-card");
  finalTitle.textContent = "Барабанная дробь...";
  finalAdminChoices.classList.add("hidden");
  finalHint.textContent = "";
  isFinalRevealing = true;
  isFinalRevealed = false;

  const drumrollStartAtMs = Number(schedule && schedule.drumroll_start_at_ms);
  const elapsedMs = Number.isFinite(drumrollStartAtMs)
    ? Math.max(0, getServerNowMs() - drumrollStartAtMs)
    : 0;

  stopAudio(drumrollAudio);
  playAudio(drumrollAudio, {
    offsetSeconds: Math.min(elapsedMs / 1000, 6.9),
  });
}

function showFinalReveal(answer = "boy", sequenceId = null, playSound = true) {
  const alreadyShowingThisReveal = isFinalRevealed
    && (!sequenceId || activeFinalSequenceId === sequenceId);

  finalModal.classList.remove("hidden");
  finalCard.classList.remove("final-drumroll-card");
  finalCard.classList.add("final-reveal-card");
  finalAdminChoices.classList.add("hidden");

  isFinalRevealing = false;
  isFinalRevealed = true;
  finalTitle.textContent = answer === "girl" ? "ДЕВОЧКА!" : "МАЛЬЧИК!";
  finalHint.textContent = "Нажмите, чтобы перейти к секретному раунду";

  stopAudio(drumrollAudio);

  if (playSound && sequenceId !== lastBabySoundSequenceId) {
    lastBabySoundSequenceId = sequenceId;
    stopAudio(babyLaughterAudio);
    playAudio(babyLaughterAudio);
  }

  if (!alreadyShowingThisReveal && typeof window.launchGenderConfetti === "function") {
    window.launchGenderConfetti();
  }
}

function scheduleFinalDrumroll(schedule) {
  if (!schedule || !schedule.sequence_id) {
    return;
  }

  const sequenceId = String(schedule.sequence_id);
  const drumrollStartAtMs = Number(schedule.drumroll_start_at_ms);
  const revealAtMs = Number(schedule.reveal_at_ms);

  if (!Number.isFinite(drumrollStartAtMs) || !Number.isFinite(revealAtMs)) {
    return;
  }

  if (activeFinalSequenceId !== sequenceId) {
    clearFinalSequenceTimers();
    activeFinalSequenceId = sequenceId;
  }

  finalModal.classList.remove("hidden");
  finalAdminChoices.classList.add("hidden");
  isFinalRevealing = true;

  if (getServerNowMs() >= drumrollStartAtMs) {
    if (!finalCard.classList.contains("final-drumroll-card") && !isFinalRevealed) {
      showFinalDrumroll(schedule);
    }
  } else if (drumrollStartTimeoutId === null) {
    drumrollStartTimeoutId = scheduleForServerTime(drumrollStartAtMs, () => {
      drumrollStartTimeoutId = null;
      showFinalDrumroll(schedule);
    });
  }
}

function scheduleFinalRevealDisplay(data) {
  const sequenceId = String(data.sequence_id || activeFinalSequenceId || "");
  const revealAtMs = Number(data.reveal_at_ms);
  const answer = data.answer || "boy";

  if (!Number.isFinite(revealAtMs)) {
    showFinalReveal(answer, sequenceId);
    return;
  }

  if (activeFinalSequenceId && sequenceId && activeFinalSequenceId !== sequenceId) {
    return;
  }

  activeFinalSequenceId = sequenceId || activeFinalSequenceId;

  if (finalRevealTimeoutId !== null) {
    window.clearTimeout(finalRevealTimeoutId);
  }

  finalRevealTimeoutId = scheduleForServerTime(revealAtMs, () => {
    finalRevealTimeoutId = null;
    showFinalReveal(answer, sequenceId);
  });
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
  clearFinalSequenceTimers();
  stopAuctionSound();
  stopAudio(drumrollAudio);
  stopAudio(babyLaughterAudio);
  activeFinalSequenceId = null;
  lastBabySoundSequenceId = null;

  renderBoard(data.board || [], Boolean(data.all_questions_used));
  renderRating(data.players || []);
}

async function revealFinalRound() {
  if (isFinalRevealing || isFinalRevealed) {
    return;
  }

  isFinalRevealing = true;
  await unlockAdminAudio();

  try {
    const response = await fetchWithTimeout("/api/admin/final/reveal", {
      method: "POST",
    });

    const data = await response.json();

    if (!response.ok) {
      isFinalRevealing = false;
      alert(data.message || "Не удалось раскрыть финальный ответ.");
      return;
    }

    scheduleFinalDrumroll(data.schedule);
  } catch (error) {
    isFinalRevealing = false;
    alert("Не удалось запланировать финальное раскрытие. Проверьте соединение с сервером.");
  }
}

async function loadCurrentGameState() {
  const response = await fetchWithTimeout("/api/game-state");

  if (!response.ok) {
    return;
  }

  const data = await response.json();
  const phase = data.state && data.state.current_phase;

  if (phase === "answer_reveal") {
    showAdminAnswerReveal(data.answer_reveal);
    return;
  }

  if (answerRevealInProgress) {
    finishAdminAnswerReveal();
  }

  if (phase === "final_open") {
    if (finalModal.classList.contains("hidden") || isFinalRevealed || isFinalRevealing) {
      showFinalModal(data.final_counts || { boy: 0, girl: 0 });
    } else {
      updateFinalCounts(data.final_counts || { boy: 0, girl: 0 });
    }
    return;
  }

  if (phase === "final_drumroll" || phase === "final_revealing") {
    updateFinalCounts(data.final_counts || { boy: 0, girl: 0 });
    scheduleFinalDrumroll(data.final_schedule);
    return;
  }

  if (phase === "final_revealed") {
    const schedule = data.final_schedule;
    const revealAtMs = Number(schedule && schedule.reveal_at_ms);
    const sequenceId = schedule && schedule.sequence_id;

    if (Number.isFinite(revealAtMs) && getServerNowMs() < revealAtMs) {
      scheduleFinalDrumroll(schedule);
      scheduleFinalRevealDisplay({
        answer: data.state.actual_gender || "boy",
        sequence_id: sequenceId,
        reveal_at_ms: revealAtMs,
      });
    } else {
      showFinalReveal(
        data.state.actual_gender || "boy",
        sequenceId,
        false,
      );
    }
    return;
  }

  if (phase === "secret_names") {
    showSecretModal(data.baby_names || []);
    return;
  }

  if (!data.question || !data.state || !data.state.question_open) {
    return;
  }

  if (phase === "auction_bidding") {
    renderAdminQuestionCard(data.question, data.auction || null);
    playAuctionSound();
    return;
  }

  if (phase === "auction_question") {
    stopAuctionSound();
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
    if (
      data.error === "question_already_open"
      || data.error === "answer_reveal_in_progress"
    ) {
      if (data.answer_reveal) {
        showAdminAnswerReveal(data.answer_reveal);
      } else {
        await loadCurrentGameState();
      }
      return;
    }

    alert(data.message || "Не удалось открыть вопрос.");
    return;
  }

  if (data.question && data.question.is_auction) {
    playAuctionSound();
  }

  renderAdminQuestionCard(data.question, data.auction || null);
}

async function closeCurrentQuestion() {
  if (answerRevealInProgress || isClosingQuestion) {
    return;
  }

  if (!currentQuestion) {
    await loadCurrentGameState();

    if (!currentQuestion) {
      alert("Сейчас нет открытой карточки вопроса. Состояние игры обновлено.");
      return;
    }
  }

  isClosingQuestion = true;
  adminQuestionCard.classList.add("is-processing");

  try {
    let response;

    try {
      response = await fetchWithTimeout("/api/admin/questions/current/close", {
        method: "POST",
        timeoutMs: 15000,
      });
    } catch (firstError) {
      if (!socket.connected) {
        socket.connect();
      }

      await new Promise((resolve) => window.setTimeout(resolve, 350));
      response = await fetchWithTimeout("/api/admin/questions/current/close", {
        method: "POST",
        timeoutMs: 15000,
      });
    }

    const data = await response.json();

    if (!response.ok) {
      if (data.error === "no_open_question") {
        hideAdminQuestionCard();
        await loadBoard();
        return;
      }

      if (data.error === "answer_reveal_in_progress" && data.answer_reveal) {
        showAdminAnswerReveal(data.answer_reveal);
        return;
      }

      alert(data.message || "Не удалось закрыть вопрос.");
      return;
    }

    renderBoard(data.board || [], Boolean(data.all_questions_used));
    renderRating(data.players || []);

    if (data.answer_reveal) {
      showAdminAnswerReveal(data.answer_reveal);
    } else {
      hideAdminQuestionCard();
    }
  } catch (error) {
    await loadCurrentGameState();

    if (!answerRevealInProgress) {
      alert(
        "Не удалось закрыть вопрос. Состояние игры обновлено; попробуйте нажать карточку ещё раз."
      );
    }
  } finally {
    isClosingQuestion = false;
    adminQuestionCard.classList.remove("is-processing");
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

document.addEventListener("pointerdown", () => {
  unlockAdminAudio();
}, { once: true });

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
  adminQuestionCard.addEventListener("click", () => {
    if (answerRevealInProgress) {
      return;
    }

    closeCurrentQuestion();
  });
}

if (resetGameButton) {
  resetGameButton.addEventListener("click", resetGame);
}

if (finalResetGameButton) {
  finalResetGameButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    resetGame();
  });
}

if (secretResetGameButton) {
  secretResetGameButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    resetGame();
  });
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

socket.on("game_reset", () => {
  clearFinalSequenceTimers();
  stopAuctionSound();
  stopAudio(drumrollAudio);
  stopAudio(babyLaughterAudio);
  activeFinalSequenceId = null;
  clearAnswerRevealTimers();
  activeAnswerRevealSequenceId = null;
  answerRevealInProgress = false;
  isFinalRevealing = false;
  isFinalRevealed = false;
});


socket.on("question_opened", (data) => {
  if (data.question) {
    renderAdminQuestionCard(data.question);
  }
});

socket.on("question_closed", (data) => {
  stopAuctionSound();
  renderBoard(data.board || [], Boolean(data.all_questions_used));

  if (data.answer_reveal) {
    showAdminAnswerReveal(data.answer_reveal);
  } else {
    hideAdminQuestionCard();
  }
});

socket.on("answer_reveal_finished", (data) => {
  finishAdminAnswerReveal(String(data && data.sequence_id || ""));
});

socket.on("connect", () => {
  socket.emit("admin_request_board");
  loadCurrentGameState();
});

socket.on("auction_started", (data) => {
  if (!data.auction) {
    return;
  }

  playAuctionSound();

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

  stopAuctionSound();
  renderAdminQuestionCard(currentQuestion, null, data.winner);
});

socket.on("final_started", (data) => {
  showFinalModal(data.counts || { boy: 0, girl: 0 });
});

socket.on("final_vote_updated", (data) => {
  updateFinalCounts(data.counts || { boy: 0, girl: 0 });
});

socket.on("final_reveal_scheduled", (data) => {
  scheduleFinalDrumroll(data.schedule);
});

socket.on("final_revealed", (data) => {
  scheduleFinalRevealDisplay(data);
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
  if (adminStateRefreshInProgress || isClosingQuestion) {
    return;
  }

  adminStateRefreshInProgress = true;

  try {
    if (!socket.connected) {
      socket.connect();
    }

    await loadBoard();
    socket.emit("admin_request_rating");
  } catch (error) {
    console.warn("Не удалось обновить состояние админки после простоя.", error);
  } finally {
    adminStateRefreshInProgress = false;
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

window.setInterval(() => {
  if (!document.hidden) {
    refreshAdminStateAfterIdle();
  }
}, 30000);

loadBoard();
if (adminQuestionImage) {
  adminQuestionImage.addEventListener("error", () => {
    adminQuestionImageWrap.classList.add("hidden");
    adminQuestionCard.classList.remove("has-question-image");
  });
}
