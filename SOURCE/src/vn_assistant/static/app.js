"use strict";
const $ = (id) => document.getElementById(id);
const STORE = "triviet.chats.v1";
let chats = [],
  active = null,
  controller = null,
  pending = false,
  requestEpoch = 0,
  scrollFrame = null;
try {
  const saved = JSON.parse(localStorage.getItem(STORE) || "[]");
  if (Array.isArray(saved))
    chats = saved
      .filter((c) => c && typeof c.id === "string" && Array.isArray(c.messages))
      .slice(0, 20)
      .map((c) => ({
        id: c.id,
        title:
          typeof c.title === "string"
            ? c.title.slice(0, 60)
            : "Cuộc trò chuyện mới",
        messages: c.messages
          .filter(
            (m) =>
              m &&
              ["user", "assistant"].includes(m.role) &&
              typeof m.content === "string",
          )
          .slice(-60),
      }));
} catch (_) {}
const make = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};
function persist() {
  try {
    const saved = chats
      .slice(0, 20)
      .map((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.result
            ? {
                ...m,
                result: {
                  status: m.result.status,
                  citations: m.result.citations?.map(
                    ({ number, kind, title, source, source_url }) => ({
                      number,
                      kind,
                      title,
                      source,
                      source_url,
                    }),
                  ),
                  timings_ms: m.result.timings_ms,
                  context_resolution: m.result.context_resolution,
                },
              }
            : m,
        ),
      }));
    localStorage.setItem(STORE, JSON.stringify(saved));
  } catch (_) {
    notify(
      "Trình duyệt chưa lưu được lịch sử. Bạn vẫn có thể tiếp tục hỏi đáp trong phiên này.",
    );
  }
}
function notify(text) {
  $("notice").textContent = text || "";
  $("notice").hidden = !text;
}
function menu(open) {
  $("sidebar").classList.toggle("open", open);
  $("shade").hidden = !open;
  $("menu").setAttribute("aria-expanded", String(open));
  document.querySelector(".workspace").inert = open && innerWidth <= 750;
  if (innerWidth <= 750) (open ? $("new-chat") : $("menu")).focus();
}
function current() {
  return chats.find((c) => c.id === active);
}
function newChat() {
  cancel();
  active = null;
  render();
  menu(false);
  $("question").value = "";
  inputState();
  $("question").focus();
}
function history() {
  const root = $("sessions");
  root.replaceChildren();
  $("session-count").textContent = String(chats.length);
  if (!chats.length)
    root.append(
      make(
        "p",
        "history-empty",
        "Những câu chuyện bạn khám phá sẽ xuất hiện ở đây.",
      ),
    );
  for (const chat of chats) {
    const button = make(
      "button",
      "session" + (chat.id === active ? " active" : ""),
      chat.title || "Cuộc trò chuyện mới",
    );
    button.title = chat.title || "Cuộc trò chuyện mới";
    button.onclick = () => {
      cancel();
      active = chat.id;
      render();
      menu(false);
    };
    root.append(button);
  }
}
function inputState() {
  const input = $("question");
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
  $("character-count").textContent = `${input.value.length} / 2000`;
  $("send").disabled = pending || input.value.trim().length < 2;
  $("stop").hidden = !pending;
}
function scroll() {
  cancelAnimationFrame(scrollFrame);
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null;
    if (current()?.messages.length)
      $("conversation-scroll").scrollTop = $("conversation-scroll").scrollHeight;
  });
}
function assistantHead() {
  const head = make("div", "assistant-head");
  const img = make("img");
  img.src = "/assets/mark.svg";
  img.alt = "";
  head.append(img, make("span", "", "Tri Việt"));
  return head;
}
function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch (_) {
    return null;
  }
}
function sourceList(citations) {
  const details = make("details", "sources");
  details.append(make("summary", "", `${citations.length} nguồn minh chứng`));
  const grid = make("div", "source-grid");
  citations.forEach((source, index) => {
    const card = make("article", "source-card");
    card.append(
      make(
        "small",
        "",
        `[${source.number || index + 1}] · ${source.kind === "kg" ? "ĐỒ THỊ TRI THỨC" : "VĂN BẢN TRUY XUẤT"}`,
      ),
      make("strong", "", source.title || "Minh chứng trong bộ dữ liệu"),
      make("p", "", source.source || "Dữ liệu cục bộ"),
    );
    const url = safeUrl(source.source_url);
    if (url) {
      const link = make("a", "", "Mở tài liệu gốc ↗");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      card.append(link);
    } else card.append(make("p", "", "Bản ghi nguồn được lưu trong hệ thống"));
    grid.append(card);
  });
  details.append(grid);
  return details;
}
function messageView(message) {
  const article = make("article", "message " + message.role);
  if (message.role === "user") {
    article.append(make("div", "user-text", message.content));
    return article;
  }
  article.append(assistantHead());
  if (message.error) {
    article.append(make("div", "error-text", message.content));
    const retry = make("button", "retry", "Thử lại câu hỏi ↻");
    retry.onclick = () => {
      $("question").value = message.question || "";
      inputState();
      $("question").focus();
    };
    article.append(retry);
    return article;
  }
  const result = message.result || {};
  const text = (message.content || "").split("\n\nNguồn minh chứng:")[0];
  article.append(make("div", "answer-text", text));
  const labels = {
    answered: "Đã đối chiếu minh chứng",
    partial: "Có thông tin cần làm rõ",
    abstained: "Chưa đủ căn cứ để kết luận",
    needs_clarification: "Cần thêm thông tin",
  };
  article.append(
    make(
      "div",
      "answer-status " + (result.status || ""),
      labels[result.status] || "Phản hồi từ Tri Việt",
    ),
  );
  if (Array.isArray(result.citations) && result.citations.length)
    article.append(sourceList(result.citations));
  const footer = make("div", "answer-footer");
  const total = result.timings_ms?.total;
  if (Number.isFinite(total))
    footer.append(make("span", "", `${(total / 1000).toFixed(2)} giây`));
  if (result.context_resolution?.resolved)
    footer.append(make("span", "", "Đã liên kết ngữ cảnh"));
  const copy = make("button", "", "Sao chép");
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      copy.textContent = "Đã sao chép";
    } catch (_) {
      copy.textContent = "Chưa sao chép được";
    }
  };
  footer.append(copy);
  article.append(footer);
  return article;
}
function render() {
  cancelAnimationFrame(scrollFrame);
  scrollFrame = null;
  history();
  const messages = current()?.messages || [];
  $("welcome").hidden = Boolean(messages.length);
  $("messages").replaceChildren(...messages.map(messageView));
  inputState();
  if (messages.length) scroll();
  else $("conversation-scroll").scrollTo({ top: 0, behavior: "instant" });
}
function cancel() {
  requestEpoch++;
  if (controller) controller.abort();
  controller = null;
  pending = false;
  $("pending")?.remove();
  inputState();
}
async function connect() {
  $("connection-label").textContent = "Đang kiểm tra…";
  $("connection-dot").className = "dot";
  try {
    let response = await fetch("/health", {
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error();
    let status = await response.json();
    if (!status.llm?.ready || !status.kg_ready || !status.faiss_ready) {
      $("connection-label").textContent = "Đang chuẩn bị mô hình…";
      response = await fetch("/v1/system/warmup", {
        method: "POST",
        signal: AbortSignal.timeout(90000),
      });
      if (!response.ok) throw new Error();
    }
    $("connection-label").textContent = "Sẵn sàng cùng bạn khám phá";
    $("connection-dot").className = "dot ready";
  } catch (_) {
    $("connection-label").textContent = "Mô hình chưa sẵn sàng · thử lại ↻";
    $("connection-dot").className = "dot offline";
  }
}
async function submit(text) {
  text = text.trim();
  if (pending || text.length < 2 || text.length > 2000) return;
  notify("");
  let chat = current();
  if (!chat) {
    chat = { id: crypto.randomUUID(), title: text.slice(0, 50), messages: [] };
    chats.unshift(chat);
    chats = chats.slice(0, 20);
    active = chat.id;
  }
  const previous = chat.messages
    .filter((m) => !m.error)
    .slice(-12)
    .map((m) => ({ role: m.role, content: m.content.slice(0, 12000) }));
  chat.messages.push({ role: "user", content: text });
  pending = true;
  const epoch = ++requestEpoch;
  controller = new AbortController();
  const thisController = controller;
  $("question").value = "";
  persist();
  render();
  const waiting = make("article", "message assistant");
  waiting.id = "pending";
  waiting.append(assistantHead());
  const dots = make("div", "typing");
  dots.append(make("i"), make("i"), make("i"));
  waiting.append(
    dots,
    make("p", "pending-label", "Đang tra cứu và đối chiếu minh chứng…"),
  );
  $("messages").append(waiting);
  scroll();
  const timer = setTimeout(() => thisController.abort("timeout"), 90000);
  try {
    const response = await fetch("/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text, top_k: 3, history: previous }),
      signal: thisController.signal,
    });
    let result;
    try {
      result = await response.json();
    } catch (_) {
      throw new Error("Phản hồi từ máy chủ chưa đọc được. Bạn thử lại nhé.");
    }
    if (!response.ok) {
      if (response.status === 503)
        throw new Error(
          "Mô hình hoặc dữ liệu đang chưa sẵn sàng. Bạn kiểm tra kết nối rồi thử lại nhé.",
        );
      if (response.status === 422 || response.status === 400)
        throw new Error(
          "Câu hỏi chưa phù hợp hoặc quá dài. Bạn thử diễn đạt ngắn hơn nhé.",
        );
      if (response.status === 429)
        throw new Error(
          "Hệ thống đang xử lý nhiều câu hỏi. Bạn thử lại sau ít giây nhé.",
        );
      throw new Error("Máy chủ gặp lỗi khi xử lý. Bạn có thể thử lại câu hỏi.");
    }
    if (epoch !== requestEpoch) return;
    chat.messages.push({
      role: "assistant",
      content: result.answer || "Mình chưa có đủ dữ liệu cho câu hỏi này.",
      result,
    });
  } catch (error) {
    if (epoch !== requestEpoch) return;
    const message = thisController.signal.aborted
      ? "Đã hết thời gian chờ phản hồi. Bạn có thể thử lại câu hỏi."
      : error instanceof TypeError
        ? "Không kết nối được backend. Bạn kiểm tra máy chủ và thử lại nhé."
        : error.message;
    chat.messages.push({
      role: "assistant",
      content: message,
      error: true,
      question: text,
    });
  } finally {
    clearTimeout(timer);
    if (epoch === requestEpoch) {
      pending = false;
      controller = null;
      chat.messages = chat.messages.slice(-60);
      persist();
      render();
      $("question").focus();
    }
  }
}
$("chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submit($("question").value);
});
$("question").addEventListener("input", inputState);
$("question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    submit($("question").value);
  }
});
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.onclick = () => submit(button.dataset.prompt);
});
$("new-chat").onclick = newChat;
$("stop").onclick = () => {
  cancel();
  notify("Đã dừng chờ phản hồi. Bạn có thể gửi câu hỏi khác.");
};
$("menu").onclick = () => menu(!$("sidebar").classList.contains("open"));
$("shade").onclick = () => menu(false);
$("reconnect").onclick = connect;
$("about").onclick = () => $("scope-dialog").showModal();
$("close-about").onclick = () => $("scope-dialog").close();
$("clear-chat").onclick = () => {
  if (!active) return;
  if (confirm("Xóa cuộc trò chuyện này khỏi trình duyệt?")) {
    chats = chats.filter((c) => c.id !== active);
    persist();
    newChat();
  }
};
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    newChat();
  }
  if (event.key === "Escape") menu(false);
});
render();
connect();
