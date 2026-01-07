/**
 * iTerm MCP Dashboard - Real-time SSE Client
 */

class ItermDashboard {
    constructor() {
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.events = [];
        this.maxEvents = 100;

        // DOM elements
        this.agentGrid = document.getElementById('agentGrid');
        this.noAgents = document.getElementById('noAgents');
        this.teamsList = document.getElementById('teamsList');
        this.noTeams = document.getElementById('noTeams');
        this.eventStream = document.getElementById('eventStream');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.agentCount = document.getElementById('agentCount');
        this.paneCount = document.getElementById('paneCount');
        this.teamCount = document.getElementById('teamCount');
        this.lastUpdate = document.getElementById('lastUpdate');
        this.clearEventsBtn = document.getElementById('clearEvents');

        // Templates
        this.agentCardTemplate = document.getElementById('agentCardTemplate');
        this.teamItemTemplate = document.getElementById('teamItemTemplate');
        this.eventItemTemplate = document.getElementById('eventItemTemplate');

        this.init();
    }

    init() {
        this.connect();
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.clearEventsBtn.addEventListener('click', () => this.clearEvents());
    }

    connect() {
        this.updateConnectionStatus('reconnecting', 'Connecting...');

        // Close existing connection if any
        if (this.eventSource) {
            this.eventSource.close();
        }

        try {
            this.eventSource = new EventSource('/events');

            this.eventSource.onopen = () => {
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected', 'Connected');
                this.addEvent('info', 'dashboard', 'Connected to server');
            };

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.updateDashboard(data);
                } catch (e) {
                    console.error('Failed to parse SSE data:', e);
                }
            };

            this.eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);
                this.eventSource.close();
                this.handleDisconnect();
            };

        } catch (e) {
            console.error('Failed to create EventSource:', e);
            this.handleDisconnect();
        }
    }

    handleDisconnect() {
        this.updateConnectionStatus('disconnected', 'Disconnected');

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(this.reconnectDelay * this.reconnectAttempts, 10000);
            this.updateConnectionStatus('reconnecting', `Reconnecting in ${delay/1000}s...`);

            setTimeout(() => this.connect(), delay);
        } else {
            this.updateConnectionStatus('disconnected', 'Connection failed');
            this.addEvent('error', 'dashboard', 'Max reconnection attempts reached');
        }
    }

    updateConnectionStatus(state, text) {
        const dot = this.connectionStatus.querySelector('.status-dot');
        const statusText = this.connectionStatus.querySelector('.status-text');

        dot.className = 'status-dot ' + state;
        statusText.textContent = text;
    }

    updateDashboard(data) {
        this.updateAgents(data.agents || []);
        this.updateTeams(data.teams || []);
        this.updateStats(data);
        this.updateNotifications(data.notifications || []);
        this.updateLastUpdate();
    }

    updateAgents(agents) {
        // Clear existing agents (except template)
        const existingCards = this.agentGrid.querySelectorAll('.agent-card');
        existingCards.forEach(card => card.remove());

        if (agents.length === 0) {
            this.noAgents.style.display = 'block';
            return;
        }

        this.noAgents.style.display = 'none';

        agents.forEach(agent => {
            const card = this.createAgentCard(agent);
            this.agentGrid.appendChild(card);
        });
    }

    createAgentCard(agent) {
        const template = this.agentCardTemplate.content.cloneNode(true);
        const card = template.querySelector('.agent-card');

        // Set agent data
        card.dataset.agentName = agent.name;
        card.querySelector('.agent-name').textContent = agent.name;
        card.querySelector('.agent-status-icon').textContent = this.getStatusIcon(agent.status || 'idle');
        card.querySelector('.session-id').textContent = agent.session_id ?
            agent.session_id.substring(0, 8) + '...' : 'N/A';
        card.querySelector('.role-name').textContent = agent.role || 'general';
        card.querySelector('.team-names').textContent = (agent.teams || []).join(', ') || 'none';

        // Setup action buttons with API calls (no iterm2:// URL needed)
        const focusBtn = card.querySelector('.focus-btn');
        const sendBtn = card.querySelector('.send-btn');

        focusBtn.href = '#';
        focusBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.focusAgent(agent.name);
        });

        sendBtn.href = '#';
        sendBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.promptSendCommand(agent.name);
        });

        return card;
    }

    getStatusIcon(status) {
        const icons = {
            'idle': '\u2713',      // checkmark
            'active': '\u26A1',    // lightning
            'busy': '\u23F3',      // hourglass
            'error': '\u2717',     // x
            'blocked': '\u23F8'    // pause
        };
        return icons[status] || '\u2022';  // bullet
    }

    buildItermUrl(command, ...args) {
        const encodedArgs = args.map(arg => encodeURIComponent(arg)).join('%20');
        const fullCommand = encodeURIComponent(`${command} ${args.join(' ')}`);
        return `iterm2:///command?c=${fullCommand}`;
    }

    async focusAgent(agentName) {
        try {
            const response = await fetch(`/api/focus?agent=${encodeURIComponent(agentName)}`);
            const result = await response.json();
            if (result.success) {
                this.addEvent('success', agentName, 'Focused');
            } else {
                this.addEvent('error', agentName, result.error || 'Focus failed');
            }
        } catch (e) {
            console.error('Focus request failed:', e);
            this.addEvent('error', agentName, 'Focus request failed');
        }
    }

    async promptSendCommand(agentName) {
        const command = prompt(`Send command to ${agentName}:`);
        if (command) {
            try {
                const response = await fetch(`/api/send?agent=${encodeURIComponent(agentName)}&command=${encodeURIComponent(command)}`);
                const result = await response.json();
                if (result.success) {
                    this.addEvent('success', agentName, `Sent: ${command}`);
                } else {
                    this.addEvent('error', agentName, result.error || 'Send failed');
                }
            } catch (e) {
                console.error('Send request failed:', e);
                this.addEvent('error', agentName, 'Send request failed');
            }
        }
    }

    updateTeams(teams) {
        // Clear existing teams
        const existingItems = this.teamsList.querySelectorAll('.team-item');
        existingItems.forEach(item => item.remove());

        if (teams.length === 0) {
            this.noTeams.style.display = 'block';
            return;
        }

        this.noTeams.style.display = 'none';

        teams.forEach(team => {
            const item = this.createTeamItem(team);
            this.teamsList.appendChild(item);
        });
    }

    createTeamItem(team) {
        const template = this.teamItemTemplate.content.cloneNode(true);
        const item = template.querySelector('.team-item');

        item.dataset.teamName = team.name;
        item.querySelector('.team-name').textContent = team.name;
        item.querySelector('.member-count').textContent = (team.members || []).length;

        return item;
    }

    updateStats(data) {
        this.agentCount.textContent = data.agents_online || 0;
        this.paneCount.textContent = data.pane_count || 0;
        this.teamCount.textContent = (data.teams || []).length;
    }

    updateNotifications(notifications) {
        // Add new notifications to event stream
        notifications.forEach(notification => {
            if (!this.events.find(e => e.id === notification.id)) {
                this.addEvent(
                    notification.level || 'info',
                    notification.agent || 'system',
                    notification.summary || notification.message,
                    notification.id
                );
            }
        });
    }

    addEvent(level, agent, message, id = null) {
        const event = {
            id: id || Date.now().toString(),
            time: new Date(),
            level,
            agent,
            message
        };

        this.events.unshift(event);

        // Trim old events
        if (this.events.length > this.maxEvents) {
            this.events = this.events.slice(0, this.maxEvents);
        }

        this.renderEvents();
    }

    renderEvents() {
        this.eventStream.innerHTML = '';

        this.events.forEach(event => {
            const item = this.createEventItem(event);
            this.eventStream.appendChild(item);
        });
    }

    createEventItem(event) {
        const template = this.eventItemTemplate.content.cloneNode(true);
        const item = template.querySelector('.event-item');

        item.querySelector('.event-time').textContent = this.formatTime(event.time);

        const levelEl = item.querySelector('.event-level');
        levelEl.textContent = this.getLevelIcon(event.level);
        levelEl.className = 'event-level ' + event.level;

        item.querySelector('.event-agent').textContent = event.agent;
        item.querySelector('.event-message').textContent = event.message;

        return item;
    }

    getLevelIcon(level) {
        const icons = {
            'info': '\u2139',      // info
            'warning': '\u26A0',   // warning
            'error': '\u2717',     // x
            'success': '\u2713',   // check
            'blocked': '\u23F8'    // pause
        };
        return icons[level] || '\u2022';
    }

    formatTime(date) {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    updateLastUpdate() {
        this.lastUpdate.textContent = this.formatTime(new Date());
    }

    clearEvents() {
        this.events = [];
        this.renderEvents();
        this.addEvent('info', 'dashboard', 'Event log cleared');
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new ItermDashboard();
});
