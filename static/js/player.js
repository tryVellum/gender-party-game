const DEVICE_TOKEN_KEY = "gender_party_device_token";

const nicknameView = document.getElementById("nickname-view");
const playerView = document.getElementById("player-view");
const nicknameForm = document.getElementById("nickname-form");
const nicknameInput = document.getElementById("nickname-input");
const nicknameError = document.getElementById("nickname-error");
const playerGreeting = document.getElementById("player-greeting");
const playerScore = document.getElementById("player-score");

const waitingState = document.getElementById("waiting-state");
const questionState = document.getElementById("question-state");
const playerQuestionMeta = document.getElementById("player-question-meta");
const playerQuestionTitle = document.getElementById("player-question-title");
const playerQuestionImageWrap = document.getElementById("player-question-image-wrap");
const playerQuestionImage = document.getElementById("player-question-image");
const playerAnswerArea = document.getElementById("player-answer-area");
const playerAnswerStatus = document.getElementById("player-answer-status");

const finalState = document.getElementById("final-state");
const initialFinalStateMarkup = finalState ? finalState.innerHTML : "";
let finalBoyButton = document.getElementById("final-boy-button");
let finalGirlButton = document.getElementById("final-girl-button");
let finalPlayerStatus = document.getElementById("final-player-status");

const secretState = document.getElementById("secret-state");
const babyNameForm = document.getElementById("baby-name-form");
const babyNameInput = document.getElementById("baby-name-input");
const babyNameStatus = document.getElementById("baby-name-status");
const babyNamesList = document.getElementById("baby-names-list");

let currentPlayer = null;
let currentQuestion = null;
let selectedAnswer = null;
let lastResultTimeoutId = null;
let currentAuction = null;
let auctionWinner = null;
let activeFinalSequenceId = null;
let finalDrumrollTimeoutId = null;
let finalRevealTimeoutId = null;

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

function clearFinalSequenceTimers() {
  if (finalDrumrollTimeoutId !== null) {
    window.clearTimeout(finalDrumrollTimeoutId);
    finalDrumrollTimeoutId = null;
  }

  if (finalRevealTimeoutId !== null) {
    window.clearTimeout(finalRevealTimeoutId);
    finalRevealTimeoutId = null;
  }
}

function createDeviceToken() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }

  if (window.crypto && typeof window.crypto.getRandomValues === "function") {
    const values = new Uint32Array(4);
    window.crypto.getRandomValues(values);

    return [
      Date.now().toString(36),
      values[0].toString(36),
      values[1].toString(36),
      values[2].toString(36),
      values[3].toString(36),
    ].join("-");
  }

  return [
    Date.now().toString(36),
    Math.random().toString(36).slice(2),
    Math.random().toString(36).slice(2),
  ].join("-");
}

function getOrCreateDeviceToken() {
  let deviceToken = localStorage.getItem(DEVICE_TOKEN_KEY);

  if (!deviceToken) {
    deviceToken = createDeviceToken();
    localStorage.setItem(DEVICE_TOKEN_KEY, deviceToken);
  }

  return deviceToken;
}

function showNicknameView() {
  nicknameView.classList.remove("hidden");
  playerView.classList.add("hidden");
}

function showPlayerView(player) {
  currentPlayer = player;

  nicknameView.classList.add("hidden");
  playerView.classList.remove("hidden");

  playerGreeting.textContent = `Привет, ${player.nickname}!`;
  playerScore.textContent = String(player.score);
}

function showNicknameError(message) {
  nicknameError.textContent = message;
}

function showWaitingState() {
  currentQuestion = null;
  selectedAnswer = null;
  currentAuction = null;
  auctionWinner = null;
  activeFinalSequenceId = null;
  clearFinalSequenceTimers();

  waitingState.classList.remove("hidden");
  questionState.classList.add("hidden");

  if (finalState) {
    finalState.classList.add("hidden");
  }

  if (secretState) {
    secretState.classList.add("hidden");
  }

  playerQuestionMeta.textContent = "";
  playerQuestionTitle.textContent = "";
  renderPlayerQuestionImage(null);
  playerAnswerArea.innerHTML = "";
  playerAnswerStatus.textContent = "";
}


function showWaitingStateWithResult(resultText) {
  showWaitingState();

  if (lastResultTimeoutId) {
    clearTimeout(lastResultTimeoutId);
  }

  waitingState.innerHTML = `
    <div class="result-message">
      ${resultText}
    </div>
  `;

  lastResultTimeoutId = window.setTimeout(() => {
    waitingState.innerHTML = `
      <p class="status-text">
        Ждём начала игры...
      </p>
    `;
  }, 3500);
}


function renderPlayerQuestionImage(question, visible = true) {
  const imageUrl = visible && question ? question.image_url : null;

  questionState.classList.toggle("has-question-image", Boolean(imageUrl));

  if (!imageUrl) {
    playerQuestionImageWrap.classList.add("hidden");
    playerQuestionImage.removeAttribute("src");
    playerQuestionImage.alt = "";
    return;
  }

  playerQuestionImage.src = imageUrl;
  playerQuestionImage.alt = `Иллюстрация к вопросу: ${question.question}`;
  playerQuestionImageWrap.classList.remove("hidden");
}

function showQuestionState(question, savedAnswer = null, extra = {}) {
  currentQuestion = question;
  selectedAnswer = savedAnswer ? savedAnswer.answer : null;
  currentAuction = extra.auction || null;
  auctionWinner = extra.auctionWinner || null;

  waitingState.classList.add("hidden");
  questionState.classList.remove("hidden");

  if (finalState) {
    finalState.classList.add("hidden");
  }

  if (secretState) {
    secretState.classList.add("hidden");
  }

  playerQuestionMeta.textContent = `${question.category} · ${question.points} баллов`;

  if (question.is_auction && extra.mode === "bid") {
    renderPlayerQuestionImage(null);
    playerQuestionTitle.textContent = "АУКЦИОН";
    renderAuctionBidForm(extra.auctionBid || null, extra.auction || null);
    return;
  }

  if (question.is_auction && extra.mode === "wait_winner") {
    renderPlayerQuestionImage(null);
    playerQuestionTitle.textContent = "АУКЦИОН";
    renderAuctionWaitingWinner(extra.winner);
    return;
  }

  if (question.is_auction && extra.mode === "winner_question") {
    playerQuestionTitle.textContent = question.question;
  } else {
    playerQuestionTitle.textContent = question.question;
  }

  renderPlayerQuestionImage(question);

  playerAnswerStatus.textContent = selectedAnswer
    ? `Ответ сохранён: ${selectedAnswer}`
    : "";

  if (question.type === "choice") {
    renderChoiceAnswers(question.options);
    return;
  }

  renderTextAnswer();
}

function bindFinalVoteButtons() {
  if (finalBoyButton && finalBoyButton.dataset.voteHandlerBound !== "1") {
    finalBoyButton.dataset.voteHandlerBound = "1";
    finalBoyButton.addEventListener("click", () => {
      submitFinalVote("boy");
    });
  }

  if (finalGirlButton && finalGirlButton.dataset.voteHandlerBound !== "1") {
    finalGirlButton.dataset.voteHandlerBound = "1";
    finalGirlButton.addEventListener("click", () => {
      submitFinalVote("girl");
    });
  }
}

function restoreFinalChoiceMarkup() {
  if (!finalState) {
    return;
  }

  if (!finalState.querySelector("#final-boy-button")) {
    finalState.innerHTML = initialFinalStateMarkup;
  }

  finalBoyButton = document.getElementById("final-boy-button");
  finalGirlButton = document.getElementById("final-girl-button");
  finalPlayerStatus = document.getElementById("final-player-status");
  bindFinalVoteButtons();
}

function showFinalState(savedVote = null) {
  restoreFinalChoiceMarkup();

  currentQuestion = null;
  selectedAnswer = null;
  activeFinalSequenceId = null;
  clearFinalSequenceTimers();

  waitingState.classList.add("hidden");
  questionState.classList.add("hidden");
  finalState.classList.remove("hidden");

  if (secretState) {
    secretState.classList.add("hidden");
  }

  const choice = savedVote ? savedVote.choice : null;
  markFinalChoice(choice);

  finalPlayerStatus.textContent = choice
    ? `Ваш выбор: ${choice === "boy" ? "Мальчик" : "Девочка"}`
    : "Выберите один вариант. Выбор можно изменить до раскрытия.";
}

function markFinalChoice(choice) {
  finalBoyButton.classList.toggle("selected", choice === "boy");
  finalGirlButton.classList.toggle("selected", choice === "girl");
}

async function submitFinalVote(choice) {
  const deviceToken = getOrCreateDeviceToken();

  const response = await fetch("/api/player/final-vote", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_token: deviceToken,
      choice,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    finalPlayerStatus.textContent = data.message || "Не удалось сохранить выбор.";
    return;
  }

  markFinalChoice(choice);
  finalPlayerStatus.textContent = `Ваш выбор: ${choice === "boy" ? "Мальчик" : "Девочка"}`;
}

function showFinalDrumrollForPlayer() {
  waitingState.classList.add("hidden");
  questionState.classList.add("hidden");
  finalState.classList.remove("hidden");

  if (secretState) {
    secretState.classList.add("hidden");
  }

  finalState.innerHTML = `
    <div class="final-player-reveal drumroll">
      <p>Барабанная дробь...</p>
    </div>
  `;
}

function showFinalRevealForPlayer(
  scoreUpdates = [],
  finalResult = null,
  answer = "boy",
) {
  const myUpdate = currentPlayer
    ? scoreUpdates.find((item) => Number(item.player_id) === Number(currentPlayer.id))
    : null;

  const resultingScore = myUpdate
    ? Number(myUpdate.score)
    : finalResult && Number.isFinite(Number(finalResult.score))
      ? Number(finalResult.score)
      : null;

  if (currentPlayer && resultingScore !== null) {
    currentPlayer.score = resultingScore;
    playerScore.textContent = String(resultingScore);
  }

  const isCorrect = myUpdate
    ? true
    : Boolean(finalResult && finalResult.is_correct);

  const answerLabel = answer === "girl" ? "девочка" : "мальчик";
  const answerTitle = answer === "girl" ? "ДЕВОЧКА!" : "МАЛЬЧИК!";

  const resultText = isCorrect && resultingScore !== null
    ? `Вы угадали! Ваши баллы удвоены: ${resultingScore}`
    : `Ответ: ${answerLabel}! Ваши баллы не изменились.`;

  finalState.innerHTML = `
    <div class="final-player-reveal ${answer === "girl" ? "girl" : "boy"}">
      <p>Это</p>
      <strong>${answerTitle}</strong>
      <span>${resultText}</span>
    </div>
  `;

  if (typeof window.launchGenderConfetti === "function") {
    window.launchGenderConfetti();
  }
}

function scheduleFinalDrumrollForPlayer(schedule) {
  if (!schedule || !schedule.sequence_id) {
    return;
  }

  const sequenceId = String(schedule.sequence_id);
  const drumrollStartAtMs = Number(schedule.drumroll_start_at_ms);

  if (!Number.isFinite(drumrollStartAtMs)) {
    return;
  }

  if (activeFinalSequenceId !== sequenceId) {
    clearFinalSequenceTimers();
    activeFinalSequenceId = sequenceId;
  }

  if (getServerNowMs() >= drumrollStartAtMs) {
    showFinalDrumrollForPlayer();
    return;
  }

  if (finalDrumrollTimeoutId !== null) {
    return;
  }

  finalDrumrollTimeoutId = scheduleForServerTime(drumrollStartAtMs, () => {
    finalDrumrollTimeoutId = null;
    showFinalDrumrollForPlayer();
  });
}

function scheduleFinalRevealForPlayer(data, finalResult = null) {
  const sequenceId = String(data.sequence_id || activeFinalSequenceId || "");
  const revealAtMs = Number(data.reveal_at_ms);
  const answer = data.answer || "boy";
  const scoreUpdates = data.score_updates || [];

  if (activeFinalSequenceId && sequenceId && activeFinalSequenceId !== sequenceId) {
    return;
  }

  activeFinalSequenceId = sequenceId || activeFinalSequenceId;

  if (!Number.isFinite(revealAtMs)) {
    showFinalRevealForPlayer(scoreUpdates, finalResult, answer);
    return;
  }

  if (finalRevealTimeoutId !== null) {
    window.clearTimeout(finalRevealTimeoutId);
  }

  finalRevealTimeoutId = scheduleForServerTime(revealAtMs, () => {
    finalRevealTimeoutId = null;
    showFinalRevealForPlayer(scoreUpdates, finalResult, answer);
  });
}

// function renderAuctionPlaceholder() {
//   playerAnswerArea.innerHTML = `
//     <div class="auction-player-card">
//       <p>Это аукционный вопрос.</p>
//       <p>Ставки добавим на следующем этапе.</p>
//     </div>
//   `;
// }

function renderAuctionBidForm(existingBid = null, auction = currentAuction) {
  const playerScoreValue = currentPlayer ? Number(currentPlayer.score) : 0;
  const participantPlayerIds = auction && Array.isArray(auction.participant_player_ids)
    ? auction.participant_player_ids.map(Number)
    : null;
  const isConfirmedParticipant = !participantPlayerIds
    || (currentPlayer && participantPlayerIds.includes(Number(currentPlayer.id)));

  if (existingBid) {
    playerAnswerArea.innerHTML = `
      <div class="auction-player-card">
        <p>Ваша ставка принята:</p>
        <strong>${existingBid.bid}</strong>
        <p>Ждём ставки остальных игроков...</p>
      </div>
    `;
    playerAnswerStatus.textContent = "";
    return;
  }

  if (playerScoreValue <= 0) {
    playerAnswerArea.innerHTML = `
      <div class="auction-player-card">
        <p>У вас ${playerScoreValue} баллов.</p>
        <p>Вы не участвуете в этом аукционе, потому что для ставки нужны положительные баллы.</p>
        <p>Ожидаем завершения ставок других игроков...</p>
        </div>
    `;
    playerAnswerStatus.textContent = "";
    return;
  }

  if (!isConfirmedParticipant) {
    playerAnswerArea.innerHTML = `
      <div class="auction-player-card">
        <p>Перед началом аукциона устройство не подтвердило активное подключение.</p>
        <p>В этом аукционе ставка недоступна. Не закрывайте страницу перед следующим аукционом.</p>
      </div>
    `;
    playerAnswerStatus.textContent = "";
    return;
  }

  playerAnswerArea.innerHTML = `
    <form id="auction-bid-form" class="text-answer-form">
      <p class="auction-bid-help">
        Ваши баллы: <strong>${playerScoreValue}</strong>
      </p>

      <input
        id="auction-bid-input"
        class="text-input"
        type="number"
        min="0"
        max="${playerScoreValue}"
        placeholder="Введите ставку"
        required
      >

      <button class="primary-button" type="submit">
        Поставить
      </button>
    </form>
  `;

  const form = document.getElementById("auction-bid-form");
  const input = document.getElementById("auction-bid-input");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const bid = Number(input.value);

    if (!Number.isInteger(bid)) {
      playerAnswerStatus.textContent = "Введите ставку целым числом.";
      return;
    }

    await submitAuctionBid(bid);
  });
}

function renderAuctionWaitingWinner(winner) {
  if (!winner) {
    playerAnswerArea.innerHTML = `
      <div class="auction-player-card">
        <p>Ставки завершены.</p>
        <p>Определяем победителя...</p>
      </div>
    `;
    return;
  }

  playerAnswerArea.innerHTML = `
    <div class="auction-player-card">
      <p>Вопрос достался игроку:</p>
      <strong>${winner.nickname}</strong>
      <p>Ставка: ${winner.bid}</p>
      <p>Ожидаем ответ победителя...</p>
    </div>
  `;
}

function showSecretState(names = []) {
  currentQuestion = null;
  selectedAnswer = null;

  waitingState.classList.add("hidden");
  questionState.classList.add("hidden");
  finalState.classList.add("hidden");
  secretState.classList.remove("hidden");

  updateBabyNameFormVisibility(names);
  renderBabyNames(names);
}

function updateBabyNameFormVisibility(names = []) {
  if (!babyNameForm || !currentPlayer) {
    return;
  }

  const myName = names.find((item) => {
    return Number(item.created_by_player_id) === Number(currentPlayer.id);
  });

  if (myName) {
    babyNameForm.classList.add("hidden");
    babyNameStatus.textContent = `Вы уже предложили имя: ${myName.display_name}`;
    return;
  }

  babyNameForm.classList.remove("hidden");
}

function renderBabyNames(names) {
  names = [...names].sort((first, second) => {
    return Number(second.rating) - Number(first.rating);
  });

  if (!names.length) {
    babyNamesList.innerHTML = `
      <div class="auction-player-card">
        <p>Пока никто не предложил имя.</p>
      </div>
    `;
    return;
  }

  babyNamesList.innerHTML = names
    .map((item) => {
      return `
        <div class="baby-name-item">
          <div>
            <strong>${item.display_name}</strong>
            <span>Рейтинг: ${item.rating}</span>
          </div>

          <form class="baby-name-vote-form" data-name-id="${item.id}">
            <input
              class="text-input baby-name-vote-input"
              type="number"
              min="1"
              placeholder="Баллы"
              required
            >
            <button class="secondary-button" type="submit">
              Отдать
            </button>
          </form>
        </div>
      `;
    })
    .join("");

  document.querySelectorAll(".baby-name-vote-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const input = form.querySelector(".baby-name-vote-input");
      const nameId = Number(form.dataset.nameId);
      const amount = Number(input.value);

      if (!Number.isInteger(amount) || amount <= 0) {
        babyNameStatus.textContent = "Введите количество баллов.";
        return;
      }

      await voteForBabyName(nameId, amount);
    });
  });
}

async function submitBabyName(name) {
  const deviceToken = getOrCreateDeviceToken();

  const response = await fetch("/api/player/baby-name", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_token: deviceToken,
      name,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    babyNameStatus.textContent = data.message || "Не удалось отправить имя.";
    return;
  }

  babyNameInput.value = "";
  babyNameStatus.textContent = "Имя отправлено.";
  updateBabyNameFormVisibility(data.names || []);
  renderBabyNames(data.names || []);
}

async function voteForBabyName(nameId, amount) {
  const deviceToken = getOrCreateDeviceToken();

  const response = await fetch("/api/player/baby-name-vote", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_token: deviceToken,
      name_id: nameId,
      amount,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    babyNameStatus.textContent = data.message || "Не удалось отдать баллы.";
    return;
  }

  if (data.score_update && currentPlayer) {
    currentPlayer.score = data.score_update.score;
    playerScore.textContent = String(data.score_update.score);
  }

  babyNameStatus.textContent = "Баллы отданы.";
  renderBabyNames(data.names || []);
}

async function submitAuctionBid(bid) {
  if (!currentQuestion) {
    return;
  }

  const deviceToken = getOrCreateDeviceToken();

  const response = await fetch("/api/player/auction-bid", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_token: deviceToken,
      question_id: currentQuestion.id,
      bid,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    playerAnswerStatus.textContent = data.message || "Не удалось сохранить ставку.";
    return;
  }

  playerAnswerStatus.textContent = "Ставка сохранена.";

  if (data.winner) {
    if (currentPlayer && data.winner.player_id === currentPlayer.id && data.question) {
      showQuestionState(data.question, null, {
        mode: "winner_question",
        auctionWinner: data.winner,
      });
      return;
    }

    showQuestionState(currentQuestion, null, {
      mode: "wait_winner",
      winner: data.winner,
    });
    return;
  }

  renderAuctionBidForm({
    bid,
  }, currentAuction);
}

function renderChoiceAnswers(options) {
  playerAnswerArea.innerHTML = "";

  options.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "answer-button";
    button.textContent = option;

    if (option === selectedAnswer) {
      button.classList.add("selected");
    }

    button.addEventListener("click", async () => {
      selectedAnswer = option;
      await submitAnswer(option);
      renderChoiceAnswers(options);
    });

    playerAnswerArea.appendChild(button);
  });
}

function renderTextAnswer() {
  playerAnswerArea.innerHTML = `
    <form id="text-answer-form" class="text-answer-form">
      <input
        id="text-answer-input"
        class="text-input"
        type="text"
        placeholder="Введите ответ"
        autocomplete="off"
        required
      >
      <button class="primary-button" type="submit">
        Отправить ответ
      </button>
    </form>
  `;

  const form = document.getElementById("text-answer-form");
  const input = document.getElementById("text-answer-input");

  if (selectedAnswer) {
    input.value = selectedAnswer;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const answer = input.value.trim();

    if (!answer) {
      playerAnswerStatus.textContent = "Введите ответ.";
      return;
    }

    selectedAnswer = answer;
    await submitAnswer(answer);
  });
}

async function submitAnswer(answer) {
  if (!currentQuestion) {
    return;
  }

  const deviceToken = getOrCreateDeviceToken();

  const response = await fetch("/api/player/answer", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_token: deviceToken,
      question_id: currentQuestion.id,
      answer,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    playerAnswerStatus.textContent = data.message || "Не удалось сохранить ответ.";
    return;
  }

  playerAnswerStatus.textContent = `Ответ сохранён: ${answer}`;
}

async function fetchCurrentPlayer(deviceToken) {
  const response = await fetch(`/api/player?device_token=${encodeURIComponent(deviceToken)}`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error("Не удалось получить данные игрока.");
  }

  const data = await response.json();
  return data.player;
}

async function fetchGameState(deviceToken) {
  const response = await fetch(`/api/game-state?device_token=${encodeURIComponent(deviceToken)}`);

  if (!response.ok) {
    throw new Error("Не удалось получить состояние игры.");
  }

  return response.json();
}

async function createPlayer(deviceToken, nickname) {
  const response = await fetch("/api/player", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_token: deviceToken,
      nickname,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || "Не удалось создать игрока.");
  }

  return data.player;
}

bindFinalVoteButtons();

if (babyNameForm) {
  babyNameForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = babyNameInput.value.trim();

    if (!name) {
      babyNameStatus.textContent = "Введите имя.";
      return;
    }

    await submitBabyName(name);
  });
}

function applyGameState(gameState) {
  const phase = gameState.state.current_phase;

  if (phase === "secret_names") {
    showSecretState(gameState.baby_names || []);
    return;
  }

  if (phase === "final_open") {
    showFinalState(gameState.final_vote);
    return;
  }

  if (phase === "final_drumroll" || phase === "final_revealing") {
    scheduleFinalDrumrollForPlayer(gameState.final_schedule);
    return;
  }

  if (phase === "final_revealed") {
    const schedule = gameState.final_schedule;
    const revealAtMs = Number(schedule && schedule.reveal_at_ms);
    const revealData = {
      answer: gameState.state.actual_gender || "boy",
      sequence_id: schedule && schedule.sequence_id,
      reveal_at_ms: revealAtMs,
      score_updates: [],
    };

    if (Number.isFinite(revealAtMs) && getServerNowMs() < revealAtMs) {
      scheduleFinalDrumrollForPlayer(schedule);
      scheduleFinalRevealForPlayer(revealData, gameState.final_result);
    } else {
      showFinalRevealForPlayer(
        [],
        gameState.final_result,
        gameState.state.actual_gender || "boy",
      );
    }
    return;
  }

  if (gameState.question) {
    if (phase === "auction_bidding") {
      showQuestionState(gameState.question, null, {
        mode: "bid",
        auction: gameState.auction,
        auctionBid: gameState.auction_bid,
      });
      return;
    }

    if (phase === "auction_question") {
      if (
        currentPlayer
        && Number(gameState.state.auction_winner_player_id) === Number(currentPlayer.id)
      ) {
        showQuestionState(gameState.question, gameState.player_answer, {
          mode: "winner_question",
          auctionWinner: gameState.auction_winner,
        });
      } else {
        showQuestionState(gameState.question, null, {
          mode: "wait_winner",
          winner: gameState.auction_winner,
        });
      }
      return;
    }

    showQuestionState(gameState.question, gameState.player_answer);
    return;
  }

  showWaitingState();
}

async function initializePlayer() {
  const deviceToken = getOrCreateDeviceToken();

  try {
    const player = await fetchCurrentPlayer(deviceToken);

    if (player) {
      showPlayerView(player);

      socket.emit("player_identify", {
        device_token: deviceToken,
      });

      const gameState = await fetchGameState(deviceToken);

      applyGameState(gameState);

      return;
    }

    showNicknameView();
  } catch (error) {
    showNicknameView();
    showNicknameError("Ошибка подключения. Обновите страницу.");
  }
}

if (nicknameForm) {
  nicknameForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const deviceToken = getOrCreateDeviceToken();
    const nickname = nicknameInput.value.trim();

    showNicknameError("");

    if (!nickname) {
      showNicknameError("Введите никнейм.");
      return;
    }

    try {
      const player = await createPlayer(deviceToken, nickname);
      showPlayerView(player);

      socket.emit("player_identify", {
        device_token: deviceToken,
      });

      const gameState = await fetchGameState(deviceToken);

      applyGameState(gameState);

    } catch (error) {
      showNicknameError(error.message);
    }
  });
}

socket.on("connect", () => {
  const deviceToken = localStorage.getItem(DEVICE_TOKEN_KEY);

  if (!deviceToken) {
    return;
  }

  socket.emit("player_identify", {
    device_token: deviceToken,
  });
});

socket.on("presence_probe", (data) => {
  const probeId = data && data.probe_id;
  const deviceToken = localStorage.getItem(DEVICE_TOKEN_KEY);

  if (!probeId || !deviceToken) {
    return;
  }

  socket.emit("presence_ack", {
    probe_id: probeId,
    device_token: deviceToken,
  });
});

socket.on("player_identified", (data) => {
  if (!data.ok) {
    return;
  }

  showPlayerView(data.player);
});

socket.on("question_opened", (data) => {
  if (!data.question || !currentPlayer) {
    return;
  }

  showQuestionState(data.question);
});

socket.on("question_closed", (data) => {
  if (!currentPlayer) {
    showWaitingState();
    return;
  }

  const scoreUpdates = data.score_updates || [];
  const myUpdate = scoreUpdates.find((item) => item.player_id === currentPlayer.id);

  if (!myUpdate) {
    showWaitingStateWithResult("Ответ не был отправлен. Баллы не изменились.");
    return;
  }

  currentPlayer.score = myUpdate.score;
  playerScore.textContent = String(myUpdate.score);

  const sign = myUpdate.points_delta > 0 ? "+" : "";
  const resultText = myUpdate.is_correct
    ? `Правильно! ${sign}${myUpdate.points_delta} баллов`
    : `Неправильно. ${myUpdate.points_delta} баллов`;

  showWaitingStateWithResult(resultText);
});

socket.on("score_updated", (data) => {
  if (!currentPlayer) {
    return;
  }

  if (data.player_id !== currentPlayer.id) {
    return;
  }

  currentPlayer.score = data.score;
  playerScore.textContent = String(data.score);
});

socket.on("auction_started", (data) => {
  if (!data.auction || !currentPlayer) {
    return;
  }

  showQuestionState(
    {
      id: data.auction.question_id,
      category: "Аукцион",
      points: "",
      is_auction: true,
    },
    null,
    {
      mode: "bid",
      auction: data.auction,
    },
  );
});

socket.on("auction_progress_updated", (data) => {
  currentAuction = data.auction;
});

socket.on("auction_winner_selected", (data) => {
  if (!currentPlayer || !currentQuestion) {
    return;
  }

  const winner = data.winner;

  if (winner.player_id === currentPlayer.id) {
  playerQuestionTitle.textContent = "Вы выиграли аукцион!";
  playerAnswerStatus.textContent = "";
  playerAnswerArea.innerHTML = `
    <div class="auction-player-card">
      <p>Ваша ставка победила:</p>
      <strong>${winner.bid}</strong>
      <p>Сейчас появится вопрос...</p>
    </div>
  `;
  return;
}

  showQuestionState(currentQuestion, null, {
    mode: "wait_winner",
    winner,
  });
});

socket.on("auction_question_for_winner", (data) => {
  if (!data.question || !currentPlayer) {
    return;
  }

  showQuestionState(data.question, null, {
    mode: "winner_question",
    auctionWinner: {
      player_id: currentPlayer.id,
      nickname: currentPlayer.nickname,
      bid: data.bid,
    },
  });
});

socket.on("final_started", () => {
  if (!currentPlayer) {
    return;
  }

  showFinalState();
});

socket.on("final_reveal_scheduled", (data) => {
  if (!currentPlayer) {
    return;
  }

  scheduleFinalDrumrollForPlayer(data.schedule);
});

socket.on("final_revealed", (data) => {
  scheduleFinalRevealForPlayer(data);
});

socket.on("secret_started", (data) => {
  if (!currentPlayer) {
    return;
  }

  showSecretState(data.names || []);
});

socket.on("baby_names_updated", (data) => {
  if (!secretState.classList.contains("hidden")) {
    updateBabyNameFormVisibility(data.names || []);
    renderBabyNames(data.names || []);
  }
});

socket.on("game_reset", () => {
  localStorage.removeItem(DEVICE_TOKEN_KEY);

  currentPlayer = null;
  currentQuestion = null;
  selectedAnswer = null;
  currentAuction = null;
  auctionWinner = null;
  activeFinalSequenceId = null;
  clearFinalSequenceTimers();

  showWaitingState();
  showNicknameView();

  if (nicknameInput) {
    nicknameInput.value = "";
  }

  if (nicknameError) {
    nicknameError.textContent = "Игра сброшена. Введите никнейм заново.";
  }
});

initializePlayer();
if (playerQuestionImage) {
  playerQuestionImage.addEventListener("error", () => {
    playerQuestionImageWrap.classList.add("hidden");
    questionState.classList.remove("has-question-image");
  });
}
