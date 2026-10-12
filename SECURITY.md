# 🛡️ Security Policy

We take the security of **Pan-Transfer-Bot** and the privacy of user credentials very seriously. This document outlines our security policies and procedures for reporting vulnerabilities.

---

## 📦 Supported Versions

| Version | Supported          |
| :------ | :----------------- |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability or credential leak issue in this repository, **please DO NOT report it via public GitHub issues.**

Instead, please report it responsibly:
1. Contact the maintainers privately via GitHub Security Advisories ([Draft an Advisory](https://github.com/)) or via security email.
2. Include a detailed description of the vulnerability, steps to reproduce, and impact assessment.
3. Allow the maintainers reasonable time to review, patch, and release an update before public disclosure.

---

## 🔐 Credentials & Sensitive Data Handling

### 1. Cloud Drive Cookies & BDUSS Protection
- Pan-Transfer-Bot interacts with cloud drive web APIs using session cookies (such as Baidu's `BDUSS` and Quark's `b-user-id` / token).
- These cookies grant full access to your cloud drive account. **Treat them with the same confidentiality as your primary account password.**
- Never share your `.env` or `settings.json` file.
- The `.gitignore` file is strictly configured to prevent accidental staging or committing of `.env`, `settings.json`, and cookie dumps.

### 2. Network & Public Exposure
- By default, the application binds to `HOST=0.0.0.0` on port `8000`.
- If you deploy this service on a public VPS or cloud server:
  - Do **NOT** expose port 8000 directly to the public internet without an authentication layer.
  - Put the service behind a reverse proxy (e.g. Nginx, Caddy, or Cloudflare Tunnel) with HTTPS/TLS.
  - Implement basic HTTP authentication (e.g., HTTP Basic Auth or OAuth / Cloudflare Access) to restrict unauthorized access to your instance.

### 3. Docker Container Isolation
- When running in Docker, credentials are provided via environment variables or volume mounts.
- Ensure proper permissions on mounted files (`chmod 600 settings.json` on Linux).
