// ResolveAI Frontend Application
const API = '';

// State
let currentView = 'dashboard';
let tickets = [];
let customers = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    loadDashboard();
});

// Navigation
function setupNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentView = btn.dataset.view;
            render();
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
                    <div class="value">${stats.total_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Open</div>
                    <div class="value open">${stats.open_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">In Progress</div>
                    <div class="value in-progress">${stats.in_progress_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Resolved</div>
                    <div class="value resolved">${stats.resolved_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Closed</div>
                    <div class="value closed">${stats.closed_tickets}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Avg Resolution</div>
                    <div class="value">${stats.avg_resolution_hours ? stats.avg_resolution_hours + 'h' : 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="label">SLA Breached</div>
                    <div class="value sla-breached">${stats.sla_breached || 0}</div>
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
                                    <tr class="${t.sla_breached ? 'sla-breached-row' : ''}">
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
        `;
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

        main.innerHTML = `
            <button class="btn btn-sm" onclick="loadTickets()" style="margin-bottom:16px">← Back to Tickets</button>
            <div class="ticket-detail">
                <div>
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">#${ticket.id} — ${esc(ticket.subject)}</span>
                            <div>
                                <button class="btn btn-sm btn-primary" onclick="showAIModal(${ticket.id})">🤖 AI Reply</button>
                                <button class="btn btn-sm" onclick="showEditTicketModal(${ticket.id})">Edit</button>
                            </div>
                        </div>
                        <div class="card-body">
                            <p style="margin-bottom:16px">${esc(ticket.description)}</p>
                            ${ticket.ai_reply ? `
                                <div class="ai-reply-box">
                                    <div class="label">AI Suggested Reply</div>
                                    <div class="ai-reply-content">${esc(ticket.ai_reply)}</div>
                                    <div style="margin-top:12px;display:flex;gap:8px">
                                        <button class="btn btn-sm btn-primary" onclick="useAIReply(${ticket.id})">Use This Reply</button>
                                        <button class="btn btn-sm" onclick="showAIModal(${ticket.id})">Regenerate</button>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><span class="card-title">Conversation</span></div>
                        <div class="card-body">
                            ${messages.map(m => `
                                <div class="message message-${m.sender}${m.is_ai_generated ? '-ai' : ''}">
                                    <div class="message-meta">${m.sender}${m.is_ai_generated ? ' (AI)' : ''} — ${formatDate(m.created_at)}</div>
                                    ${esc(m.content)}
                                </div>
                            `).join('')}
                            <div style="margin-top:16px">
                                <div class="form-group">
                                    <textarea class="form-textarea" id="reply-content" placeholder="Type your reply..."></textarea>
                                </div>
                                <button class="btn btn-primary" onclick="sendReply(${ticket.id})">Send Reply</button>
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
