/**
 * 论文分析助手 - 聊天界面前端逻辑 v3
 * 支持多会话切换、消息持久化、打断生成
 */

// ========== 全局状态 ==========
const state = {
    sessionId: null,
    paperTitle: '',
    paperLoaded: false,
    isProcessing: false,
    processingSessionId: null,     // 正在生成的是哪个会话
    currentAbortController: null,  // 只由停止按钮触发 abort
};

// 所有会话的数据存储
const sessionStore = {};

// ========== DOM 元素 ==========
const $ = (sel) => document.querySelector(sel);

const els = {
    sidebar: $('#sidebar'),
    chatList: $('#chatList'),
    messageList: $('#messageList'),
    welcomeScreen: $('#welcomeScreen'),
    currentPaperTitle: $('#currentPaperTitle'),
    currentPaperSubtitle: $('#currentPaperSubtitle'),
    quickActions: $('#quickActions'),
    messageInput: $('#messageInput'),
    btnSend: $('#btnSend'),
    btnStop: $('#btnStop'),
    btnAttach: $('#btnAttach'),
    btnNewChat: $('#btnNewChat'),
    btnToggleSidebar: $('#btnToggleSidebar'),
    btnSettings: $('#btnSettings'),
    btnDownload: $('#btnDownload'),
    fileInput: $('#fileInput'),
    dragOverlay: $('#dragOverlay'),
    uploadAreaSidebar: $('#uploadAreaSidebar'),
};

// ========== 工具函数 ==========

function formatTime() {
    return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true, gfm: true });
        return marked.parse(text);
    }
    return text.replace(/\n/g, '<br>');
}

function showToast(message, type = 'info') {
    const existing = $('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ========== 会话存储 ==========

function cleanHtml(html) {
    // 移除 typing-message 节点（它们不应该被持久化）
    if (!html) return '';
    const div = document.createElement('div');
    div.innerHTML = html;
    div.querySelectorAll('.typing-message').forEach(el => el.remove());
    return div.innerHTML;
}

function saveCurrentSession() {
    if (!state.sessionId) return;
    if (!sessionStore[state.sessionId]) {
        sessionStore[state.sessionId] = {};
    }
    sessionStore[state.sessionId].title = state.paperTitle;
    sessionStore[state.sessionId].paperLoaded = state.paperLoaded;
    const msgContainer = els.messageList.querySelector('.messages-container');
    if (msgContainer) {
        // 清理 typing 指示器后再保存
        sessionStore[state.sessionId].messagesHtml = cleanHtml(msgContainer.innerHTML);
    }
}

function restoreSession(sessionId) {
    const sess = sessionStore[sessionId];
    if (!sess) return false;

    // 不取消正在进行的请求！切换前保存当前会话即可
    if (state.sessionId && state.sessionId !== sessionId) {
        saveCurrentSession();
    }

    state.sessionId = sessionId;
    state.paperTitle = sess.title || '';
    state.paperLoaded = sess.paperLoaded || false;

    // 如果是正在生成的会话，恢复 isProcessing 状态
    if (state.processingSessionId === sessionId) {
        state.isProcessing = true;
    } else {
        state.isProcessing = false;
    }

    els.currentPaperTitle.textContent = state.paperTitle || '论文分析助手';
    els.currentPaperSubtitle.textContent = state.paperTitle
        ? (sess.paperData ? `${sess.paperData.authors || ''} · ${sess.paperData.section_count || 0} 章节 · ${(sess.paperData.text_length || 0).toLocaleString()} 字` : '')
        : '上传论文开始分析';

    els.welcomeScreen.style.display = 'none';
    const container = getOrCreateMessageContainer();
    container.innerHTML = cleanHtml(sess.messagesHtml || '');

    els.quickActions.style.display = state.paperLoaded ? 'flex' : 'none';
    els.btnDownload.style.display = state.paperLoaded ? 'flex' : 'none';

    els.chatList.querySelectorAll('.chat-item').forEach(el => {
        el.classList.toggle('active', el.dataset.sid === sessionId);
        // 高亮正在生成的会话
        if (el.dataset.sid === state.processingSessionId) {
            el.classList.add('generating');
        } else {
            el.classList.remove('generating');
        }
    });

    setProcessingUI(state.isProcessing);
    scrollToBottom();
    return true;
}

function getOrCreateMessageContainer() {
    let container = els.messageList.querySelector('.messages-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'messages-container';
        els.messageList.appendChild(container);
    }
    return container;
}

// ========== 消息渲染 ==========

function addMessage(type, content, extra = {}) {
    els.welcomeScreen.style.display = 'none';

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}${extra.isFile ? ' file-message' : ''}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    if (type === 'user') {
        avatar.textContent = '我';
    } else {
        avatar.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>';
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (extra.isFile) {
        const ext = (extra.fileName || 'docx').split('.').pop().toLowerCase();
        bubble.innerHTML = `
            <div class="file-card clickable" data-url="${escapeHtml(extra.downloadUrl || '')}">
                <div class="file-card-icon ${ext}">${ext}</div>
                <div class="file-card-info">
                    <div class="file-card-name">${escapeHtml(extra.fileName || 'report.docx')}</div>
                    <div class="file-card-meta">${formatFileSize(extra.fileSize || 0)} · 点击下载</div>
                </div>
                <div class="file-card-dl">⬇</div>
            </div>`;
        bubble.querySelector('.file-card').addEventListener('click', () => {
            if (extra.downloadUrl) window.open(extra.downloadUrl, '_blank');
        });
    } else if (type === 'user') {
        bubble.textContent = content;
    } else {
        if (extra.isMarkdown !== false) {
            bubble.innerHTML = renderMarkdown(content);
        } else {
            bubble.textContent = content;
        }
    }

    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = formatTime();

    if (type === 'user') {
        msgDiv.appendChild(bubble);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(time);
    } else {
        msgDiv.appendChild(avatar);
        const contentWrap = document.createElement('div');
        contentWrap.appendChild(bubble);
        contentWrap.appendChild(time);
        msgDiv.appendChild(contentWrap);
    }

    getOrCreateMessageContainer().appendChild(msgDiv);
    scrollToBottom();
    saveCurrentSessionDelayed();
    return msgDiv;
}

function addFileCard(filename, fileSize) {
    els.welcomeScreen.style.display = 'none';
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user';
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '我';
    const wrap = document.createElement('div');
    const card = document.createElement('div');
    card.className = 'file-card';
    const ext = filename.split('.').pop().toLowerCase();
    card.innerHTML = `
        <div class="file-card-icon ${ext}">${ext}</div>
        <div class="file-card-info">
            <div class="file-card-name">${escapeHtml(filename)}</div>
            <div class="file-card-meta">${formatFileSize(fileSize)}</div>
        </div>`;
    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = formatTime();
    wrap.appendChild(card);
    wrap.appendChild(time);
    msgDiv.appendChild(wrap);
    msgDiv.appendChild(avatar);
    getOrCreateMessageContainer().appendChild(msgDiv);
    scrollToBottom();
    saveCurrentSessionDelayed();
    return msgDiv;
}

function showTyping() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ai typing-message';
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>';
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    const wrap = document.createElement('div');
    wrap.appendChild(bubble);
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(wrap);
    getOrCreateMessageContainer().appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

function removeTyping() {
    els.messageList.querySelectorAll('.typing-message').forEach(el => el.remove());
}

function scrollToBottom() {
    els.messageList.scrollTop = els.messageList.scrollHeight;
}

let _saveTimer = null;
function saveCurrentSessionDelayed() {
    clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => saveCurrentSession(), 300);
}

// ========== 打断生成（仅停止按钮触发）==========

function cancelGeneration() {
    if (state.currentAbortController) {
        state.currentAbortController.abort();
        state.currentAbortController = null;
    }
    removeTyping();
    state.isProcessing = false;
    state.processingSessionId = null;
    setProcessingUI(false);
    // 清除侧栏生成状态
    els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('generating'));
}

function setProcessingUI(processing) {
    if (processing) {
        els.btnSend.style.display = 'none';
        els.btnStop.style.display = 'flex';
    } else {
        els.btnSend.style.display = '';
        els.btnStop.style.display = 'none';
    }
}

// 停止按钮事件 - 唯一的打断入口
els.btnStop.addEventListener('click', () => {
    cancelGeneration();
    addMessage('ai', '⏹ **已停止生成**');
    showToast('已停止', 'info');
});

// 检查响应是否属于当前显示的会话，不属于则存入 sessionStore
function stashResponseIfNeeded(targetSid, htmlSnippet) {
    if (state.sessionId !== targetSid) {
        // 存入目标会话
        if (!sessionStore[targetSid]) sessionStore[targetSid] = {};
        const existing = cleanHtml(sessionStore[targetSid].messagesHtml || '');
        sessionStore[targetSid].messagesHtml = existing + htmlSnippet;
        return true; // 已暂存
    }
    return false; // 当前正在显示此会话，正常渲染
}

// ========== API 调用（支持 AbortController） ==========

async function apiCall(url, body = null, isJson = true) {
    // 创建新的 AbortController
    state.currentAbortController = new AbortController();
    const signal = state.currentAbortController.signal;

    try {
        const options = { method: body ? 'POST' : 'GET', headers: {}, signal };
        if (body) {
            if (body instanceof FormData) {
                options.body = body;
            } else {
                options.headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(body);
            }
        }
        const response = await fetch(url, options);
        if (isJson) return await response.json();
        return response;
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error('ABORTED');
        }
        throw err;
    } finally {
        state.currentAbortController = null;
    }
}

async function uploadFile(file) {
    if (state.isProcessing) return;

    // 检查 API Key 配置
    try {
        const settingsResp = await fetch('/api/settings');
        const settingsData = await settingsResp.json();
        if (!settingsData.has_api_key) {
            showToast('请先配置 API Key', 'error');
            setTimeout(() => { window.location.href = '/settings'; }, 1500);
            return;
        }
    } catch (err) {
        // 如果检查失败，继续尝试（可能是网络问题）
    }

    state.isProcessing = true;
    state.processingSessionId = state.sessionId; // 记录生成所属会话
    setProcessingUI(true);

    if (state.sessionId) saveCurrentSession();

    addFileCard(file.name, file.size);
    showTyping();

    try {
        const formData = new FormData();
        formData.append('file', file);
        const result = await apiCall('/api/upload', formData);

        if (result === undefined) return; // 被 abort
        removeTyping();

        if (result.success) {
            state.sessionId = result.session_id;
            state.paperTitle = result.title;
            state.paperLoaded = true;

            sessionStore[state.sessionId] = {
                title: result.title,
                paperLoaded: true,
                paperData: result,
                messagesHtml: '',
            };

            updateHeaderForPaper(result);
            els.quickActions.style.display = 'flex';
            els.btnDownload.style.display = 'flex';

            const infoLines = [
                `**论文解析完成！**`, ``,
                `- **标题**: ${result.title}`,
                `- **作者**: ${result.authors}`,
                `- **章节数**: ${result.section_count}`,
                `- **总字数**: ${result.text_length.toLocaleString()}`,
            ];
            if (result.sections && result.sections.length > 0) {
                infoLines.push(`- **章节**: ${result.sections.join('、')}`);
            }
            addMessage('ai', infoLines.join('\n'));
            addChatToList(state.sessionId, result.title);
            saveCurrentSession();

            setTimeout(() => generateQuickSummary(), 500);
        } else {
            addMessage('ai', `❌ ${result.error || '文件上传失败'}`);
        }
    } catch (err) {
        if (err.message === 'ABORTED') return;
        removeTyping();
        addMessage('ai', `❌ 上传失败: ${err.message}`);
        showToast(err.message, 'error');
    } finally {
        state.isProcessing = false;
        state.processingSessionId = null;
        setProcessingUI(false);
        els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('generating'));
    }
}

async function generateQuickSummary() {
    if (!state.sessionId || state.isProcessing) return;

    const targetSid = state.sessionId;
    state.isProcessing = true;
    state.processingSessionId = targetSid;
    setProcessingUI(true);
    showTyping();

    try {
        const result = await apiCall('/api/chat', {
            session_id: targetSid, intent: 'summary', detail: 'detailed',
        });
        if (result === undefined) return; // 被 abort
        removeTyping();

        if (state.sessionId !== targetSid) {
            // 暂存
            stashSimpleMessage(targetSid, result.content || '');
            return;
        }
        if (result.success) {
            addMessage('ai', result.content);
        } else {
            addMessage('ai', `❌ ${result.error}`);
        }
    } catch (err) {
        if (err.message === 'ABORTED') return;
        removeTyping();
        if (state.sessionId === targetSid) {
            addMessage('ai', `❌ 摘要生成失败: ${err.message}`);
        }
    } finally {
        state.isProcessing = false;
        state.processingSessionId = null;
        setProcessingUI(false);
        els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('generating'));
    }
}

function stashSimpleMessage(targetSid, content) {
    if (!sessionStore[targetSid]) return;
    const html = `<div class="message ai"><div class="message-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></div><div><div class="message-bubble">${renderMarkdown(content)}</div></div></div>`;
    sessionStore[targetSid].messagesHtml = cleanHtml(sessionStore[targetSid].messagesHtml || '') + html;
}

async function sendMessage(message, intent = 'question') {
    if (!message.trim() && intent === 'question') return;
    if (!state.sessionId) { showToast('请先上传一篇论文', 'info'); return; }
    if (state.isProcessing) return;

    const targetSid = state.sessionId;  // 记住这个请求属于哪个会话
    state.isProcessing = true;
    state.processingSessionId = targetSid;
    setProcessingUI(true);

    // 标记侧栏中的生成状态
    els.chatList.querySelectorAll('.chat-item').forEach(el => {
        if (el.dataset.sid === targetSid) el.classList.add('generating');
    });

    addMessage('user', message || getIntentLabel(intent));
    showTyping();

    try {
        const body = { session_id: targetSid, intent: intent };
        if (intent === 'question') body.message = message;
        const result = await apiCall('/api/chat', body);

        if (result === undefined) return; // 被 abort
        removeTyping();

        // 用户可能已切换到其他会话 —— 结果需要存入 targetSid
        if (state.sessionId !== targetSid) {
            // 暂存到目标会话
            stashMessagesToSession(targetSid, result, message, intent);
            return;
        }

        if (result.success) {
            renderAIResponse(result);
        } else {
            addMessage('ai', `❌ ${result.error}`);
        }
    } catch (err) {
        if (err.message === 'ABORTED') return;
        removeTyping();
        if (state.sessionId === targetSid) {
            addMessage('ai', `❌ 请求失败: ${err.message}`);
        }
        showToast(err.message, 'error');
    } finally {
        state.isProcessing = false;
        state.processingSessionId = null;
        setProcessingUI(false);
        els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('generating'));
    }
}

// 将 AI 响应暂存到目标会话
function stashMessagesToSession(targetSid, result, userMessage, intent) {
    if (!sessionStore[targetSid]) return;

    // 构建临时容器来收集 HTML
    const tempDiv = document.createElement('div');
    const origContainer = getOrCreateMessageContainer();

    // 暂存用户消息
    const userLabel = document.createElement('div');
    userLabel.className = 'message user';
    userLabel.innerHTML = `<div class="message-avatar">我</div><div class="message-bubble">${escapeHtml(userMessage || getIntentLabel(intent))}</div>`;
    tempDiv.appendChild(userLabel);

    // 暂存 AI 响应
    if (result.success) {
        const saveCurrentContainer = els.messageList.querySelector('.messages-container');
        // 临时替换容器来收集 HTML
        const fakeContainer = document.createElement('div');
        fakeContainer.className = 'messages-container';
        // 用当前 DOM 的方式渲染（简化版）
        let aiHtml = '';
        if (result.type === 'full_report') {
            const report = [
                `# 📄 完整分析报告`, ``,
                `## 摘要`, result.abstract || '（未提取）', ``,
                `## 关键词`,
                (result.keywords || []).map(k => `\`${k}\``).join(' ') || '（未提取）', ``,
            ];
            if (result.research_questions && result.research_questions.length > 0) {
                report.push(`## 研究问题`);
                result.research_questions.forEach((q, i) => report.push(`${i + 1}. ${q}`));
                report.push('');
            }
            if (result.methodology) { report.push(`## 研究方法`, result.methodology, ''); }
            if (result.contributions && result.contributions.length > 0) {
                report.push(`## 主要贡献`);
                result.contributions.forEach(c => report.push(`- ${c}`));
                report.push('');
            }
            if (result.strengths && result.strengths.length > 0) {
                report.push(`## 优点`);
                result.strengths.forEach(s => report.push(`- ✓ ${s}`));
                report.push('');
            }
            if (result.limitations && result.limitations.length > 0) {
                report.push(`## 局限性`);
                result.limitations.forEach(l => report.push(`- ⚠ ${l}`));
                report.push('');
            }
            if (result.reading_notes) { report.push(`## 阅读建议`, result.reading_notes, ''); }
            aiHtml = renderMarkdown(report.join('\n'));
        } else if (result.type === 'keywords' && Array.isArray(result.content)) {
            aiHtml = renderMarkdown('**关键词提取结果**\n\n' +
                result.content.map((k, i) => `${i + 1}. \`${k}\``).join('\n'));
        } else {
            aiHtml = renderMarkdown(result.content || '分析完成');
        }

        const aiDiv = document.createElement('div');
        aiDiv.className = 'message ai';
        aiDiv.innerHTML = `<div class="message-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></div><div><div class="message-bubble">${aiHtml}</div></div>`;
        tempDiv.appendChild(aiDiv);

        // Word 文件卡片
        if (result.report_url) {
            const ext = 'docx';
            const fileDiv = document.createElement('div');
            fileDiv.className = 'message ai';
            fileDiv.innerHTML = `<div class="message-avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></div><div><div class="message-bubble"><div class="file-card clickable" data-url="${escapeHtml(result.report_url)}"><div class="file-card-icon ${ext}">${ext}</div><div class="file-card-info"><div class="file-card-name">论文分析报告_${escapeHtml(state.paperTitle || 'report')}.docx</div><div class="file-card-meta">${formatFileSize(result.report_size || 0)} · 点击下载</div></div><div class="file-card-dl">⬇</div></div></div></div>`;
            tempDiv.appendChild(fileDiv);
        }
    }

    // 合并到 sessionStore
    const existing = cleanHtml(sessionStore[targetSid].messagesHtml || '');
    sessionStore[targetSid].messagesHtml = existing + tempDiv.innerHTML;
}

function renderAIResponse(result) {
    switch (result.type) {
        case 'summary':
        case 'bilingual':
        case 'methodology':
        case 'answer':
            addMessage('ai', result.content);
            break;
        case 'keywords':
            if (Array.isArray(result.content)) {
                addMessage('ai', '**关键词提取结果**\n\n' +
                    result.content.map((k, i) => `${i + 1}. \`${k}\``).join('\n'));
            }
            break;
        case 'full_report':
            const report = [
                `# 📄 完整分析报告`, ``,
                `## 摘要`, result.abstract || '（未提取）', ``,
                `## 关键词`,
                (result.keywords || []).map(k => `\`${k}\``).join(' ') || '（未提取）', ``,
            ];
            if (result.research_questions && result.research_questions.length > 0) {
                report.push(`## 研究问题`);
                result.research_questions.forEach((q, i) => report.push(`${i + 1}. ${q}`));
                report.push('');
            }
            if (result.methodology) { report.push(`## 研究方法`, result.methodology, ''); }
            if (result.contributions && result.contributions.length > 0) {
                report.push(`## 主要贡献`);
                result.contributions.forEach(c => report.push(`- ${c}`));
                report.push('');
            }
            if (result.strengths && result.strengths.length > 0) {
                report.push(`## 优点`);
                result.strengths.forEach(s => report.push(`- ✓ ${s}`));
                report.push('');
            }
            if (result.limitations && result.limitations.length > 0) {
                report.push(`## 局限性`);
                result.limitations.forEach(l => report.push(`- ⚠ ${l}`));
                report.push('');
            }
            if (result.reading_notes) { report.push(`## 阅读建议`, result.reading_notes, ''); }
            addMessage('ai', report.join('\n'));

            if (result.report_url) {
                setTimeout(() => {
                    addMessage('ai', '', {
                        isFile: true,
                        fileName: `论文分析报告_${state.paperTitle || 'report'}.docx`,
                        downloadUrl: result.report_url,
                        fileSize: result.report_size || 0,
                    });
                }, 500);
            }
            break;
        default:
            addMessage('ai', result.content || '分析完成');
    }
}

function getIntentLabel(intent) {
    const labels = {
        summary: '请帮我生成论文摘要',
        keywords: '请帮我提取关键词',
        methodology: '请分析研究方法',
        full_report: '请生成完整分析报告',
        bilingual: '请生成中英双语摘要',
    };
    return labels[intent] || intent;
}

// ========== 下载报告 ==========

async function downloadReport() {
    if (!state.sessionId) { showToast('请先上传论文', 'info'); return; }
    if (state.isProcessing) return;

    state.isProcessing = true;
    setProcessingUI(true);
    showToast('正在生成 Word 报告...', 'info');

    try {
        const response = await apiCall('/api/download-report',
            { session_id: state.sessionId }, false);

        if (state.isProcessing === false) return; // 被中断

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            addMessage('ai', '', {
                isFile: true,
                fileName: `论文分析_${state.paperTitle || 'report'}.docx`,
                downloadUrl: url,
                fileSize: blob.size,
            });
            showToast('报告已生成', 'success');
        } else {
            const err = await response.json().catch(() => ({}));
            showToast(err.error || '下载失败', 'error');
        }
    } catch (err) {
        if (err.message === 'ABORTED') return;
        showToast('下载失败: ' + err.message, 'error');
    } finally {
        state.isProcessing = false;
        setProcessingUI(false);
    }
}

// ========== 界面更新 ==========

function updateHeaderForPaper(data) {
    els.currentPaperTitle.textContent = data.title || '未知论文';
    els.currentPaperSubtitle.textContent =
        `${data.authors || '未知作者'} · ${data.section_count} 章节 · ${data.text_length.toLocaleString()} 字`;
}

function addChatToList(sessionId, title) {
    const emptyHint = els.chatList.querySelector('.empty-hint');
    if (emptyHint) emptyHint.remove();

    let existing = els.chatList.querySelector(`[data-sid="${sessionId}"]`);
    if (existing) {
        existing.querySelector('.chat-item-title').textContent = title;
        els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
        existing.classList.add('active');
        return;
    }

    els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));

    const item = document.createElement('div');
    item.className = 'chat-item active';
    item.dataset.sid = sessionId;
    item.innerHTML = `
        <div class="chat-item-title">${escapeHtml(title)}</div>
        <div class="chat-item-meta">${formatTime()}</div>
        <button class="chat-item-delete" title="删除">×</button>`;

    item.addEventListener('click', (e) => {
        if (e.target.classList.contains('chat-item-delete')) return;
        if (state.sessionId === sessionId) return;

        // 切换时不打断生成！只保存当前会话，然后切换
        if (state.sessionId) saveCurrentSession();

        if (restoreSession(sessionId)) {
            els.chatList.querySelectorAll('.chat-item').forEach(el => {
                el.classList.toggle('active', el.dataset.sid === sessionId);
            });
        }
    });

    item.querySelector('.chat-item-delete').addEventListener('click', (e) => {
        e.stopPropagation();
        // 如果删除的是正在生成的会话，先打断
        if (state.processingSessionId === sessionId) {
            cancelGeneration();
        }
        delete sessionStore[sessionId];
        item.remove();
        if (state.sessionId === sessionId) {
            resetChat();
        }
        if (els.chatList.querySelectorAll('.chat-item:not(.empty-hint)').length === 0) {
            els.chatList.innerHTML = `
                <div class="chat-item empty-hint">
                    <p>暂无对话</p><span>上传一篇论文开始吧</span>
                </div>`;
        }
    });

    els.chatList.insertBefore(item, els.chatList.firstChild);
}

function resetChat() {
    if (state.sessionId) saveCurrentSession();

    state.sessionId = null;
    state.paperTitle = '';
    state.paperLoaded = false;
    state.isProcessing = false;
    els.currentPaperTitle.textContent = '论文分析助手';
    els.currentPaperSubtitle.textContent = '上传论文开始分析';
    els.quickActions.style.display = 'none';
    els.btnDownload.style.display = 'none';

    const container = els.messageList.querySelector('.messages-container');
    if (container) container.remove();
    els.welcomeScreen.style.display = '';

    els.chatList.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    setProcessingUI(false);
}

// ========== 事件 ==========

els.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
    els.fileInput.value = '';
});

els.btnAttach.addEventListener('click', () => els.fileInput.click());
els.uploadAreaSidebar.addEventListener('click', () => els.fileInput.click());
document.getElementById('btnWelcomeUpload')?.addEventListener('click', () => els.fileInput.click());

function handleSend() {
    const message = els.messageInput.value.trim();
    if (!message) return;
    els.messageInput.value = '';
    els.messageInput.style.height = 'auto';
    updateSendButton();
    sendMessage(message, 'question');
}

els.btnSend.addEventListener('click', handleSend);
els.messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});
els.messageInput.addEventListener('input', () => {
    els.messageInput.style.height = 'auto';
    els.messageInput.style.height = Math.min(els.messageInput.scrollHeight, 120) + 'px';
    updateSendButton();
});

function updateSendButton() {
    els.btnSend.classList.toggle('active', els.messageInput.value.trim().length > 0);
}

els.quickActions.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-quick');
    if (!btn) return;
    sendMessage('', btn.dataset.intent);
});

els.btnDownload.addEventListener('click', downloadReport);
els.btnNewChat.addEventListener('click', resetChat);
els.btnSettings?.addEventListener('click', () => {
    window.location.href = '/settings';
});
els.btnToggleSidebar.addEventListener('click', () => {
    els.sidebar.classList.toggle('collapsed');
});

// ========== 拖拽 & 粘贴 ==========

let dragCounter = 0;
document.addEventListener('dragenter', (e) => { e.preventDefault(); dragCounter++; if (dragCounter === 1) els.dragOverlay.classList.add('active'); });
document.addEventListener('dragleave', (e) => { e.preventDefault(); dragCounter--; if (dragCounter === 0) els.dragOverlay.classList.remove('active'); });
document.addEventListener('dragover', (e) => e.preventDefault());
document.addEventListener('drop', (e) => {
    e.preventDefault(); dragCounter = 0; els.dragOverlay.classList.remove('active');
    const file = e.dataTransfer.files[0];
    if (file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext === 'pdf' || ext === 'docx') uploadFile(file);
        else showToast('仅支持 PDF 和 DOCX 文件', 'error');
    }
});

document.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
        if (item.kind === 'file') {
            const file = item.getAsFile();
            const ext = file.name.split('.').pop().toLowerCase();
            if (ext === 'pdf' || ext === 'docx') {
                e.preventDefault();
                uploadFile(file);
                return;
            }
        }
    }
});

// ========== 初始化 ==========
async function initApp() {
    try {
        const resp = await fetch('/api/settings');
        const data = await resp.json();
        const dot = document.querySelector('#apiStatus .status-dot');
        const text = document.querySelector('#apiStatus .status-text');

        if (data.has_api_key) {
            if (dot) dot.className = 'status-dot online';
            if (text) text.textContent = 'API 已连接 · ' + data.provider;
            document.getElementById('apiKeyBanner')?.style.setProperty('display', 'none');
        } else {
            if (dot) dot.className = 'status-dot offline';
            if (text) text.textContent = '请设置 API Key';
            const banner = document.getElementById('apiKeyBanner');
            if (banner) banner.style.display = 'block';
        }
    } catch (err) {
        const dot = document.querySelector('#apiStatus .status-dot');
        if (dot) dot.className = 'status-dot offline';
    }
}

updateSendButton();
els.messageInput.focus();
initApp();
