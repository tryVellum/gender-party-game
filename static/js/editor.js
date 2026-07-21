const editorTopics = document.getElementById("editor-topics");
const editorLoading = document.getElementById("editor-loading");
const editorStatus = document.getElementById("editor-status");
const editorFooter = document.getElementById("editor-footer");
const editorSaveButton = document.getElementById("editor-save-button");
const editorSaveBottomButton = document.getElementById("editor-save-bottom-button");
const editorAuctionSummary = document.getElementById("editor-auction-summary");
const choiceOptionTemplate = document.getElementById("choice-option-template");

let editorQuestions = [];
let isEditorSaving = false;
let isEditorDirty = false;
let maxImageBytes = 5 * 1024 * 1024;
let maxOptions = 8;
const previewObjectUrls = new Set();

function setEditorStatus(message = "", kind = "") {
  editorStatus.textContent = message;
  editorStatus.className = "editor-status";
  if (kind) {
    editorStatus.classList.add(`is-${kind}`);
  }
}

function markEditorDirty() {
  isEditorDirty = true;
  setEditorStatus("Есть несохранённые изменения.", "pending");
}

function clearPreviewObjectUrls() {
  previewObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  previewObjectUrls.clear();
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function createElement(tagName, className = "", text = "") {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (text) {
    element.textContent = text;
  }
  return element;
}

function updateAuctionSummary() {
  const selected = document.querySelector('input[name="auction-question"]:checked');
  if (!selected || !selected.value) {
    editorAuctionSummary.textContent = "Аукционный вопрос не выбран.";
    return;
  }

  const card = document.querySelector(`[data-question-id="${CSS.escape(selected.value)}"]`);
  const category = card ? card.dataset.category : "";
  const points = card ? card.dataset.points : "";
  editorAuctionSummary.textContent = `Выбран вопрос: ${category} · ${points} баллов.`;
}

function createAuctionControl(question) {
  const label = createElement("label", "editor-auction-toggle");
  const radio = document.createElement("input");
  radio.type = "radio";
  radio.name = "auction-question";
  radio.value = question.id;
  radio.checked = Boolean(question.is_auction);
  radio.addEventListener("change", () => {
    updateAuctionSummary();
    markEditorDirty();
  });

  const text = createElement("span", "", "Сделать вопрос аукционным");
  label.append(radio, text);
  return label;
}

function addChoiceOptionRow(container, optionValue = "", isCorrect = false) {
  if (container.querySelectorAll(".editor-option-row").length >= maxOptions) {
    setEditorStatus(`Можно добавить не более ${maxOptions} вариантов.`, "error");
    return;
  }

  const fragment = choiceOptionTemplate.content.cloneNode(true);
  const row = fragment.querySelector(".editor-option-row");
  const input = fragment.querySelector(".editor-option-input");
  const correct = fragment.querySelector(".editor-option-correct");
  const removeButton = fragment.querySelector(".editor-remove-option");

  input.value = optionValue;
  correct.checked = isCorrect;
  input.addEventListener("input", markEditorDirty);
  correct.addEventListener("change", markEditorDirty);
  removeButton.addEventListener("click", () => {
    row.remove();
    markEditorDirty();
  });

  container.appendChild(fragment);
}

function renderAnswerEditor(card, question) {
  const answerArea = card.querySelector(".editor-answer-editor");
  const questionType = card.querySelector(".editor-question-type").value;
  answerArea.innerHTML = "";

  if (questionType === "choice") {
    const help = createElement(
      "p",
      "editor-field-help",
      "Отметьте галочкой один или несколько правильных вариантов.",
    );
    const optionsContainer = createElement("div", "editor-options-list");
    const correctAnswers = new Set(
      (question.correct_answers || []).map((answer) => String(answer).toLocaleLowerCase("ru")),
    );
    const options = question.options && question.options.length
      ? question.options
      : ["", "", "", ""];

    options.forEach((option) => {
      addChoiceOptionRow(
        optionsContainer,
        option,
        correctAnswers.has(String(option).toLocaleLowerCase("ru")),
      );
    });

    const addButton = createElement("button", "secondary-button editor-add-option", "+ Добавить вариант");
    addButton.type = "button";
    addButton.addEventListener("click", () => {
      addChoiceOptionRow(optionsContainer);
      markEditorDirty();
    });

    answerArea.append(help, optionsContainer, addButton);
    return;
  }

  const label = createElement("label", "editor-field-label", "Допустимые правильные ответы");
  const help = createElement(
    "p",
    "editor-field-help",
    "Перечислите варианты через запятую или с новой строки.",
  );
  const textarea = createElement("textarea", "editor-text-answers");
  textarea.rows = 4;
  textarea.placeholder = "например: плацента, детское место";
  textarea.value = (question.correct_answers || []).join(", ");
  textarea.addEventListener("input", markEditorDirty);
  label.append(help, textarea);
  answerArea.appendChild(label);
}

function setImagePreview(root, imageUrl, filename = "") {
  const preview = root.querySelector(".editor-image-preview");
  const image = root.querySelector(".editor-image-preview img");
  const filenameElement = root.querySelector(".editor-image-filename");

  if (!imageUrl) {
    preview.classList.add("hidden");
    image.removeAttribute("src");
    image.alt = "";
    filenameElement.textContent = "Изображение не выбрано";
    return;
  }

  image.src = imageUrl;
  image.alt = "Предпросмотр изображения вопроса";
  filenameElement.textContent = filename || "Новое изображение";
  preview.classList.remove("hidden");
}

function createImageEditor(card, question) {
  const wrap = createElement("div", "editor-image-control");
  const title = createElement("span", "editor-field-label-text", "Изображение вопроса");
  const preview = createElement("div", "editor-image-preview hidden");
  const image = document.createElement("img");
  const filename = createElement("span", "editor-image-filename", "Изображение не выбрано");
  preview.append(image, filename);

  const controls = createElement("div", "editor-image-buttons");
  const uploadLabel = createElement("label", "secondary-button editor-upload-button", "Выбрать JPG");
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".jpg,.jpeg,image/jpeg";
  fileInput.className = "editor-image-input";
  uploadLabel.appendChild(fileInput);

  const removeButton = createElement("button", "secondary-button danger-button editor-remove-image", "Убрать фото");
  removeButton.type = "button";
  removeButton.disabled = !question.image;

  card.dataset.originalImage = question.image || "";
  card.dataset.removeImage = "0";

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      return;
    }
    if (file.size > maxImageBytes) {
      fileInput.value = "";
      setEditorStatus("Изображение должно быть не больше 5 МБ.", "error");
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    previewObjectUrls.add(objectUrl);
    card.dataset.removeImage = "0";
    removeButton.disabled = false;
    setImagePreview(wrap, objectUrl, file.name);
    markEditorDirty();
  });

  removeButton.addEventListener("click", () => {
    fileInput.value = "";
    card.dataset.removeImage = "1";
    removeButton.disabled = true;
    setImagePreview(wrap, null);
    markEditorDirty();
  });

  controls.append(uploadLabel, removeButton);
  wrap.append(title, preview, controls);
  setImagePreview(wrap, question.image_url, question.image || "");
  return wrap;
}

function captureAnswerState(card, question) {
  if (question.type === "choice") {
    question.options = [];
    question.correct_answers = [];
    card.querySelectorAll(".editor-option-row").forEach((row) => {
      const value = row.querySelector(".editor-option-input").value.trim();
      if (!value) {
        return;
      }
      question.options.push(value);
      if (row.querySelector(".editor-option-correct").checked) {
        question.correct_answers.push(value);
      }
    });
    return;
  }

  const textarea = card.querySelector(".editor-text-answers");
  if (textarea) {
    question.correct_answers = splitTextAnswers(textarea.value);
  }
}

function createQuestionCard(question) {
  const card = createElement("article", "editor-question-card");
  card.dataset.questionId = question.id;
  card.dataset.category = question.category;
  card.dataset.points = String(question.points);

  const header = createElement("div", "editor-question-card-header");
  const headingWrap = createElement("div");
  const pointBadge = createElement("span", "editor-points-badge", `${question.points} баллов`);
  const idText = createElement("span", "editor-question-id", question.id);
  headingWrap.append(pointBadge, idText);
  header.append(headingWrap, createAuctionControl(question));

  const textLabel = createElement("label", "editor-field-label", "Текст вопроса");
  const textarea = createElement("textarea", "editor-question-text");
  textarea.rows = question.question.length > 180 ? 6 : 3;
  textarea.maxLength = 1200;
  textarea.value = question.question;
  textarea.addEventListener("input", markEditorDirty);
  textLabel.appendChild(textarea);

  const typeLabel = createElement("label", "editor-field-label", "Тип ответа");
  const typeSelect = createElement("select", "editor-question-type");
  const choiceOption = new Option("Выбор из вариантов", "choice");
  const textOption = new Option("Текстовый ответ", "text");
  typeSelect.append(choiceOption, textOption);
  typeSelect.value = question.type;
  typeSelect.addEventListener("change", () => {
    captureAnswerState(card, question);
    question.type = typeSelect.value;
    if (typeSelect.value === "choice" && (!question.options || question.options.length < 2)) {
      question.options = ["", "", "", ""];
      question.correct_answers = [];
    }
    renderAnswerEditor(card, question);
    markEditorDirty();
  });
  typeLabel.appendChild(typeSelect);

  const imageEditor = createImageEditor(card, question);
  const answerEditor = createElement("div", "editor-answer-editor");

  card.append(header, textLabel, typeLabel, imageEditor, answerEditor);
  renderAnswerEditor(card, question);
  return card;
}

function renderEditor() {
  clearPreviewObjectUrls();
  editorTopics.innerHTML = "";
  const groupedQuestions = new Map();

  editorQuestions.forEach((question) => {
    if (!groupedQuestions.has(question.category)) {
      groupedQuestions.set(question.category, []);
    }
    groupedQuestions.get(question.category).push(question);
  });

  groupedQuestions.forEach((questions, category) => {
    const section = createElement("section", "editor-topic-section");
    const heading = createElement("h2", "editor-topic-title", category);
    const grid = createElement("div", "editor-question-grid");
    questions
      .sort((first, second) => Number(first.points) - Number(second.points))
      .forEach((question) => grid.appendChild(createQuestionCard(question)));
    section.append(heading, grid);
    editorTopics.appendChild(section);
  });

  const noAuction = document.querySelector('input[name="auction-question"][value=""]');
  if (!document.querySelector('input[name="auction-question"]:checked') && noAuction) {
    noAuction.checked = true;
  }
  updateAuctionSummary();
  editorLoading.classList.add("hidden");
  editorTopics.classList.remove("hidden");
  editorFooter.classList.remove("hidden");
}

function splitTextAnswers(value) {
  const seen = new Set();
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter((item) => {
      if (!item) {
        return false;
      }
      const normalized = item.toLocaleLowerCase("ru");
      if (seen.has(normalized)) {
        return false;
      }
      seen.add(normalized);
      return true;
    });
}

function collectQuestion(card) {
  const type = card.querySelector(".editor-question-type").value;
  const question = {
    id: card.dataset.questionId,
    category: card.dataset.category,
    points: Number(card.dataset.points),
    type,
    question: card.querySelector(".editor-question-text").value.trim(),
    options: [],
    correct_answers: [],
    is_auction: Boolean(
      document.querySelector(`input[name="auction-question"][value="${CSS.escape(card.dataset.questionId)}"]:checked`),
    ),
    remove_image: card.dataset.removeImage === "1",
  };

  if (type === "choice") {
    card.querySelectorAll(".editor-option-row").forEach((row) => {
      const value = row.querySelector(".editor-option-input").value.trim();
      const isCorrect = row.querySelector(".editor-option-correct").checked;
      if (!value) {
        return;
      }
      question.options.push(value);
      if (isCorrect) {
        question.correct_answers.push(value);
      }
    });
  } else {
    question.correct_answers = splitTextAnswers(
      card.querySelector(".editor-text-answers").value,
    );
  }

  return question;
}

function validateBeforeSave(questions) {
  const emptyQuestion = questions.find((question) => !question.question);
  if (emptyQuestion) {
    return `Введите текст вопроса «${emptyQuestion.category} · ${emptyQuestion.points}».`;
  }

  for (const question of questions) {
    if (question.type === "choice") {
      if (question.options.length < 2) {
        return `Для вопроса «${question.category} · ${question.points}» нужно минимум два варианта.`;
      }
      if (!question.correct_answers.length) {
        return `Отметьте правильный вариант у вопроса «${question.category} · ${question.points}».`;
      }
    } else if (!question.correct_answers.length) {
      return `Введите правильный ответ для вопроса «${question.category} · ${question.points}».`;
    }
  }

  return "";
}

function setSavingState(saving) {
  isEditorSaving = saving;
  [editorSaveButton, editorSaveBottomButton].forEach((button) => {
    button.disabled = saving;
    button.textContent = saving ? "Сохранение…" : "Сохранить игру";
  });
}

async function saveEditor() {
  if (isEditorSaving) {
    return;
  }

  const cards = [...document.querySelectorAll(".editor-question-card")];
  const questions = cards.map(collectQuestion);
  const validationMessage = validateBeforeSave(questions);
  if (validationMessage) {
    setEditorStatus(validationMessage, "error");
    return;
  }

  const genderInput = document.querySelector('input[name="actual-gender"]:checked');
  if (!genderInput) {
    setEditorStatus("Выберите правильный пол ребёнка.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("payload", JSON.stringify({
    actual_gender: genderInput.value,
    questions,
  }));

  cards.forEach((card) => {
    const fileInput = card.querySelector(".editor-image-input");
    const file = fileInput.files && fileInput.files[0];
    if (file) {
      formData.append(`image_${card.dataset.questionId}`, file, file.name);
    }
  });

  setSavingState(true);
  setEditorStatus("Сохраняю настройки игры…", "pending");

  try {
    const response = await fetchWithTimeout("/api/admin/editor", {
      method: "POST",
      body: formData,
    }, 30000);
    const data = await response.json();

    if (!response.ok) {
      setEditorStatus(data.message || "Не удалось сохранить редактор.", "error");
      return;
    }

    editorQuestions = data.questions || [];
    const gender = document.querySelector(`input[name="actual-gender"][value="${data.actual_gender}"]`);
    if (gender) {
      gender.checked = true;
    }
    isEditorDirty = false;
    renderEditor();
    setEditorStatus("Настройки игры сохранены.", "success");
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    const message = error && error.name === "AbortError"
      ? "Сервер слишком долго сохраняет данные. Проверьте соединение и повторите."
      : "Не удалось связаться с сервером.";
    setEditorStatus(message, "error");
  } finally {
    setSavingState(false);
  }
}

async function loadEditor() {
  try {
    const response = await fetchWithTimeout("/api/admin/editor");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || "Не удалось загрузить редактор.");
    }

    editorQuestions = data.questions || [];
    maxImageBytes = Number(data.limits && data.limits.max_image_bytes) || maxImageBytes;
    maxOptions = Number(data.limits && data.limits.max_options) || maxOptions;

    const gender = document.querySelector(`input[name="actual-gender"][value="${data.actual_gender}"]`);
    if (gender) {
      gender.checked = true;
    }

    renderEditor();
    isEditorDirty = false;
    setEditorStatus("");
  } catch (error) {
    editorLoading.textContent = error.message || "Не удалось загрузить редактор.";
    editorLoading.classList.add("is-error");
  }
}

[editorSaveButton, editorSaveBottomButton].forEach((button) => {
  button.addEventListener("click", saveEditor);
});

document.querySelectorAll('input[name="actual-gender"]').forEach((input) => {
  input.addEventListener("change", markEditorDirty);
});

document.querySelector('input[name="auction-question"][value=""]').addEventListener("change", () => {
  updateAuctionSummary();
  markEditorDirty();
});

window.addEventListener("beforeunload", (event) => {
  if (!isEditorDirty || isEditorSaving) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
});

loadEditor();
