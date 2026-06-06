# Usage Guide

## 1. Deploy the Backend

Host the FastAPI server on any platform that supports Python. **Render** and **Railway** are the easiest options for small businesses — both have free tiers.

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Set this as your start command on whichever platform you choose. Make sure to add all your `.env` variables as environment variables on the platform dashboard — do not upload the `.env` file itself.

---

## 2. Configure Your Business

Edit your `.env` (or platform environment variables) with your real business details:

```env
BUSINESS_NAME="Your Business"
BUSINESS_HOURS="Mon–Fri 9AM–6PM"
BUSINESS_PHONE="+1 234 567 8900"

API_KEY="your-api-key"
API_BASE="https://api.groq.com/openai/v1"
MODEL="llama3-8b-8192"

PROJECT_ID="your-business-id"
ALLOWED_DOMAINS="yourdomain.com,www.yourdomain.com"
WIDGET_API_KEY="your-random-secret"
```

> No API key yet? Leave `API_KEY` blank — the fallback engine will handle responses automatically.

---

## 3. Configure Widget Security

ChatForge supports lightweight widget authentication without requiring a database.

### Required

```env
PROJECT_ID="your-business-id"
ALLOWED_DOMAINS="yourdomain.com,www.yourdomain.com"
```

### Optional but Recommended

```env
WIDGET_API_KEY="your-random-secret"
```

The backend validates:

- Project ID
- Widget API key (if configured)
- Origin header
- Referer header
- Allowed domains

`WIDGET_API_KEY` is optional but strongly recommended for production. When set, any request that does not include the matching key will be rejected with a `401` response.

Requests from unauthorized websites are automatically rejected regardless of whether a widget key is configured.

---

## 4. Embed on Your Website

Once the backend is live, paste this into any page's HTML before the closing `</body>` tag:

```html
<script
  src="https://your-server.com/widget.js"
  data-project-id="your-business-id"
  data-widget-key="your-random-secret"
></script>
```

The chat widget appears automatically in the bottom-right corner of your page.

---

## 5. Test It

Open your website and verify:

### Allowed Domain

- Widget loads
- Chat messages work
- Streaming responses work

### Unauthorized Domain

- Requests return 401 or 403
- Widget cannot use your AI endpoint

### Wrong Widget Key

- Requests return 401

---

## Choosing a Free AI Provider

If you are just getting started, **Groq** is the recommended option — no credit card required.

1. Sign up at [https://console.groq.com](https://console.groq.com)
2. Generate an API key
3. Add the following to your config:

```env
API_BASE="https://api.groq.com/openai/v1"
MODEL="llama-3.1-8b-instant"
```

---

## Troubleshooting

| Problem                       | Fix                                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| Widget doesn't appear         | Check browser console for script errors                                            |
| 401 Invalid Project           | Verify `PROJECT_ID` matches the `data-project-id` attribute in your embed code     |
| 401 Invalid Widget Key        | Verify `WIDGET_API_KEY` matches the `data-widget-key` attribute in your embed code |
| 403 Domain Not Allowed        | Verify `ALLOWED_DOMAINS` includes your website domain                              |
| API errors                    | Verify `API_KEY`, `API_BASE`, and `MODEL` are all set correctly                    |
| Rate limit errors             | Increase `RATE_LIMIT` in `.env`, e.g. `40/minute`. Format: `"<number>/minute"`     |
| Works locally, not production | Verify deployment URL and CORS settings                                            |
