/**
 * 中国体育彩票数据处理模块
 */

class LotteryManager {
    constructor() {
        this.matches = [];
        this.selectedMatches = new Set();
        this.isCollapsed = true; // 默认折叠状态
        this.defaultShowCount = 10; // 默认显示的比赛数量
        this.initializeEventListeners();
    }

    // 统一获取胜平负赔率，兼容 had/hhad/wdl 等不同结构
    getWdlOdds(odds) {
        const empty = {};
        if (!odds || typeof odds !== 'object') return empty;

        // 优先使用不让球胜平负(had)
        if (odds.had && (odds.had.h || odds.had.d || odds.had.a)) {
            return odds.had;
        }
        // 兼容旧结构：让球胜平负(hhad) 用作回退
        if (odds.hhad && (odds.hhad.h || odds.hhad.d || odds.hhad.a)) {
            return odds.hhad;
        }
        // 其他可能命名
        if (odds.wdl && (odds.wdl.home || odds.wdl.draw || odds.wdl.away)) {
            return { h: odds.wdl.home, d: odds.wdl.draw, a: odds.wdl.away };
        }
        if (typeof odds.home !== 'undefined' && typeof odds.draw !== 'undefined' && typeof odds.away !== 'undefined') {
            return { h: odds.home, d: odds.draw, a: odds.away };
        }
        return empty;
    }

    initializeEventListeners() {
        // 刷新比赛数据按钮
        const refreshBtn = document.getElementById('refresh-lottery-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                const daysSelect = document.getElementById('days-filter');
                const days = daysSelect ? parseInt(daysSelect.value) : 3;
                this.refreshMatches(days);
            });
        }

        // 数据说明按钮（绿色版只提示本机数据来源）
        const forceRefreshBtn = document.getElementById('force-refresh-lottery-btn');
        if (forceRefreshBtn) {
            forceRefreshBtn.addEventListener('click', () => {
                this.showForceRefreshModal();
            });
        }

        // 天数筛选
        const daysFilter = document.getElementById('days-filter');
        if (daysFilter) {
            daysFilter.addEventListener('change', (e) => {
                this.refreshMatches(parseInt(e.target.value));
            });
        }

        // 折叠/展开切换按钮
        const toggleBtn = document.getElementById('toggle-matches-btn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                this.toggleMatchesDisplay();
            });
        }

        // 生成组合参考按钮
        const generateParlayBtn = document.getElementById('generate-parlay-btn');
        if (generateParlayBtn) {
            generateParlayBtn.addEventListener('click', () => {
                this.generateBestParlay();
            });
        }

        // 清空选择按钮
        const clearBtn = document.getElementById('clear-lottery-selection-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clearSelection();
            });
        }

        // 体彩AI预测按钮
        const predictBtn = document.getElementById('lottery-ai-predict-btn');
        if (predictBtn) {
            predictBtn.addEventListener('click', () => {
                this.startLotteryAIPrediction();
            });
        }
    }

    async refreshMatches(days = 3) {
        const container = document.getElementById('lottery-matches');
        const refreshBtn = document.getElementById('refresh-lottery-btn');

        try {
            // 显示加载状态
            container.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> 正在读取本机比赛数据...</div>';
            this.updateMatchesCount(0, 0);

            if (refreshBtn) {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 读取中...';
            }

            // 从数据库获取比赛数据
            const response = await fetch(`/api/lottery/matches?days=${days}`);

            // 尝试解析JSON
            let data;
            try {
                const responseText = await response.text();
                if (!responseText.trim()) {
                    throw new Error('服务器返回空响应');
                }
                data = JSON.parse(responseText);
            } catch (jsonError) {
                console.error('JSON解析错误:', jsonError);
                throw new Error('服务器响应格式错误，请刷新页面重试');
            }

            // 检查HTTP状态：优先展示后端给出的小白提示，避免只显示 404。
            if (!response.ok) {
                throw new Error(data.message || this.getFriendlyLotteryError(response.status));
            }

            if (data.success) {
                this.matches = data.matches || [];
                this.renderMatches();

                // 显示数据来源信息
                this.showMessage(`已读取 ${data.count || this.matches.length} 场本机比赛数据`, 'success');
            } else {
                throw new Error(data.message || '获取比赛数据失败');
            }

        } catch (error) {
            console.error('获取彩票数据失败:', error);
            this.matches = [];
            this.updateMatchesCount(0, 0);
            container.innerHTML = `
                <div class="empty-message lottery-empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>暂时没有可用的体彩本机数据</h3>
                    <p>${this.escapeHtml(error.message)}</p>
                    <p class="soft-help-text">这不影响“世界杯专题”的基础预测。体彩模式需要先在“设置”里配置数据库，或等待新版绿色数据包。</p>
                    <div class="lottery-empty-actions">
                        <button onclick="lotteryManager.refreshMatches()" class="btn secondary-btn">
                            <i class="fas fa-redo"></i> 重新读取本机体彩数据
                        </button>
                        <button onclick="document.getElementById('settings-btn')?.click()" class="btn primary-btn">
                            <i class="fas fa-cog"></i> 打开设置
                        </button>
                    </div>
                </div>
            `;
            this.showMessage('未读取到体彩数据，世界杯基础预测仍可用', 'warning');
        } finally {
            // 恢复按钮状态
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="fas fa-sync"></i> 重新读取本机体彩数据';
            }
        }
    }

    getFriendlyLotteryError(status) {
        if (status === 404) return '本机暂无体彩比赛数据。本模式只读取本机数据库；未配置数据库时不会联网更新。世界杯基础预测不受影响。';
        if (status === 504) return '读取本机/数据库数据超时，请稍后重试。';
        if (status === 500) return '读取本机/数据库数据失败，请检查设置中的数据库配置。';
        return `读取数据失败 (${status})`;
    }

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
    }

    renderMatches() {
        const container = document.getElementById('lottery-matches');

        if (!this.matches || this.matches.length === 0) {
            container.innerHTML = '<div class="empty-message">暂无体彩比赛数据。本模式只读取本机数据库；未配置数据库时不会联网更新。你也可以先使用世界杯专题基础预测。</div>';
            this.updateMatchesCount(0, 0);
            return;
        }

        // 按联赛分组
        const matchesByLeague = this.groupMatchesByLeague(this.matches);

        let html = '';
        let cardIndex = 0;
        for (const [leagueName, matches] of Object.entries(matchesByLeague)) {
            html += this.renderLeagueSection(leagueName, matches, cardIndex);
            cardIndex += matches.length;
        }

        container.innerHTML = html;

        // 应用折叠状态
        this.applyCollapseState();

        // 更新统计信息
        this.updateMatchesCount(this.matches.length, this.getVisibleMatchesCount());

        // 更新按钮文字
        this.updateToggleButton();

        // 绑定事件
        this.bindMatchEvents();
    }

    groupMatchesByLeague(matches) {
        const grouped = {};
        matches.forEach(match => {
            const league = match.league_name || '其他';
            if (!grouped[league]) {
                grouped[league] = [];
            }
            grouped[league].push(match);
        });
        return grouped;
    }

    renderLeagueSection(leagueName, matches, startIndex = 0) {
        let html = `
            <div class="league-section">
                <h3 class="league-title">
                    <i class="fas fa-futbol"></i> ${leagueName}
                    <span class="match-count">(${matches.length}场)</span>
                </h3>
                <div class="league-matches">
        `;

        matches.forEach((match, index) => {
            const cardIndex = startIndex + index;
            html += this.renderMatchCard(match, cardIndex);
        });

        html += `
                </div>
            </div>
        `;

        return html;
    }

    renderMatchCard(match, cardIndex) {
        const isSelected = this.selectedMatches.has(match.match_id);
        const matchTime = this.formatMatchTime(match.match_time, match.match_date);
        const collapseClass = cardIndex >= this.defaultShowCount ? 'collapsed' : 'show-first-few';

        // 获取赔率信息
        const odds = match.odds || {};

        return `
            <div class="lottery-match-card ${isSelected ? 'selected' : ''}"
                 data-match-id="${match.match_id}">
                <div class="match-header">
                    <div class="match-time">${matchTime}</div>
                    <div class="match-status">${this.getMatchStatus(match.status)}</div>
                </div>

                <div class="match-teams">
                    <div class="team home-team">
                        <span class="team-name">${match.home_team}</span>
                    </div>
                    <div class="vs">VS</div>
                    <div class="team away-team">
                        <span class="team-name">${match.away_team}</span>
                    </div>
                </div>

                ${this.renderOddsSection(odds)}

                <div class="match-actions">
                    <button class="select-match-btn ${isSelected ? 'selected' : ''}"
                            data-match-id="${match.match_id}">
                        <i class="fas ${isSelected ? 'fa-check-square' : 'fa-square'}"></i>
                        ${isSelected ? '已选择' : '选择比赛'}
                    </button>
                </div>
            </div>
        `;
    }

    renderOddsSection(odds) {
        const wdlOdds = this.getWdlOdds(odds);
        const scoreOdds = odds.score || {};
        const goalOdds = odds.goal || {};
        const halfFullOdds = odds.half_full || {};

        let html = '<div class="odds-section">';

        // 胜平负赔率
        if (wdlOdds.h || wdlOdds.d || wdlOdds.a) {
            html += `
                <div class="odds-group">
                    <div class="odds-title">胜平负</div>
                    <div class="odds-values">
                        <span class="odds-item">主胜: ${wdlOdds.h || 'N/A'}</span>
                        <span class="odds-item">平局: ${wdlOdds.d || 'N/A'}</span>
                        <span class="odds-item">客胜: ${wdlOdds.a || 'N/A'}</span>
                    </div>
                </div>
            `;
        }

        // 如果有其他赔率，也可以显示
        if (Object.keys(scoreOdds).length > 0) {
            html += `
                <div class="odds-group">
                    <div class="odds-title">比分玩法</div>
                    <div class="odds-note">共 ${Object.keys(scoreOdds).length} 个选项</div>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    formatMatchTime(matchTime, matchDate) {
        try {
            if (matchDate && matchTime) {
                return `${matchDate} ${matchTime}`;
            } else if (matchDate) {
                return matchDate;
            } else if (matchTime) {
                return matchTime;
            } else {
                return '时间待定';
            }
        } catch (error) {
            return '时间待定';
        }
    }

    getMatchStatus(status) {
        const statusMap = {
            'PENDING': '未开始',
            'LIVE': '进行中',
            'FINISHED': '已结束',
            'CANCELLED': '已取消',
            'Selling': '销售中',
            'Unknown': '未知'
        };
        return statusMap[status] || '未知';
    }

    bindMatchEvents() {
        // 选择比赛按钮
        document.querySelectorAll('.select-match-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const matchId = btn.getAttribute('data-match-id');
                this.toggleMatchSelection(matchId);
            });
        });

        // 点击比赛卡片也能选择
        document.querySelectorAll('.lottery-match-card').forEach(card => {
            card.addEventListener('click', () => {
                const matchId = card.getAttribute('data-match-id');
                this.toggleMatchSelection(matchId);
            });
        });
    }

    toggleMatchSelection(matchId) {
        const match = this.matches.find(m => m.match_id === matchId);
        if (!match) return;

        if (this.selectedMatches.has(matchId)) {
            // 取消选择
            this.selectedMatches.delete(matchId);
        } else {
            // 选择比赛
            this.selectedMatches.add(matchId);
        }

        // 更新显示
        this.updateMatchCardSelection(matchId);
        this.updateSelectionInfo();
        this.updateSelectedMatchesDisplay();

        // 检查是否显示组合推荐
        this.checkParlayRecommendation();

        // 如果当前是体彩模式，立即更新AI模式的显示
        if (window.aiPredictionManager && window.aiPredictionManager.currentMode === 'lottery') {
            window.aiPredictionManager.updateModeSpecificDisplay('lottery');
            window.aiPredictionManager.updateAIPredictButtonText();
        }
    }

    updateMatchCardSelection(matchId) {
        const card = document.querySelector(`[data-match-id="${matchId}"]`);
        const btn = card.querySelector('.select-match-btn');
        const isSelected = this.selectedMatches.has(matchId);

        if (isSelected) {
            card.classList.add('selected');
            btn.classList.add('selected');
            btn.innerHTML = '<i class="fas fa-check-square"></i> 已选择';
        } else {
            card.classList.remove('selected');
            btn.classList.remove('selected');
            btn.innerHTML = '<i class="fas fa-square"></i> 选择比赛';
        }
    }

    updateSelectionInfo() {
        const count = this.selectedMatches.size;

        // 更新主界面的比赛计数
        const matchCount = document.getElementById('match-count');
        if (matchCount) {
            matchCount.textContent = `(${count})`;
        }

        // 更新AI预测按钮状态（如果AI预测管理器存在）
        if (window.aiPredictionManager && typeof window.aiPredictionManager.updateAIPredictButtonText === 'function') {
            window.aiPredictionManager.updateAIPredictButtonText();
        }
    }

    updateSelectedMatchesDisplay() {
        const container = document.getElementById('lottery-selected-matches');
        const countElement = document.getElementById('lottery-selected-count');
        const clearBtn = document.getElementById('clear-lottery-selection-btn');
        const predictBtn = document.getElementById('lottery-ai-predict-btn');

        if (!container) return;

        const selectedMatches = this.getSelectedMatches();
        const count = selectedMatches.length;

        // 更新计数
        if (countElement) {
            countElement.textContent = `(${count})`;
        }

        // 更新按钮状态
        if (clearBtn) {
            clearBtn.disabled = count === 0;
        }
        if (predictBtn) {
            predictBtn.disabled = count === 0;
        }

        // 更新选中比赛列表
        if (count === 0) {
            container.innerHTML = '<div class="empty-message"><i class="fas fa-info-circle"></i><p>请在上方选择比赛</p></div>';
            return;
        }

        let html = '';
        selectedMatches.forEach((match, index) => {
            html += this.renderSelectedMatchCard(match, index);
        });

        container.innerHTML = html;
        this.bindSelectedMatchEvents();
    }

    renderSelectedMatchCard(match, index) {
        const odds = this.getWdlOdds(match.odds);
        return `
            <div class="match-card lottery-selected-card" data-match-id="${match.match_id}">
                <div class="match-info">
                    <div class="teams">
                        <span class="home-team">${match.home_team}</span>
                        <span class="vs">VS</span>
                        <span class="away-team">${match.away_team}</span>
                    </div>
                    <div class="league">${match.league_name}</div>
                </div>

                <div class="odds-info">
                    <div class="odds-group">
                        <span class="odds-label">胜平负:</span>
                        <span class="odds-values">${odds.h || 'N/A'} / ${odds.d || 'N/A'} / ${odds.a || 'N/A'}</span>
                    </div>
                </div>

                <div class="match-actions">
                    <button class="remove-selected-match-btn" data-match-id="${match.match_id}">
                        <i class="fas fa-times"></i> 移除
                    </button>
                </div>
            </div>
        `;
    }

    bindSelectedMatchEvents() {
        // 移除选中比赛按钮
        document.querySelectorAll('.remove-selected-match-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const matchId = btn.getAttribute('data-match-id');
                this.toggleMatchSelection(matchId); // 重用现有逻辑
            });
        });
    }

    getSelectedMatches() {
        return this.matches.filter(match => this.selectedMatches.has(match.match_id));
    }

    clearSelection() {
        this.selectedMatches.clear();
        document.querySelectorAll('.lottery-match-card').forEach(card => {
            card.classList.remove('selected');
        });
        document.querySelectorAll('.select-match-btn').forEach(btn => {
            btn.classList.remove('selected');
            btn.innerHTML = '<i class="fas fa-square"></i> 选择比赛';
        });
        this.updateSelectionInfo();
        this.updateSelectedMatchesDisplay();
    }

    showMessage(message, type = 'info') {
        // 简单的消息提示
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;

        document.body.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.remove();
        }, 3000);
    }

    // 开始彩票AI预测
    async startLotteryAIPrediction() {
        // 检查登录状态和预测权限
        if (!await window.authManager.checkPredictionLimit()) {
            return;
        }

        const selectedMatches = this.getSelectedMatches();

        if (selectedMatches.length === 0) {
            this.showMessage('请先选择比赛', 'error');
            return;
        }

        console.log('开始彩票AI预测，选中比赛:', selectedMatches.length);

        try {
            // 显示加载状态
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.classList.remove('hidden');
            }

            // 转换数据格式为AI预测需要的格式
            const aiMatches = selectedMatches.map(match => {
                const wdl = this.getWdlOdds(match.odds);
                return ({
                match_id: match.match_id,
                home_team: match.home_team,
                away_team: match.away_team,
                league_name: match.league_name,
                home_odds: parseFloat(wdl.h),
                draw_odds: parseFloat(wdl.d),
                away_odds: parseFloat(wdl.a),
                source: 'lottery'
            });
            });

            // 直接调用Gemini API进行预测
            const predictions = [];
            for (const match of aiMatches) {
                try {
                    console.log(`开始预测彩票比赛: ${match.home_team} vs ${match.away_team}`);

                    // 使用AI预测管理器的方法
                    if (window.aiPredictionManager) {
                        const prediction = await window.aiPredictionManager.predictMatchWithGemini(match);
                        if (prediction) {
                            predictions.push(prediction);
                            console.log(`彩票比赛预测成功: ${match.home_team} vs ${match.away_team}`);
                        }
                    } else {
                        throw new Error('AI预测管理器未初始化');
                    }
                } catch (error) {
                    console.error(`预测彩票比赛失败 ${match.home_team} vs ${match.away_team}:`, error);
                    // 继续处理其他比赛
                }
            }

            if (predictions.length > 0) {
                console.log('彩票AI预测成功:', predictions);
                this.displayAIPredictionResults(predictions);

                // 保存预测结果到数据库
                this.savePredictionsToDatabase(predictions);
            } else {
                throw new Error('所有彩票比赛预测都失败了，请检查网络连接或API配置');
            }

        } catch (error) {
            console.error('AI预测错误:', error);
            this.showMessage('AI预测失败: ' + error.message, 'error');
        } finally {
            // 隐藏加载状态
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.classList.add('hidden');
            }
        }
    }

    // 显示AI预测结果
    displayAIPredictionResults(predictions) {
        // 显示结果区域
        const resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');

            // 显示AI分析标签
            const aiTab = document.querySelector('[data-tab="ai-analysis"]');
            if (aiTab) {
                aiTab.classList.remove('hidden');
                aiTab.click(); // 切换到AI分析标签
            }

            // 渲染AI结果
            const aiResultsContainer = document.getElementById('ai-analysis-results');
            if (aiResultsContainer) {
                let html = '<div class="simple-ai-results">';

                predictions.forEach(prediction => {
                    html += `
                        <div class="ai-result-card lottery-selected-card">
                            <div class="match-header">
                                <div class="match-title">
                                    <span>${prediction.home_team}</span>
                                    <span> vs </span>
                                    <span>${prediction.away_team}</span>
                                </div>
                                <div class="league-info">${prediction.league_name}</div>
                            </div>

                            <div class="odds-display">
                                <div class="odds-item">主胜: ${prediction.odds.home}</div>
                                <div class="odds-item">平局: ${prediction.odds.draw}</div>
                                <div class="odds-item">客胜: ${prediction.odds.away}</div>
                            </div>

                            <div class="ai-analysis-content">
                                <h4><i class="fas fa-brain"></i> AI智能分析</h4>
                                <div class="analysis-text">${this.formatAnalysisText(prediction.ai_analysis)}</div>
                            </div>

                            <div class="match-source">
                                <span class="source-tag">体彩数据</span>
                            </div>
                        </div>
                    `;
                });

                html += '</div>';
                aiResultsContainer.innerHTML = html;
            }
        }

        this.showMessage(`AI预测完成，分析了 ${predictions.length} 场比赛`, 'success');
    }

    // 格式化AI分析文本（与AI模式保持一致）
    formatAnalysisText(text) {
        if (!text) return '暂无分析';

        // 处理markdown格式并转换为HTML
        let formatted = text
            // 处理标题
            .replace(/\*\*([^*]+)\*\*/g, '<h5>$1</h5>')
            // 处理粗体
            .replace(/\*([^*]+)\*/g, '<strong>$1</strong>')
            // 处理列表项
            .replace(/^\s*[\*\-]\s+(.+)$/gm, '<li>$1</li>')
            // 处理数字列表
            .replace(/^\s*(\d+)\.\s+(.+)$/gm, '<li>$2</li>')
            // 处理换行
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        // 包装在段落中
        if (!formatted.includes('<p>')) {
            formatted = '<p>' + formatted + '</p>';
        }

        // 处理列表包装
        formatted = formatted.replace(/(<li>.*?<\/li>)/gs, function(match) {
            if (!match.includes('<ul>')) {
                return '<ul>' + match + '</ul>';
            }
            return match;
        });

        // 处理连续的列表项
        formatted = formatted.replace(/(<\/li>)\s*(<li>)/g, '$1$2');
        formatted = formatted.replace(/(<\/ul>)\s*(<ul>)/g, '');

        return formatted;
    }

    // 显示强制刷新模态框
    showForceRefreshModal() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3><i class="fas fa-database"></i> 数据说明</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <p><strong>当前数据来源：</strong>本机数据库或绿色包内置数据。</p>
                    <p><strong>重要说明：</strong>这里不是实时比分源，也不会自动联网同步。</p>
                    <p class="help-text soft-help-text">
                        <i class="fas fa-info-circle"></i>
                        如果比赛列表为空或不够新，世界杯基础预测仍可使用；体彩模式只读取本机数据库，未配置数据库时不会联网更新。
                    </p>
                    <p class="help-text warning-help-text">
                        <i class="fas fa-shield-alt"></i>
                        为了避免误导，已开赛或已结束但缺少赛果的比赛，不会当作赛前预测展示。
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="btn secondary-btn" onclick="this.closest('.modal-overlay').remove()">
                        <i class="fas fa-times"></i> 关闭
                    </button>
                    <button class="btn primary-btn" onclick="this.closest('.modal-overlay').remove(); lotteryManager.refreshMatches();">
                        <i class="fas fa-sync"></i> 重新读取本机体彩数据
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // 点击背景关闭模态框
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    // 保存预测结果到数据库
    async savePredictionsToDatabase(predictions) {
        try {
            for (const prediction of predictions) {
                // 提取预测结果和信心指数
                const aiAnalysis = prediction.ai_analysis || '';
                let predictedResult = '未知';
                let confidence = 5.0;

                // 从AI分析中提取预测结果
                if (aiAnalysis.includes('主胜') || aiAnalysis.includes('主队')) {
                    predictedResult = '主胜';
                } else if (aiAnalysis.includes('客胜') || aiAnalysis.includes('客队')) {
                    predictedResult = '客胜';
                } else if (aiAnalysis.includes('平局') || aiAnalysis.includes('平')) {
                    predictedResult = '平局';
                }

                // 从AI分析中提取信心指数
                const confidenceMatch = aiAnalysis.match(/信心指数[：:]?\s*(\d+(?:\.\d+)?)/);
                if (confidenceMatch) {
                    confidence = parseFloat(confidenceMatch[1]);
                }

                const saveData = {
                    mode: 'lottery',
                    match_data: prediction,
                    prediction_result: predictedResult,
                    confidence: confidence,
                    ai_analysis: aiAnalysis
                };

                // 发送到后端保存
                const response = await fetch('/api/save-prediction', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(saveData)
                });

                if (response.ok) {
                    console.log(`✅ 彩票预测结果已保存: ${prediction.home_team} vs ${prediction.away_team}`);
                } else {
                    console.warn(`⚠️ 彩票预测结果保存失败: ${prediction.home_team} vs ${prediction.away_team}`);
                }
            }
        } catch (error) {
            console.error('保存彩票预测结果到数据库失败:', error);
        }
    }

    // 折叠/展开功能
    toggleMatchesDisplay() {
        this.isCollapsed = !this.isCollapsed;
        this.applyCollapseState();
        this.updateMatchesCount(this.matches.length, this.getVisibleMatchesCount());
        this.updateToggleButton();
    }

    applyCollapseState() {
        const cards = document.querySelectorAll('#lottery-matches .lottery-match-card');
        const container = document.getElementById('lottery-matches');

        // 清除现有的折叠指示器
        const existingOverlay = container.querySelector('.matches-fade-overlay');
        if (existingOverlay) {
            existingOverlay.remove();
        }

        cards.forEach((card, index) => {
            if (this.isCollapsed && index >= this.defaultShowCount) {
                card.classList.add('hidden-match');
            } else {
                card.classList.remove('hidden-match');
            }
        });

        // 如果是折叠状态且有超过10场比赛，添加渐变指示器
        if (this.isCollapsed && cards.length > this.defaultShowCount) {
            const overlay = document.createElement('div');
            overlay.className = 'matches-fade-overlay';
            overlay.innerHTML = `还有 ${cards.length - this.defaultShowCount} 场比赛...`;
            container.appendChild(overlay);
        }
    }

    getVisibleMatchesCount() {
        if (this.isCollapsed) {
            return Math.min(this.matches.length, this.defaultShowCount);
        }
        return this.matches.length;
    }

    updateMatchesCount(total, visible) {
        const totalElement = document.getElementById('total-matches-count');
        const visibleElement = document.getElementById('visible-matches-count');

        if (totalElement) totalElement.textContent = total;
        if (visibleElement) visibleElement.textContent = visible;
    }

    updateToggleButton() {
        const toggleBtn = document.getElementById('toggle-matches-btn');
        if (!toggleBtn) return;

        if (this.isCollapsed) {
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i> 显示全部';
        } else {
            toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i> 收起';
        }
    }

    // 组合参考
    async generateBestParlay() {
        // 检查登录状态和预测权限
        if (!await window.authManager.checkPredictionLimit()) {
            return;
        }

        const selectedMatchesArray = Array.from(this.selectedMatches).map(id =>
            this.matches.find(match => match.match_id === id)
        ).filter(Boolean);

        if (selectedMatchesArray.length < 2) {
            this.showMessage('请至少选择2场比赛才能生成组合推荐', 'warning');
            return;
        }

        const parlaySection = document.getElementById('best-parlay-recommendation');
        const parlayContent = document.getElementById('parlay-content');
        const generateBtn = document.getElementById('generate-parlay-btn');

        if (!parlaySection || !parlayContent) return;

        // 显示推荐区域
        parlaySection.classList.remove('hidden');

        // 显示加载状态
        parlayContent.innerHTML = '<div class="parlay-loading"><i class="fas fa-spinner fa-spin"></i> AI正在分析最佳组合...</div>';

        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 分析中';
        }

        try {
            // 构建AI分析提示词
            const prompt = this.buildParlayPrompt(selectedMatchesArray);

            // 调用AI分析
            const aiResponse = await this.callGeminiForParlay(prompt);

            // 显示推荐结果
            this.displayParlayRecommendation(aiResponse, selectedMatchesArray);

        } catch (error) {
            console.error('生成组合推荐失败:', error);
            parlayContent.innerHTML = `
                <div class="parlay-error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>AI分析失败: ${error.message}</p>
                    <button class="btn compact-btn" onclick="lotteryManager.generateBestParlay()">
                        <i class="fas fa-refresh"></i> 重试
                    </button>
                </div>
            `;
        } finally {
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.innerHTML = '<i class="fas fa-magic"></i> 重新生成';
            }
        }
    }

    buildParlayPrompt(matches) {
        let prompt = `作为专业的足球分析师，请为以下${matches.length}场比赛提供组合参考：\n\n`;

        matches.forEach((match, index) => {
            const odds = this.getWdlOdds(match.odds);
            prompt += `比赛${index + 1}: ${match.home_team} vs ${match.away_team}\n`;
            prompt += `联赛: ${match.league_name}\n`;
            prompt += `时间: ${match.match_time}\n`;
            prompt += `赔率: 主胜${odds.h || 'N/A'} 平局${odds.d || 'N/A'} 客胜${odds.a || 'N/A'}\n\n`;
        });

        prompt += `请提供：
1. **推荐组合方案**: 每场比赛的推荐结果(主胜/平局/客胜)
2. **组合赔率**: 计算总赔率
3. **信心指数**: 1-10分评分
4. **分析理由**: 每场比赛的简要分析(球队实力、近期状态、历史对战等)
5. **风险评估**: 指出潜在风险点

要求：
- 格式简洁明了
- 突出重点信息
- 控制在300字以内`;

        return prompt;
    }

    async callGeminiForParlay(prompt) {
        const response = await fetch('/api/ai/analyze-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            if (window.settingsManager) {
                window.settingsManager.openSettingsModal(false);
            }
            throw new Error(data.error || data.message || `AI\u63a5\u53e3\u8c03\u7528\u5931\u8d25\uff1a${response.status}`);
        }
        return data.analysis;
    }

    displayParlayRecommendation(aiResponse, matches) {
        const parlayContent = document.getElementById('parlay-content');
        if (!parlayContent) return;

        // 计算总赔率 (简单估算)
        let totalOdds = 1;
        matches.forEach(match => {
            const odds = this.getWdlOdds(match.odds);
            const avgOdds = (parseFloat(odds.h || 0) + parseFloat(odds.d || 0) + parseFloat(odds.a || 0)) / 3;
            totalOdds *= (avgOdds || 2.5);
        });

        parlayContent.innerHTML = `
            <div class="parlay-recommendation">
                <div class="parlay-stats">
                    <div class="parlay-stat">
                        <span class="parlay-stat-value">${matches.length}</span>
                        <span class="parlay-stat-label">场比赛</span>
                    </div>
                    <div class="parlay-stat">
                        <span class="parlay-stat-value">${totalOdds.toFixed(2)}</span>
                        <span class="parlay-stat-label">预估赔率</span>
                    </div>
                </div>

                <div class="parlay-analysis">
                    ${this.formatAnalysisText(aiResponse)}
                </div>
            </div>
        `;
    }

    // 检查是否显示组合推荐
    checkParlayRecommendation() {
        const parlaySection = document.getElementById('best-parlay-recommendation');
        if (!parlaySection) return;

        if (this.selectedMatches.size >= 2) {
            parlaySection.classList.remove('hidden');
        } else {
            parlaySection.classList.add('hidden');
        }
    }
}

// 全局实例
let lotteryManager = null;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    lotteryManager = new LotteryManager();
    window.lotteryManager = lotteryManager; // 暴露为全局变量
});

// 导出给其他模块使用
window.LotteryManager = LotteryManager;
