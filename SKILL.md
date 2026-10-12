---
name: pan-transfer-bot
description: Automated tool to parse Twitter/X posts, extract Quark and Baidu Pan cloud storage links, automatically transfer files into personal cloud storage with date-based archiving, generate new dedicated share links, and create engaging social media copy locally without external AI APIs.
---

# Pan-Transfer-Bot Agent Skill

## 1. Overview
The `pan-transfer-bot` skill provides autonomous AI agents with the capability to process social media posts containing cloud drive resource links. It automatically:
- Resolves and parses Quark Pan (`pan.quark.cn`) and Baidu Pan (`pan.baidu.com`) links, including redirected shortlinks.
- Extracts passcodes/access codes from arbitrary text strings or query parameters.
- Transfers the shared files to the user's authenticated cloud drive under a structured date hierarchy (`YYYY/MM/DD`).
- Generates a fresh, permanent, public share link belonging to the user.
- Employs a local deterministic copywriting engine to rewrite marketing posts with formatting, categories, and emojis (zero third-party AI tokens required).

---

## 2. Service Endpoints

The tool runs a FastAPI server at `http://localhost:8000` (or configured `HOST:PORT`).

### Endpoint 1: Link & Text Parser
- **Method**: `POST /api/parse`
- **Request Body**:
  ```json
  {
    "text": "Check out this course: https://pan.quark.cn/s/abcdef123456 code: 8888"
  }
  ```
- **Response**:
  ```json
  {
    "platform": "quark",
    "links": ["https://pan.quark.cn/s/abcdef123456"],
    "share_ids": ["abcdef123456"],
    "passcode": "8888",
    "clean_text": "Check out this course:"
  }
  ```

---

### Endpoint 2: Full Transfer & Copywriting Pipeline
- **Method**: `POST /api/generate`
- **Request Body**:
  ```json
  {
    "text": "Original tweet content with link",
    "link": "https://pan.quark.cn/s/abcdef123456",
    "passcode": "8888",
    "custom_title": "Optional Custom Title",
    "quark_cookie": "Optional Override Cookie",
    "baidu_cookie": "Optional Override Cookie"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "platform": "quark",
    "original_link": "https://pan.quark.cn/s/abcdef123456",
    "new_link": "https://pan.quark.cn/s/your_new_share_link",
    "passcode": "8888",
    "title": "Course Bundle",
    "file_count": 5,
    "files": [...],
    "rewritten_text": "Engaging rewritten post...",
    "final_tweet": "Complete tweet ready to publish with new link",
    "transfer_msg": "转存成功"
  }
  ```

---

### Endpoint 3: Cookie Settings Management
- **GET /api/settings**: Returns boolean indicators for configured credentials (`has_quark`, `has_baidu`).
- **POST /api/settings**: Saves cookies to `settings.json` and updates `.env`.
- **POST /api/settings/auto-detect**: Scans local Chrome/Edge browser storage and imports authenticated cookies.

---

## 3. Autonomous Agent Workflow Guide

When an agent needs to automate content replication and cloud drive transfer:
1. **Health Check**: Call `GET http://localhost:8000/` or `GET http://localhost:8000/api/settings` to verify server availability and credential readiness.
2. **Auto-Detect Credentials (if needed)**: If cookies are missing, trigger `POST /api/settings/auto-detect`.
3. **Submit Raw Content**: Send the raw tweet string to `POST /api/generate`.
4. **Retrieve Results**: Extract `final_tweet` and `new_link` from the JSON response to publish or display to the end user.
