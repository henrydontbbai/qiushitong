/**
 * 本机绿色版设置管理
 */

class SettingsManager {
    constructor() {
        this.status = null;
        this.bindEvents();
        this.loadStatus();
    }

    bindEvents() {
        const settingsBtn = document.getElementById('settings-btn');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', (event) => {
                event.preventDefault();
                this.openSettingsModal(false);
            });
        }

        const saveBtn = document.getElementById('settings-save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings());
        }

        const testDbBtn = document.getElementById('settings-test-db-btn');
        if (testDbBtn) {
            testDbBtn.addEventListener('click', () => this.testDatabase());
        }

        const testAiBtn = document.getElementById('settings-test-ai-btn');
        if (testAiBtn) {
            testAiBtn.addEventListener('click', () => this.testAI());
        }

        const skipBtn = document.getElementById('settings-skip-btn');
        if (skipBtn) {
            skipBtn.addEventListener('click', () => this.closeSettingsModal());
        }

        const providerSelect = document.getElementById('settings-ai-provider');
        if (providerSelect) {
            providerSelect.addEventListener('change', () => this.applyProviderDefaults(false));
        }
    }

    async loadStatus() {
        try {
            const response = await fetch('/api/local-settings/status');
            const data = await response.json();
            if (data.success) {
                this.status = data;
                this.applyStatus(data);
                if (!data.database_configured && !localStorage.getItem('MATCHPREDICT_SETTINGS_SKIPPED')) {
                    this.openSettingsModal(true);
                }
            }
        } catch (error) {
            console.warn('读取本机设置状态失败:', error);
        }
    }

    applyStatus(status) {
        const providerInput = document.getElementById('settings-ai-provider');
        if (providerInput && status.ai_provider) {
            providerInput.value = status.ai_provider;
        }

        const baseUrlInput = document.getElementById('settings-ai-base-url');
        if (baseUrlInput && status.ai_base_url) {
            baseUrlInput.value = status.ai_base_url;
            window.AI_BASE_URL = status.ai_base_url;
        }

        const modelInput = document.getElementById('settings-ai-model');
        if (modelInput && status.ai_model) {
            modelInput.value = status.ai_model;
            window.AI_MODEL = status.ai_model;
        }

        if (status.ai_provider) {
            window.AI_PROVIDER = status.ai_provider;
        }

        this.applyProviderDefaults(false);
        this.renderStatus(status);
    }

    applyProviderDefaults(force = false) {
        const provider = document.getElementById('settings-ai-provider')?.value || 'openai_compatible';
        const baseUrlInput = document.getElementById('settings-ai-base-url');
        const modelInput = document.getElementById('settings-ai-model');

        if (baseUrlInput && (force || !baseUrlInput.value.trim())) {
            baseUrlInput.value = provider === 'gemini'
                ? 'https://generativelanguage.googleapis.com/v1beta'
                : 'https://api.openai.com/v1';
        }

        if (modelInput && provider === 'gemini' && (force || !modelInput.value.trim())) {
            modelInput.value = 'gemini-2.5-flash-lite-preview-06-17';
        }
    }

    renderStatus(status, message = '') {
        const container = document.getElementById('settings-status');
        if (!container) return;

        const dbText = status && status.database_configured ? '数据库已配置' : '数据库未配置';
        const aiText = status && status.ai_configured ? 'AI 已配置' : 'AI 未配置';
        const modelText = status && status.ai_model ? `当前模型：${status.ai_model}` : '当前模型：未设置';
        container.innerHTML = `
            <div class="settings-status-card">
                <div><strong>${dbText}</strong> · ${aiText}</div>
                <p>${message || `${modelText}。数据库未配置时，经典模式仍可正常使用。`}</p>
            </div>
        `;
    }

    openSettingsModal(isFirstRun = false) {
        const modal = document.getElementById('settings-modal');
        if (!modal) return;
        modal.classList.remove('hidden');
        if (isFirstRun) {
            this.renderStatus(this.status || {}, '首次使用建议先填写数据库和 AI 接口；也可以跳过，先用经典模式。');
        }
    }

    closeSettingsModal() {
        localStorage.setItem('MATCHPREDICT_SETTINGS_SKIPPED', '1');
        const modal = document.getElementById('settings-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    collectSettings() {
        this.applyProviderDefaults(false);
        return {
            database: {
                host: document.getElementById('settings-db-host')?.value || '',
                port: document.getElementById('settings-db-port')?.value || '',
                name: document.getElementById('settings-db-name')?.value || '',
                user: document.getElementById('settings-db-user')?.value || '',
                password: document.getElementById('settings-db-password')?.value || ''
            },
            ai: {
                provider: document.getElementById('settings-ai-provider')?.value || 'openai_compatible',
                base_url: document.getElementById('settings-ai-base-url')?.value || '',
                api_key: document.getElementById('settings-ai-key')?.value || '',
                model: document.getElementById('settings-ai-model')?.value || ''
            }
        };
    }

    async saveSettings() {
        const settings = this.collectSettings();
        try {
            const response = await fetch('/api/local-settings/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.message || '保存失败');
            }

            window.AI_PROVIDER = settings.ai.provider;
            window.AI_BASE_URL = settings.ai.base_url;
            window.AI_MODEL = settings.ai.model;
            localStorage.removeItem('GEMINI_API_KEY');
            localStorage.removeItem('MATCHPREDICT_SETTINGS_SKIPPED');

            this.status = data;
            this.renderStatus(data, '设置已保存。');
            this.showToast('设置已保存', 'success');
        } catch (error) {
            this.showToast(error.message || '保存设置失败', 'error');
            this.renderStatus(this.status || {}, error.message || '保存设置失败');
        }
    }

    hasDatabaseFields(settings) {
        const database = settings.database || {};
        return Boolean(
            database.host ||
            database.port ||
            database.name ||
            database.user ||
            database.password
        );
    }

    async testDatabase(settings = null) {
        settings = settings || this.collectSettings();
        try {
            const response = await fetch('/api/local-settings/test-db', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await response.json();
            this.renderStatus(this.status || {}, data.message || '测试完成');
            this.showToast(data.message || '测试完成', data.success ? 'success' : 'error');
        } catch (error) {
            this.showToast(error.message || '数据库测试失败', 'error');
        }
    }

    async testAI(settings = null) {
        settings = settings || this.collectSettings();
        try {
            const response = await fetch('/api/local-settings/test-ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await response.json();
            this.renderStatus(this.status || {}, data.message || 'AI 测试完成');
            this.showToast(data.message || 'AI 测试完成', data.success ? 'success' : 'error');
        } catch (error) {
            this.showToast(error.message || 'AI 测试失败', 'error');
        }
    }

    showToast(message, type = 'info') {
        if (window.authManager && window.authManager.showMessage) {
            window.authManager.showMessage(message, type);
        } else {
            alert(message);
        }
    }
}

const settingsManager = new SettingsManager();
window.settingsManager = settingsManager;
