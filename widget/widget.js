/**
 * ChatForge Widget v1.0
 * ─────────────────────────────────────────────────────────────────────────────
 * Embeddable AI chat widget. Drop onto any site with a single <script> tag.
 *
 * Architecture:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │  Bootstrap  →  Config fetch  →  DOM inject  →  Events  │
 *   └─────────────────────────────────────────────────────────┘
 *
 * State machine (widget lifecycle):
 *   CLOSED  ──[click bubble]──▶  OPEN
 *   OPEN    ──[click bubble]──▶  CLOSED
 *   OPEN    ──[send message]──▶  STREAMING  ──[done]──▶  OPEN
 *   OPEN    ──[rate limited]──▶  ERROR_STATE ──[auto]──▶  OPEN
 *
 * All DOM is scoped inside a Shadow DOM to guarantee zero style conflicts
 * with the host page. Widget state is module-scoped (not global).
 * ─────────────────────────────────────────────────────────────────────────────
 */

(function () {
  "use strict";

  // ───────────────────────────────────────────────────────────────────────────
  // 1. BOOTSTRAP — read script tag attributes
  // ───────────────────────────────────────────────────────────────────────────

  const script = document.currentScript;
  const projectId = script.getAttribute("data-project-id") || "";
  const widgetKey = script.getAttribute("data-widget-key") || "";

  // Derive server URL from the script src so the widget works on any domain
  // e.g. <script src="https://myapp.onrender.com/widget.js"> → serverUrl = "https://myapp.onrender.com"
  const serverUrl = script.src.replace(/\/widget\.js(\?.*)?$/, "");

  // Each page-load gets a fresh UUID → fresh session → no memory bleed
  const sessionId = crypto.randomUUID();

  // ───────────────────────────────────────────────────────────────────────────
  // 2. MODULE STATE
  // ───────────────────────────────────────────────────────────────────────────

  const state = {
    isOpen: false,
    isStreaming: false,
    greetingShown: false,
    config: {
      color: "#2563EB",
      greeting: "Hi! How can I help you today?",
      quick_replies: [],
      business_name: "ChatForge",
    },
  };

  // ───────────────────────────────────────────────────────────────────────────
  // 3. STYLES — injected into Shadow DOM to be fully isolated
  // ───────────────────────────────────────────────────────────────────────────

  function buildStyles(color) {
    // Derive accessible colours from the brand colour
    const isDark = isColorDark(color);
    const onColor = isDark ? "#ffffff" : "#1a1a1a";

    return `
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      :host {
        --brand:       ${color};
        --brand-light: ${hexToRgba(color, 0.12)};
        --brand-ring:  ${hexToRgba(color, 0.35)};
        --on-brand:    ${onColor};
        --bg:          #ffffff;
        --bg-alt:      #f4f6f9;
        --surface:     #ffffff;
        --border:      #e2e8f0;
        --text:        #1e293b;
        --text-muted:  #64748b;
        --ai-bubble:   #f1f5f9;
        --user-bubble: var(--brand);
        --on-user:     var(--on-brand);
        --shadow-sm:   0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
        --shadow-md:   0 4px 16px rgba(0,0,0,.12), 0 2px 6px rgba(0,0,0,.08);
        --shadow-lg:   0 20px 48px rgba(0,0,0,.18), 0 8px 16px rgba(0,0,0,.10);
        --radius:      16px;
        --radius-sm:   8px;
        --radius-pill: 9999px;
        --font:        -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        --duration:    220ms;
        --ease:        cubic-bezier(0.34, 1.20, 0.64, 1);
        --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
        font-family: var(--font);
      }

      /* ── Bubble trigger ─────────────────────────────────────── */
      #cf-bubble {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 2147483646;
        width: 60px;
        height: 60px;
        border-radius: var(--radius-pill);
        background: var(--brand);
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: var(--shadow-md), 0 0 0 0 var(--brand-ring);
        transition: transform var(--duration) var(--ease),
                    box-shadow var(--duration) ease;
        outline: none;
      }
      #cf-bubble:hover {
        transform: scale(1.08);
        box-shadow: var(--shadow-lg), 0 0 0 6px var(--brand-ring);
      }
      #cf-bubble:active { transform: scale(0.96); }
      #cf-bubble:focus-visible {
        box-shadow: var(--shadow-md), 0 0 0 3px var(--brand), 0 0 0 6px var(--brand-ring);
      }
      #cf-bubble svg { transition: transform var(--duration) var(--ease); }

      /* Unread badge */
      #cf-badge {
        position: absolute;
        top: -3px;
        right: -3px;
        width: 18px;
        height: 18px;
        border-radius: var(--radius-pill);
        background: #ef4444;
        border: 2px solid #fff;
        font-size: 10px;
        font-weight: 700;
        color: #fff;
        display: none;
        align-items: center;
        justify-content: center;
        line-height: 1;
        font-family: var(--font);
      }
      #cf-badge.visible { display: flex; animation: badge-pop .3s var(--ease); }

      @keyframes badge-pop {
        from { transform: scale(0); }
        to   { transform: scale(1); }
      }

      /* ── Chat panel ─────────────────────────────────────────── */
      #cf-panel {
        position: fixed;
        bottom: 96px;
        right: 24px;
        z-index: 2147483645;
        width: min(380px, calc(100vw - 32px));
        height: min(560px, calc(100vh - 120px));
        background: var(--bg);
        border-radius: var(--radius);
        box-shadow: var(--shadow-lg);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        border: 1px solid var(--border);
        transform-origin: bottom right;
        /* Hidden state */
        transform: scale(0.88) translateY(12px);
        opacity: 0;
        pointer-events: none;
        transition: transform var(--duration) var(--ease),
                    opacity var(--duration) ease;
      }
      #cf-panel.open {
        transform: scale(1) translateY(0);
        opacity: 1;
        pointer-events: all;
      }

      /* ── Header ─────────────────────────────────────────────── */
      #cf-header {
        background: var(--brand);
        color: var(--on-brand);
        padding: 16px 18px 14px;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
        position: relative;
      }
      .cf-avatar {
        width: 36px;
        height: 36px;
        border-radius: var(--radius-pill);
        background: var(--brand-light);
        border: 2px solid rgba(255,255,255,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 18px;
        line-height: 1;
      }
      .cf-header-text { flex: 1; min-width: 0; }
      .cf-name {
        font-weight: 700;
        font-size: 15px;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .cf-status {
        font-size: 12px;
        opacity: 0.85;
        display: flex;
        align-items: center;
        gap: 5px;
        margin-top: 1px;
      }
      .cf-status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #4ade80;
        box-shadow: 0 0 0 2px rgba(74, 222, 128, 0.35);
        animation: pulse-dot 2.5s ease-in-out infinite;
        flex-shrink: 0;
      }
      @keyframes pulse-dot {
        0%, 100% { box-shadow: 0 0 0 2px rgba(74,222,128,0.35); }
        50%       { box-shadow: 0 0 0 4px rgba(74,222,128,0.15); }
      }
      #cf-close-btn {
        background: rgba(255,255,255,0.15);
        border: none;
        color: var(--on-brand);
        cursor: pointer;
        border-radius: var(--radius-sm);
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background var(--duration) ease;
        flex-shrink: 0;
      }
      #cf-close-btn:hover { background: rgba(255,255,255,0.25); }
      #cf-close-btn:focus-visible { outline: 2px solid rgba(255,255,255,0.7); outline-offset: 2px; }

      /* ── Messages area ───────────────────────────────────────── */
      #cf-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        scroll-behavior: smooth;
        /* Custom scrollbar */
        scrollbar-width: thin;
        scrollbar-color: var(--border) transparent;
      }
      #cf-messages::-webkit-scrollbar { width: 4px; }
      #cf-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

      /* ── Message bubbles (improved user bubble styling) ───────── */
      .cf-msg-row {
        display: flex;
        gap: 8px;
        animation: msg-in .25s var(--ease-out) both;
      }
      @keyframes msg-in {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      .cf-msg-row.user { flex-direction: row-reverse; }

      .cf-msg-avatar {
        width: 28px;
        height: 28px;
        border-radius: var(--radius-pill);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 14px;
        margin-top: auto;
        background: var(--brand-light);
        border: 1.5px solid var(--border);
      }
      .cf-msg-row.user .cf-msg-avatar {
        background: var(--brand);
        border-color: var(--brand);
        color: var(--on-brand);
      }

      .cf-bubble {
        max-width: 260px;
        padding: 10px 14px;
        border-radius: 18px;
        font-size: 14px;
        line-height: 1.5;
        color: var(--text);
        background: var(--ai-bubble);
        word-break: break-word;
        white-space: pre-wrap;
        position: relative;
      }
      /* AI bubble: sharp corner on bottom-left */
      .cf-msg-row.ai .cf-bubble {
        border-bottom-left-radius: 4px;
      }
      /* User bubble: improved styling - sharp corner on bottom-right, shadow, better contrast */
      .cf-msg-row.user .cf-bubble {
        background: var(--user-bubble);
        color: var(--on-user);
        border-bottom-right-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
      }

      /* Timestamp */
      .cf-ts {
        font-size: 10px;
        color: var(--text-muted);
        margin-top: 4px;
        padding: 0 4px;
        opacity: 0.7;
        text-align: right;
      }
      .cf-msg-row.ai .cf-ts { text-align: left; }

      /* Typing / streaming cursor */
      .cf-cursor {
        display: inline-block;
        width: 2px;
        height: 14px;
        background: var(--text-muted);
        border-radius: 1px;
        margin-left: 2px;
        vertical-align: middle;
        animation: blink .9s step-end infinite;
      }
      @keyframes blink {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0; }
      }

      /* Typing indicator (dots) */
      #cf-typing {
        display: none;
        padding: 0 4px;
        animation: msg-in .2s var(--ease-out) both;
      }
      #cf-typing.visible { display: flex; align-items: center; gap: 8px; }
      .cf-typing-dots {
        background: var(--ai-bubble);
        border-radius: 18px;
        border-bottom-left-radius: 4px;
        padding: 10px 16px;
        display: flex;
        gap: 5px;
        align-items: center;
      }
      .cf-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--text-muted);
        animation: dot-bounce 1.2s ease-in-out infinite;
      }
      .cf-dot:nth-child(2) { animation-delay: .2s; }
      .cf-dot:nth-child(3) { animation-delay: .4s; }
      @keyframes dot-bounce {
        0%, 60%, 100% { transform: translateY(0); opacity: .4; }
        30%            { transform: translateY(-5px); opacity: 1; }
      }

      /* ── Quick replies ───────────────────────────────────────── */
      #cf-quick-replies {
        padding: 6px 14px 10px;
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        flex-shrink: 0;
        border-top: 1px solid var(--border);
        background: var(--bg-alt);
      }
      #cf-quick-replies.hidden { display: none; }
      .cf-qr-btn {
        border: 1.5px solid var(--brand);
        background: var(--brand-light);
        color: var(--brand);
        border-radius: var(--radius-pill);
        padding: 6px 13px;
        font-size: 12.5px;
        font-weight: 600;
        cursor: pointer;
        font-family: var(--font);
        transition: background var(--duration) ease,
                    color var(--duration) ease,
                    transform 100ms ease;
        white-space: nowrap;
        line-height: 1.4;
      }
      .cf-qr-btn:hover {
        background: var(--brand);
        color: var(--on-brand);
      }
      .cf-qr-btn:active { transform: scale(0.97); }
      .cf-qr-btn:focus-visible {
        outline: 2px solid var(--brand);
        outline-offset: 2px;
      }

      /* ── Input area ─────────────────────────────────────────── */
      #cf-input-area {
        padding: 12px 14px;
        display: flex;
        gap: 9px;
        align-items: flex-end;
        border-top: 1px solid var(--border);
        background: var(--bg);
        flex-shrink: 0;
      }
      #cf-input {
        flex: 1;
        border: 1.5px solid var(--border);
        border-radius: 20px;
        padding: 9px 14px;
        font-size: 14px;
        font-family: var(--font);
        color: var(--text);
        background: var(--bg-alt);
        resize: none;
        outline: none;
        max-height: 100px;
        line-height: 1.5;
        transition: border-color var(--duration) ease,
                    box-shadow var(--duration) ease;
        overflow-y: auto;
      }
      #cf-input:focus {
        border-color: var(--brand);
        box-shadow: 0 0 0 3px var(--brand-ring);
        background: var(--bg);
      }
      #cf-input::placeholder { color: var(--text-muted); }
      #cf-input:disabled { opacity: 0.55; cursor: not-allowed; }

      #cf-send-btn {
        width: 40px;
        height: 40px;
        border-radius: 20px;
        background: var(--brand);
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        color: var(--on-brand);
        transition: background var(--duration) ease,
                    transform 100ms ease,
                    opacity var(--duration) ease;
      }
      #cf-send-btn:hover:not(:disabled) { filter: brightness(1.08); }
      #cf-send-btn:active:not(:disabled) { transform: scale(0.94); }
      #cf-send-btn:disabled { opacity: 0.45; cursor: not-allowed; }
      #cf-send-btn:focus-visible {
        outline: 2px solid var(--brand);
        outline-offset: 2px;
      }

      /* ── Error notice ────────────────────────────────────────── */
      .cf-error-notice {
        text-align: center;
        font-size: 12.5px;
        color: #b91c1c;
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: var(--radius-sm);
        padding: 8px 12px;
        margin: 0 4px;
        animation: msg-in .2s var(--ease-out) both;
      }

      /* ── Powered-by footer ───────────────────────────────────── */
      #cf-footer {
        text-align: center;
        font-size: 10.5px;
        color: var(--text-muted);
        padding: 5px 0 7px;
        flex-shrink: 0;
        letter-spacing: 0.01em;
        background: var(--bg);
      }
      #cf-footer a {
        color: var(--brand);
        text-decoration: none;
        font-weight: 600;
      }
      #cf-footer a:hover { text-decoration: underline; }

      /* ── Mobile: full-screen panel ───────────────────────────── */
      @media (max-width: 480px) {
        #cf-panel {
          bottom: 0;
          right: 0;
          left: 0;
          width: 100%;
          height: 85vh;
          border-radius: var(--radius) var(--radius) 0 0;
          transform-origin: bottom center;
        }
        #cf-bubble {
          bottom: 20px;
          right: 20px;
        }
      }
    `;
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 4. COLOUR UTILITIES
  // ───────────────────────────────────────────────────────────────────────────

  function isColorDark(hex) {
    const c = hex.replace("#", "");
    const r = parseInt(c.slice(0, 2), 16);
    const g = parseInt(c.slice(2, 4), 16);
    const b = parseInt(c.slice(4, 6), 16);
    // Perceived luminance (WCAG formula)
    return 0.299 * r + 0.587 * g + 0.114 * b < 128;
  }

  function hexToRgba(hex, alpha) {
    const c = hex.replace("#", "");
    const r = parseInt(c.slice(0, 2), 16);
    const g = parseInt(c.slice(2, 4), 16);
    const b = parseInt(c.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 5. SVG ICONS — inline for zero network requests
  // ───────────────────────────────────────────────────────────────────────────

  const icons = {
    chat: `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>`,
    close: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>`,
    send: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>`,
    bot: "🤖",
    user: "👤",
  };

  // ───────────────────────────────────────────────────────────────────────────
  // 6. DOM CONSTRUCTION — all inside Shadow DOM
  // ───────────────────────────────────────────────────────────────────────────

  function buildWidget() {
    // Host element — floats above everything on the page
    const host = document.createElement("div");
    host.id = "cf-host";
    host.setAttribute("role", "region");
    host.setAttribute("aria-label", "ChatForge AI assistant");
    document.body.appendChild(host);

    // Shadow root — encapsulates all styles and DOM
    const shadow = host.attachShadow({ mode: "open" });

    // Style tag (will be updated when config loads)
    const styleEl = document.createElement("style");
    styleEl.textContent = buildStyles(state.config.color);
    shadow.appendChild(styleEl);

    // ── Floating bubble ──────────────────────────────────────────────────────
    const bubble = document.createElement("button");
    bubble.id = "cf-bubble";
    bubble.setAttribute("aria-label", "Open chat");
    bubble.setAttribute("aria-haspopup", "dialog");
    bubble.setAttribute("aria-expanded", "false");
    bubble.innerHTML = `${icons.chat}<span id="cf-badge" aria-label="1 unread message"></span>`;
    shadow.appendChild(bubble);

    // ── Chat panel ───────────────────────────────────────────────────────────
    const panel = document.createElement("div");
    panel.id = "cf-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Chat window");
    panel.setAttribute("aria-modal", "true");

    panel.innerHTML = `
      <!-- Header -->
      <div id="cf-header">
        <div class="cf-avatar" aria-hidden="true">🤖</div>
        <div class="cf-header-text">
          <div class="cf-name" id="cf-business-name">${sanitize(state.config.business_name)}</div>
          <div class="cf-status">
            <span class="cf-status-dot" aria-hidden="true"></span>
            <span>Online</span>
          </div>
        </div>
        <button id="cf-close-btn" aria-label="Close chat">${icons.close}</button>
      </div>

      <!-- Messages -->
      <div id="cf-messages" role="log" aria-live="polite" aria-label="Chat messages"></div>

      <!-- Typing indicator -->
      <div id="cf-typing" aria-hidden="true">
        <div class="cf-typing-dots">
          <div class="cf-dot"></div>
          <div class="cf-dot"></div>
          <div class="cf-dot"></div>
        </div>
      </div>

      <!-- Quick replies -->
      <div id="cf-quick-replies" class="hidden" role="group" aria-label="Quick reply options"></div>

      <!-- Input -->
      <div id="cf-input-area">
        <textarea
          id="cf-input"
          rows="1"
          placeholder="Type a message…"
          aria-label="Message input"
          autocomplete="off"
          autocorrect="off"
          spellcheck="true"
          maxlength="2000"
        ></textarea>
        <button id="cf-send-btn" aria-label="Send message" disabled>${icons.send}</button>
      </div>

      <!-- Footer -->
      <div id="cf-footer" aria-hidden="true">
        Powered by <a href="https://github.com/AshminDhungana/chatforge" target="_blank" rel="noopener">ChatForge</a>
      </div>
    `;
    shadow.appendChild(panel);

    return { host, shadow, styleEl, bubble, panel };
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 7. DOM REFERENCES (populated after buildWidget)
  // ───────────────────────────────────────────────────────────────────────────

  let refs = {};

  function cacheRefs(shadow) {
    refs = {
      shadow,
      bubble:       shadow.getElementById("cf-bubble"),
      badge:        shadow.getElementById("cf-badge"),
      panel:        shadow.getElementById("cf-panel"),
      header:       shadow.getElementById("cf-header"),
      businessName: shadow.getElementById("cf-business-name"),
      messages:     shadow.getElementById("cf-messages"),
      typing:       shadow.getElementById("cf-typing"),
      quickReplies: shadow.getElementById("cf-quick-replies"),
      input:        shadow.getElementById("cf-input"),
      sendBtn:      shadow.getElementById("cf-send-btn"),
      closeBtn:     shadow.getElementById("cf-close-btn"),
    };
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 8. WIDGET OPEN / CLOSE
  // ───────────────────────────────────────────────────────────────────────────

  function openWidget() {
    state.isOpen = true;
    refs.panel.classList.add("open");
    refs.bubble.setAttribute("aria-expanded", "true");
    refs.bubble.setAttribute("aria-label", "Close chat");
    refs.bubble.innerHTML = `${icons.close}<span id="cf-badge"></span>`;

    // Hide unread badge
    refs.badge = refs.shadow.getElementById("cf-badge");
    if (refs.badge) refs.badge.classList.remove("visible");

    // Show greeting + quick replies on first open
    if (!state.greetingShown) {
      state.greetingShown = true;
      appendMessage("ai", state.config.greeting);
      renderQuickReplies(state.config.quick_replies);
    }

    // Focus input for keyboard users after animation
    setTimeout(() => refs.input.focus(), 240);
  }

  function closeWidget() {
    state.isOpen = false;
    refs.panel.classList.remove("open");
    refs.bubble.setAttribute("aria-expanded", "false");
    refs.bubble.setAttribute("aria-label", "Open chat");
    refs.bubble.innerHTML = `${icons.chat}<span id="cf-badge" class="${state.greetingShown ? "" : "visible"}" aria-label="1 unread message"></span>`;
    refs.badge = refs.shadow.getElementById("cf-badge");
  }

  function toggleWidget() {
    state.isOpen ? closeWidget() : openWidget();
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 9. MESSAGE RENDERING
  // ───────────────────────────────────────────────────────────────────────────

  function sanitize(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTime() {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date());
  }

  /**
   * Append a complete message bubble.
   * Returns the bubble <div> so callers can update it during streaming.
   */
  function appendMessage(role, text, opts = {}) {
    const row = document.createElement("div");
    row.className = `cf-msg-row ${role}`;

    const avatarEl = document.createElement("div");
    avatarEl.className = "cf-msg-avatar";
    avatarEl.setAttribute("aria-hidden", "true");
    avatarEl.textContent = role === "ai" ? "🤖" : "👤";

    const bubbleEl = document.createElement("div");
    bubbleEl.className = "cf-bubble";
    bubbleEl.textContent = text;

    // Streaming cursor (shown during streaming)
    const cursorEl = document.createElement("span");
    cursorEl.className = "cf-cursor";
    cursorEl.setAttribute("aria-hidden", "true");

    const wrapper = document.createElement("div");
    wrapper.style.display = "flex";
    wrapper.style.flexDirection = "column";
    wrapper.style.alignItems = role === "user" ? "flex-end" : "flex-start";

    if (opts.withCursor) bubbleEl.appendChild(cursorEl);

    wrapper.appendChild(bubbleEl);

    // Add timestamp
    if (!opts.noTimestamp) {
      const tsEl = document.createElement("div");
      tsEl.className = "cf-ts";
      tsEl.textContent = formatTime();
      wrapper.appendChild(tsEl);
    }

    if (role === "ai") {
      row.appendChild(avatarEl);
      row.appendChild(wrapper);
    } else {
      row.appendChild(wrapper);
      row.appendChild(avatarEl);
    }

    refs.messages.appendChild(row);
    scrollToBottom();

    return { bubbleEl, cursorEl, row };
  }

  function appendErrorNotice(message) {
    const el = document.createElement("div");
    el.className = "cf-error-notice";
    el.setAttribute("role", "alert");
    el.textContent = message;
    refs.messages.appendChild(el);
    scrollToBottom();
    // Auto-remove after 5s
    setTimeout(() => el.remove(), 5000);
  }

  function scrollToBottom() {
    refs.messages.scrollTop = refs.messages.scrollHeight;
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 10. QUICK REPLIES
  // ───────────────────────────────────────────────────────────────────────────

  function renderQuickReplies(replies) {
    if (!replies || replies.length === 0) return;

    refs.quickReplies.innerHTML = "";
    replies.forEach((label) => {
      const btn = document.createElement("button");
      btn.className = "cf-qr-btn";
      btn.textContent = label;
      btn.setAttribute("aria-label", `Quick reply: ${label}`);
      btn.addEventListener("click", () => {
        hideQuickReplies();
        sendMessage(label);
      });
      refs.quickReplies.appendChild(btn);
    });
    refs.quickReplies.classList.remove("hidden");
  }

  function hideQuickReplies() {
    refs.quickReplies.classList.add("hidden");
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 11. INPUT HANDLING
  // ───────────────────────────────────────────────────────────────────────────

  function setInputDisabled(disabled) {
    refs.input.disabled = disabled;
    refs.sendBtn.disabled = disabled;
  }

  function clearInput() {
    refs.input.value = "";
    refs.input.style.height = "";
    refs.input.style.height = refs.input.scrollHeight + "px";
    // explicitly disable send button because input is empty
    refs.sendBtn.disabled = true;
  }

  function autoResizeTextarea() {
    refs.input.style.height = "auto";
    refs.input.style.height = Math.min(refs.input.scrollHeight, 100) + "px";
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 12. TYPING INDICATOR
  // ───────────────────────────────────────────────────────────────────────────

  function showTyping() {
    refs.typing.classList.add("visible");
    refs.typing.setAttribute("aria-hidden", "false");
    scrollToBottom();
  }

  function hideTyping() {
    refs.typing.classList.remove("visible");
    refs.typing.setAttribute("aria-hidden", "true");
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 13. API — STREAMING CHAT
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Streams a reply from the backend and renders tokens progressively.
   *
   * Protocol: text/event-stream
   *   - Each line: `data: <token>`
   *   - Terminal:  `data: [DONE]`
   *
   * Error handling:
   *   - Network failure      → error notice
   *   - HTTP 429             → rate-limit notice
   *   - HTTP 401/403         → auth error notice
   *   - Server 5xx           → generic error notice
   *   - Stream timeout       → partial message shown, notice appended
   */
  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || state.isStreaming) return;

    state.isStreaming = true;
    hideQuickReplies();
    setInputDisabled(true);
    clearInput();

    // Render user message
    appendMessage("user", trimmed);

    // Show typing indicator briefly, then switch to streaming bubble
    showTyping();

    let response;
    try {
      response = await fetch(`${serverUrl}/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          session_id: sessionId,
          project_id: projectId,
          widget_key: widgetKey || undefined,
        }),
        signal: AbortSignal.timeout(60_000), // 60s hard timeout
      });
    } catch (err) {
      hideTyping();
      const msg =
        err.name === "TimeoutError"
          ? "Request timed out. Please try again."
          : "Connection error. Check your network and try again.";
      appendErrorNotice(msg);
      finishStreaming();
      return;
    }

    if (!response.ok) {
      hideTyping();
      const errorMessages = {
        401: "Authentication error — invalid widget credentials.",
        403: "Access denied — this domain is not authorized.",
        429: "You're sending messages too fast. Please wait a moment.",
        500: "The server encountered an error. Please try again.",
        503: "The server is temporarily unavailable.",
      };
      appendErrorNotice(
        errorMessages[response.status] ||
          `Unexpected error (HTTP ${response.status}). Please try again.`
      );
      finishStreaming();
      return;
    }

    // ── Stream processing ────────────────────────────────────────────────────
    hideTyping();
    const { bubbleEl, cursorEl } = appendMessage("ai", "", { withCursor: true, noTimestamp: true });
    let buffer = ""; // Accumulates partial SSE lines between chunks
    let fullText = ""; // Complete AI reply

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE lines end with \n\n; process all complete events in the buffer
        const events = buffer.split("\n\n");
        buffer = events.pop(); // Last element may be incomplete

        for (const event of events) {
          const line = event.trim();
          if (!line.startsWith("data: ")) continue;

          const token = line.slice(6); // strip "data: "
          if (token === "[DONE]") break;

          fullText += token;
          // Update bubble text without inner HTML to prevent XSS
          bubbleEl.textContent = fullText;
          bubbleEl.appendChild(cursorEl); // Keep cursor at end
          scrollToBottom();
        }
      }
    } catch (streamErr) {
      // Partial message received — show what we got
      if (!fullText) {
        appendErrorNotice("Stream interrupted. Please try again.");
      }
    } finally {
      // Remove cursor, add timestamp
      cursorEl.remove();
      const tsEl = document.createElement("div");
      tsEl.className = "cf-ts";
      tsEl.textContent = formatTime();
      bubbleEl.closest(".cf-msg-row").querySelector("div[style]").appendChild(tsEl);

      scrollToBottom();
      finishStreaming();
    }
  }

  function finishStreaming() {
    state.isStreaming = false;
    setInputDisabled(false);
    // ensure send button is disabled if input is empty after streaming
    refs.sendBtn.disabled = !refs.input.value.trim();
    refs.input.focus();
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 14. CONFIG FETCH
  // ───────────────────────────────────────────────────────────────────────────

  async function fetchConfig(styleEl) {
    try {
      const res = await fetch(`${serverUrl}/api/v1/config`);
      if (!res.ok) return;

      const cfg = await res.json();

      // Update state
      state.config = {
        color:        cfg.color         || state.config.color,
        greeting:     cfg.greeting      || state.config.greeting,
        quick_replies: cfg.quick_replies || [],
        business_name: cfg.business_name || state.config.business_name,
      };

      // Patch styles with real brand colour
      styleEl.textContent = buildStyles(state.config.color);

      // Patch header text
      if (refs.businessName) refs.businessName.textContent = state.config.business_name;
    } catch {
      // Silently fall back to defaults — widget still works
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 15. EVENT LISTENERS
  // ───────────────────────────────────────────────────────────────────────────

  function attachEvents() {
    // Bubble toggle
    refs.bubble.addEventListener("click", toggleWidget);

    // Close button
    refs.closeBtn.addEventListener("click", closeWidget);

    // Send button
    refs.sendBtn.addEventListener("click", () => {
      sendMessage(refs.input.value);
    });

    // Enter to send (Shift+Enter for newline)
    refs.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(refs.input.value);
      }
    });

    // Auto-resize textarea + enable/disable send button
    refs.input.addEventListener("input", () => {
      autoResizeTextarea();
      refs.sendBtn.disabled = !refs.input.value.trim() || state.isStreaming;
    });

    // Escape closes panel
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && state.isOpen) closeWidget();
    });

    // Click outside closes panel
    document.addEventListener("click", (e) => {
      if (!state.isOpen) return;
      // The shadow host contains both the bubble and the panel
      if (!e.composedPath().includes(refs.shadow.host)) {
        closeWidget();
      }
    });
  }

  // ───────────────────────────────────────────────────────────────────────────
  // 16. INITIALISATION
  // ───────────────────────────────────────────────────────────────────────────

  async function init() {
    // Build DOM (sync — must happen before any async work)
    const { shadow, styleEl, bubble, panel } = buildWidget();
    cacheRefs(shadow);
    attachEvents();

    // Show unread badge on bubble while we load config
    const badge = shadow.getElementById("cf-badge");
    if (badge) badge.classList.add("visible");

    // Fetch config from server (async — updates colour, greeting, etc.)
    await fetchConfig(styleEl);

    // Update badge reference after DOM update
    refs.badge = shadow.getElementById("cf-badge");
  }

  // Run after DOM is ready (supports both head and body placement)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();