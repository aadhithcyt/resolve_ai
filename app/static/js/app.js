// ResolveAI Frontend Application
const API = '';

// State
let currentView = 'dashboard';
let tickets = [];
let customers = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupKeyboardShortcuts();
    setupThemeToggle();
    setupNotificationBell();
    setupHamburgerMenu();
    initNotifications();
    startPresence();
    setupRipple();
    loadDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopPresence();
    disconnectChat();
});

// Helper: add data-label attributes to table cells for mobile card layout
function addTableLabels() {
    document.querySelectorAll('.table-wrap table').forEach(table => {
        const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
        if (headers.length === 0) return;
        table.querySelectorAll('tbody tr').forEach(tr => {
            tr.querySelectorAll('td').forEach((td, i) => {
                if (headers[i]) td.setAttribute('data-label', headers[i]);
            });
        });
    });
}

// Navigation
function setupNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            transitionToView(btn.dataset.view);
        });
    });
}

function render() {
    const main = document.getElementById('main-content');
    switch(currentView) {
        case 'dashboard': loadDashboard(); break;
        case 'tickets': loadTickets(); break;
        case 'customers': loadCustomers(); break;
        case 'knowledge': loadKnowledge(); break;
        case 'analytics': loadAnalytics(); break;
    }
}

// ─── Ripple Effect ───────────────────────────────────────────────────────────
function setupRipple() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn, .btn-primary, .btn-accent, .icon-btn, .nav-btn');
        if (!btn) return;
        const rect = btn.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        btn.style.setProperty('--ripple-x', x + '%');
        btn.style.setProperty('--ripple-y', y + '%');
        // Force reflow then reset for next click
        void btn.offsetWidth;
    });
}

// ─── Animated Counter ────────────────────────────────────────────────────────
function animateCounter(el, target, duration = 800) {
    if (!el) return;
    const start = 0;
    const startTime = performance.now();
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(start + (target - start) * eased);
        el.textContent = current;
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

// ─── Smooth View Transition ──────────────────────────────────────────────────
function transitionToView(newView) {
    const main = document.getElementById('main-content');
    // Fade out
    main.style.opacity = '0';
    main.style.transform = 'translateY(8px)';
    main.style.transition = 'opacity 0.15s ease, transform 0.15s ease';
    setTimeout(() => {
        currentView = newView;
        render();
        // Fade in
        main.style.opacity = '1';
        main.style.transform = 'translateY(0)';
    }, 150);
}

// API helpers
async function api(endpoint, options = {}) {
    const url = API + endpoint;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Request failed');
    }
    return res.status === 204 ? null : res.json();
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// Dashboard
async function loadDashboard() {
    const main = document.getElementById('main-content');
    main.innerHTML = '<div class="loading"></div>';
    try {
        const stats = await api('/api/dashboard/stats');
        main.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">Total Tickets</div>
                    <div class="value" id="stat-total">${stats.total_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Open</div>
                    <div class="value open" id="stat-open">${stats.open_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">In Progress</div>
                    <div class="value in-progress" id="stat-progress">${stats.in_progress_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Resolved</div>
                    <div class="value resolved" id="stat-resolved">${stats.resolved_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Closed</div>
                    <div class="value closed" id="stat-closed">${stats.closed_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Avg Resolution</div>
                    <div class="value" id="stat-avg">${stats.avg_resolution_hours ? stats.avg_resolution_hours + 'h' : 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="label">SLA Breached</div>
                    <div class="value sla-breached" id="stat-sla">${stats.sla_breached || 0}</div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Recent Tickets</span>
                    <button class="btn btn-primary btn-sm" onclick="showNewTicketModal()">+ New Ticket</button>
                </div>
                <div class="card-body table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Subject</th>
                                <th>Customer</th>
                                <th>Status</th>
                                <th>Priority</th>
                                <th>Created</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${stats.recent_tickets.map(t => `
                                <tr>
                                    <td>#${t.id}</td>
                                    <td><a href="#" onclick="showTicketDetail(${t.id}); return false;">${esc(t.subject)}</a></td>
                                    <td>${esc(t.customer_name || '')}</td>
                                    <td><span class="badge badge-${t.status}">${t.status.replace('_', ' ')}</span></td>
                                    <td><span class="badge badge-${t.priority}">${t.priority}</span></td>
                                    <td>${formatDate(t.created_at)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    ${stats.recent_tickets.length === 0 ? '<div class="empty-state"><div class="icon">📭</div><p>No tickets yet. Create your first one!</p></div>' : ''}
                </div>
            </div>
        `;
        // Animate counters
        animateCounter(document.getElementById('stat-total'), stats.total_tickets);
        animateCounter(document.getElementById('stat-open'), stats.open_tickets);
        animateCounter(document.getElementById('stat-progress'), stats.in_progress_tickets);
        animateCounter(document.getElementById('stat-resolved'), stats.resolved_tickets);
        animateCounter(document.getElementById('stat-closed'), stats.closed_tickets);
        animateCounter(document.getElementById('stat-sla'), stats.sla_breached || 0);
    } catch (e) {
        main.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${esc(e.message)}</p></div>`;
    }
}

// Tickets
async function loadTickets(filters = {}) {
    const main = document.getElementById('main-content');
    main.innerHTML = '<div class="loading"></div>';
    try {
        const params = new URLSearchParams();
        if (filters.status) params.set('status', filters.status);
        if (filters.priority) params.set('priority', filters.priority);
        if (filters.search) params.set('search', filters.search);
        if (filters.sla_breached) params.set('sla_breached', filters.sla_breached);

        tickets = await api('/api/tickets/?' + params.toString());
        main.innerHTML = `
            <div class="tickets-layout">
                <div class="tickets-main">
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">Tickets (${tickets.length})</span>
                            <button class="btn btn-primary btn-sm" onclick="showNewTicketModal()">+ New Ticket</button>
                        </div>
                        <div class="card-body">
                            <div class="filters">
                                <select class="form-select" id="filter-status" onchange="applyFilters()">
                                    <option value="">All Status</option>
                                    <option value="open">Open</option>
                                    <option value="in_progress">In Progress</option>
                                    <option value="resolved">Resolved</option>
                                    <option value="closed">Closed</option>
                                </select>
                                <select class="form-select" id="filter-priority" onchange="applyFilters()">
                                    <option value="">All Priority</option>
                                    <option value="low">Low</option>
                                    <option value="medium">Medium</option>
                                    <option value="high">High</option>
                                    <option value="urgent">Urgent</option>
                                </select>
                                <select class="form-select" id="filter-sla" onchange="applyFilters()">
                                    <option value="">All SLA</option>
                                    <option value="true">SLA Breached</option>
                                    <option value="false">SLA On Track</option>
                                </select>
                                <input type="text" class="form-input" id="filter-search" placeholder="Search tickets..." style="flex:1" onkeyup="debounceApplyFilters()">
                            </div>
                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>ID</th>
                                            <th>Subject</th>
                                            <th>Customer</th>
                                            <th>Status</th>
                                            <th>Priority</th>
                                            <th>Category</th>
                                            <th>Sentiment</th>
                                            <th>Created</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${tickets.map(t => `
                                            <tr class="${t.sla_breached ? 'sla-breached-row' : ''}" data-ticket-id="${t.id}">
                                                <td>#${t.id}</td>
                                                <td><a href="#" onclick="showTicketDetail(${t.id}); return false;">${esc(t.subject)}</a></td>
                                                <td>${esc(t.customer_name || '')}</td>
                                                <td><span class="badge badge-${t.status}">${t.status.replace('_', ' ')}</span></td>
                                                <td><span class="badge badge-${t.priority}">${t.priority}</span></td>
                                                <td>${esc(t.category)}</td>
                                                <td>${t.sentiment ? `<span class="badge badge-${t.sentiment}">${t.sentiment}</span>` : '-'}</td>
                                                <td>${t.sla_breached ? '<span class="badge badge-sla-breached">SLA BREACHED</span>' : ''}</td>
                                                <td>${formatDate(t.created_at)}</td>
                                                <td>
                                                    <button class="btn btn-sm" onclick="showTicketDetail(${t.id})">View</button>
                                                    <button class="btn btn-sm btn-danger" onclick="deleteTicket(${t.id})">Delete</button>
                                                </td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                                ${tickets.length === 0 ? '<div class="empty-state"><div class="icon">📭</div><p>No tickets found.</p></div>' : ''}
                            </div>
                        </div>
                    </div>
                </div>
                <div class="tickets-sidebar">
                    <div class="card">
                        <div class="card-header"><span class="card-title">Agents</span></div>
                        <div class="card-body">
                            <p style="font-size:0.75rem;color:var(--text2);margin-bottom:12px">Drag tickets onto an agent to assign</p>
                            <div id="agent-list" class="agent-list">
                                ${presenceAgents.length > 0 ? presenceAgents.map(a => `
                                    <div class="agent-item" data-agent-name="${esc(a.agent_id)}">
                                        <span class="agent-status-dot ${esc(a.status)}"></span>
                                        <span class="agent-name">${esc(a.agent_id)}</span>
                                    </div>
                                `).join('') : '<p style="color:var(--text2);font-size:0.875rem">No agents online</p>'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        setupDragAndDrop();
    } catch (e) {
        main.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${esc(e.message)}</p></div>`;
    }
}

function applyFilters() {
    const status = document.getElementById('filter-status')?.value || '';
    const priority = document.getElementById('filter-priority')?.value || '';
    const search = document.getElementById('filter-search')?.value || '';
    const sla = document.getElementById('filter-sla')?.value || '';
    loadTickets({ status, priority, search, sla_breached: sla });
}

let debounceTimer;
function debounceApplyFilters() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyFilters, 300);
}

// Ticket Detail
async function showTicketDetail(ticketId) {
    const main = document.getElementById('main-content');
    main.innerHTML = '<div class="loading"></div>';
    try {
        const [ticket, messages] = await Promise.all([
            api(`/api/tickets/${ticketId}`),
            api(`/api/tickets/${ticketId}/messages`),
        ]);

        const customer = await api(`/api/customers/${ticket.customer_id}`).catch(() => null);
        const attachments = await api(`/api/tickets/${ticketId}/attachments`).catch(() => []);

        // Connect to real-time chat
        const agentId = localStorage.getItem('agent_id') || 'agent';
        connectChat(ticketId, 'agent', agentId);

        main.innerHTML = `
            <button class="btn btn-sm" onclick="loadTickets()" style="margin-bottom:16px">← Back to Tickets</button>
            <div class="ticket-detail">
                <div>
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">#${ticket.id} — ${esc(ticket.subject)}</span>
                            <div>
                                <button class="btn btn-sm btn-primary" onclick="showAIModal(${ticket.id})">🤖 AI Reply</button>
                                <button class="btn btn-sm btn-accent" onclick="showAgentStreamingModal(${ticket.id})">🧠 AI Agent</button>
                                <button class="btn btn-sm" onclick="showEditTicketModal(${ticket.id})">Edit</button>
                            </div>
                        </div>
                        <div class="card-body">
                            <p style="margin-bottom:16px">${esc(ticket.description)}</p>
                            ${ticket.ai_reply ? `
                                <div class="ai-reply-box" id="ai-reply-${ticket.id}">
                                    <div class="label">AI Suggested Reply</div>
                                    <div class="ai-reply-content">${esc(ticket.ai_reply)}</div>
                                    <div style="margin-top:12px;display:flex;gap:8px">
                                        <button class="btn btn-sm btn-primary" onclick="showAIReplyEditor(${ticket.id})">✏️ Edit</button>
                                        <button class="btn btn-sm" onclick="useAIReply(${ticket.id})">Use This Reply</button>
                                        <button class="btn btn-sm" onclick="showAIModal(${ticket.id})">Regenerate</button>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">Conversation</span>
                            <span class="chat-presence" id="chat-presence" style="font-size:0.75rem;color:var(--text2)"></span>
                        </div>
                        <div class="card-body">
                            <div id="chat-messages" style="max-height:400px;overflow-y:auto;margin-bottom:16px">
                                ${messages.map(m => `
                                    <div class="message message-${m.sender}${m.is_ai_generated ? '-ai' : ''}">
                                        <div class="message-meta">${m.sender}${m.is_ai_generated ? ' (AI)' : ''} — ${formatDate(m.created_at)}</div>
                                        ${esc(m.content)}
                                    </div>
                                `).join('')}
                            </div>
                            <div id="chat-typing" style="display:none;font-size:0.875rem;color:var(--text2);margin-bottom:8px"></div>
                            <div style="display:flex;gap:8px">
                                <input type="text" class="form-input" id="chat-input" placeholder="Type a message..." style="flex:1" onkeypress="if(event.key==='Enter')sendChatMessage()">
                                <button class="btn btn-primary" onclick="sendChatMessage()">Send</button>
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">Attachments (${attachments.length})</span>
                        </div>
                        <div class="card-body">
                            ${attachments.length > 0 ? `
                                <div class="attachment-list">
                                    ${attachments.map(a => `
                                        <div class="attachment-item">
                                            <span class="attachment-icon">📎</span>
                                            <a href="/api/attachments/${a.id}/download" class="attachment-name" download="${esc(a.filename)}">${esc(a.filename)}</a>
                                            <span class="attachment-meta">${esc(a.content_type || 'unknown')} — ${formatDate(a.uploaded_at)}</span>
                                            <button class="btn btn-sm btn-danger" onclick="deleteAttachment(${a.id}, ${ticket.id})">Delete</button>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : '<p style="color:var(--text2)">No attachments yet.</p>'}
                            <hr style="border-color:var(--border);margin:12px 0">
                            <div class="form-group">
                                <label class="form-label">Upload Attachment</label>
                                <input type="file" class="form-input" id="attachment-file" style="margin-bottom:8px">
                                <button class="btn btn-sm btn-primary" onclick="uploadAttachment(${ticket.id})">Upload File</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div>
                    <div class="card">
                        <div class="card-header"><span class="card-title">Details</span></div>
                        <div class="card-body">
                            <p><strong>Customer:</strong> ${esc(customer?.name || 'Unknown')}</p>
                            <p><strong>Email:</strong> ${esc(customer?.email || '-')}</p>
                            <p><strong>Company:</strong> ${esc(customer?.company || '-')}</p>
                            <hr style="border-color:var(--border);margin:12px 0">
                            <p><strong>Status:</strong> <span class="badge badge-${ticket.status}">${ticket.status.replace('_', ' ')}</span></p>
                            <p><strong>Priority:</strong> <span class="badge badge-${ticket.priority}">${ticket.priority}</span></p>
                            <p><strong>Category:</strong> ${esc(ticket.category)}</p>
                            <p><strong>Sentiment:</strong> ${ticket.sentiment ? `<span class="badge badge-${ticket.sentiment}">${ticket.sentiment}</span>` : '-'}</p>
                            <p><strong>Assigned:</strong> ${esc(ticket.assigned_to || 'Unassigned')}</p>
                            <hr style="border-color:var(--border);margin:12px 0">
                            <p><strong>SLA Due:</strong> ${ticket.sla_due_at ? formatDate(ticket.sla_due_at) : '-'}</p>
                            <p><strong>SLA Status:</strong> ${ticket.sla_breached ? '<span class="badge badge-sla-breached">BREACHED</span>' : '<span class="badge badge-resolved">On Track</span>'}</p>
                            <hr style="border-color:var(--border);margin:12px 0">
                            <p><strong>Created:</strong> ${formatDate(ticket.created_at)}</p>
                            <p><strong>Updated:</strong> ${formatDate(ticket.updated_at)}</p>
                            ${ticket.resolved_at ? `<p><strong>Resolved:</strong> ${formatDate(ticket.resolved_at)}</p>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    } catch (e) {
        main.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${esc(e.message)}</p></div>`;
    }
}

// Knowledge Base
async function loadKnowledge() {
    const main = document.getElementById('main-content');
    main.innerHTML = '<div class="loading"></div>';
    try {
        const articles = await api('/api/kb/');
        main.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Knowledge Base (${articles.length})</span>
                    <button class="btn btn-primary btn-sm" onclick="showNewKBModal()">+ Add Article</button>
                </div>
                <div class="card-body">
                    <div class="filters">
                        <input type="text" class="form-input" id="kb-search" placeholder="Search knowledge base..." style="flex:1" onkeyup="debounceKBSearch()">
                    </div>
                    <div class="table-wrap">
                        <table>
                            <thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Tags</th><th>Actions</th></tr></thead>
                            <tbody>
                                ${articles.map(a => `
                                    <tr>
                                        <td>#${a.id}</td>
                                        <td>${esc(a.title)}</td>
                                        <td><span class="badge badge-medium">${esc(a.category)}</span></td>
                                        <td>${esc(a.tags || '-')}</td>
                                        <td>
                                            <button class="btn btn-sm" onclick="showKBDetail(${a.id})">View</button>
                                            <button class="btn btn-sm btn-danger" onclick="deleteKB(${a.id})">Delete</button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                        ${articles.length === 0 ? '<div class="empty-state"><div class="icon">📚</div><p>No knowledge base articles yet.</p></div>' : ''}
                    </div>
                </div>
            </div>
        `;
    } catch (e) {
        main.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${esc(e.message)}</p></div>`;
    }
}

function debounceKBSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
        const q = document.getElementById('kb-search')?.value || '';
        if (!q) { loadKnowledge(); return; }
        const main = document.getElementById('main-content');
        try {
            const result = await api('/api/kb/search?query=' + encodeURIComponent(q));
            const tbody = main.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = result.results.map(a => `
                    <tr>
                        <td>#${a.id}</td>
                        <td>${esc(a.title)}</td>
                        <td><span class="badge badge-medium">${esc(a.category)}</span></td>
                        <td>${esc(a.tags || '-')}</td>
                        <td>
                            <button class="btn btn-sm" onclick="showKBDetail(${a.id})">View</button>
                            <button class="btn btn-sm btn-danger" onclick="deleteKB(${a.id})">Delete</button>
                        </td>
                    </tr>
                `).join('');
            }
        } catch (e) { /* ignore */ }
    }, 300);
}

function showNewKBModal() {
    showModal('New Knowledge Article', `
        <div class="form-group"><label class="form-label">Title *</label><input type="text" class="form-input" id="kb-title"></div>
        <div class="form-group"><label class="form-label">Content *</label><textarea class="form-textarea" id="kb-content" placeholder="Article content, FAQ, or solution..."></textarea></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group"><label class="form-label">Category</label><input type="text" class="form-input" id="kb-category" value="general"></div>
            <div class="form-group"><label class="form-label">Tags</label><input type="text" class="form-input" id="kb-tags" placeholder="comma,separated"></div>
        </div>
    `, `<button class="btn" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createKB()">Create</button>`);
}

async function createKB() {
    const data = {
        title: document.getElementById('kb-title').value,
        content: document.getElementById('kb-content').value,
        category: document.getElementById('kb-category').value || 'general',
        tags: document.getElementById('kb-tags').value || null,
    };
    if (!data.title || !data.content) { showToast('Title and content required', 'error'); return; }
    try {
        await api('/api/kb/', { method: 'POST', body: JSON.stringify(data) });
        closeModal(); showToast('Article created'); loadKnowledge();
    } catch (e) { showToast(e.message, 'error'); }
}

async function showKBDetail(id) {
    const a = await api(`/api/kb/${id}`);
    showModal(esc(a.title), `<p style="white-space:pre-wrap">${esc(a.content)}</p><p style="margin-top:12px;color:var(--text2);font-size:0.75rem">Category: ${esc(a.category)} | Tags: ${esc(a.tags || '-')}</p>`);
}

async function deleteKB(id) {
    if (!confirm('Delete this article?')) return;
    try { await api(`/api/kb/${id}`, { method: 'DELETE' }); showToast('Deleted'); loadKnowledge(); }
    catch (e) { showToast(e.message, 'error'); }
}

// Analytics
async function loadAnalytics() {
    const main = document.getElementById('main-content');
    main.innerHTML = '<div class="loading"></div>';
    try {
        const stats = await api('/api/analytics/ai');
        main.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><div class="label">Total AI Replies</div><div class="value">${stats.total_ai_replies}</div></div>
                <div class="stat-card"><div class="label">Accepted</div><div class="value resolved">${stats.accepted_replies}</div></div>
                <div class="stat-card"><div class="label">Acceptance Rate</div><div class="value">${stats.acceptance_rate}%</div></div>
                <div class="stat-card"><div class="label">Avg Tool Calls</div><div class="value">${stats.avg_tool_calls}</div></div>
            </div>
            <div class="card">
                <div class="card-header"><span class="card-title">Tool Usage</span></div>
                <div class="card-body">
                    ${Object.entries(stats.tool_usage).map(([tool, count]) => `
                        <p><strong>${esc(tool)}:</strong> ${count} calls</p>
                    `).join('') || '<p>No tool usage data yet.</p>'}
                </div>
            </div>
            <div class="card">
                <div class="card-header"><span class="card-title">Recent AI Activity</span></div>
                <div class="card-body">
                    ${stats.recent_activity.map(a => `
                        <div class="message message-ai">
                            <div class="message-meta">Ticket #${a.ticket_id} — ${a.tool_calls_made} tool calls — ${formatDate(a.created_at)}</div>
                            ${esc(a.reply_text.substring(0, 150))}...
                        </div>
                    `).join('') || '<p>No AI activity yet.</p>'}
                </div>
            </div>
        `;
    } catch (e) {
        main.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${esc(e.message)}</p></div>`;
    }
}

// Customers
async function loadCustomers() {
    const main = document.getElementById('main-content');
    main.innerHTML = '<div class="loading"></div>';
    try {
        customers = await api('/api/customers/');
        main.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Customers (${customers.length})</span>
                    <button class="btn btn-primary btn-sm" onclick="showNewCustomerModal()">+ New Customer</button>
                </div>
                <div class="card-body table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Phone</th>
                                <th>Company</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${customers.map(c => `
                                <tr>
                                    <td>#${c.id}</td>
                                    <td>${esc(c.name)}</td>
                                    <td>${esc(c.email)}</td>
                                    <td>${esc(c.phone || '-')}</td>
                                    <td>${esc(c.company || '-')}</td>
                                    <td>${formatDate(c.created_at)}</td>
                                    <td>
                                        <button class="btn btn-sm" onclick="showEditCustomerModal(${c.id})">Edit</button>
                                        <button class="btn btn-sm btn-danger" onclick="deleteCustomer(${c.id})">Delete</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    ${customers.length === 0 ? '<div class="empty-state"><div class="icon">👤</div><p>No customers yet.</p></div>' : ''}
                </div>
            </div>
        `;
    } catch (e) {
        main.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${esc(e.message)}</p></div>`;
    }
}

// Modals
function showModal(title, bodyHTML, footerHTML = '') {
    const overlay = document.getElementById('modal-overlay');
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <span class="modal-title">${title}</span>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">${bodyHTML}</div>
            <div class="modal-footer">${footerHTML}</div>
        </div>
    `;
    overlay.classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// New Ticket Modal
async function showNewTicketModal() {
    if (customers.length === 0) {
        try { customers = await api('/api/customers/'); } catch(e) {}
    }
    showModal('New Ticket', `
        <div class="form-group">
            <label class="form-label">Customer *</label>
            <select class="form-select" id="ticket-customer">
                <option value="">Select customer...</option>
                ${customers.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.email)})</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Subject *</label>
            <input type="text" class="form-input" id="ticket-subject" placeholder="Brief description of the issue">
        </div>
        <div class="form-group">
            <label class="form-label">Description *</label>
            <textarea class="form-textarea" id="ticket-description" placeholder="Detailed description of the issue..."></textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group">
                <label class="form-label">Priority</label>
                <select class="form-select" id="ticket-priority">
                    <option value="low">Low</option>
                    <option value="medium" selected>Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urent</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Category</label>
                <input type="text" class="form-input" id="ticket-category" value="general" placeholder="general">
            </div>
        </div>
    `, `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="createTicket()">Create Ticket</button>
    `);
}

async function createTicket() {
    const data = {
        customer_id: parseInt(document.getElementById('ticket-customer').value),
        subject: document.getElementById('ticket-subject').value,
        description: document.getElementById('ticket-description').value,
        priority: document.getElementById('ticket-priority').value,
        category: document.getElementById('ticket-category').value || 'general',
    };
    if (!data.customer_id || !data.subject || !data.description) {
        showToast('Please fill all required fields', 'error');
        return;
    }
    try {
        await api('/api/tickets/', { method: 'POST', body: JSON.stringify(data) });
        closeModal();
        showToast('Ticket created successfully');
        if (currentView === 'tickets') loadTickets();
        else if (currentView === 'dashboard') loadDashboard();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Edit Ticket Modal
async function showEditTicketModal(ticketId) {
    const ticket = await api(`/api/tickets/${ticketId}`);
    showModal('Edit Ticket #' + ticket.id, `
        <div class="form-group">
            <label class="form-label">Subject</label>
            <input type="text" class="form-input" id="edit-subject" value="${esc(ticket.subject)}">
        </div>
        <div class="form-group">
            <label class="form-label">Description</label>
            <textarea class="form-textarea" id="edit-description">${esc(ticket.description)}</textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div class="form-group">
                <label class="form-label">Status</label>
                <select class="form-select" id="edit-status">
                    ${['open','in_progress','resolved','closed'].map(s =>
                        `<option value="${s}" ${s === ticket.status ? 'selected' : ''}>${s.replace('_', ' ')}</option>`
                    ).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Priority</label>
                <select class="form-select" id="edit-priority">
                    ${['low','medium','high','urgent'].map(p =>
                        `<option value="${p}" ${p === ticket.priority ? 'selected' : ''}>${p}</option>`
                    ).join('')}
                </select>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Assigned To</label>
            <input type="text" class="form-input" id="edit-assigned" value="${esc(ticket.assigned_to || '')}">
        </div>
    `, `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="updateTicket(${ticketId})">Save Changes</button>
    `);
}

async function updateTicket(ticketId) {
    const data = {
        subject: document.getElementById('edit-subject').value,
        description: document.getElementById('edit-description').value,
        status: document.getElementById('edit-status').value,
        priority: document.getElementById('edit-priority').value,
        assigned_to: document.getElementById('edit-assigned').value || null,
    };
    try {
        await api(`/api/tickets/${ticketId}`, { method: 'PUT', body: JSON.stringify(data) });
        closeModal();
        showToast('Ticket updated');
        showTicketDetail(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteTicket(ticketId) {
    if (!confirm('Delete this ticket? This cannot be undone.')) return;
    try {
        await api(`/api/tickets/${ticketId}`, { method: 'DELETE' });
        showToast('Ticket deleted');
        loadTickets();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// AI Modal
function showAIModal(ticketId) {
    showModal('AI Reply Generator', `
        <div class="form-group">
            <label class="form-label">Tone</label>
            <select class="form-select" id="ai-tone">
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="empathetic">Empathetic</option>
                <option value="concise">Concise</option>
            </select>
        </div>
        <div id="ai-result"></div>
    `, `
        <button class="btn" onclick="closeModal()">Close</button>
        <button class="btn btn-primary" onclick="generateAIReply(${ticketId})">Generate Reply</button>
    `);
}

async function generateAIReply(ticketId) {
    const tone = document.getElementById('ai-tone').value;
    const resultDiv = document.getElementById('ai-result');
    resultDiv.innerHTML = '<div class="loading"></div>';
    try {
        const result = await api('/api/ai/reply', {
            method: 'POST',
            body: JSON.stringify({ ticket_id: ticketId, tone }),
        });
        resultDiv.innerHTML = `
            <div class="ai-reply-box">
                <div class="label">AI Generated Reply</div>
                <div class="ai-reply-content">${esc(result.reply)}</div>
                <p style="margin-top:8px;font-size:0.75rem;color:var(--text2)">
                    Sentiment: <span class="badge badge-${result.sentiment}">${result.sentiment}</span>
                    Confidence: ${(result.confidence * 100).toFixed(0)}%
                </p>
            </div>
        `;
    } catch (e) {
        resultDiv.innerHTML = `<p style="color:var(--danger)">Error: ${esc(e.message)}</p>`;
    }
}

// AI Agent Streaming Modal
function showAgentStreamingModal(ticketId) {
    showModal('AI Agent — Live', `
        <div id="agent-stream-container">
            <div id="agent-status" class="agent-status">
                <span class="typing-indicator">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </span>
                <span class="status-text">Connecting to AI agent...</span>
            </div>
            <div id="agent-tool-calls"></div>
            <div id="agent-reply-container" style="display:none">
                <div class="label">AI Agent Reply</div>
                <div id="agent-reply-content" class="agent-reply-content"></div>
                <div id="agent-reply-cursor" class="reply-cursor">|</div>
            </div>
            <div id="agent-done-actions" style="display:none;margin-top:16px;display:flex;gap:8px">
                <button class="btn btn-sm btn-primary" onclick="useAgentStreamingReply(${ticketId})">Use This Reply</button>
                <button class="btn btn-sm" onclick="closeModal()">Close</button>
            </div>
        </div>
    `, '');

    // Start streaming
    startAgentStream(ticketId);
}

async function startAgentStream(ticketId) {
    const statusEl = document.getElementById('agent-status');
    const toolCallsEl = document.getElementById('agent-tool-calls');
    const replyContainer = document.getElementById('agent-reply-content');
    const replyWrapper = document.getElementById('agent-reply-container');
    const doneActions = document.getElementById('agent-done-actions');
    const cursor = document.getElementById('agent-reply-cursor');

    let fullReply = '';
    let eventSource = null;

    try {
        const response = await fetch('/api/ai/agent/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket_id: ticketId }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Stream failed' }));
            throw new Error(err.detail || 'Stream request failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    const eventType = line.substring(7).trim();
                    // Read the next line for data
                    const dataLine = lines[lines.indexOf(line) + 1];
                    if (dataLine && dataLine.startsWith('data: ')) {
                        const dataStr = dataLine.substring(6);
                        try {
                            const data = JSON.parse(dataStr);
                            handleAgentEvent(eventType, data, {
                                statusEl,
                                toolCallsEl,
                                replyContainer,
                                replyWrapper,
                                doneActions,
                                cursor,
                                ticketId,
                                setFullReply: (val) => { fullReply = val; },
                                getFullReply: () => fullReply,
                            });
                        } catch (e) {
                            // Skip malformed JSON
                        }
                    }
                }
            }
        }
    } catch (e) {
        statusEl.innerHTML = `<span style="color:var(--danger)">Error: ${esc(e.message)}</span>`;
    }
}

function handleAgentEvent(eventType, data, ctx) {
    const { statusEl, toolCallsEl, replyContainer, replyWrapper, doneActions, cursor, ticketId, setFullReply, getFullReply } = ctx;

    switch (eventType) {
        case 'tool_call':
            // Show tool call with animation
            statusEl.innerHTML = '<span class="typing-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span><span class="status-text">Executing tool: ' + esc(data.tool_name) + '...</span>';
            const toolCallDiv = document.createElement('div');
            toolCallDiv.className = 'tool-call-item tool-call-active';
            toolCallDiv.innerHTML = `
                <div class="tool-call-header">
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">${esc(data.tool_name)}</span>
                    <span class="tool-status">Running...</span>
                </div>
                <div class="tool-args">${esc(JSON.stringify(data.tool_args, null, 2))}</div>
            `;
            toolCallsEl.appendChild(toolCallDiv);
            // Scroll to bottom
            toolCallsEl.scrollTop = toolCallsEl.scrollHeight;
            break;

        case 'tool_result':
            // Update the last tool call with result
            const lastToolCall = toolCallsEl.querySelector('.tool-call-active');
            if (lastToolCall) {
                lastToolCall.classList.remove('tool-call-active');
                lastToolCall.classList.add('tool-call-done');
                const statusSpan = lastToolCall.querySelector('.tool-status');
                if (statusSpan) statusSpan.textContent = 'Done ✓';
                const resultDiv = document.createElement('div');
                resultDiv.className = 'tool-result';
                resultDiv.innerHTML = '<div class="tool-result-label">Result:</div><pre>' + esc(JSON.stringify(data.result, null, 2)) + '</pre>';
                lastToolCall.appendChild(resultDiv);
            }
            statusEl.innerHTML = '<span class="typing-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span><span class="status-text">Processing tool result...</span>';
            break;

        case 'reply_chunk':
            // Show reply container on first chunk
            if (replyWrapper.style.display === 'none') {
                replyWrapper.style.display = 'block';
                statusEl.innerHTML = '<span class="typing-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span><span class="status-text">Generating reply...</span>';
            }
            // Append chunk with typing effect
            replyContainer.textContent += data.text;
            setFullReply(getFullReply() + data.text);
            // Blink cursor
            cursor.style.visibility = 'visible';
            clearTimeout(cursor._blinkTimer);
            cursor._blinkTimer = setTimeout(() => { cursor.style.visibility = 'hidden'; }, 500);
            break;

        case 'done':
            // Finalize
            statusEl.innerHTML = '<span style="color:var(--success)">✓ Agent completed</span>';
            cursor.style.display = 'none';
            doneActions.style.display = 'flex';
            break;

        case 'error':
            statusEl.innerHTML = '<span style="color:var(--danger)">⚠ ' + esc(data.error || 'Unknown error') + '</span>';
            break;
    }
}

async function useAgentStreamingReply(ticketId) {
    const replyContent = document.getElementById('agent-reply-content');
    const reply = replyContent ? replyContent.textContent : '';
    if (!reply.trim()) return;
    try {
        await api(`/api/tickets/${ticketId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ sender: 'agent', content: reply }),
        });
        showToast('Reply sent');
        closeModal();
        showTicketDetail(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function useAIReply(ticketId) {
    const ticket = await api(`/api/tickets/${ticketId}`);
    if (ticket.ai_reply) {
        await api(`/api/tickets/${ticketId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ sender: 'agent', content: ticket.ai_reply }),
        });
        showToast('Reply sent');
        showTicketDetail(ticketId);
    }
}

async function sendReply(ticketId) {
    const content = document.getElementById('reply-content').value;
    if (!content.trim()) return;
    try {
        await api(`/api/tickets/${ticketId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ sender: 'agent', content }),
        });
        showToast('Reply sent');
        showTicketDetail(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function uploadAttachment(ticketId) {
    const fileInput = document.getElementById('attachment-file');
    if (!fileInput.files || fileInput.files.length === 0) {
        showToast('Please select a file to upload', 'error');
        return;
    }
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`/api/tickets/${ticketId}/attachments`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Upload failed');
        }
        showToast('Attachment uploaded');
        showTicketDetail(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteAttachment(attachmentId, ticketId) {
    if (!confirm('Delete this attachment?')) return;
    try {
        await api(`/api/attachments/${attachmentId}`, { method: 'DELETE' });
        showToast('Attachment deleted');
        showTicketDetail(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Customer Modals
function showNewCustomerModal() {
    showModal('New Customer', `
        <div class="form-group">
            <label class="form-label">Name *</label>
            <input type="text" class="form-input" id="customer-name">
        </div>
        <div class="form-group">
            <label class="form-label">Email *</label>
            <input type="email" class="form-input" id="customer-email">
        </div>
        <div class="form-group">
            <label class="form-label">Phone</label>
            <input type="text" class="form-input" id="customer-phone">
        </div>
        <div class="form-group">
            <label class="form-label">Company</label>
            <input type="text" class="form-input" id="customer-company">
        </div>
    `, `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="createCustomer()">Create Customer</button>
    `);
}

async function createCustomer() {
    const data = {
        name: document.getElementById('customer-name').value,
        email: document.getElementById('customer-email').value,
        phone: document.getElementById('customer-phone').value || null,
        company: document.getElementById('customer-company').value || null,
    };
    if (!data.name || !data.email) {
        showToast('Name and email are required', 'error');
        return;
    }
    try {
        await api('/api/customers/', { method: 'POST', body: JSON.stringify(data) });
        closeModal();
        showToast('Customer created');
        loadCustomers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function showEditCustomerModal(customerId) {
    const c = await api(`/api/customers/${customerId}`);
    showModal('Edit Customer', `
        <div class="form-group">
            <label class="form-label">Name</label>
            <input type="text" class="form-input" id="edit-cust-name" value="${esc(c.name)}">
        </div>
        <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="edit-cust-email" value="${esc(c.email)}">
        </div>
        <div class="form-group">
            <label class="form-label">Phone</label>
            <input type="text" class="form-input" id="edit-cust-phone" value="${esc(c.phone || '')}">
        </div>
        <div class="form-group">
            <label class="form-label">Company</label>
            <input type="text" class="form-input" id="edit-cust-company" value="${esc(c.company || '')}">
        </div>
    `, `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="updateCustomer(${customerId})">Save</button>
    `);
}

async function updateCustomer(customerId) {
    const data = {
        name: document.getElementById('edit-cust-name').value,
        email: document.getElementById('edit-cust-email').value,
        phone: document.getElementById('edit-cust-phone').value || null,
        company: document.getElementById('edit-cust-company').value || null,
    };
    try {
        await api(`/api/customers/${customerId}`, { method: 'PUT', body: JSON.stringify(data) });
        closeModal();
        showToast('Customer updated');
        loadCustomers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteCustomer(customerId) {
    if (!confirm('Delete this customer?')) return;
    try {
        await api(`/api/customers/${customerId}`, { method: 'DELETE' });
        showToast('Customer deleted');
        loadCustomers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Utilities
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ─── Presence Indicator ──────────────────────────────────────────────────────
let presenceAgents = [];
let heartbeatInterval = null;

async function updatePresence() {
    try {
        const resp = await fetch('/api/presence/online');
        if (!resp.ok) return;
        const data = await resp.json();
        presenceAgents = data.agents || [];
        const indicator = document.getElementById('presence-indicator');
        const text = document.getElementById('presence-text');
        if (indicator && text) {
            const count = data.count || 0;
            text.textContent = `${count} agent${count !== 1 ? 's' : ''} online`;
            indicator.classList.toggle('has-online', count > 0);
        }
    } catch (e) { /* ignore */ }
}

async function sendHeartbeat() {
    try {
        const agentId = localStorage.getItem('agent_id') || 'anonymous';
        await fetch('/api/presence/heartbeat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent_id: agentId, status: 'online' }),
        });
    } catch (e) { /* ignore */ }
}

function startPresence() {
    sendHeartbeat();
    updatePresence();
    heartbeatInterval = setInterval(() => {
        sendHeartbeat();
        updatePresence();
    }, 30000);
}

function stopPresence() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

// ─── Drag-and-Drop Assignment ────────────────────────────────────────────────
let draggedTicketId = null;

function setupDragAndDrop() {
    document.querySelectorAll('[data-agent-name]').forEach(el => {
        el.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            el.classList.add('drag-over');
        });
        el.addEventListener('dragleave', () => {
            el.classList.remove('drag-over');
        });
        el.addEventListener('drop', async (e) => {
            e.preventDefault();
            el.classList.remove('drag-over');
            const agentName = el.dataset.agentName;
            if (draggedTicketId) {
                try {
                    await api(`/api/tickets/${draggedTicketId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ assigned_to: agentName }),
                    });
                    showToast(`Ticket #${draggedTicketId} assigned to ${agentName}`);
                    draggedTicketId = null;
                    loadTickets();
                } catch (err) {
                    showToast(err.message, 'error');
                }
            }
        });
    });

    document.querySelectorAll('[data-ticket-id]').forEach(el => {
        el.setAttribute('draggable', 'true');
        el.addEventListener('dragstart', (e) => {
            draggedTicketId = parseInt(el.dataset.ticketId);
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedTicketId);
        });
        el.addEventListener('dragend', () => {
            draggedTicketId = null;
        });
    });
}

// ─── Real-time Chat ──────────────────────────────────────────────────────────
let chatSocket = null;
let chatTicketId = null;

function connectChat(ticketId, role, identity) {
    if (chatSocket) {
        chatSocket.close();
        chatSocket = null;
    }
    chatTicketId = ticketId;
    const wsUrl = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/chat/${ticketId}?role=${encodeURIComponent(role)}&identity=${encodeURIComponent(identity)}`;
    chatSocket = new WebSocket(wsUrl);

    chatSocket.onopen = () => {
        console.log('Chat connected');
    };

    chatSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'message') {
                appendChatMessage(data);
            } else if (data.type === 'history') {
                renderChatHistory(data.messages);
            } else if (data.type === 'typing') {
                showTypingIndicator(data.identity);
            } else if (data.type === 'presence') {
                updateChatPresence(data.count);
            }
        } catch (e) { /* ignore */ }
    };

    chatSocket.onclose = () => {
        console.log('Chat disconnected');
        chatSocket = null;
    };

    chatSocket.onerror = (e) => {
        console.error('Chat error:', e);
    };
}

function appendChatMessage(msg) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const div = document.createElement('div');
    div.className = `message message-${msg.sender}${msg.is_ai_generated ? '-ai' : ''}`;
    div.innerHTML = `
        <div class="message-meta">${esc(msg.sender)}${msg.is_ai_generated ? ' (AI)' : ''} — ${formatDate(msg.created_at)}</div>
        ${esc(msg.content)}
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function renderChatHistory(messages) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    container.innerHTML = '';
    messages.forEach(m => {
        const div = document.createElement('div');
        div.className = `message message-${m.sender}${m.is_ai_generated ? '-ai' : ''}`;
        div.innerHTML = `
            <div class="message-meta">${esc(m.sender)}${m.is_ai_generated ? ' (AI)' : ''} — ${formatDate(m.created_at)}</div>
            ${esc(m.content)}
        `;
        container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    if (!input || !chatSocket || !input.value.trim()) return;
    chatSocket.send(JSON.stringify({
        type: 'message',
        sender: 'agent',
        content: input.value.trim(),
    }));
    input.value = '';
}

function showTypingIndicator(identity) {
    const indicator = document.getElementById('chat-typing');
    if (indicator) {
        indicator.textContent = `${identity} is typing...`;
        indicator.style.display = 'block';
        setTimeout(() => { indicator.style.display = 'none'; }, 3000);
    }
}

function updateChatPresence(count) {
    const el = document.getElementById('chat-presence');
    if (el) {
        el.textContent = `${count} online`;
    }
}

function disconnectChat() {
    if (chatSocket) {
        chatSocket.close();
        chatSocket = null;
    }
    chatTicketId = null;
}

// ─── AI Reply Collaborative Editing ──────────────────────────────────────────
let editingTicketId = null;
let originalAIReply = '';

function showAIReplyEditor(ticketId) {
    editingTicketId = ticketId;
    const ticket = tickets.find(t => t.id === ticketId);
    if (!ticket || !ticket.ai_reply) return;

    originalAIReply = ticket.ai_reply;
    const container = document.getElementById(`ai-reply-${ticketId}`);
    if (!container) return;

    container.innerHTML = `
        <div class="ai-editor">
            <div class="ai-editor-header">
                <span class="ai-editor-title">✏️ Edit AI Reply</span>
                <span class="ai-editor-hint">Edit before sending</span>
            </div>
            <textarea class="form-textarea ai-editor-textarea" id="ai-edit-textarea">${esc(ticket.ai_reply)}</textarea>
            <div class="ai-editor-actions">
                <button class="btn btn-sm btn-primary" onclick="saveAIReplyEdit(${ticketId})">Save & Send</button>
                <button class="btn btn-sm" onclick="cancelAIReplyEdit(${ticketId})">Cancel</button>
            </div>
        </div>
    `;
}

async function saveAIReplyEdit(ticketId) {
    const textarea = document.getElementById('ai-edit-textarea');
    if (!textarea) return;
    const editedContent = textarea.value.trim();
    if (!editedContent) return;

    try {
        // Update the AI reply on the ticket
        await api(`/api/tickets/${ticketId}`, {
            method: 'PUT',
            body: JSON.stringify({ ai_reply: editedContent }),
        });

        // Send as message
        await api(`/api/tickets/${ticketId}/messages`, {
            method: 'POST',
            body: JSON.stringify({
                sender: 'agent',
                content: editedContent,
                is_ai_generated: true,
            }),
        });

        showToast('AI reply edited and sent');
        editingTicketId = null;
        originalAIReply = '';
        showTicketDetail(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function cancelAIReplyEdit(ticketId) {
    editingTicketId = null;
    originalAIReply = '';
    showTicketDetail(ticketId);
}

// ─── Keyboard Shortcuts ─────────────────────────────────────────────────────
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Don't fire shortcuts when typing in inputs (except for specific ones)
        const tag = e.target.tagName.toLowerCase();
        const isInput = tag === 'input' || tag === 'textarea' || tag === 'select';

        // Escape - close modal (works everywhere)
        if (e.key === 'Escape') {
            closeModal();
            closeNotificationDropdown();
            return;
        }

        // Ctrl+Enter - send reply (when in textarea)
        if (e.ctrlKey && e.key === 'Enter' && isInput) {
            e.preventDefault();
            const replyBtn = document.querySelector('#reply-content');
            if (replyBtn) {
                const sendBtn = replyBtn.closest('.card-body')?.querySelector('.btn-primary');
                if (sendBtn) sendBtn.click();
            }
            // Also handle chat input
            const chatInput = document.getElementById('chat-input');
            if (chatInput && chatInput.tagName === 'INPUT') {
                sendChatMessage();
            }
            return;
        }

        // Ctrl+K or / - focus search
        if ((e.ctrlKey && e.key === 'k') || (!isInput && e.key === '/')) {
            e.preventDefault();
            const searchInput = document.getElementById('filter-search') || document.getElementById('kb-search');
            if (searchInput) searchInput.focus();
            return;
        }

        // Ctrl+N - new ticket
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            showNewTicketModal();
            return;
        }
    });
}

// ─── Theme Toggle ───────────────────────────────────────────────────────────
function setupThemeToggle() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    // Load saved theme or default to dark
    const savedTheme = localStorage.getItem('resolveai-theme') || 'dark';
    applyTheme(savedTheme);

    toggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        applyTheme(current);
        localStorage.setItem('resolveai-theme', current);
    });
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const toggle = document.getElementById('theme-toggle');
        if (toggle) toggle.textContent = '☀️';
    } else {
        document.documentElement.removeAttribute('data-theme');
        const toggle = document.getElementById('theme-toggle');
        if (toggle) toggle.textContent = '🌙';
    }
}

// ─── Notification Bell ──────────────────────────────────────────────────────
function setupNotificationBell() {
    const bellBtn = document.getElementById('bell-btn');
    const dropdown = document.getElementById('notification-dropdown');

    if (bellBtn && dropdown) {
        bellBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('active');
            if (dropdown.classList.contains('active')) {
                loadNotifications();
            }
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
                dropdown.classList.remove('active');
            }
        });
    }
}

function closeNotificationDropdown() {
    const dropdown = document.getElementById('notification-dropdown');
    if (dropdown) dropdown.classList.remove('active');
}

async function loadNotifications() {
    try {
        const notifications = await api('/api/notifications/');
        renderNotifications(notifications);
        updateBellBadge();
    } catch (e) {
        // Silently fail - notifications are non-critical
    }
}

function renderNotifications(notifications) {
    const list = document.getElementById('notification-list');
    if (!list) return;

    if (notifications.length === 0) {
        list.innerHTML = '<div class="notification-empty">No notifications yet</div>';
        return;
    }

    list.innerHTML = notifications.map(n => `
        <div class="notification-item ${n.read ? '' : 'unread'}" onclick="markNotificationRead(${n.id})" data-notification-id="${n.id}">
            <div class="notification-item-title">${esc(n.title)}</div>
            <div class="notification-item-body">${esc(n.body)}</div>
            <div class="notification-item-time">${formatDate(n.created_at)}</div>
        </div>
    `).join('');
}

async function updateBellBadge() {
    try {
        const { count } = await api('/api/notifications/unread-count');
        const badge = document.getElementById('bell-badge');
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (e) {
        // Silently fail
    }
}

async function markNotificationRead(id) {
    try {
        await api(`/api/notifications/${id}/read`, { method: 'POST' });
        loadNotifications();
    } catch (e) {
        // Silently fail
    }
}

async function markAllNotificationsRead() {
    try {
        await api('/api/notifications/mark-all-read', { method: 'POST' });
        loadNotifications();
    } catch (e) {
        // Silently fail
    }
}

// ─── Push Notifications (Service Worker) ────────────────────────────────────
function initNotifications() {
    const enableBtn = document.getElementById('enable-notifications-btn');
    if (!enableBtn) return;

    // Check if notifications are supported
    if (!('Notification' in window)) {
        enableBtn.style.display = 'none';
        return;
    }

    // Show enable button if permission not yet granted
    if (Notification.permission === 'default') {
        enableBtn.style.display = 'inline-flex';
    } else if (Notification.permission === 'granted') {
        enableBtn.style.display = 'none';
        registerServiceWorker();
    } else {
        // Denied
        enableBtn.style.display = 'none';
    }

    // Poll for new notifications every 30 seconds
    setInterval(updateBellBadge, 30000);
}

async function requestNotificationPermission() {
    const enableBtn = document.getElementById('enable-notifications-btn');
    try {
        const permission = await Notification.requestPermission();
        if (permission === 'granted') {
            enableBtn.style.display = 'none';
            await registerServiceWorker();
            showToast('Notifications enabled!');
        } else {
            showToast('Notification permission denied', 'error');
        }
    } catch (e) {
        showToast('Failed to enable notifications', 'error');
    }
}

async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    try {
        const registration = await navigator.serviceWorker.register('/public/sw.js');
        await subscribeToPush(registration);
    } catch (e) {
        console.error('SW registration failed:', e);
    }
}

async function subscribeToPush(registration) {
    try {
        // Check for existing subscription
        let subscription = await registration.pushManager.getSubscription();

        if (!subscription) {
            // Create new subscription
            // In production, you'd fetch the VAPID public key from the server
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(
                    'BEl62iV9i3RvJ5x2E8QJ1y4X7Z0a3c6d9f1g2h4j5k7l8m0n2o4p6q8r0s2t4'
                ),
            });
        }

        // Send subscription to server
        await api('/api/notifications/subscribe', {
            method: 'POST',
            body: JSON.stringify(subscription),
        });
    } catch (e) {
        console.error('Push subscription failed:', e);
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// ─── Hamburger Menu (Mobile) ────────────────────────────────────────────────
function setupHamburgerMenu() {
    const hamburger = document.getElementById('hamburger');
    const nav = document.getElementById('header-nav');

    if (hamburger && nav) {
        hamburger.addEventListener('click', () => {
            nav.classList.toggle('active');
            hamburger.classList.toggle('active');
            const expanded = nav.classList.contains('active');
            hamburger.setAttribute('aria-expanded', expanded);
        });

        // Close menu when clicking a nav button
        nav.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                nav.classList.remove('active');
                hamburger.classList.remove('active');
                hamburger.setAttribute('aria-expanded', 'false');
            });
        });
    }
}
