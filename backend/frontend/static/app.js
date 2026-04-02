/**
 * Snowvel Frontend Application
 * 雪花写作法 - AI 辅助小说创作系统
 */

const app = {
    // 当前状态
    currentProject: null,
    selectedTags: [],
    premiseCandidates: [],
    selectedPremise: null,
    generatedSummary: null,
    generatedOutline: null,
    tagLibrary: null,

    // 初始化
    init() {
        this.bindEvents();
        this.loadProjects();
        this.loadTagLibrary();
        this.loadConfig();
    },

    // 事件绑定
    bindEvents() {
        // 导航切换
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = e.target.dataset.page;
                this.showPage(page);
            });
        });
    },

    // 页面切换
    showPage(pageName) {
        // 更新导航
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.page === pageName);
        });

        // 切换页面
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });
        document.getElementById(`page-${pageName}`).classList.add('active');
    },

    // 显示/隐藏加载
    showLoading() {
        document.getElementById('loading').classList.remove('hidden');
    },

    hideLoading() {
        document.getElementById('loading').classList.add('hidden');
    },

    // 显示/隐藏弹窗
    showModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    },

    hideModal() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    },

    // 显示状态消息
    showStatus(elementId, message, type = 'success') {
        const el = document.getElementById(elementId);
        el.textContent = message;
        el.className = `status-message ${type}`;
        setTimeout(() => {
            el.textContent = '';
            el.className = 'status-message';
        }, 5000);
    },

    // ========== 配置管理 ==========

    async loadConfig() {
        try {
            const res = await fetch('/api/config/');
            const config = await res.json();

            if (config.configured) {
                document.getElementById('api-base-url').value = config.base_url;
                document.getElementById('api-model').value = config.model;
                // 密钥显示掩码
                document.getElementById('api-key').placeholder = `已配置: ${config.api_key_masked}`;
            }
        } catch (err) {
            console.error('加载配置失败:', err);
        }
    },

    async saveConfig() {
        const apiKey = document.getElementById('api-key').value;
        const baseUrl = document.getElementById('api-base-url').value;
        const model = document.getElementById('api-model').value;

        if (!apiKey) {
            this.showStatus('config-status', '请输入 API 密钥', 'error');
            return;
        }

        try {
            const res = await fetch('/api/config/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: apiKey,
                    base_url: baseUrl,
                    model: model
                })
            });

            if (res.ok) {
                this.showStatus('config-status', '配置已保存', 'success');
                document.getElementById('api-key').value = '';
                this.loadConfig();
            } else {
                throw new Error('保存失败');
            }
        } catch (err) {
            this.showStatus('config-status', '保存失败: ' + err.message, 'error');
        }
    },

    async testConfig() {
        // 简单测试：尝试一个需要API的操作
        this.showStatus('config-status', '测试中...', 'success');
        // 实际测试需要调用一个API端点
        // 这里简化处理
        setTimeout(() => {
            this.showStatus('config-status', '请保存配置后生成内容以测试连接', 'success');
        }, 1000);
    },

    // ========== 项目管理 ==========

    async loadProjects() {
        try {
            const res = await fetch('/api/projects/');
            const projects = await res.json();
            this.renderProjects(projects);
        } catch (err) {
            console.error('加载项目失败:', err);
            document.getElementById('projects-list').innerHTML =
                '<p style="text-align: center; color: #666;">加载失败，请刷新重试</p>';
        }
    },

    renderProjects(projects) {
        const container = document.getElementById('projects-list');

        if (projects.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 60px;">
                    <p style="color: #666; margin-bottom: 16px;">还没有项目</p>
                    <button class="btn btn-primary" onclick="app.showCreateProject()">创建第一个项目</button>
                </div>
            `;
            return;
        }

        container.innerHTML = projects.map(p => `
            <div class="project-card" onclick="app.openProject('${p.id}')">
                <h3>${this.escapeHtml(p.name)}</h3>
                <p>${this.escapeHtml(p.description || '暂无描述')}</p>
                <div class="project-meta">
                    <span>${new Date(p.created_at).toLocaleDateString('zh-CN')}</span>
                </div>
                <div class="project-progress">
                    <span class="badge ${p.layer1_completed ? 'completed' : 'pending'}">
                        ${p.layer1_completed ? '✓' : '○'} 灵感雪核
                    </span>
                    <span class="badge ${p.layer2_completed ? 'completed' : 'pending'}">
                        ${p.layer2_completed ? '✓' : '○'} 故事骨架
                    </span>
                </div>
            </div>
        `).join('');
    },

    showCreateProject() {
        this.showModal('create-project-modal');
    },

    async createProject() {
        const name = document.getElementById('new-project-name').value.trim();
        const desc = document.getElementById('new-project-desc').value.trim();

        if (!name) {
            alert('请输入项目名称');
            return;
        }

        try {
            const res = await fetch('/api/projects/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description: desc })
            });

            if (res.ok) {
                const project = await res.json();
                this.hideModal();
                document.getElementById('new-project-name').value = '';
                document.getElementById('new-project-desc').value = '';
                this.loadProjects();
                this.openProject(project.id);
            }
        } catch (err) {
            alert('创建失败: ' + err.message);
        }
    },

    showProjects() {
        this.showPage('projects');
        this.loadProjects();
    },

    async openProject(projectId) {
        try {
            const res = await fetch(`/api/projects/${projectId}`);
            const project = await res.json();

            this.currentProject = project;
            document.getElementById('project-title').textContent = project.info.name;

            // 如果有 Layer1 数据，加载它
            if (project.layer1) {
                this.selectedTags = project.layer1.tags || [];
                this.selectedPremise = project.layer1.selected_premise || null;
                this.updateSelectedTagsDisplay();
                if (this.selectedPremise) {
                    document.getElementById('layer2-premise-display').textContent = this.selectedPremise;
                }
            }

            // 如果有 Layer2 数据，显示完成状态
            if (project.layer2) {
                this.generatedSummary = {
                    sentences: project.layer2.summary_sentences,
                    emotional_costs: project.layer2.emotional_costs
                };
                this.generatedOutline = { chapters: project.layer2.outline };
            }

            // 决定显示哪个 Layer
            if (project.info.layer1_completed && !project.info.layer2_completed) {
                this.showLayer(2);
            } else {
                this.showLayer(1);
            }

            this.showPage('project-detail');
        } catch (err) {
            console.error('加载项目失败:', err);
            alert('加载项目失败');
        }
    },

    // ========== Layer 1: 灵感雪核 ==========

    async loadTagLibrary() {
        try {
            const res = await fetch('/api/projects/tags/library');
            this.tagLibrary = await res.json();
            this.renderTagLibrary();
        } catch (err) {
            console.error('加载标签库失败:', err);
        }
    },

    renderTagLibrary() {
        if (!this.tagLibrary) return;

        const container = document.getElementById('tag-library');
        const categories = [
            { key: 'genres', title: '类型' },
            { key: 'themes', title: '主题' },
            { key: 'tones', title: '基调' },
            { key: 'elements', title: '元素' }
        ];

        container.innerHTML = categories.map(cat => `
            <div class="tag-category">
                <div class="tag-category-title">${cat.title}</div>
                <div>
                    ${this.tagLibrary[cat.key].map(tag => `
                        <span class="tag ${this.selectedTags.includes(tag) ? 'selected' : ''}"
                              onclick="app.toggleTag('${tag}')">
                            ${tag}
                        </span>
                    `).join('')}
                </div>
            </div>
        `).join('');
    },

    toggleTag(tag) {
        const index = this.selectedTags.indexOf(tag);
        if (index > -1) {
            this.selectedTags.splice(index, 1);
        } else {
            this.selectedTags.push(tag);
        }
        this.renderTagLibrary();
        this.updateSelectedTagsDisplay();
    },

    updateSelectedTagsDisplay() {
        const el = document.getElementById('selected-tags-list');
        el.textContent = this.selectedTags.length > 0
            ? this.selectedTags.join('、')
            : '无';
    },

    async generatePremise() {
        if (this.selectedTags.length === 0) {
            alert('请至少选择一个标签');
            return;
        }

        this.showLoading();

        try {
            const res = await fetch('/api/projects/premise/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tags: this.selectedTags,
                    count: 3
                })
            });

            const data = await res.json();
            this.premiseCandidates = data.candidates;
            this.renderPremiseCandidates();
        } catch (err) {
            alert('生成失败: ' + err.message);
        } finally {
            this.hideLoading();
        }
    },

    renderPremiseCandidates() {
        const container = document.getElementById('premise-candidates');

        if (this.premiseCandidates.length === 0) {
            container.innerHTML = '<p style="color: #666;">暂无候选，请先生成</p>';
            return;
        }

        container.innerHTML = this.premiseCandidates.map((premise, idx) => `
            <div class="candidate-item ${this.selectedPremise === premise ? 'selected' : ''}"
                 onclick="app.selectPremise('${this.escapeHtml(premise)}')">
                <div class="premise-text">${this.escapeHtml(premise)}</div>
                <div class="premise-meta">候选 ${idx + 1} · ${premise.length} 字</div>
            </div>
        `).join('');
    },

    selectPremise(premise) {
        this.selectedPremise = premise;
        this.renderPremiseCandidates();
    },

    async saveLayer1() {
        if (!this.selectedPremise) {
            alert('请选择一个前提');
            return;
        }

        try {
            const res = await fetch(`/api/projects/${this.currentProject.info.id}/layer1`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tags: this.selectedTags,
                    selected_premise: this.selectedPremise
                })
            });

            if (res.ok) {
                // 更新显示并进入 Layer 2
                document.getElementById('layer2-premise-display').textContent = this.selectedPremise;
                this.showLayer(2);
            }
        } catch (err) {
            alert('保存失败: ' + err.message);
        }
    },

    // ========== Layer 2: 故事骨架 ==========

    showLayer(layerNum) {
        // 更新步骤指示器
        document.querySelectorAll('.step').forEach(step => {
            step.classList.remove('active');
            if (parseInt(step.dataset.step) < layerNum) {
                step.classList.add('completed');
            } else if (parseInt(step.dataset.step) === layerNum) {
                step.classList.add('active');
            }
        });

        // 切换面板
        document.querySelectorAll('.layer-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.getElementById(`layer${layerNum}-panel`).classList.add('active');
    },

    async generateSummary() {
        if (!this.selectedPremise) {
            alert('请先完成 Layer 1');
            return;
        }

        this.showLoading();

        const endingType = document.getElementById('ending-type').value;

        try {
            const res = await fetch('/api/projects/summary/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    premise: this.selectedPremise,
                    ending_type: endingType
                })
            });

            this.generatedSummary = await res.json();
            this.renderSummary();
        } catch (err) {
            alert('生成失败: ' + err.message);
        } finally {
            this.hideLoading();
        }
    },

    renderSummary() {
        if (!this.generatedSummary) return;

        const container = document.getElementById('summary-result');
        const sentences = this.generatedSummary.sentences;
        const costs = this.generatedSummary.emotional_costs;

        container.innerHTML = `
            <h4>五句话摘要</h4>
            ${sentences.map((s, i) => `
                <div class="summary-sentence">
                    <div class="sentence-num">第 ${i + 1} 句</div>
                    <div>${this.escapeHtml(s)}</div>
                </div>
            `).join('')}
            <div class="emotional-costs">
                <h4>情感代价</h4>
                ${costs.map((c, i) => `
                    <div>冲突 ${i + 1}: ${this.escapeHtml(c)}</div>
                `).join('')}
            </div>
        `;
    },

    async generateOutline() {
        if (!this.generatedSummary) {
            alert('请先生成段落摘要');
            return;
        }

        this.showLoading();

        const numChapters = parseInt(document.getElementById('chapter-count').value);

        try {
            const res = await fetch('/api/projects/outline/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    summary: this.generatedSummary,
                    num_chapters: numChapters
                })
            });

            this.generatedOutline = await res.json();
            this.renderOutline();
        } catch (err) {
            alert('生成失败: ' + err.message);
        } finally {
            this.hideLoading();
        }
    },

    renderOutline() {
        if (!this.generatedOutline) return;

        const container = document.getElementById('outline-result');
        const chapters = this.generatedOutline.chapters;

        container.innerHTML = `
            <h4>章节大纲（共 ${chapters.length} 章）</h4>
            ${chapters.map(ch => `
                <div class="chapter-item">
                    <div class="chapter-header">
                        <span class="chapter-title">${this.escapeHtml(ch.title)}</span>
                        <span class="chapter-num">第 ${ch.chapter} 章</span>
                    </div>
                    <div class="chapter-desc">${this.escapeHtml(ch.description)}</div>
                    <div class="chapter-meta">
                        <span>🎯 ${this.escapeHtml(ch.goal)}</span>
                        <span>⚔️ ${this.escapeHtml(ch.conflict)}</span>
                        <span>💥 ${this.escapeHtml(ch.setback)}</span>
                    </div>
                </div>
            `).join('')}
        `;
    },

    async saveLayer2() {
        if (!this.generatedSummary || !this.generatedOutline) {
            alert('请先生成摘要和大纲');
            return;
        }

        try {
            const res = await fetch(`/api/projects/${this.currentProject.info.id}/layer2`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    summary_sentences: this.generatedSummary.sentences,
                    emotional_costs: this.generatedSummary.emotional_costs,
                    outline: this.generatedOutline.chapters
                })
            });

            if (res.ok) {
                alert('Layer 2 已保存！Phase 1 MVP 完成！');
                this.showProjects();
            }
        } catch (err) {
            alert('保存失败: ' + err.message);
        }
    },

    // 工具函数
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
