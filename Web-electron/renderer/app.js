const STORAGE_KEY = 'dolphin_chat_history';
const CONFIG_STORAGE_KEY = 'dolphin_config';

let isProcessing = false;
let currentMessageElement = null;
let serverUrl = 'http://localhost:5000';

const elements = {
    chatOutput: document.getElementById('chat-output'),
    userInput: document.getElementById('user-input'),
    sendBtn: document.getElementById('send-btn'),
    newChatBtn: document.getElementById('new-chat-btn'),
    clearChatBtn: document.getElementById('clear-chat-btn'),
    settingsBtn: document.getElementById('settings-btn'),
    settingsModal: document.getElementById('settings-modal'),
    closeSettingsBtn: document.querySelector('.close-btn'),
    saveSettingsBtn: document.getElementById('save-settings-btn'),
    cancelSettingsBtn: document.getElementById('cancel-settings-btn'),
    serverStatus: document.querySelector('.status-dot'),
    serverStatusText: document.querySelector('.status-text'),
    modelInput: document.getElementById('model-input'),
    baseUrlInput: document.getElementById('base-url'),
    maxTokensInput: document.getElementById('max-tokens'),
    reasoningCheckbox: document.getElementById('reasoning'),
    workDirInput: document.getElementById('work-dir'),
    browseDirBtn: document.getElementById('browse-dir-btn'),
    skillsList: document.getElementById('skills-list'),
    cmdBtns: document.querySelectorAll('.cmd-btn')
};

async function init() {
    await getServerUrl();
    loadHistory();
    loadConfig();
    checkServerStatus();
    setupEventListeners();
    
    setInterval(checkServerStatus, 5000);
    
    if (elements.chatOutput.children.length === 0) {
        appendMessage('system', 'Dolphin AI 已启动\n输入消息开始对话，或使用 .help 查看帮助');
    }
}

async function getServerUrl() {
    if (window.electronAPI) {
        serverUrl = await window.electronAPI.getServerUrl();
    }
}

async function checkServerStatus() {
    try {
        const response = await fetch(`${serverUrl}/api/config`, {
            method: 'GET',
            signal: AbortSignal.timeout(3000)
        });
        
        if (response.ok) {
            elements.serverStatus.classList.add('connected');
            elements.serverStatus.classList.remove('error');
            elements.serverStatusText.textContent = '已连接';
        } else {
            throw new Error('Server error');
        }
    } catch (error) {
        elements.serverStatus.classList.remove('connected');
        elements.serverStatus.classList.add('error');
        elements.serverStatusText.textContent = '未连接';
    }
}

function setupEventListeners() {
    elements.sendBtn.addEventListener('click', sendMessage);
    
    elements.userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    elements.userInput.addEventListener('input', autoResizeTextarea);
    
    elements.newChatBtn.addEventListener('click', () => {
        clearConversation();
        appendMessage('system', '开始新对话');
    });
    
    elements.clearChatBtn.addEventListener('click', clearChat);
    
    elements.settingsBtn.addEventListener('click', openSettings);
    elements.closeSettingsBtn.addEventListener('click', closeSettings);
    elements.cancelSettingsBtn.addEventListener('click', closeSettings);
    elements.saveSettingsBtn.addEventListener('click', saveSettings);
    
    elements.browseDirBtn.addEventListener('click', browseDirectory);
    
    elements.cmdBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const cmd = btn.dataset.cmd;
            elements.userInput.value = cmd;
            sendMessage();
        });
    });
    
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            closeSettings();
        }
    });
}

function autoResizeTextarea() {
    elements.userInput.style.height = 'auto';
    elements.userInput.style.height = Math.min(elements.userInput.scrollHeight, 200) + 'px';
}

function appendMessage(type, content, save = true) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    elements.chatOutput.appendChild(messageDiv);
    elements.chatOutput.scrollTop = elements.chatOutput.scrollHeight;
    
    if (save) {
        saveHistory();
    }
    
    return messageDiv;
}

function appendTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    indicator.id = 'typing-indicator';
    elements.chatOutput.appendChild(indicator);
    elements.chatOutput.scrollTop = elements.chatOutput.scrollHeight;
    return indicator;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

async function sendMessage() {
    const message = elements.userInput.value.trim();
    if (!message || isProcessing) return;
    
    isProcessing = true;
    elements.userInput.value = '';
    elements.userInput.style.height = 'auto';
    elements.sendBtn.disabled = true;
    
    appendMessage('user', message);
    
    const typingIndicator = appendTypingIndicator();
    
    try {
        const response = await fetch(`${serverUrl}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
            body: JSON.stringify({ message })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        removeTypingIndicator();
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        let isDone = false;
        
        currentMessageElement = appendMessage('assistant', '', false);
        
        while (!isDone) {
            const { done, value } = await reader.read();
            
            if (done) {
                isDone = true;
                break;
            }
            
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop() || '';
            
            for (const part of parts) {
                const lines = part.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.done) {
                                isDone = true;
                            }
                            
                            if (data.content !== undefined) {
                                fullContent += data.content;
                                currentMessageElement.querySelector('.message-content').textContent = fullContent;
                                elements.chatOutput.scrollTop = elements.chatOutput.scrollHeight;
                                
                                if (data.type) {
                                    currentMessageElement.className = `message ${data.type}`;
                                }
                            }
                        } catch (e) {
                            console.error('Parse error:', e);
                        }
                    }
                }
            }
        }
        
        saveHistory();
        
    } catch (error) {
        removeTypingIndicator();
        appendMessage('error', `请求失败: ${error.message}`);
    } finally {
        isProcessing = false;
        elements.sendBtn.disabled = false;
        elements.userInput.focus();
        currentMessageElement = null;
    }
}

async function clearChat() {
    try {
        await fetch(`${serverUrl}/api/clear`, { method: 'POST' });
        elements.chatOutput.innerHTML = '';
        localStorage.removeItem(STORAGE_KEY);
        appendMessage('system', '对话已清空');
    } catch (error) {
        appendMessage('error', `清空失败: ${error.message}`);
    }
}

async function clearConversation() {
    try {
        await fetch(`${serverUrl}/api/clear`, { method: 'POST' });
        elements.chatOutput.innerHTML = '';
        localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
        console.error('Clear conversation error:', error);
    }
}

function saveHistory() {
    const messages = [];
    elements.chatOutput.querySelectorAll('.message').forEach(msg => {
        messages.push({
            type: msg.className.replace('message ', ''),
            content: msg.querySelector('.message-content').textContent
        });
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
}

function loadHistory() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        try {
            const messages = JSON.parse(saved);
            elements.chatOutput.innerHTML = '';
            messages.forEach(msg => {
                appendMessage(msg.type, msg.content, false);
            });
        } catch (e) {
            console.error('Load history error:', e);
        }
    }
}

async function openSettings() {
    try {
        const response = await fetch(`${serverUrl}/api/config`);
        const config = await response.json();
        
        elements.modelInput.value = config.model || '';
        elements.baseUrlInput.value = config.base_url || '';
        elements.maxTokensInput.value = config.max_tokens || 8192;
        elements.reasoningCheckbox.checked = config.reasoning || false;
        elements.workDirInput.value = config.work_directory || '';
        
        elements.skillsList.innerHTML = '';
        for (const [skillName, enabled] of Object.entries(config.skills || {})) {
            const skillDiv = document.createElement('div');
            skillDiv.className = 'skill-item';
            skillDiv.innerHTML = `
                <input type="checkbox" id="skill-${skillName}" ${enabled ? 'checked' : ''}>
                <label for="skill-${skillName}">${skillName}</label>
            `;
            elements.skillsList.appendChild(skillDiv);
        }
        
        elements.settingsModal.classList.add('show');
    } catch (error) {
        appendMessage('error', `加载设置失败: ${error.message}`);
    }
}

function closeSettings() {
    elements.settingsModal.classList.remove('show');
}

async function saveSettings() {
    try {
        const skills = {};
        elements.skillsList.querySelectorAll('.skill-item').forEach(item => {
            const checkbox = item.querySelector('input[type="checkbox"]');
            const skillName = checkbox.id.replace('skill-', '');
            skills[skillName] = checkbox.checked;
        });
        
        const config = {
            model: elements.modelInput.value,
            base_url: elements.baseUrlInput.value,
            max_tokens: parseInt(elements.maxTokensInput.value),
            reasoning: elements.reasoningCheckbox.checked,
            work_directory: elements.workDirInput.value,
            skills: skills
        };
        
        const response = await fetch(`${serverUrl}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        if (result.status === 'ok') {
            appendMessage('system', '设置已保存');
            closeSettings();
        } else {
            appendMessage('error', `保存设置失败: ${result.message}`);
        }
    } catch (error) {
        appendMessage('error', `保存设置失败: ${error.message}`);
    }
}

async function browseDirectory() {
    if (window.electronAPI) {
        const dir = await window.electronAPI.selectDirectory();
        if (dir) {
            elements.workDirInput.value = dir;
        }
    } else {
        appendMessage('error', '目录选择仅在 Electron 环境中可用');
    }
}

function loadConfig() {
    const saved = localStorage.getItem(CONFIG_STORAGE_KEY);
    if (saved) {
        try {
            const config = JSON.parse(saved);
            if (config.serverUrl) {
                serverUrl = config.serverUrl;
            }
        } catch (e) {
            console.error('Load config error:', e);
        }
    }
}

document.addEventListener('DOMContentLoaded', init);
