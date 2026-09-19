// State Management
let currentConversationId = null;
let currentLevel = "beginner";
let currentLanguage = "vi";

// DOM Elements
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const messagesList = document.getElementById("messages-list");
const chatContainer = document.getElementById("chat-container");
const welcomeHero = document.getElementById("welcome-hero");
const sendBtn = document.getElementById("send-btn");
const conversationList = document.getElementById("conversation-list");
const newChatBtn = document.getElementById("new-chat-btn");
const levelSelect = document.getElementById("level-select");
const tabBtns = document.querySelectorAll(".tab-btn");
const viewPanels = document.querySelectorAll(".view-panel");
const vocabForm = document.getElementById("vocab-form");
const vocabInput = document.getElementById("vocab-input");
const vocabResultWrapper = document.getElementById("vocab-result-wrapper");
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebar = document.getElementById("sidebar");

// Khởi chạy
document.addEventListener("DOMContentLoaded", () => {
  loadConversations();
  setupEventListeners();
  setupMarkdownRenderer();
});

function setupMarkdownRenderer() {
  if (window.marked) {
    marked.setOptions({
      breaks: true,
      gfm: true,
      highlight: function (code, lang) {
        if (window.hljs && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return code;
      }
    });
  }
}

function setupEventListeners() {
  // Gửi tin nhắn
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSendMessage();
  });

  // Tự động co giãn textarea và gửi khi gõ Enter (Shift + Enter để xuống dòng)
  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 140) + "px";
  });

  // Đổi cấp độ
  levelSelect.addEventListener("change", (e) => {
    currentLevel = e.target.value;
  });

  // Tạo cuộc trò chuyện mới
  newChatBtn.addEventListener("click", () => {
    startNewChat();
  });

  // Đổi tab (Chat vs Tra từ)
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      viewPanels.forEach((p) => p.classList.remove("active"));
      
      btn.classList.add("active");
      const targetTab = btn.getAttribute("data-tab");
      document.getElementById(`${targetTab}-panel`).classList.add("active");
      
      if (window.innerWidth <= 768) {
        sidebar.classList.remove("open");
      }
    });
  });

  // Tra cứu từ vựng
  vocabForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleVocabLookup();
  });

  // Gợi ý câu hỏi nhanh (Prompt chips)
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      messageInput.value = prompt;
      messageInput.focus();
      handleSendMessage();
    });
  });

  // Sidebar mobile toggle
  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }
}

function startNewChat() {
  currentConversationId = null;
  messagesList.innerHTML = "";
  welcomeHero.classList.remove("hidden");
  messageInput.value = "";
  messageInput.focus();
  document.querySelectorAll(".conv-item").forEach((el) => el.classList.remove("active"));
  
  if (window.innerWidth <= 768) {
    sidebar.classList.remove("open");
  }
}

async function loadConversations() {
  try {
    const res = await fetch("/api/conversations");
    if (!res.ok) return;
    const data = await res.json();
    renderConversationList(data);
  } catch (err) {
    console.error("Lỗi khi tải lịch sử:", err);
  }
}

function renderConversationList(conversations) {
  if (!conversations || conversations.length === 0) {
    conversationList.innerHTML = '<div class="empty-state">Chưa có phiên học nào</div>';
    return;
  }

  conversationList.innerHTML = "";
  conversations.forEach((conv) => {
    const item = document.createElement("div");
    item.className = `conv-item ${conv.id === currentConversationId ? "active" : ""}`;
    item.innerHTML = `
      <span class="conv-title" title="${escapeHtml(conv.title)}">💬 ${escapeHtml(conv.title)}</span>
      <button class="conv-delete-btn" title="Xóa phiên này">🗑️</button>
    `;

    item.querySelector(".conv-title").addEventListener("click", () => {
      loadConversationDetail(conv.id);
    });

    item.querySelector(".conv-delete-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteConversation(conv.id);
    });

    conversationList.appendChild(item);
  });
}

async function loadConversationDetail(convId) {
  try {
    const res = await fetch(`/api/conversations/${convId}`);
    if (!res.ok) return;
    const data = await res.json();

    currentConversationId = convId;
    welcomeHero.classList.add("hidden");
    messagesList.innerHTML = "";

    // Cập nhật active sidebar
    document.querySelectorAll(".conv-item").forEach((el) => el.classList.remove("active"));
    loadConversations();

    data.messages.forEach((msg) => {
      appendMessageToUI(msg.sender, msg.content, msg.id);
    });

    scrollToBottom();
    if (window.innerWidth <= 768) {
      sidebar.classList.remove("open");
    }
  } catch (err) {
    console.error("Lỗi tải chi tiết phiên:", err);
  }
}

async function deleteConversation(convId) {
  if (!confirm("Bạn có chắc chắn muốn xóa cuộc trò chuyện này?")) return;
  try {
    const res = await fetch(`/api/conversations/${convId}`, { method: "DELETE" });
    if (res.ok) {
      if (currentConversationId === convId) {
        startNewChat();
      }
      loadConversations();
    }
  } catch (err) {
    alert("Không thể xóa phiên hội thoại.");
  }
}

async function handleSendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  welcomeHero.classList.add("hidden");
  messageInput.value = "";
  messageInput.style.height = "auto";

  // Thêm tin nhắn của người dùng vào giao diện
  appendMessageToUI("user", text);
  scrollToBottom();

  // Thêm trạng thái bot đang xử lý (typing indicator)
  const typingElement = appendTypingIndicator();
  scrollToBottom();
  setSendingState(true);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        level: currentLevel,
        language: currentLanguage,
        conversationId: currentConversationId
      })
    });

    typingElement.remove();

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: "Lỗi kết nối đến máy chủ." }));
      appendMessageToUI("bot", `⚠️ **Thông báo:** ${errData.detail || "Không thể kết nối đến AI API."}`);
      return;
    }

    const data = await res.json();
    currentConversationId = data.conversationId;
    appendMessageToUI("bot", data.answer, data.messageId);
    
    // Tải lại sidebar để hiển thị phiên mới
    loadConversations();
  } catch (err) {
    typingElement.remove();
    appendMessageToUI("bot", "⚠️ **Lỗi mạng:** Không thể kết nối với server. Vui lòng kiểm tra lại đường truyền.");
  } finally {
    setSendingState(false);
    scrollToBottom();
  }
}

function appendMessageToUI(sender, content, messageId = null) {
  const msgItem = document.createElement("div");
  msgItem.className = `message-item ${sender}`;

  const avatar = sender === "user" ? "👤" : "🎓";
  let renderedContent = content;

  if (sender === "bot" && window.marked) {
    renderedContent = marked.parse(content);
  } else {
    renderedContent = `<p>${escapeHtml(content).replace(/\n/g, "<br>")}</p>`;
  }

  let actionsHtml = "";
  if (sender === "bot") {
    actionsHtml = `
      <div class="message-actions">
        <button class="action-btn copy-btn" title="Sao chép câu trả lời">📋 Sao chép</button>
        ${messageId ? `
          <button class="action-btn feedback-btn" data-type="like" data-id="${messageId}" title="Hữu ích">👍 Hữu ích</button>
          <button class="action-btn feedback-btn" data-type="dislike" data-id="${messageId}" title="Chưa hữu ích">👎 Chưa rõ</button>
        ` : ""}
      </div>
    `;
  }

  msgItem.innerHTML = `
    <div class="message-avatar">${avatar}</div>
    <div class="message-bubble">
      <div class="message-text">${renderedContent}</div>
      ${actionsHtml}
    </div>
  `;

  // Render LaTeX KaTeX cho công thức toán
  if (sender === "bot" && window.renderMathInElement) {
    try {
      renderMathInElement(msgItem.querySelector(".message-text"), {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\[", right: "\\]", display: true },
          { left: "\\(", right: "\\)", display: false }
        ],
        throwOnError: false
      });
    } catch (e) {
      console.warn("Lỗi render công thức KaTeX:", e);
    }
  }

  // Copy button
  const copyBtn = msgItem.querySelector(".copy-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(content).then(() => {
        copyBtn.textContent = "✅ Đã chép";
        setTimeout(() => (copyBtn.textContent = "📋 Sao chép"), 2000);
      });
    });
  }

  // Feedback buttons
  const feedbackBtns = msgItem.querySelectorAll(".feedback-btn");
  feedbackBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const type = btn.getAttribute("data-type");
      const id = btn.getAttribute("data-id");
      sendFeedback(id, type === "like");
      feedbackBtns.forEach((b) => (b.disabled = true));
      btn.classList.add("active");
    });
  });

  messagesList.appendChild(msgItem);
  return msgItem;
}

function appendTypingIndicator() {
  const typingItem = document.createElement("div");
  typingItem.className = "message-item bot";
  typingItem.innerHTML = `
    <div class="message-avatar">🎓</div>
    <div class="message-bubble">
      <div class="typing-dots">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  messagesList.appendChild(typingItem);
  return typingItem;
}

async function sendFeedback(messageId, isHelpful) {
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messageId: parseInt(messageId), isHelpful: isHelpful })
    });
  } catch (err) {
    console.warn("Lỗi gửi feedback:", err);
  }
}

async function handleVocabLookup() {
  const word = vocabInput.value.trim();
  if (!word) return;

  vocabResultWrapper.classList.remove("hidden");
  vocabResultWrapper.innerHTML = `
    <div style="text-align: center; padding: 20px;">
      <div class="typing-dots"><span></span><span></span><span></span></div>
      <p style="margin-top: 10px; color: var(--text-secondary);">Đang tra cứu từ điển...</p>
    </div>
  `;

  try {
    const res = await fetch("/api/vocab", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word: word, level: currentLevel, language: currentLanguage })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Không thể tra cứu từ này." }));
      vocabResultWrapper.innerHTML = `<p style="color: var(--danger);">⚠️ ${err.detail}</p>`;
      return;
    }

    const data = await res.json();
    renderVocabResult(data);
  } catch (e) {
    vocabResultWrapper.innerHTML = `<p style="color: var(--danger);">⚠️ Lỗi kết nối máy chủ khi tra từ.</p>`;
  }
}

function renderVocabResult(data) {
  const meaningsHtml = (data.meanings || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("");
  const examplesHtml = (data.examples || []).map((e) => `<li>${escapeHtml(e)}</li>`).join("");
  const synonymsHtml = (data.synonyms || []).map((s) => `<span class="vocab-tag">${escapeHtml(s)}</span>`).join("") || "<em>Không có</em>";
  const antonymsHtml = (data.antonyms || []).map((a) => `<span class="vocab-tag">${escapeHtml(a)}</span>`).join("") || "<em>Không có</em>";

  vocabResultWrapper.innerHTML = `
    <div class="vocab-header">
      <div class="vocab-word">${escapeHtml(data.word)}</div>
      <span class="vocab-pos">${escapeHtml(data.part_of_speech || "Word")}</span>
      <span class="vocab-phonetic">${escapeHtml(data.phonetic || "")}</span>
    </div>

    <div class="vocab-section-title">Ý nghĩa & Định nghĩa</div>
    <ul class="vocab-meanings">${meaningsHtml}</ul>

    <div class="vocab-section-title">Ví dụ minh họa</div>
    <ul class="vocab-examples">${examplesHtml}</ul>

    <div class="vocab-section-title">Từ đồng nghĩa (Synonyms)</div>
    <div class="vocab-tags">${synonymsHtml}</div>

    <div class="vocab-section-title">Từ trái nghĩa (Antonyms)</div>
    <div class="vocab-tags">${antonymsHtml}</div>
  `;
}

function setSendingState(isSending) {
  sendBtn.disabled = isSending;
  messageInput.disabled = isSending;
  if (!isSending) messageInput.focus();
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return "";
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}
