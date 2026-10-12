document.addEventListener('DOMContentLoaded', () => {
  // DOM 元素引用
  const rawContentInput = document.getElementById('rawContentInput');
  const charCount = document.getElementById('charCount');
  const detectedLinkBadge = document.getElementById('detectedLinkBadge');
  const detectedLinkText = document.getElementById('detectedLinkText');
  const passcodeInput = document.getElementById('passcodeInput');
  const customTitleInput = document.getElementById('customTitleInput');

  const fillSampleQuarkBtn = document.getElementById('fillSampleQuarkBtn');
  const fillSampleBaiduBtn = document.getElementById('fillSampleBaiduBtn');
  const clearInputBtn = document.getElementById('clearInputBtn');
  const generateBtn = document.getElementById('generateBtn');

  const statusContainer = document.getElementById('statusContainer');
  const statusProgressBar = document.getElementById('statusProgressBar');
  const statusMessage = document.getElementById('statusMessage');
  const stepItems = [
    document.getElementById('step-1'),
    document.getElementById('step-2'),
    document.getElementById('step-3'),
    document.getElementById('step-4'),
  ];

  const rewrittenTextInput = document.getElementById('rewrittenTextInput');
  const rewrittenCharCount = document.getElementById('rewrittenCharCount');
  const copyRewrittenBtn = document.getElementById('copyRewrittenBtn');

  const platformBadge = document.getElementById('platformBadge');
  const newLinkInput = document.getElementById('newLinkInput');
  const newLinkStatus = document.getElementById('newLinkStatus');
  const openNewLinkBtn = document.getElementById('openNewLinkBtn');
  const copyNewLinkBtn = document.getElementById('copyNewLinkBtn');
  const copyAllBtn = document.getElementById('copyAllBtn');

  // 设置面板元素
  const openSettingsBtn = document.getElementById('openSettingsBtn');
  const settingsModal = document.getElementById('settingsModal');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const clearSettingsBtn = document.getElementById('clearSettingsBtn');
  const autoFetchCookiesBtn = document.getElementById('autoFetchCookiesBtn');
  const configStatusBadge = document.getElementById('configStatusBadge');

  const quarkCookieInput = document.getElementById('quarkCookieInput');
  const baiduCookieInput = document.getElementById('baiduCookieInput');
  const apiBaseUrlInput = document.getElementById('apiBaseUrlInput');

  const toastContainer = document.getElementById('toastContainer');

  // 本地存储键
  const STORAGE_KEY_QUARK = 'pan_quark_cookie';
  const STORAGE_KEY_BAIDU = 'pan_baidu_cookie';
  const STORAGE_KEY_BASE_URL = 'pan_api_base_url';

  // 读取配置（优先从 localStorage 读取，同时异步从服务端 /api/settings 同步以防跨域或换端口丢失）
  async function loadSettings() {
    let quarkCookie = localStorage.getItem(STORAGE_KEY_QUARK) || '';
    let baiduCookie = localStorage.getItem(STORAGE_KEY_BAIDU) || '';
    let apiBaseUrl = localStorage.getItem(STORAGE_KEY_BASE_URL) || '';

    quarkCookieInput.value = quarkCookie;
    baiduCookieInput.value = baiduCookie;
    apiBaseUrlInput.value = apiBaseUrl;

    updateConfigBadge(quarkCookie, baiduCookie);

    // 从服务端 /api/settings 自动同步 Cookie（保证换域名/端口也不会丢失）
    try {
      const resp = await fetch(`${getBaseUrl()}/api/settings`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.quark_cookie && !quarkCookie) {
          quarkCookie = data.quark_cookie;
          localStorage.setItem(STORAGE_KEY_QUARK, quarkCookie);
          quarkCookieInput.value = quarkCookie;
        }
        if (data.baidu_cookie && !baiduCookie) {
          baiduCookie = data.baidu_cookie;
          localStorage.setItem(STORAGE_KEY_BAIDU, baiduCookie);
          baiduCookieInput.value = baiduCookie;
        }
        updateConfigBadge(quarkCookie, baiduCookie);
      }
    } catch (e) {
      console.debug('Failed to sync settings from server:', e);
    }
  }

  function updateConfigBadge(quarkCookie, baiduCookie) {
    if (quarkCookie && baiduCookie) {
      configStatusBadge.textContent = '双网盘已配置';
      configStatusBadge.classList.add('configured');
    } else if (quarkCookie) {
      configStatusBadge.textContent = '夸克已配置';
      configStatusBadge.classList.add('configured');
    } else if (baiduCookie) {
      configStatusBadge.textContent = '百度已配置';
      configStatusBadge.classList.add('configured');
    } else {
      configStatusBadge.textContent = '未配置';
      configStatusBadge.classList.remove('configured');
    }
  }

  loadSettings();

  // 设置面板事件
  openSettingsBtn.addEventListener('click', () => {
    loadSettings();
    settingsModal.classList.remove('hidden');
  });

  function closeSettings() {
    settingsModal.classList.add('hidden');
  }

  closeSettingsBtn.addEventListener('click', closeSettings);
  cancelSettingsBtn.addEventListener('click', closeSettings);

  function sanitizeCookie(raw) {
    if (!raw) return '';
    let text = raw.trim();

    // 1. cURL -b '...' 或 --cookie '...'
    const m_b = text.match(/(?:-b|--cookie)\s+\$?['"]([^'"]+)['"]/);
    if (m_b) return m_b[1].trim();

    // 2. cURL -H 'cookie: ...' 或 -H $'cookie: ...' 或 --header
    const m_h = text.match(/(?:-H|--header)\s+\$?['"](?:cookie|Cookie):\s*([^'"]+)['"]/i);
    if (m_h) return m_h[1].trim();

    // 3. 逐行匹配
    for (const line of text.split('\n')) {
      const lineClean = line.trim().replace(/[\\^]+$/, '').trim();
      const mLineH = lineClean.match(/(?:-H|--header|-b|--cookie)\s+\$?['"]?(?:cookie|Cookie)?\s*[:：=]?\s*([^'"]+)/i);
      if (mLineH && mLineH[1].includes('=')) {
        const val = mLineH[1].trim().replace(/^['"`]+|['"`]+$/g, '');
        if (val.includes('b-user-id') || val.includes('__pus') || val.includes('BDUSS') || val.includes(';')) {
          return val;
        }
      }
      const m = lineClean.match(/^(?:cookie|Cookie)\s*[:：]\s*(.+)$/i);
      if (m) {
        const val = m[1].trim().replace(/^['"`]+|['"`]+$/g, '');
        if (val) return val;
      }
    }

    // 4. JSON / JS 对象 "cookie": "..."
    const mJson = text.match(/['"`]cookie['"`]\s*[:：=]\s*['"`]([^'"`]+)['"`]/i);
    if (mJson) return mJson[1].trim();

    // 5. 扫描包含关键字段的行
    for (const line of text.split('\n')) {
      let lineClean = line.trim().replace(/[\\^]+$/, '').trim().replace(/^['"`]+|['"`]+$/g, '');
      if (lineClean.includes('__pus=') || lineClean.includes('b-user-id=') || lineClean.includes('BDUSS=')) {
        if (lineClean.includes(':')) {
          lineClean = lineClean.substring(lineClean.indexOf(':') + 1).trim();
        }
        return lineClean.replace(/^['"`\s]+|['"`\s]+$/g, '');
      }
    }

    // 6. 前缀剥离
    if (text.toLowerCase().startsWith('cookie:')) {
      text = text.substring(7).trim();
    }

    return text.replace(/[\r\n]+/g, '; ').trim();
  }

  // 粘贴或输入时自动提纯
  quarkCookieInput.addEventListener('input', () => {
    const val = quarkCookieInput.value;
    if (val.includes('curl') || val.includes('-H') || val.includes('Cookie:')) {
      const cleaned = sanitizeCookie(val);
      if (cleaned && cleaned !== val) {
        quarkCookieInput.value = cleaned;
        showToast('已自动识别 cURL / 请求头并提纯夸克 Cookie', 'info');
      }
    }
  });

  baiduCookieInput.addEventListener('input', () => {
    const val = baiduCookieInput.value;
    if (val.includes('curl') || val.includes('-H') || val.includes('Cookie:')) {
      const cleaned = sanitizeCookie(val);
      if (cleaned && cleaned !== val) {
        baiduCookieInput.value = cleaned;
        showToast('已自动识别 cURL / 请求头并提纯百度 Cookie', 'info');
      }
    }
  });

  // 自动从本机浏览器获取 Cookie 按钮事件
  if (autoFetchCookiesBtn) {
    autoFetchCookiesBtn.addEventListener('click', async () => {
      const originalHtml = autoFetchCookiesBtn.innerHTML;
      autoFetchCookiesBtn.disabled = true;
      autoFetchCookiesBtn.innerHTML = `
        <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite; display: inline-block;">
          <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-linecap="round"></circle>
        </svg>
        <span>正在扫描本机 Chrome / Edge 读取 Cookie...</span>
      `;
      try {
        const resp = await fetch(`${getBaseUrl()}/api/settings/auto-detect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await resp.json();
        if (data.success) {
          const qCookie = data.quark_cookie || '';
          const bCookie = data.baidu_cookie || '';

          quarkCookieInput.value = qCookie;
          baiduCookieInput.value = bCookie;
          localStorage.setItem(STORAGE_KEY_QUARK, qCookie);
          localStorage.setItem(STORAGE_KEY_BAIDU, bCookie);

          updateConfigBadge(qCookie, bCookie);

          let found = [];
          if (data.has_quark) found.push('夸克网盘');
          if (data.has_baidu) found.push('百度网盘');
          showToast(`⚡ 成功自动获取 ${found.join(' 和 ')} Cookie 并已保存！`, 'success');
        } else {
          showToast(data.message || '未在本地浏览器中找到网盘 Cookie，请确认已在浏览器中登录网盘', 'info');
        }
      } catch (err) {
        showToast('自动获取异常: ' + err.message, 'error');
      } finally {
        autoFetchCookiesBtn.disabled = false;
        autoFetchCookiesBtn.innerHTML = originalHtml;
      }
    });
  }

  saveSettingsBtn.addEventListener('click', async () => {
    const quarkCookie = sanitizeCookie(quarkCookieInput.value);
    const baiduCookie = sanitizeCookie(baiduCookieInput.value);
    const baseUrl = apiBaseUrlInput.value.trim();

    localStorage.setItem(STORAGE_KEY_QUARK, quarkCookie);
    localStorage.setItem(STORAGE_KEY_BAIDU, baiduCookie);
    localStorage.setItem(STORAGE_KEY_BASE_URL, baseUrl);

    // 填回输入框让用户看到提纯结果
    quarkCookieInput.value = quarkCookie;
    baiduCookieInput.value = baiduCookie;

    // 自动同步持久化保存到服务端
    try {
      await fetch(`${getBaseUrl()}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quark_cookie: quarkCookie,
          baidu_cookie: baiduCookie,
          api_base_url: baseUrl
        })
      });
    } catch (e) {
      console.warn('Failed to sync settings to backend:', e);
    }

    updateConfigBadge(quarkCookie, baiduCookie);
    closeSettings();
    showToast('网盘 Cookie 配置已智能提纯并保存', 'success');
  });

  clearSettingsBtn.addEventListener('click', async () => {
    localStorage.removeItem(STORAGE_KEY_QUARK);
    localStorage.removeItem(STORAGE_KEY_BAIDU);
    localStorage.removeItem(STORAGE_KEY_BASE_URL);

    quarkCookieInput.value = '';
    baiduCookieInput.value = '';
    apiBaseUrlInput.value = '';

    try {
      await fetch(`${getBaseUrl()}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quark_cookie: '',
          baidu_cookie: '',
          api_base_url: ''
        })
      });
    } catch (e) {
      console.warn('Failed to clear settings on backend:', e);
    }

    updateConfigBadge('', '');
    showToast('网盘配置已清空', 'info');
  });

  // Toast 消息函数
  function showToast(msg, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 4000);
  }

  // 示例数据
  const SAMPLE_QUARK = `🔥 2026最新全栈开发从零到精通实战资源包合集，建议收藏慢慢看～
🔗：https://pan.quark.cn/s/12345678abcd`;

  const SAMPLE_BAIDU = `🔥 Python深度学习与大模型实战全套教程，从零基础到进阶项目打包～
链接: https://pan.baidu.com/s/1aBcDeFgHiJkLmNoPqRsTuV 提取码: abcd`;

  fillSampleQuarkBtn.addEventListener('click', () => {
    rawContentInput.value = SAMPLE_QUARK;
    checkInputContent();
  });

  fillSampleBaiduBtn.addEventListener('click', () => {
    rawContentInput.value = SAMPLE_BAIDU;
    checkInputContent();
  });

  clearInputBtn.addEventListener('click', () => {
    rawContentInput.value = '';
    passcodeInput.value = '';
    customTitleInput.value = '';
    checkInputContent();
    rewrittenTextInput.value = '';
    rewrittenCharCount.textContent = '0 字';
    if (newLinkInput) newLinkInput.value = '';
    if (openNewLinkBtn) openNewLinkBtn.classList.add('hidden');
    if (platformBadge) platformBadge.classList.add('hidden');
    if (newLinkStatus) newLinkStatus.textContent = '待生成';
  });

  // 操作栏【粘贴】与【清除】按钮绑定
  const pasteBtn = document.getElementById('pasteBtn');
  if (pasteBtn) {
    pasteBtn.addEventListener('click', async () => {
      try {
        let text = '';
        if (navigator.clipboard && navigator.clipboard.readText) {
          text = await navigator.clipboard.readText();
        }
        if (!text) {
          showToast('剪贴板中暂无文本内容', 'info');
          return;
        }
        rawContentInput.value = text;
        passcodeInput.value = '';
        checkInputContent();
        rawContentInput.focus();
        rawContentInput.style.borderColor = 'var(--cyan-400)';
        rawContentInput.style.boxShadow = '0 0 0 3px rgba(56, 189, 248, 0.25)';
        setTimeout(() => {
          rawContentInput.style.borderColor = '';
          rawContentInput.style.boxShadow = '';
        }, 600);
        showToast('已成功粘贴剪贴板内容', 'success');
      } catch (err) {
        console.warn('Clipboard read error:', err);
        rawContentInput.focus();
        showToast('浏览器限制自动访问剪贴板，请直接按 Ctrl+V 粘贴', 'info');
      }
    });
  }

  const clearBtn = document.getElementById('clearBtn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      clearInputBtn.click();
      showToast('已清空全部输入与生成内容', 'info');
    });
  }

  // 输入监听与智能识别
  rawContentInput.addEventListener('input', checkInputContent);

  function checkInputContent() {
    const val = rawContentInput.value;
    charCount.textContent = `${val.length} 字`;

    const isQuark = /(?:pan|b)\.quark\.cn\/s\/[a-zA-Z0-9]+/i.test(val);
    const isBaidu = /(?:pan|yun)\.baidu\.com\/(?:s\/|share\/link)/i.test(val);
    const hasAnyUrl = /https?:\/\/[^\s\u4e00-\u9fa5\r\n]+/i.test(val);

    if (isQuark) {
      detectedLinkBadge.classList.remove('hidden');
      detectedLinkText.textContent = '⚡ 已检测到夸克网盘直链';
      detectedLinkBadge.style.color = '#38bdf8';
    } else if (isBaidu) {
      detectedLinkBadge.classList.remove('hidden');
      detectedLinkText.textContent = '⚡ 已检测到百度网盘直链';
      detectedLinkBadge.style.color = '#60a5fa';
    } else if (hasAnyUrl) {
      detectedLinkBadge.classList.remove('hidden');
      detectedLinkText.textContent = '🔗 已检测到分享/防封中转链接（生成时自动穿透）';
      detectedLinkBadge.style.color = '#a855f7';
    } else {
      detectedLinkBadge.classList.add('hidden');
    }

    // 自动尝试提取提取码填入（优先取 URL 中自带的 ?pwd=xxxx，其次取文本中的 提取码: xxxx 等）
    const pwdMatch = val.match(/[?&]pwd=([a-zA-Z0-9]{4,6})/i)
      || val.match(/(?:提取码|提取|密码|访问码|code|pwd|key)\s*[:：=\s]\s*([a-zA-Z0-9]{4,6})/i);
    if (pwdMatch) {
      passcodeInput.value = pwdMatch[1];
    } else if (!val.trim()) {
      passcodeInput.value = '';
    }
  }

  rewrittenTextInput.addEventListener('input', () => {
    rewrittenCharCount.textContent = `${rewrittenTextInput.value.length} 字`;
  });

  // 进度步骤切换
  function setProgress(step, percent, msg) {
    statusProgressBar.style.width = `${percent}%`;
    statusMessage.textContent = msg;

    stepItems.forEach((el, index) => {
      el.classList.remove('active', 'done');
      if (index + 1 < step) {
        el.classList.add('done');
      } else if (index + 1 === step) {
        el.classList.add('active');
      }
    });
  }

  function getApiHeaders() {
    return { 'Content-Type': 'application/json' };
  }

  function getBaseUrl() {
    return localStorage.getItem(STORAGE_KEY_BASE_URL) || '';
  }

  // 点击一键生成
  generateBtn.addEventListener('click', async () => {
    const text = rawContentInput.value.trim();
    if (!text) {
      showToast('请先输入网盘链接或推特原帖内容', 'error');
      rawContentInput.focus();
      return;
    }

    generateBtn.disabled = true;
    statusContainer.classList.remove('hidden');

    try {
      // 步骤 1: 识别平台
      setProgress(1, 20, '正在识别网盘类型与提取链接...');
      await new Promise(r => setTimeout(r, 200));

      // 步骤 2: 解析与发起请求
      setProgress(2, 45, '正在请求网盘转存服务...');

      const baseUrl = getBaseUrl();
      const headers = getApiHeaders();

      // 自动提纯本地已存储的 Cookie（若存有历史 cURL/换行内容则自动提纯）
      const rawQuark = localStorage.getItem(STORAGE_KEY_QUARK) || '';
      const rawBaidu = localStorage.getItem(STORAGE_KEY_BAIDU) || '';
      const cleanQuark = sanitizeCookie(rawQuark);
      const cleanBaidu = sanitizeCookie(rawBaidu);

      if (cleanQuark && cleanQuark !== rawQuark) {
        localStorage.setItem(STORAGE_KEY_QUARK, cleanQuark);
      }
      if (cleanBaidu && cleanBaidu !== rawBaidu) {
        localStorage.setItem(STORAGE_KEY_BAIDU, cleanBaidu);
      }

      // 若链接自带 ?pwd=xxxx，强校验并同步纠正 passcodeInput，防止历史残留
      const embeddedPwd = text.match(/[?&]pwd=([a-zA-Z0-9]{4,6})/i);
      if (embeddedPwd) {
        passcodeInput.value = embeddedPwd[1];
      }

      const payload = {
        text: text,
        passcode: passcodeInput.value.trim(),
        custom_title: customTitleInput.value.trim(),
        quark_cookie: cleanQuark,
        baidu_cookie: cleanBaidu
      };

      const response = await fetch(`${baseUrl}/api/generate`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      const resData = await response.json();

      if (!response.ok) {
        throw new Error(resData.detail || resData.error || '生成失败');
      }

      // 步骤 3: 转存状态
      setProgress(3, 75, '正在执行本地智能二创改写...');
      await new Promise(r => setTimeout(r, 200));

      // 步骤 4: 完成
      setProgress(4, 100, '✅ 处理完成！已生成二创文案与对应专属链接');
      stepItems.forEach(el => el.classList.add('done'));

      // 填充二创文案（已直接植入链接）
      const completeCopy = resData.final_tweet || resData.rewritten_text || '';
      rewrittenTextInput.value = completeCopy;
      rewrittenCharCount.textContent = `${completeCopy.length} 字`;

      // 平台标签
      platformBadge.classList.remove('hidden');
      if (resData.platform === 'quark') {
        platformBadge.textContent = '夸克网盘';
        platformBadge.style.color = '#38bdf8';
      } else if (resData.platform === 'baidu') {
        platformBadge.textContent = '百度网盘';
        platformBadge.style.color = '#60a5fa';
      }

      // 用户专属新链接展示（仅展示属于你的专属分享链接）
      if (resData.new_link) {
        let fullNewLink = resData.new_link;
        if (resData.passcode) {
          fullNewLink += ` (提取码: ${resData.passcode})`;
        }
        if (newLinkInput) {
          newLinkInput.value = fullNewLink;
        }
        if (openNewLinkBtn) {
          openNewLinkBtn.href = resData.new_link;
          openNewLinkBtn.classList.remove('hidden');
        }
        if (newLinkStatus) {
          newLinkStatus.textContent = '转存成功 · 专属新链接已生成（永久有效）';
          newLinkStatus.className = 'link-tag tag-success';
        }
      } else {
        if (newLinkInput) {
          newLinkInput.value = '';
        }
        if (openNewLinkBtn) {
          openNewLinkBtn.classList.add('hidden');
        }
        if (newLinkStatus) {
          newLinkStatus.textContent = resData.transfer_msg || '未获取到专属链接';
          newLinkStatus.className = 'link-tag tag-warning';
        }
      }

      if (resData.transfer_msg) {
        showToast(resData.transfer_msg, resData.new_link ? 'success' : 'info');
      } else {
        showToast('一键处理完成！二创文案与你的专属链接已就绪', 'success');
      }

    } catch (err) {
      console.error(err);
      showToast('处理异常: ' + err.message, 'error');
      statusMessage.textContent = '出错: ' + err.message;
    } finally {
      generateBtn.disabled = false;
    }
  });

  // 支持 Ctrl + Enter 快捷键一键生成
  rawContentInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      generateBtn.click();
    }
  });

  function triggerCopyAnimation(button, successHtml) {
    if (!button) return;
    const original = button.innerHTML;
    button.innerHTML = successHtml;
    button.style.borderColor = 'rgba(52, 211, 153, 0.6)';
    button.style.color = '#34d399';
    setTimeout(() => {
      button.innerHTML = original;
      button.style.borderColor = '';
      button.style.color = '';
    }, 1600);
  }

  // 复制文案按钮
  copyRewrittenBtn.addEventListener('click', async () => {
    const val = rewrittenTextInput.value.trim();
    if (!val) {
      showToast('二创文案内容为空', 'error');
      return;
    }
    await navigator.clipboard.writeText(val);
    triggerCopyAnimation(copyRewrittenBtn, `
      <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
      <span>已复制文案！</span>
    `);
    showToast('已复制二创文案', 'success');
  });

  // 复制专属新链接按钮
  copyNewLinkBtn.addEventListener('click', async () => {
    const val = newLinkInput.value.trim();
    if (!val) {
      showToast('你的专属分享链接为空，请先点击一键生成', 'error');
      return;
    }
    await navigator.clipboard.writeText(val);
    triggerCopyAnimation(copyNewLinkBtn, `
      <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
      <span>已复制链接！</span>
    `);
    showToast('已复制你的专属网盘分享链接', 'success');
  });

  // 一键复制文案 + 链接
  copyAllBtn.addEventListener('click', async () => {
    const text = rewrittenTextInput.value.trim();
    const link = newLinkInput.value.trim();

    if (!text && !link) {
      showToast('暂无生成内容可供复制', 'error');
      return;
    }

    let combined = text;
    if (link && !text.includes(link)) {
      combined += `\n\n🔗 资源链接：${link}`;
    }

    await navigator.clipboard.writeText(combined);
    const titleEl = copyAllBtn.querySelector('.btn-copy-title');
    if (titleEl) {
      const originalTitle = titleEl.innerHTML;
      titleEl.innerHTML = `
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        已复制完整文案与链接！
      `;
      setTimeout(() => {
        titleEl.innerHTML = originalTitle;
      }, 1800);
    }
    showToast('🎉 已复制完整二创文案（含网盘链接），可直接粘贴发布！', 'success');
  });
});
