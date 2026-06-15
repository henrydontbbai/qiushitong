/**
 * 2026 世界杯专题：单场预测前端闭环。
 * 基础预测不依赖 AI；AI 只解释已有概率。
 */
class WorldCupManager {
    constructor() {
        this.fixtures = [];
        this.currentPrediction = null;
        this.currentPredictionText = '';
        this.toastTimer = null;
        this.bindEvents();
        this.loadWorldCupDashboard();
    }

    bindEvents() {
        const refreshBtn = document.getElementById('worldcup-refresh-btn');
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.loadWorldCupDashboard());

        const explainBtn = document.getElementById('worldcup-ai-explain-btn');
        if (explainBtn) explainBtn.addEventListener('click', () => this.explainCurrentPrediction());

        const copyBtn = document.getElementById('worldcup-copy-btn');
        if (copyBtn) copyBtn.addEventListener('click', () => this.copyCurrentPrediction());

        const downloadBtn = document.getElementById('worldcup-download-btn');
        if (downloadBtn) downloadBtn.addEventListener('click', () => this.downloadCurrentPredictionTxt());

        const printBtn = document.getElementById('worldcup-print-btn');
        if (printBtn) printBtn.addEventListener('click', () => this.printCurrentPrediction());

        const fixturesContainer = document.getElementById('worldcup-fixtures');
        if (fixturesContainer) {
            fixturesContainer.addEventListener('click', (event) => {
                const button = event.target.closest('.worldcup-predict-btn');
                if (!button) return;
                this.predictFixture(button.getAttribute('data-match-id'));
            });
        }
    }


    async loadWorldCupDashboard() {
        await Promise.all([
            this.loadMeta(),
            this.loadGroups(),
            this.loadBracketRules(),
            this.loadTournament(),
            this.loadFixtures()
        ]);
    }

    async loadMeta() {
        const container = document.getElementById('worldcup-meta');
        if (!container) return;
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在加载数据说明...</div>';
        try {
            const response = await fetch('/api/worldcup/meta');
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '数据说明加载失败');
            const sources = (data.sources || []).map(source => `
                <li>
                    <strong>${this.escapeHtml(source.name || source.source_id || '数据来源')}</strong>
                    <span>${this.escapeHtml(source.data_cutoff_at || data.data_cutoff_at || '未知')}</span>
                    ${source.source_url ? `<a href="${this.escapeHtml(source.source_url)}" target="_blank" rel="noopener noreferrer">来源</a>` : ''}
                </li>
            `).join('');
            container.innerHTML = `
                <div class="worldcup-meta-stats">
                    <span>球队：${data.teams_count || 0}</span>
                    <span>小组：${data.groups_count || 0}</span>
                    <span>赛程：${data.fixtures_count || 0}</span>
                    <span>已赛：${data.finished_count || 0}</span>
                    <span>未赛：${data.scheduled_count || 0}</span>
                </div>
                <div class="worldcup-data-quality">模型版本：${this.escapeHtml(data.model_version || '未知')} · 数据截止：${this.escapeHtml(data.data_cutoff_at || '未知')}</div>
                <ul class="worldcup-source-list">${sources || '<li>暂无来源说明</li>'}</ul>
                <div class="worldcup-disclaimer">${(data.limitations || []).map(item => this.escapeHtml(item)).join('；')}</div>
            `;
        } catch (error) {
            container.innerHTML = `<div class="empty-message">${this.escapeHtml(error.message || '数据说明加载失败')}</div>`;
        }
    }

    async loadGroups() {
        const container = document.getElementById('worldcup-groups');
        if (!container) return;
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在加载小组积分和小组出线概率...</div>';
        try {
            const response = await fetch('/api/worldcup/groups?simulate=1&trials=500&seed=2026');
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '小组数据加载失败');
            this.renderGroups(data.groups || [], data.simulation);
        } catch (error) {
            container.innerHTML = `<div class="empty-message">${this.escapeHtml(error.message || '小组数据加载失败')}</div>`;
        }
    }

    renderGroups(groups, simulation) {
        const container = document.getElementById('worldcup-groups');
        if (!container) return;
        const simulationByTeam = {};
        (simulation?.groups || []).forEach(group => {
            (group.teams || []).forEach(team => {
                simulationByTeam[team.team_id] = team;
            });
        });
        container.innerHTML = groups.map(group => `
            <div class="worldcup-group-card">
                <h4>${this.escapeHtml(group.group)} 组</h4>
                <table class="worldcup-group-table">
                    <thead>
                        <tr><th>队</th><th>赛</th><th>净胜</th><th>分</th><th>出线</th></tr>
                    </thead>
                    <tbody>
                        ${(group.teams || []).map(team => {
                            const sim = simulationByTeam[team.team_id] || {};
                            return `<tr>
                                <td>${team.rank || ''}. ${this.escapeHtml(team.team_name || team.team_id)}</td>
                                <td>${team.played || 0}</td>
                                <td>${team.goal_difference || 0}</td>
                                <td><strong>${team.points || 0}</strong></td>
                                <td>${simulation ? this.formatPercent(sim.qualify_probability) : '未模拟'}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `).join('') + '<div class="worldcup-disclaimer">小组出线概率基于当前本地数据和单场模型模拟；不含淘汰赛和冠军概率，概率不代表赛果保证。</div>';
    }


    async loadBracketRules() {
        const container = document.getElementById('worldcup-bracket-rules');
        if (!container) return;
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在加载淘汰赛规则...</div>';
        try {
            const response = await fetch('/api/worldcup/bracket-rules');
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '淘汰赛规则加载失败');
            container.innerHTML = `
                <div class="worldcup-meta-stats">
                    <span>Round of 32?${data.round_of_32_slots_count || 0} 场</span>
                    <span>第三名组合：${data.third_place_assignments_count || 0}</span>
                    <span>晋级规则：24+8</span>
                </div>
                <div class="worldcup-data-quality">${this.escapeHtml(data.message || '淘汰赛规则已准备；冠军路径模拟可在下方查看。')}</div>
                <div class="worldcup-disclaimer">${this.escapeHtml(data.disclaimer || '当前仅校验 2026 Round of 32 规则；冠军路径概率由单独接口计算。')}</div>
            `;
        } catch (error) {
            container.innerHTML = `<div class="empty-message">${this.escapeHtml(error.message || '淘汰赛规则加载失败')}</div>`;
        }
    }

    async loadTournament() {
        const container = document.getElementById('worldcup-tournament');
        if (!container) return;
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在加载冠军路径模拟...</div>';
        try {
            const response = await fetch('/api/worldcup/tournament?trials=500&seed=2026');
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '冠军路径模拟加载失败');
            this.renderTournament(data);
        } catch (error) {
            container.innerHTML = `<div class="empty-message">${this.escapeHtml(error.message || '冠军路径模拟加载失败')}。基础单场预测不受影响。</div>`;
        }
    }

    renderTournament(data) {
        const container = document.getElementById('worldcup-tournament');
        if (!container) return;
        const teams = (data.teams || []).slice(0, 12);
        container.innerHTML = `
            <div class="worldcup-meta-stats">
                <span>模拟次数：${data.trials || 0}</span>
                <span>32 强合计：${this.formatNumber(data.round_totals?.round_of_32_probability)}</span>
                <span>冠军概率合计：${this.formatNumber(data.round_totals?.champion_probability)}</span>
            </div>
            <div class="worldcup-data-quality">模型版本：${this.escapeHtml(data.model_version || '未知')} · 数据截止：${this.escapeHtml(data.data_cutoff_at || '未知')}</div>
            <table class="worldcup-tournament-table">
                <thead>
                    <tr>
                        <th>球队</th>
                        <th>进16强</th>
                        <th>进8强</th>
                        <th>进4强</th>
                        <th>进决赛</th>
                        <th>冠军概率</th>
                    </tr>
                </thead>
                <tbody>
                    ${teams.map(team => `
                        <tr>
                            <td>${this.escapeHtml(team.team_name || team.team_id)}</td>
                            <td>${this.formatPercent(team.round_of_16_probability)}</td>
                            <td>${this.formatPercent(team.quarter_final_probability)}</td>
                            <td>${this.formatPercent(team.semi_final_probability)}</td>
                            <td>${this.formatPercent(team.final_probability)}</td>
                            <td><strong>${this.formatPercent(team.champion_probability)}</strong></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            <div class="worldcup-disclaimer">${this.escapeHtml(data.disclaimer || '冠军路径模拟为概率参考，不代表赛果保证。')}</div>
        `;
    }

    async loadFixtures() {
        const container = document.getElementById('worldcup-fixtures');
        const status = document.getElementById('worldcup-status');
        if (!container) return;
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在加载赛程...</div>';
        try {
            const response = await fetch('/api/worldcup/fixtures');
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '赛程加载失败');
            this.fixtures = data.fixtures || [];
            if (status) {
                status.textContent = `已加载 ${this.fixtures.length} 场世界杯比赛。数据截止：${data.data_cutoff_at || '未知'}。基础预测无需 AI Key。`;
            }
            this.renderFixtures();
        } catch (error) {
            container.innerHTML = `<div class="empty-message">${this.escapeHtml(error.message || '赛程加载失败')}</div>`;
        }
    }

    renderFixtures() {
        const container = document.getElementById('worldcup-fixtures');
        if (!container) return;
        if (!this.fixtures.length) {
            container.innerHTML = '<div class="empty-message">暂无世界杯赛程数据。</div>';
            return;
        }

        container.innerHTML = this.fixtures.map(fixture => `
            <div class="worldcup-fixture-card" data-match-id="${this.escapeHtml(fixture.match_id)}">
                <div class="worldcup-fixture-main">
                    <div>
                        <div class="worldcup-fixture-title">${this.escapeHtml(fixture.home_team)} vs ${this.escapeHtml(fixture.away_team)}</div>
                        <div class="worldcup-fixture-meta">${this.escapeHtml(this.formatStage(fixture))} · ${this.escapeHtml(this.formatDate(fixture.kickoff_at))} · ${this.escapeHtml(fixture.venue || '')}</div>
                    </div>
                    <button class="btn compact-btn primary-btn worldcup-predict-btn" data-match-id="${this.escapeHtml(fixture.match_id)}">
                        <i class="fas fa-chart-line"></i> ${fixture.status === 'finished' ? '查看赛果' : '查看预测'}
                    </button>
                </div>
                <div class="worldcup-fixture-note">${fixture.status === 'finished' && fixture.final_score ? `已完赛：${fixture.final_score.home}-${fixture.final_score.away}` : '未赛比赛可查看模型概率参考'}</div>
            </div>
        `).join('');

    }

    async predictFixture(matchId) {
        const resultContainer = document.getElementById('worldcup-prediction');
        const explainBtn = document.getElementById('worldcup-ai-explain-btn');
        const explanation = document.getElementById('worldcup-explanation');
        if (resultContainer) resultContainer.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在计算预测...</div>';
        if (explainBtn) explainBtn.disabled = true;
        this.toggleExportButtons(false);
        if (explanation) explanation.classList.add('hidden');

        try {
            const response = await fetch('/api/worldcup/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ match_id: matchId })
            });
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '预测失败');
            this.currentPrediction = data;
            this.currentPredictionText = this.buildPredictionText(data);
            this.renderPrediction(data);
            this.toggleExportButtons(true);
            if (explainBtn && !data.locked_result) explainBtn.disabled = false;
        } catch (error) {
            this.currentPrediction = null;
            this.currentPredictionText = '';
            this.toggleExportButtons(false);
            if (resultContainer) resultContainer.innerHTML = `<div class="empty-message">${this.escapeHtml(error.message || '预测失败')}</div>`;
        }
    }

    renderPrediction(data) {
        const container = document.getElementById('worldcup-prediction');
        if (!container) return;

        if (data.locked_result) {
            container.innerHTML = `
                <div class="worldcup-result-summary">
                    <h4>已完赛结果</h4>
                    <div class="worldcup-score-lock">${data.final_score.home} - ${data.final_score.away}</div>
                    <p>${this.escapeHtml(data.summary || '此比赛已完赛，结果已锁定。')}</p>
                    <p class="worldcup-disclaimer">${this.escapeHtml(data.disclaimer || '已完赛信息仅作展示。')}</p>
                </div>
            `;
            return;
        }

        const probs = data.probabilities || {};
        const xg = data.expected_goals || {};
        const topScores = data.top_scores || [];
        container.innerHTML = `
            <div class="worldcup-result-summary">
                <h4>${this.escapeHtml(data.teams?.home?.display_name_zh || data.teams?.home?.display_name || '主队')} vs ${this.escapeHtml(data.teams?.away?.display_name_zh || data.teams?.away?.display_name || '客队')}</h4>
                <div class="worldcup-prob-grid">
                    ${this.renderProb('胜', probs.home_win)}
                    ${this.renderProb('平', probs.draw)}
                    ${this.renderProb('负', probs.away_win)}
                </div>
                <div class="worldcup-xg">预期进球 xG：${this.formatXg(xg.home)} / ${this.formatXg(xg.away)}</div>
                <h5>Top 5 最可能比分</h5>
                <div class="worldcup-score-list">
                    ${topScores.map(score => `<div>${score.home_goals}-${score.away_goals}<span>${this.formatPercent(score.probability)}</span></div>`).join('')}
                </div>
                ${this.renderMarket(data.market_probabilities)}
                ${this.renderDataQuality(data.data_quality)}
                <div class="worldcup-data-quality">模型版本：${this.escapeHtml(data.model_version || '')} · 数据截止：${this.escapeHtml(data.data_cutoff_at || '')}</div>
                <p class="worldcup-disclaimer">${this.escapeHtml(data.disclaimer || '概率不代表赛果保证，仅供模型模拟参考，非决策建议。')}</p>
            </div>
        `;
    }

    renderProb(label, value) {
        const pct = this.formatPercent(value);
        const width = Math.round((value || 0) * 100);
        return `<div class="worldcup-prob-item"><strong>${label}</strong><span>${pct}</span><div class="worldcup-bar"><i style="width:${width}%"></i></div></div>`;
    }

    renderMarket(market) {
        if (!market) return '';
        return `<div class="worldcup-market">市场隐含概率对照：胜 ${this.formatPercent(market.home_win)} / 平 ${this.formatPercent(market.draw)} / 负 ${this.formatPercent(market.away_win)}。该项只做对照，不参与主模型。</div>`;
    }


    toggleExportButtons(enabled) {
        ['worldcup-copy-btn', 'worldcup-download-btn', 'worldcup-print-btn'].forEach(id => {
            const button = document.getElementById(id);
            if (button) button.disabled = !enabled;
        });
    }

    buildPredictionText(data) {
        const home = data.teams?.home?.display_name_zh || data.teams?.home?.display_name || '主队';
        const away = data.teams?.away?.display_name_zh || data.teams?.away?.display_name || '客队';
        const probs = data.probabilities || {};
        const xg = data.expected_goals || {};
        const lines = [
            'MatchPredict 世界杯单场预测',
            `${home} vs ${away}`,
        ];

        if (data.locked_result && data.final_score) {
            lines.push(`已完赛结果：${data.final_score.home}-${data.final_score.away}`);
        } else {
            const topScores = (data.top_scores || [])
                .map(score => `${score.home_goals}-${score.away_goals} ${this.formatPercent(score.probability)}`)
                .join('；');
            lines.push(`胜 / 平 / 负：${this.formatPercent(probs.home_win)} / ${this.formatPercent(probs.draw)} / ${this.formatPercent(probs.away_win)}`);
            lines.push(`预期进球 xG：${this.formatXg(xg.home)} / ${this.formatXg(xg.away)}`);
            lines.push(`Top 5 最可能比分：${topScores || '暂无'}`);
            if (data.data_quality) {
                lines.push(`数据完整度：${data.data_quality.level || '未知'} (${data.data_quality.score || 0}/${data.data_quality.max_score || 4})`);
            }
        }

        lines.push(`模型版本：${data.model_version || '未知'}`);
        lines.push(`数据截止：${data.data_cutoff_at || '未知'}`);
        lines.push(data.disclaimer || '概率不代表赛果保证，仅供模型模拟参考。');
        return lines.join('\n');
    }

    async copyCurrentPrediction() {
        if (!this.currentPredictionText) return;
        try {
            if (navigator.clipboard?.writeText) {
                try {
                    await navigator.clipboard.writeText(this.currentPredictionText);
                } catch (_) {
                    this.copyTextWithFallback(this.currentPredictionText);
                }
            } else {
                this.copyTextWithFallback(this.currentPredictionText);
            }
            this.showToast('已复制当前结果', 'success');
        } catch (error) {
            this.showToast('复制失败，可改用下载 TXT 或打印', 'error');
        }
    }

    copyTextWithFallback(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', 'readonly');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (!copied) {
            throw new Error('浏览器未允许复制');
        }
    }

    downloadCurrentPredictionTxt() {
        if (!this.currentPredictionText) return;
        const blob = new Blob([this.currentPredictionText], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `worldcup-prediction-${Date.now()}.txt`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.showToast('TXT 已下载', 'success');
    }

    printCurrentPrediction() {
        if (!this.currentPredictionText) return;
        const popup = window.open('', '_blank', 'width=900,height=700');
        if (!popup) {
            this.showToast('浏览器拦截了打印窗口，请放行后重试', 'error');
            return;
        }
        const escaped = this.escapeHtml(this.currentPredictionText);
        popup.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>MatchPredict 世界杯预测</title><style>body{font-family:Arial,sans-serif;padding:24px;line-height:1.6;}pre{white-space:pre-wrap;}</style></head><body><pre>${escaped}</pre></body></html>`);
        popup.document.close();
        popup.focus();
        popup.print();
    }

    showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
            return;
        }
        let toast = document.getElementById('worldcup-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'worldcup-toast';
            toast.style.position = 'fixed';
            toast.style.right = '20px';
            toast.style.bottom = '20px';
            toast.style.zIndex = '9999';
            toast.style.padding = '10px 14px';
            toast.style.borderRadius = '8px';
            toast.style.color = '#fff';
            toast.style.boxShadow = '0 8px 24px rgba(0,0,0,0.18)';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.background = type === 'error' ? '#d64545' : '#16794c';
        toast.style.display = 'block';
        clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 2400);
    }

    renderDataQuality(quality) {
        if (!quality) return '<div class="worldcup-data-quality">数据完整度：未知</div>';
        const levelMap = { high: '高', medium: '中', low: '低' };
        return `<div class="worldcup-data-quality">数据完整度：${levelMap[quality.level] || quality.level || '未知'}（${quality.score || 0}/${quality.max_score || 4}）</div>`;
    }

    async explainCurrentPrediction() {
        if (!this.currentPrediction) return;
        const container = document.getElementById('worldcup-explanation');
        if (!container) return;
        container.classList.remove('hidden');
        container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在生成白话解释...</div>';
        try {
            const response = await fetch('/api/worldcup/explain', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prediction: this.currentPrediction })
            });
            const data = await response.json();
            if (!data.success) throw new Error(data.message || '解释生成失败');
            container.innerHTML = `
                <h4><i class="fas fa-brain"></i> 白话解释</h4>
                <p>${this.escapeHtml(data.explanation)}</p>
                <small>${data.fallback_used ? '未配置或调用 AI 失败，已使用本地解释；基础预测不受影响。' : 'AI 只解释已有概率，不改写预测结果。'}</small>
            `;
        } catch (error) {
            container.innerHTML = `<div class="empty-message">AI 解释失败：${this.escapeHtml(error.message || '解释生成失败')}。基础预测结果仍可正常参考。</div>`;
        }
    }

    formatStage(fixture) {
        return `${fixture.stage === 'group' ? '小组赛' : fixture.stage || '比赛'} ${fixture.group ? fixture.group + '组' : ''}`;
    }

    formatDate(value) {
        if (!value) return '';
        try {
            return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        } catch (_) {
            return value;
        }
    }

    formatPercent(value) {
        return `${((value || 0) * 100).toFixed(1)}%`;
    }

    formatXg(value) {
        return Number(value || 0).toFixed(2);
    }

    formatNumber(value) {
        return Number(value || 0).toFixed(2);
    }

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
    }
}

function initWorldCupManager() {
    if (!window.worldCupManager) {
        window.worldCupManager = new WorldCupManager();
    }
}

if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', initWorldCupManager);
} else {
    initWorldCupManager();
}
