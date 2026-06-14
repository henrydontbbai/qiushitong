/**
 * 2026 世界杯专题：单场预测前端闭环。
 * 基础预测不依赖 AI；AI 只解释已有概率。
 */
class WorldCupManager {
    constructor() {
        this.fixtures = [];
        this.currentPrediction = null;
        this.bindEvents();
        this.loadFixtures();
    }

    bindEvents() {
        const refreshBtn = document.getElementById('worldcup-refresh-btn');
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.loadFixtures());

        const explainBtn = document.getElementById('worldcup-ai-explain-btn');
        if (explainBtn) explainBtn.addEventListener('click', () => this.explainCurrentPrediction());
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

        container.querySelectorAll('.worldcup-predict-btn').forEach(button => {
            button.addEventListener('click', () => this.predictFixture(button.getAttribute('data-match-id')));
        });
    }

    async predictFixture(matchId) {
        const resultContainer = document.getElementById('worldcup-prediction');
        const explainBtn = document.getElementById('worldcup-ai-explain-btn');
        const explanation = document.getElementById('worldcup-explanation');
        if (resultContainer) resultContainer.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在计算预测...</div>';
        if (explainBtn) explainBtn.disabled = true;
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
            this.renderPrediction(data);
            if (explainBtn && !data.locked_result) explainBtn.disabled = false;
        } catch (error) {
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
                <p class="worldcup-disclaimer">${this.escapeHtml(data.disclaimer || '概率不代表赛果保证，仅供模型模拟参考，非投注建议。')}</p>
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

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
    }
}

window.addEventListener('DOMContentLoaded', () => {
    window.worldCupManager = new WorldCupManager();
});
