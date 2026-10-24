const fileInput = document.querySelector("#file-input");
const dropzone = document.querySelector("#dropzone");
const fileList = document.querySelector("#file-list");
const fileCount = document.querySelector("#file-count");
const clearButton = document.querySelector("#clear-button");
const form = document.querySelector("#question-form");
const question = document.querySelector("#question");
const welcome = document.querySelector("#welcome");
const answer = document.querySelector("#answer");
const errorBox = document.querySelector("#error");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

function renderFiles(files) {
  fileCount.textContent = `${files.length} ${files.length === 1 ? "file" : "files"}`;
  clearButton.classList.toggle("hidden", files.length === 0);
  fileList.innerHTML = files.length ? files.map(file => `
    <div class="file"><span class="file-icon">${escapeHtml(file.name.split(".").pop().toUpperCase())}</span>
    <span class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span></div>`).join("") :
    '<p class="empty">Your uploaded notes<br />will appear here.</p>';
}

async function upload(files) {
  if (!files.length) return;
  const body = new FormData();
  [...files].forEach(file => body.append("files", file));
  try {
    const response = await fetch("/api/documents", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not upload notes.");
    renderFiles(data.documents);
    errorBox.classList.add("hidden");
  } catch (error) { showError(error.message); }
}

fileInput.addEventListener("change", event => upload(event.target.files));
["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => {
  event.preventDefault(); dropzone.classList.add("dragging");
}));
["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, event => {
  event.preventDefault(); dropzone.classList.remove("dragging");
}));
dropzone.addEventListener("drop", event => upload(event.dataTransfer.files));

clearButton.addEventListener("click", async () => {
  await fetch("/api/documents", { method: "DELETE" });
  renderFiles([]);
  answer.classList.add("hidden");
  welcome.classList.remove("hidden");
});

document.querySelectorAll(".suggestion-list button").forEach(button => {
  button.addEventListener("click", () => { question.value = button.textContent; question.focus(); });
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  const value = question.value.trim();
  if (!value) return;
  errorBox.classList.add("hidden");
  welcome.classList.add("hidden");
  answer.classList.remove("hidden");
  answer.innerHTML = '<h3>Taking a quiet moment...</h3><div class="answer-body">Thinking through your notes.</div>';
  try {
    const response = await fetch("/api/questions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not get an answer.");
    const safeAnswer = escapeHtml(data.answer).replace(/\n/g, "<br>");
    const safeSources = data.sources.map(escapeHtml).join(", ");
    answer.innerHTML = `<h3>Here is what I found</h3><div class="answer-body">${safeAnswer}</div>
      ${data.sources.length ? `<div class="sources">Based on: ${safeSources}</div>` : ""}`;
  } catch (error) {
    answer.classList.add("hidden");
    welcome.classList.remove("hidden");
    showError(error.message);
  }
});

fetch("/api/session").then(response => response.json()).then(data => renderFiles(data.documents));
