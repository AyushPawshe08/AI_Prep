/**
 * AI Learning Pipeline — Frontend Application Logic
 * Replaces Streamlit with high-performance vanilla JS & CSS
 */

// ==========================================================================
// STATE & CONFIG
// ==========================================================================

const API_BASE_URL = window.location.origin;

let currentTopic = "";
let currentResult = null;
let progressInterval = null;
let activeStepIndex = 0;
let quizState = {}; // { questionIndex: { selected: 'A', submitted: true, isCorrect: bool } }

const WORKFLOW_STEPS = [
  "Objectives",
  "Explanation",
  "Analogy",
  "Technical",
  "Code",
  "Quiz",
  "Revision"
];

// Configure marked.js options
if (window.marked) {
  marked.setOptions({
    gfm: true,
    breaks: true,
    highlight: function(code, lang) {
      if (window.hljs) {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
      }
      return code;
    }
  });
}

// ==========================================================================
// DOM ELEMENTS
// ==========================================================================

const searchForm = document.getElementById("searchForm");
const topicInput = document.getElementById("topicInput");
const generateBtn = document.getElementById("generateBtn");
const btnText = generateBtn.querySelector(".btn-text");
const btnLoader = generateBtn.querySelector(".btn-loader");
const btnArrow = generateBtn.querySelector(".btn-arrow");
const statusIndicator = document.getElementById("statusIndicator");
const statusLabel = statusIndicator.querySelector(".status-label");

const progressSection = document.getElementById("progressSection");
const progressTopicTitle = document.getElementById("progressTopicTitle");
const progressPercentage = document.getElementById("progressPercentage");
const progressFill = document.getElementById("progressFill");
const stepperNodes = document.querySelectorAll(".step-item");

const errorBanner = document.getElementById("errorBanner");
const errorMessage = document.getElementById("errorMessage");
const errorDismiss = document.getElementById("errorDismiss");

const resultsContainer = document.getElementById("resultsContainer");
const moduleTopic = document.getElementById("moduleTopic");
const downloadPdfBtn = document.getElementById("downloadPdfBtn");
const pdfBtnText = document.getElementById("pdfBtnText");
const printBtn = document.getElementById("printBtn");
const copyCodeBtn = document.getElementById("copyCodeBtn");
const generateAnotherBtn = document.getElementById("generateAnotherBtn");
const toast = document.getElementById("toast");

// ==========================================================================
// INITIALIZATION & EVENT LISTENERS
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  // Preset pills
  document.querySelectorAll(".preset-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      topicInput.value = pill.getAttribute("data-topic");
      triggerGeneration();
    });
  });

  // Form submit
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    triggerGeneration();
  });

  // Error dismiss
  if (errorDismiss) {
    errorDismiss.addEventListener("click", () => {
      errorBanner.style.display = "none";
    });
  }

  // Print button
  if (printBtn) {
    printBtn.addEventListener("click", () => {
      window.print();
    });
  }

  // PDF Download button
  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener("click", handleDownloadPdf);
  }

  // Copy code button
  if (copyCodeBtn) {
    copyCodeBtn.addEventListener("click", handleCopyCode);
  }

  // Generate another module
  if (generateAnotherBtn) {
    generateAnotherBtn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
      topicInput.focus();
      topicInput.select();
    });
  }

  // Section Navigation Observer
  setupNavScrollObserver();
});

// ==========================================================================
// GENERATION WORKFLOW
// ==========================================================================

function triggerGeneration() {
  const topic = topicInput.value.trim();
  if (!topic) {
    topicInput.focus();
    return;
  }

  currentTopic = topic;
  currentResult = null;
  quizState = {};

  hideError();
  resultsContainer.style.display = "none";

  // Set UI to loading state
  setLoadingState(true);

  // Start progress animation
  startProgressAnimation(topic);

  // Call Backend API
  fetch(`${API_BASE_URL}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ topic: topic })
  })
    .then(async (response) => {
      if (!response.ok) {
        let errDetail = "Failed to generate learning material";
        try {
          const errJson = await response.json();
          if (errJson.detail) errDetail = errJson.detail;
        } catch (e) {}
        throw new Error(errDetail);
      }
      return response.json();
    })
    .then((data) => {
      completeProgressAnimation(() => {
        setLoadingState(false);
        currentResult = data;
        renderModule(data, topic);
      });
    })
    .catch((error) => {
      clearInterval(progressInterval);
      setLoadingState(false);
      progressSection.style.display = "none";
      showError(error.message || "An unexpected error occurred. Please try again.");
    });
}

function setLoadingState(isLoading) {
  if (isLoading) {
    generateBtn.disabled = true;
    btnText.textContent = "Synthesizing...";
    btnLoader.style.display = "inline-block";
    btnArrow.style.display = "none";

    statusIndicator.classList.add("busy");
    statusLabel.textContent = "Processing";
  } else {
    generateBtn.disabled = false;
    btnText.textContent = "Generate Module";
    btnLoader.style.display = "none";
    btnArrow.style.display = "inline-block";

    statusIndicator.classList.remove("busy");
    statusLabel.textContent = "Ready";
  }
}

function startProgressAnimation(topic) {
  progressSection.style.display = "block";
  progressTopicTitle.textContent = `Synthesizing module for "${topic}"`;
  activeStepIndex = 0;

  updateStepperUI(0, 5);

  let currentPercent = 5;
  const targetPercents = [15, 30, 48, 65, 80, 92];

  clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    if (activeStepIndex < WORKFLOW_STEPS.length - 1) {
      activeStepIndex++;
      const target = targetPercents[activeStepIndex] || 90;
      currentPercent = target;
      updateStepperUI(activeStepIndex, currentPercent);
    }
  }, 2800);
}

function completeProgressAnimation(callback) {
  clearInterval(progressInterval);
  updateStepperUI(WORKFLOW_STEPS.length - 1, 100);

  setTimeout(() => {
    progressSection.style.display = "none";
    if (callback) callback();
  }, 600);
}

function updateStepperUI(activeIdx, percent) {
  progressPercentage.textContent = `${percent}%`;
  progressFill.style.width = `${percent}%`;

  stepperNodes.forEach((node, idx) => {
    node.classList.remove("active", "completed");
    if (idx < activeIdx) {
      node.classList.add("completed");
    } else if (idx === activeIdx) {
      node.classList.add("active");
    }
  });
}

// ==========================================================================
// RENDER MODULE
// ==========================================================================

function renderModule(result, topic) {
  moduleTopic.textContent = topic || "Learning Module";
  
  // 1. Objectives
  renderObjectives(result.learning_objectives || "");

  // 2. Explanation
  renderExplanation(result.explanation || "");

  // 3. Analogy
  renderAnalogy(result.analogy || "");

  // 4. Technical Explanation
  renderTechnical(result.technical_explanation || "");

  // 5. Code Example
  renderCode(result.code_example || "");

  // 6. Quiz & Answers
  renderQuiz(result.quiz || "", result.answers || "");

  // 7. Revision Notes
  renderRevisionNotes(result.revision_notes || "");

  // Show container and smoothly scroll to it
  resultsContainer.style.display = "block";
  resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
}

// --- Section 01: Objectives ---
function renderObjectives(rawText) {
  const container = document.getElementById("objectivesContent");
  if (!rawText.trim()) {
    container.innerHTML = '<p class="prose-content"><em>No objectives returned.</em></p>';
    return;
  }

  // Check if rawText has numbered items
  const lines = rawText.split("\n")
    .map(l => l.trim())
    .filter(l => l.length > 0 && /^\s*(\d+[\.\)]|\-|\*)\s*/.test(l));

  if (lines.length > 0) {
    let html = '<div class="objectives-grid">';
    lines.forEach((line, i) => {
      const cleanText = line.replace(/^\s*[\d]+[\.\)]\s*|\*\*/g, "").replace(/^[-*]\s*/, "").trim();
      const numStr = String(i + 1).padStart(2, "0");
      html += `
        <div class="obj-item">
          <div class="obj-num">${numStr}</div>
          <div class="obj-text">${escapeHtml(cleanText)}</div>
        </div>
      `;
    });
    html += '</div>';
    container.innerHTML = html;
  } else {
    container.innerHTML = `<div class="prose-content">${parseMarkdown(rawText)}</div>`;
  }
}

// --- Section 02: Simple Explanation ---
function renderExplanation(text) {
  const contentEl = document.getElementById("explanationContent");
  const termsWrap = document.getElementById("explanationTerms");
  
  contentEl.innerHTML = parseMarkdown(text || "<em>No content returned.</em>");

  // Extract key terms
  const terms = extractTerms(text);
  if (terms && terms.length > 0) {
    termsWrap.style.display = "flex";
    termsWrap.innerHTML = terms.map(t => `<span class="term-badge">${escapeHtml(t)}</span>`).join("");
  } else {
    termsWrap.style.display = "none";
  }
}

// --- Section 03: Analogy ---
function renderAnalogy(text) {
  const contentEl = document.getElementById("analogyContent");
  contentEl.innerHTML = parseMarkdown(text || "<em>No analogy returned.</em>");
}

// --- Section 04: Technical Explanation ---
function renderTechnical(text) {
  const contentEl = document.getElementById("technicalContent");
  contentEl.innerHTML = parseMarkdown(text || "<em>No technical explanation returned.</em>");
}

// --- Section 05: Code Example ---
function renderCode(rawField) {
  const codeBlock = document.getElementById("codeBlock");
  const codeNotes = document.getElementById("codeNotes");
  const codeFilename = document.getElementById("codeFilename");

  const { code, notes } = extractPythonCode(rawField);

  if (code) {
    codeBlock.textContent = code;
    codeBlock.className = "language-python";
    if (window.hljs) {
      hljs.highlightElement(codeBlock);
    }
  } else {
    codeBlock.textContent = rawField || "# No code example returned.";
  }

  codeFilename.textContent = `${slugify(currentTopic || "solution")}.py`;

  if (notes && notes.trim()) {
    codeNotes.style.display = "block";
    codeNotes.innerHTML = parseMarkdown(notes);
  } else {
    codeNotes.style.display = "none";
  }
}

// --- Section 06: Quiz ---
function renderQuiz(quizRaw, answersRaw) {
  const container = document.getElementById("quizQuestionsContainer");
  const scoreHeader = document.getElementById("quizScoreHeader");
  const scorePill = document.getElementById("quizScorePill");
  
  const { quizBody, embeddedAnswerKey } = stripEmbeddedAnswerKey(quizRaw);
  const correctLetters = parseAnswerLetters(embeddedAnswerKey || answersRaw);
  const blocks = parseMcqBlocks(quizBody);

  quizState = {};

  if (!blocks || blocks.length === 0 || blocks.every(b => !b.prose.trim())) {
    scoreHeader.style.display = "none";
    container.innerHTML = `<div class="prose-content">${parseMarkdown(quizBody || answersRaw || "<em>No quiz returned.</em>")}</div>`;
    return;
  }

  scoreHeader.style.display = "block";
  scorePill.textContent = `Score: 0 / ${blocks.length}`;

  const answersSplit = answersRaw.split(/^#{1,4}\s*question\s+\d+.*$/im);

  let html = "";
  blocks.forEach((block, qIdx) => {
    const qNum = qIdx + 1;
    const qPad = String(qNum).padStart(2, "0");
    const explanationText = (qNum < answersSplit.length) ? answersSplit[qNum] : answersRaw;

    html += `
      <div class="quiz-block" id="quiz-block-${qNum}">
        <div class="quiz-tag">Question ${qPad}</div>
        <div class="quiz-question-text">${parseMarkdown(block.prose || "Choose the best answer:")}</div>
        
        <div class="quiz-options-list" id="quiz-options-${qNum}">
          ${block.options.map(([letter, optText]) => `
            <button type="button" class="quiz-option-btn" data-q="${qNum}" data-opt="${letter}" onclick="selectQuizOption(${qNum}, '${letter}')">
              <span class="opt-letter">${letter}</span>
              <span class="opt-label">${escapeHtml(optText)}</span>
            </button>
          `).join("")}
        </div>

        <div class="quiz-actions">
          <button type="button" class="submit-answer-btn" id="submit-btn-${qNum}" disabled onclick="submitQuizAnswer(${qNum})">
            Check Answer
          </button>
          <div class="quiz-feedback-pill" id="feedback-${qNum}" style="display: none;"></div>
        </div>

        <details class="quiz-explanation-drawer">
          <summary class="quiz-explanation-summary">View Detailed Solution & Explanation</summary>
          <div class="quiz-explanation-body prose-content">
            ${parseMarkdown(explanationText || "See full answer key above.")}
          </div>
        </details>
      </div>
    `;
  });

  container.innerHTML = html;

  // Store parsed correct letters on container for lookup
  container.dataset.correctLetters = JSON.stringify(correctLetters);
}

window.selectQuizOption = function(qNum, letter) {
  if (quizState[qNum]?.submitted) return; // already submitted

  quizState[qNum] = { selected: letter, submitted: false };

  const optionsContainer = document.getElementById(`quiz-options-${qNum}`);
  const buttons = optionsContainer.querySelectorAll(".quiz-option-btn");
  buttons.forEach(btn => {
    if (btn.getAttribute("data-opt") === letter) {
      btn.classList.add("selected");
    } else {
      btn.classList.remove("selected");
    }
  });

  const submitBtn = document.getElementById(`submit-btn-${qNum}`);
  if (submitBtn) {
    submitBtn.disabled = false;
  }
};

window.submitQuizAnswer = function(qNum) {
  const state = quizState[qNum];
  if (!state || !state.selected || state.submitted) return;

  const container = document.getElementById("quizQuestionsContainer");
  let correctLetters = {};
  try {
    correctLetters = JSON.parse(container.dataset.correctLetters || "{}");
  } catch (e) {}

  const correctLetter = correctLetters[qNum];
  const chosenLetter = state.selected.toUpperCase();
  const isCorrect = correctLetter ? (chosenLetter === correctLetter) : true;

  state.submitted = true;
  state.isCorrect = isCorrect;

  // Update UI for buttons
  const optionsContainer = document.getElementById(`quiz-options-${qNum}`);
  const buttons = optionsContainer.querySelectorAll(".quiz-option-btn");
  buttons.forEach(btn => {
    btn.disabled = true;
    const optLetter = btn.getAttribute("data-opt").toUpperCase();
    if (optLetter === chosenLetter) {
      btn.classList.add(isCorrect ? "correct" : "incorrect");
    }
    if (!isCorrect && optLetter === correctLetter) {
      btn.classList.add("correct");
    }
  });

  // Update feedback pill
  const feedbackEl = document.getElementById(`feedback-${qNum}`);
  feedbackEl.style.display = "inline-flex";
  if (correctLetter) {
    if (isCorrect) {
      feedbackEl.className = "quiz-feedback-pill correct";
      feedbackEl.innerHTML = `✓ Correct! Excellent job.`;
    } else {
      feedbackEl.className = "quiz-feedback-pill incorrect";
      feedbackEl.innerHTML = `✗ Incorrect — Correct answer is ${correctLetter}`;
    }
  } else {
    feedbackEl.className = "quiz-feedback-pill correct";
    feedbackEl.innerHTML = `✓ Answer recorded.`;
  }

  // Disable submit button
  const submitBtn = document.getElementById(`submit-btn-${qNum}`);
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Checked";
  }

  // Update overall score
  updateTotalScore();
};

function updateTotalScore() {
  const container = document.getElementById("quizQuestionsContainer");
  const totalQuestions = container.querySelectorAll(".quiz-block").length;
  let correctCount = 0;

  Object.values(quizState).forEach(st => {
    if (st.submitted && st.isCorrect) correctCount++;
  });

  const scorePill = document.getElementById("quizScorePill");
  if (scorePill && totalQuestions > 0) {
    const percentage = Math.round((correctCount / totalQuestions) * 100);
    scorePill.textContent = `Score: ${correctCount} / ${totalQuestions} (${percentage}%)`;
  }
}

// --- Section 07: Revision Notes ---
function renderRevisionNotes(rawText) {
  const gridEl = document.getElementById("revisionGrid");
  const fullContentEl = document.getElementById("fullRevisionContent");

  const items = parseRevisionItems(rawText);

  if (items && items.length > 0) {
    gridEl.style.display = "grid";
    gridEl.innerHTML = items.map(([term, def]) => `
      <div class="revision-card-item">
        <div class="rterm">${escapeHtml(term)}</div>
        <div class="rdef">${escapeHtml(def)}</div>
      </div>
    `).join("");
  } else {
    gridEl.style.display = "none";
  }

  fullContentEl.innerHTML = parseMarkdown(rawText || "<em>No revision notes returned.</em>");
}

// ==========================================================================
// ACTIONS (PDF EXPORT, COPY CODE, NAVIGATION)
// ==========================================================================

async function handleDownloadPdf() {
  if (!currentResult || !currentTopic) {
    showToast("No generated module to export.");
    return;
  }

  pdfBtnText.textContent = "Generating PDF...";
  downloadPdfBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/export-pdf`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        topic: currentTopic,
        result: currentResult
      })
    });

    if (!response.ok) {
      throw new Error("Backend PDF export failed");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${slugify(currentTopic || "learning_module")}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    showToast("PDF downloaded successfully!");
  } catch (err) {
    console.warn("Falling back to window.print():", err);
    showToast("PDF download fell back to print view.");
    window.print();
  } finally {
    pdfBtnText.textContent = "Download PDF";
    downloadPdfBtn.disabled = false;
  }
}

function handleCopyCode() {
  const codeBlock = document.getElementById("codeBlock");
  if (!codeBlock) return;

  const codeText = codeBlock.textContent;
  navigator.clipboard.writeText(codeText).then(() => {
    const copyText = copyCodeBtn.querySelector(".copy-text");
    copyText.textContent = "Copied!";
    showToast("Code copied to clipboard!");
    setTimeout(() => {
      copyText.textContent = "Copy Code";
    }, 2000);
  }).catch(() => {
    showToast("Failed to copy code.");
  });
}

function setupNavScrollObserver() {
  const navPills = document.querySelectorAll(".nav-pill");
  const sections = document.querySelectorAll(".section-card");

  window.addEventListener("scroll", () => {
    let currentId = "";
    sections.forEach(sec => {
      const top = sec.offsetTop - 140;
      if (window.scrollY >= top) {
        currentId = sec.getAttribute("id");
      }
    });

    if (currentId) {
      navPills.forEach(pill => {
        if (pill.getAttribute("href") === `#${currentId}`) {
          pill.classList.add("active");
        } else {
          pill.classList.remove("active");
        }
      });
    }
  });
}

// ==========================================================================
// PARSING & HELPER UTILITIES
// ==========================================================================

function parseMarkdown(md) {
  if (!md) return "";
  if (!window.marked || !window.DOMPurify) {
    return escapeHtml(md).replace(/\n/g, "<br>");
  }

  const rendered = marked.parse(String(md), {
    gfm: true,
    breaks: true
  });
  const sanitized = DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true }
  });
  return enhanceMarkdownHtml(sanitized);
}

function enhanceMarkdownHtml(html) {
  const container = document.createElement("div");
  container.innerHTML = html;

  container.querySelectorAll("table").forEach(table => {
    if (table.parentElement.classList.contains("markdown-table-wrap")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "markdown-table-wrap";
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });

  if (window.hljs) {
    container.querySelectorAll("pre code").forEach(codeBlock => {
      hljs.highlightElement(codeBlock);
    });
  }

  if (!window.katex) return container.innerHTML;

  const textNodes = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.parentElement.closest("code, pre, script, style")) {
      textNodes.push(node);
    }
  }

  const mathPattern = /\$\$([\s\S]+?)\$\$|\$(?!\s)([^$\n]+?)(?<!\s)\$/g;
  textNodes.forEach(textNode => {
    const text = textNode.nodeValue;
    mathPattern.lastIndex = 0;
    if (!mathPattern.test(text)) return;
    mathPattern.lastIndex = 0;

    const fragment = document.createDocumentFragment();
    let lastIndex = 0;
    let match;
    while ((match = mathPattern.exec(text))) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      const math = document.createElement("span");
      math.className = match[1] ? "math-display" : "math-inline";
      math.innerHTML = DOMPurify.sanitize(katex.renderToString(match[1] || match[2], {
        displayMode: Boolean(match[1]),
        throwOnError: false
      }));
      fragment.appendChild(math);
      lastIndex = mathPattern.lastIndex;
    }
    fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    textNode.replaceWith(fragment);
  });

  return container.innerHTML;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function slugify(text) {
  return text.toString().toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^\w\-]+/g, "")
    .replace(/\-\-+/g, "_")
    .replace(/^-+/, "")
    .replace(/-+$/, "");
}

function extractTerms(text, limit = 6) {
  if (!text) return [];
  const regex = /\*\*([A-Za-z][A-Za-z0-9 \-/]{2,28})\*\*/g;
  const terms = [];
  const seen = new Set();
  let match;
  while ((match = regex.exec(text)) !== null) {
    const term = match[1].trim();
    const key = term.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      terms.push(term);
    }
    if (terms.length >= limit) break;
  }
  return terms;
}

function extractPythonCode(codeField) {
  if (!codeField) return { code: "", notes: "" };
  const match = codeField.match(/```(?:python)?\s*\n([\s\S]*?)```/);
  if (!match) {
    return { code: codeField, notes: "" };
  }
  const code = match[1].trim();
  const notes = (codeField.slice(0, match.index) + codeField.slice(match.index + match[0].length)).trim();
  return { code, notes };
}

function stripEmbeddedAnswerKey(quizText) {
  if (!quizText) return { quizBody: "", embeddedAnswerKey: "" };
  const match = quizText.match(/^#{1,4}\s*answer key.*$/im);
  if (!match) {
    return { quizBody: quizText, embeddedAnswerKey: "" };
  }
  return {
    quizBody: quizText.slice(0, match.index).trim(),
    embeddedAnswerKey: quizText.slice(match.index).trim()
  };
}

function parseMcqBlocks(quizBody) {
  if (!quizBody) return [];
  const headerRegex = /^#{1,4}\s*question\s+\d+.*$/gim;
  let matches = [];
  let m;
  while ((m = headerRegex.exec(quizBody)) !== null) {
    matches.push(m.index);
  }

  let rawBlocks = [];
  if (matches.length > 0) {
    for (let i = 0; i < matches.length; i++) {
      const start = matches[i];
      const end = (i + 1 < matches.length) ? matches[i + 1] : quizBody.length;
      rawBlocks.push(quizBody.slice(start, end).trim());
    }
  } else {
    rawBlocks = [quizBody.trim()];
  }

  const optionRegex = /^\s*([A-D])[\.\)]\s+(.*)$/gm;
  return rawBlocks.map(block => {
    const options = [];
    let optMatch;
    while ((optMatch = optionRegex.exec(block)) !== null) {
      options.push([optMatch[1], optMatch[2]]);
    }
    const prose = block.replace(/^\s*([A-D])[\.\)]\s+.*$/gm, "").trim();
    return { prose, options };
  });
}

function parseAnswerLetters(answerKeyText) {
  const mapping = {};
  if (!answerKeyText) return mapping;
  const regex = /\*\*Q(\d+):\*\*\s*\*\*([A-Za-z0-9]+)\*\*/g;
  let match;
  while ((match = regex.exec(answerKeyText)) !== null) {
    mapping[parseInt(match[1], 10)] = match[2].trim().toUpperCase();
  }
  // Alternate format: 1. B or Q1: B
  if (Object.keys(mapping).length === 0) {
    const altRegex = /(?:Q?(\d+)[:\.]?\s*(?:\*\*)?([A-D])(?:\*\*|\b))/gi;
    while ((match = altRegex.exec(answerKeyText)) !== null) {
      mapping[parseInt(match[1], 10)] = match[2].trim().toUpperCase();
    }
  }
  return mapping;
}

function parseRevisionItems(revisionText, limit = 8) {
  if (!revisionText) return [];
  const items = [];
  
  // Try table rows: | **Term** | Definition |
  const tableRegex = /\|\s*\*\*([^|*]{2,40})\*\*\s*\|\s*([^|]{2,140})\|/g;
  let match;
  while ((match = tableRegex.exec(revisionText)) !== null) {
    const term = match[1].trim();
    const def = match[2].replace(/[*`]/g, "").trim();
    if (term && def && !term.includes("---")) {
      items.push([term, def]);
    }
  }

  // Fallback: **Term**: definition
  if (items.length === 0) {
    const lineRegex = /^\*\*([^*\n]{2,40})\*\*\s*[-–—:]\s*(.{5,140})$/gm;
    while ((match = lineRegex.exec(revisionText)) !== null) {
      items.push([match[1].trim(), match[2].trim()]);
    }
  }

  return items.slice(0, limit);
}

function showError(msg) {
  if (errorMessage) errorMessage.textContent = msg;
  if (errorBanner) errorBanner.style.display = "flex";
}

function hideError() {
  if (errorBanner) errorBanner.style.display = "none";
}

function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 2800);
}
