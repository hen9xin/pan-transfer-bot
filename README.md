<div align="center">

# 📦 Pan-Transfer-Bot

**给 AI Agent 用的夸克 / 百度网盘资源整理 Skill + 本地文案助手**

一条分享链接进来 → 识别提取码 → 转存到你的网盘并按日期归档 → 生成你的分享链接 → 本地生成配套文案，零 API 成本。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker Support](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](Dockerfile)
[![Release](https://img.shields.io/github/v/release/hen9xin/pan-transfer-bot?color=orange)](https://github.com/hen9xin/pan-transfer-bot/releases)
[![GitHub Stars](https://img.shields.io/github/stars/hen9xin/pan-transfer-bot?style=social)](https://github.com/hen9xin/pan-transfer-bot/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/hen9xin/pan-transfer-bot)](https://github.com/hen9xin/pan-transfer-bot/commits)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-8A2BE2.svg)](SKILL.md)

**[中文文档](#-中文文档) | [English](#-english)**

<!-- TODO: 替换为实际演示 GIF（建议 ≤15 秒：粘贴 → 一键生成 → 复制） -->
<!-- ![Demo](docs/demo.gif) -->

</div>

---

<a name="-中文文档"></a>
## 📖 中文文档

### 💡 项目简介

**Pan-Transfer-Bot** 帮你整理**自己的**网盘资源工作流：把包含夸克 / 百度网盘链接的文本交给它，它会：

1. **自动识别网盘类型**（夸克网盘 `pan.quark.cn` / 百度网盘 `pan.baidu.com`），并穿透短链 / 中转链接。
2. **自动提取提取码**：支持 URL 参数（`?pwd=`）与"提取码: xxxx"等常见写法。
3. **转存到你的网盘并按 `年/月/日` 归档**，再生成一个由你账号创建的分享链接。
4. **本地生成配套文案**：内置纯本地改写与排版算法（句式调整、Emoji、标签），无需任何外部大模型 API Key。

可以通过 **Web 界面**、**REST API**，或作为 **Agent Skill**（[SKILL.md](SKILL.md)）让 Claude Code 等 AI Agent 直接调用。

### ⚖️ 版权与合规声明（请先阅读）

- 本工具定位为**个人资源整理与文案辅助**，仅处理你**有权保存和分享**的内容（如自己的资料、已获授权或明确允许转发的公开资源）。
- **请勿**用于搬运、洗稿他人原创内容，或去除作者署名、绕过原作者分享渠道。转发他人资源时，建议保留原作者来源与署名。
- 请遵守 Twitter/X、夸克网盘、百度网盘的服务协议，以及所在地法律法规。
- 因不当使用产生的一切后果由使用者自行承担，与开发者无关。详见文末 [免责声明](#️-免责声明--disclaimer)。

### ✨ 核心特性

| 功能 | 说明 |
| :--- | :--- |
| ⚡ **零外部 AI 依赖** | 内置本地确定性文案引擎（`services/text_generator.py`），离线可用、无 API 费用。 |
| 🔄 **双网盘支持** | 夸克网盘与百度网盘，支持短链 / 中转链接自动重定向解析。 |
| 🔑 **提取码识别** | 从混杂文本或 URL 参数中提取密码，减少手动复制。 |
| 📁 **日期归档** | 文件自动保存到个人网盘 `年/月/日` 目录，便于管理。 |
| 🔗 **生成个人分享链接** | 由你的账号创建新的公开分享链接；百度网盘可在 `.env` 中设置默认 4 位提取码。 |
| 💻 **Cookie 一键获取** | 本地 Windows 上可从已登录的 Chrome / Edge 读取网盘 Cookie，免去 F12 手动复制。 |
| 🐳 **Docker 部署** | 提供 `Dockerfile` 与 `docker-compose.yml`，适合服务器 / NAS。 |
| 🤖 **Agent Skill** | 附带 `SKILL.md`，描述接口与用法，供 AI Agent 调用。 |

---

### ⏱️ 30 秒上手（Docker）

```bash
git clone https://github.com/hen9xin/pan-transfer-bot.git
cd pan-transfer-bot
cp .env.example .env
touch settings.json          # 预先创建，避免 Docker 把挂载点建成目录
docker compose up -d --build
```

浏览器打开 **`http://localhost:8000`**（服务器部署则为 `http://<服务器IP>:8000`），在右上角 **「网盘 Cookie 配置」** 填入 Cookie 即可。

查看日志：`docker compose logs -f`

<details>
<summary><b>本地 Python 运行</b></summary>

```bash
git clone https://github.com/hen9xin/pan-transfer-bot.git
cd pan-transfer-bot
python -m pip install -r requirements.txt   # 推荐 Python 3.10+
cp .env.example .env                         # 按需修改，或启动后在 Web 界面配置
python app.py
```

访问 **`http://localhost:8000`**。

</details>

---

### 🤖 作为 Claude Code / Agent Skill 使用

本仓库根目录的 [`SKILL.md`](SKILL.md) 是标准的 Agent Skill 描述文件（含 `name` / `description` 头信息及接口说明）。

**1. 先启动服务**（见上方 Docker 或 Python 方式），确认 `http://localhost:8000` 可访问。

**2. 安装 Skill 到 Claude Code**

```bash
# 个人级（所有项目可用）
mkdir -p ~/.claude/skills/pan-transfer-bot
cp SKILL.md ~/.claude/skills/pan-transfer-bot/

# 或项目级（仅当前项目）
mkdir -p .claude/skills/pan-transfer-bot
cp SKILL.md .claude/skills/pan-transfer-bot/
```

其他支持 `SKILL.md` 的 Agent 框架，按其 skills 目录约定放置即可。

**3. 在对话中直接使用**，例如：

> 帮我把这条内容里的夸克链接转存到我的网盘并生成分享文案：`https://pan.quark.cn/s/xxxx 提取码: 8888`

Agent 会按 `SKILL.md` 调用 `POST /api/parse` 与 `POST /api/generate`。

---

### 🔑 网盘 Cookie 配置

进入 Web 页面，点击右上角 **「网盘 Cookie 配置」**：

1. **一键自动获取**：在本地 Windows 主机运行、且已在 Chrome / Edge 登录过网盘时，点击 **「⚡ 一键从本机浏览器自动获取 Cookie」**。
2. **夸克网盘手动配置**：登录 [pan.quark.cn](https://pan.quark.cn/) → `F12` → `Network` → 刷新 → 选任一请求，复制 `Request Headers` 中的 `Cookie`。
3. **百度网盘手动配置**：登录 [pan.baidu.com](https://pan.baidu.com/) → `F12` → `Network`，复制包含 `BDUSS=` 的 `Cookie`。

> 💡 未配置 Cookie 时仍可使用"文案生成"功能；配置后才会启用转存与分享链接生成。

### 🔒 Cookie 安全说明

- 网盘 Cookie 等同于账号登录凭证，**请勿泄露、截图或提交到仓库**。
- Cookie 只保存在你本机 / 你自己的服务器上：Web 界面保存的配置写入项目目录下的 `settings.json` 与 `.env`，两者均已在 `.gitignore` 中排除。
- 本项目不会把 Cookie 上传到任何第三方服务，仅用于直接请求夸克 / 百度网盘官方接口。
- "一键自动获取"只在本机读取浏览器已登录网盘的 Cookie，需要你主动点击触发。
- 部署到公网服务器时，**不要直接暴露 8000 端口**，建议置于内网、VPN 或带鉴权的反向代理之后（本服务自身不带登录鉴权）。
- 发现安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，不要公开提 issue。

---

### 🔌 REST API

#### 1. 链接与文本解析 `POST /api/parse`
- 请求体：`{"text": "推文内容或网盘链接"}`
- 响应：网盘类型、链接列表、分享 ID、提取码与纯净正文。

#### 2. 转存与文案生成 `POST /api/generate`
```json
{
  "text": "包含网盘链接的原文",
  "link": "",
  "passcode": "",
  "custom_title": "自定义分享标题(可选)",
  "quark_cookie": "",
  "baidu_cookie": ""
}
```
- 响应：`new_link`（你的分享链接）、`passcode`（提取码）、`rewritten_text`（生成文案）、`final_tweet`（组合好的完整文案）。

#### 3. 配置
- `GET /api/settings`：获取当前网盘配置状态。
- `POST /api/settings`：保存网盘 Cookie 与 API 基础地址。
- `POST /api/settings/auto-detect`：触发本机浏览器 Cookie 自动获取。

---

### ❓ FAQ

**Q：需要 OpenAI / DeepSeek 等 API Key 吗？**
不需要。默认使用纯本地文案引擎。`.env.example` 中预留了可选的 DeepSeek 配置项，仓库中有对应模块 `services/ai_rewrite.py`，不配置不影响使用。

**Q：一键获取 Cookie 在 macOS / Linux / Docker 里能用吗？**
该功能面向本地 Windows 上的 Chrome / Edge。其他环境或 Docker 部署时，请按上文手动复制 Cookie。

**Q：会不会导致网盘账号异常？**
本工具通过你自己的 Cookie 调用网盘接口，频繁、大批量操作可能触发平台风控。请适度使用，并遵守平台规则。

**Q：Cookie 过期了怎么办？**
重新登录网盘后再次获取并在「网盘 Cookie 配置」中保存即可。

**Q：Docker 启动后配置丢失？**
`docker-compose.yml` 会把 `./settings.json` 挂载进容器。请在启动前执行 `touch settings.json`，确保它是一个文件。

**Q：支持哪些网盘？**
目前仅夸克网盘与百度网盘。

---

### 📁 项目结构

```text
├── app.py                     # FastAPI 后端与路由
├── config.py                  # 配置加载（.env & settings.json）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example               # 环境变量模板
├── SKILL.md                   # AI Agent Skill 描述
├── SECURITY.md                # 安全漏洞报告说明
├── CONTRIBUTING.md            # 贡献指南
├── LICENSE                    # MIT
├── services/
│   ├── ai_rewrite.py          # 可选 DeepSeek 改写模块
│   ├── baidu.py               # 百度网盘客户端（校验、转存、分享）
│   ├── cookie_extractor.py    # 本机浏览器 Cookie 读取
│   ├── link_parser.py         # 链接解析与提取码识别
│   ├── quark.py               # 夸克网盘客户端（token、转存、分享）
│   └── text_generator.py      # 本地文案引擎
└── static/                    # Web 前端（index.html / script.js / style.css）
```

### 🤝 参与贡献

欢迎 Issue 与 PR，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。如果这个项目对你有帮助，欢迎点个 ⭐ Star！

---

<a name="-english"></a>
## 🌐 English

**Pan-Transfer-Bot** is an agent skill and web tool for organizing **your own** Quark Pan / Baidu Pan resources. Paste text containing a share link and it detects the provider, resolves short links, extracts the passcode, saves the files into your drive under `YYYY/MM/DD`, creates a share link from your account, and drafts accompanying post copy with a local rule-based engine — no LLM API key required. It ships with a FastAPI REST API, a web UI, Docker support, and a [`SKILL.md`](SKILL.md) for Claude Code and other agents.

```bash
git clone https://github.com/hen9xin/pan-transfer-bot.git
cd pan-transfer-bot
cp .env.example .env && touch settings.json
docker compose up -d --build     # then open http://localhost:8000
```

Install as a Claude Code skill: `mkdir -p ~/.claude/skills/pan-transfer-bot && cp SKILL.md ~/.claude/skills/pan-transfer-bot/` (the service must be running).

Cookies stay on your machine (`settings.json` / `.env`, both git-ignored); don't expose port 8000 publicly. Please only process content you have the right to save and share. Report vulnerabilities via [SECURITY.md](SECURITY.md).

---

### ⚠️ 免责声明 / Disclaimer

1. 本项目仅供学习、技术研究与个人效率提升使用。
2. 请遵守 Twitter/X、夸克网盘以及百度网盘的相关平台服务协议与条款。
3. 请尊重数字资源版权，切勿利用本工具传播侵权或违法违规内容。
4. 使用者因操作不当或违反平台规定所产生的后果由使用者自行承担，与本项目开发者无关。

*This project is for learning and personal productivity only. Respect copyright and platform terms of service.*

---

### 💖 赞助与支持 / Support & Sponsor

如果本项目切实帮您节省了繁琐的手动操作时间、提升了推特运营效率，欢迎请作者喝一杯咖啡 ☕ 您的支持是本项目持续优化迭代与维护的最大动力！

If this project helps you save time and automate your social media workflow, consider buying the author a coffee ☕! Your support keeps this open-source project actively maintained.

<div align="center">

| 微信赞助 (WeChat Pay) |
| :---: |
| <img src="assets/sponsor_wechat.jpg" alt="WeChat Pay" width="260" /> |
| **扫码支持作者 · 感谢每一份心意与鼓励 ❤️**<br><sub>Scan with WeChat to support the developer</sub> |

</div>

---

### 📄 License

[MIT License](LICENSE)
