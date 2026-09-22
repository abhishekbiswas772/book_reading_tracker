const API_BASE = "";

const el = {
  globalError: document.getElementById("global-error"),
  countToRead: document.getElementById("count-to-read"),
  countReading: document.getElementById("count-reading"),
  countDone: document.getElementById("count-done"),
  addForm: document.getElementById("add-book-form"),
  addTitle: document.getElementById("add-title"),
  addAuthor: document.getElementById("add-author"),
  addStatus: document.getElementById("add-status"),
  addTitleError: document.getElementById("add-title-error"),
  addAuthorError: document.getElementById("add-author-error"),
  addStatusError: document.getElementById("add-status-error"),
  addFormMessage: document.getElementById("add-form-message"),
  statusFilter: document.getElementById("status-filter"),
  searchBox: document.getElementById("search-box"),
  bookList: document.getElementById("book-list"),
  emptyState: document.getElementById("empty-state"),
  noSearchResults: document.getElementById("no-search-results"),
  editModal: document.getElementById("edit-modal"),
  editForm: document.getElementById("edit-book-form"),
  editId: document.getElementById("edit-id"),
  editTitle: document.getElementById("edit-title"),
  editAuthor: document.getElementById("edit-author"),
  editStatus: document.getElementById("edit-status"),
  editTitleError: document.getElementById("edit-title-error"),
  editAuthorError: document.getElementById("edit-author-error"),
  editStatusError: document.getElementById("edit-status-error"),
  editFormMessage: document.getElementById("edit-form-message"),
  editCancel: document.getElementById("edit-cancel"),
};

const STATUS_LABELS = {
  "to-read": "To Read",
  reading: "Reading",
  done: "Done",
};

function showGlobalError(message) {
  el.globalError.textContent = message;
  el.globalError.hidden = false;
}

function clearGlobalError() {
  el.globalError.hidden = true;
  el.globalError.textContent = "";
}

function formatDate(isoString) {
  if (!isoString) return "unknown";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    throw { networkError: true, message: "Network error — could not reach the server." };
  }

  if (response.status === 204) {
    return null;
  }

  let body = null;
  try {
    body = await response.json();
  } catch (parseErr) {
    // no body / not JSON, ignore
  }

  if (!response.ok) {
    throw { networkError: false, status: response.status, body };
  }

  return body;
}

async function fetchCounts() {
  try {
    const counts = await apiRequest("/book/status-counts");
    el.countToRead.textContent = counts["to-read"] ?? 0;
    el.countReading.textContent = counts["reading"] ?? 0;
    el.countDone.textContent = counts["done"] ?? 0;
  } catch (err) {
    showGlobalError(errorMessage(err, "Could not load status counts."));
  }
}

let currentBooks = [];

async function fetchBooks() {
  const status = el.statusFilter.value;
  const path = status ? `/book?status=${encodeURIComponent(status)}` : "/book";
  try {
    currentBooks = await apiRequest(path);
    renderFilteredBooks();
  } catch (err) {
    showGlobalError(errorMessage(err, "Could not load the book list."));
  }
}

function renderFilteredBooks() {
  const query = el.searchBox.value.trim().toLowerCase();
  if (!query) {
    renderBooks(currentBooks);
    return;
  }
  const filtered = currentBooks.filter((book) => {
    const title = (book.title || "").toLowerCase();
    const author = (book.author || "").toLowerCase();
    return title.includes(query) || author.includes(query);
  });
  renderBooks(filtered, { searchActive: true });
}

function errorMessage(err, fallback) {
  if (err && err.networkError) return err.message;
  if (err && err.body && err.body.detail) return err.body.detail;
  return fallback;
}

function renderBooks(books, { searchActive = false } = {}) {
  el.bookList.querySelectorAll(".book-card").forEach((node) => node.remove());

  if (!books || books.length === 0) {
    el.emptyState.hidden = !(!searchActive && currentBooks.length === 0);
    el.noSearchResults.hidden = !(searchActive && currentBooks.length > 0);
    return;
  }
  el.emptyState.hidden = true;
  el.noSearchResults.hidden = true;

  books.forEach((book) => {
    el.bookList.appendChild(buildBookCard(book));
  });
}

function buildBookCard(book) {
  const card = document.createElement("div");
  card.className = "book-card";
  card.dataset.id = book.id;

  const info = document.createElement("div");
  info.className = "book-info";

  const title = document.createElement("div");
  title.className = "book-title";
  title.textContent = book.title;

  const author = document.createElement("div");
  author.className = "book-author";
  author.textContent = book.author ? book.author : "Unknown author";

  const badge = document.createElement("span");
  badge.className = "status-badge";
  badge.dataset.status = book.status;
  badge.textContent = STATUS_LABELS[book.status] || book.status;

  const dates = document.createElement("div");
  dates.className = "book-dates";
  dates.textContent = `Added ${formatDate(book.created_at)} · Updated ${formatDate(book.updated_at)}`;

  info.appendChild(title);
  info.appendChild(author);
  info.appendChild(badge);
  info.appendChild(dates);

  const actions = document.createElement("div");
  actions.className = "book-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "edit-btn";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => openEditModal(book));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "delete-btn";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", () => deleteBook(book));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);

  card.appendChild(info);
  card.appendChild(actions);

  return card;
}

function clearFieldErrors(prefix) {
  document.getElementById(`${prefix}-title-error`).textContent = "";
  document.getElementById(`${prefix}-author-error`).textContent = "";
  document.getElementById(`${prefix}-status-error`).textContent = "";
  document.getElementById(`${prefix}-form-message`).textContent = "";
}

function applyFieldError(prefix, err) {
  const messageEl = document.getElementById(`${prefix}-form-message`);
  if (err.networkError) {
    messageEl.textContent = err.message;
    return;
  }
  if (err.status === 422 && err.body && err.body.field) {
    const fieldErrorEl = document.getElementById(`${prefix}-${err.body.field}-error`);
    if (fieldErrorEl) {
      fieldErrorEl.textContent = err.body.detail;
      return;
    }
  }
  if (err.body && err.body.detail) {
    messageEl.textContent = err.body.detail;
    return;
  }
  messageEl.textContent = "Something went wrong. Please try again.";
}

el.addForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  clearFieldErrors("add");

  const payload = {
    title: el.addTitle.value.trim(),
    status: el.addStatus.value,
  };
  const author = el.addAuthor.value.trim();
  if (author) payload.author = author;

  try {
    await apiRequest("/book", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    el.addForm.reset();
    el.addStatus.value = "to-read";
    await Promise.all([fetchBooks(), fetchCounts()]);
  } catch (err) {
    applyFieldError("add", err);
  }
});

function openEditModal(book) {
  clearFieldErrors("edit");
  el.editId.value = book.id;
  el.editTitle.value = book.title;
  el.editAuthor.value = book.author || "";
  el.editStatus.value = book.status;
  el.editModal.hidden = false;
}

function closeEditModal() {
  el.editModal.hidden = true;
}

el.editCancel.addEventListener("click", closeEditModal);
el.editModal.addEventListener("click", (evt) => {
  if (evt.target === el.editModal) closeEditModal();
});

el.editForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  clearFieldErrors("edit");

  const bookId = el.editId.value;
  const payload = {
    title: el.editTitle.value.trim(),
    author: el.editAuthor.value.trim() || null,
    status: el.editStatus.value,
  };

  try {
    await apiRequest(`/book/${encodeURIComponent(bookId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    closeEditModal();
    await Promise.all([fetchBooks(), fetchCounts()]);
  } catch (err) {
    applyFieldError("edit", err);
  }
});

async function deleteBook(book) {
  const confirmed = confirm(`Delete "${book.title}"? This cannot be undone.`);
  if (!confirmed) return;

  try {
    await apiRequest(`/book/${encodeURIComponent(book.id)}`, { method: "DELETE" });
    await Promise.all([fetchBooks(), fetchCounts()]);
  } catch (err) {
    showGlobalError(errorMessage(err, "Could not delete the book."));
  }
}

el.statusFilter.addEventListener("change", () => {
  clearGlobalError();
  fetchBooks();
});

el.searchBox.addEventListener("input", () => {
  renderFilteredBooks();
});

async function init() {
  clearGlobalError();
  await Promise.all([fetchBooks(), fetchCounts()]);
}

init();
