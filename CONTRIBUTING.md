# 🤝 Contributing to Pan-Transfer-Bot

Thank you for your interest in contributing to **Pan-Transfer-Bot**! We welcome bug reports, feature enhancements, documentation improvements, and code contributions from everyone.

---

## 📜 Code of Conduct

By participating in this project, you agree to abide by our code of conduct:
- Be respectful, courteous, and constructive in all discussions and pull requests.
- Foster an inclusive, open, and welcoming environment for everyone.
- Focus on what is best for the overall community and project quality.

---

## 🔒 Golden Rule: Security & Privacy First

> [!CAUTION]
> **NEVER commit personal credentials, real cookies, or secrets!**
> - Do NOT commit `.env` or `settings.json` files containing actual tokens.
> - Ensure all tests, samples, and documentation use dummy tokens (e.g. `your_cookie_here`, `1234abcd`).
> - Keep extraction passwords generic or randomized.

---

## 🛠️ Development Setup

### 1. Fork & Clone
```bash
git clone https://github.com/hen9xin/pan-transfer-bot.git
cd pan-transfer-bot
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Create a Working Branch
```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-description
```

---

## 📝 Commit Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation only changes
- `style:` Changes that do not affect the meaning of the code (formatting, white-space)
- `refactor:` A code change that neither fixes a bug nor adds a feature
- `perf:` A code change that improves performance
- `test:` Adding missing tests or correcting existing tests
- `chore:` Changes to the build process, tooling, or libraries

**Examples:**
- `feat(quark): add support for batch file transfer`
- `fix(parser): resolve issue parsing url parameters with special characters`
- `docs: update deployment guidelines in README.md`

---

## 🧪 Submitting a Pull Request

1. **Verify your changes locally**:
   - Ensure the FastAPI server boots up cleanly: `python app.py`.
   - Test both Quark Pan and Baidu Pan parsing capabilities.
   - Verify that the Web UI operates without console errors.
2. **Push to your fork**:
   ```bash
   git push origin feat/your-feature-name
   ```
3. **Open a Pull Request**:
   - Provide a clear and concise title describing the change.
   - Fill out the PR description with context, rationale, and reproduction steps.
   - Tag any relevant issues (e.g., `Fixes #12`).

---

## 💡 Ideas for Contribution

- [ ] Additional cloud drive providers (e.g. 123pan, Aliyun Drive, PikPak).
- [ ] Integration with Twitter/X API v2 for direct automated scheduled posting.
- [ ] Multi-account rotation pool for handling transfer quotas.
- [ ] Localization and i18n support in the frontend UI.

Thank you for helping make **Pan-Transfer-Bot** better! 🚀
