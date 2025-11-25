let ws = null;
let subscriptions = new Set();

// Auto-detect WebSocket URL based on current page location
function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/charting/streaming`;
}

// Set default WebSocket URL
(function() {
    const wsUrlInput = document.getElementById('wsUrl');
    if (wsUrlInput && !wsUrlInput.value) {
        wsUrlInput.value = getWebSocketUrl();
    }
})();

// Update current time
function updateTime() {
    document.getElementById('currentTime').textContent = new Date().toLocaleTimeString();
}
setInterval(updateTime, 1000);
updateTime();

function updateStatus(status, className) {
    const statusEl = document.getElementById('status');
    statusEl.textContent = status;
    statusEl.className = `status ${className}`;
}

function addMessage(type, title, body) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const time = new Date().toLocaleTimeString();
    messageDiv.innerHTML = `
        <div class="message-header">
            <span>${title}</span>
            <span class="message-time">${time}</span>
        </div>
        <div class="message-body">${typeof body === 'string' ? body : JSON.stringify(body, null, 2)}</div>
    `;
    
    messagesDiv.insertBefore(messageDiv, messagesDiv.firstChild);
    
    // Keep only last 50 messages
    while (messagesDiv.children.length > 50) {
        messagesDiv.removeChild(messagesDiv.lastChild);
    }
}

function updateSubscriptionsList() {
    const listDiv = document.getElementById('subscriptionsList');
    if (subscriptions.size === 0) {
        listDiv.innerHTML = '<div style="color: #666; font-style: italic;">No active subscriptions</div>';
    } else {
        listDiv.innerHTML = Array.from(subscriptions).map(id => `
            <div class="subscription-item">
                <div class="subscription-info">
                    <span class="subscription-id">${id}</span>
                </div>
            </div>
        `).join('');
    }
}

function connect() {
    const url = document.getElementById('wsUrl').value;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        addMessage('error', 'Error', 'Already connected!');
        return;
    }
    
    updateStatus('Connecting...', 'connecting');
    addMessage('info', 'Connection', `Connecting to ${url}...`);
    
    try {
        ws = new WebSocket(url);
        
        ws.onopen = function() {
            updateStatus('Connected', 'connected');
            addMessage('success', 'Connection', 'WebSocket connected successfully!');
            document.getElementById('connectBtn').disabled = true;
            document.getElementById('disconnectBtn').disabled = false;
            document.getElementById('subscribeBtn').disabled = false;
            document.getElementById('unsubscribeBtn').disabled = false;
        };
        
        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                // Handle subscription status
                if (data.status === 'subscribed') {
                    subscriptions.add(data.subscriber_id);
                    updateSubscriptionsList();
                    addMessage('success', 'Subscription', data);
                } else if (data.status === 'unsubscribed') {
                    subscriptions.delete(data.subscriber_id);
                    updateSubscriptionsList();
                    addMessage('info', 'Unsubscription', data);
                } else if (data.error) {
                    addMessage('error', 'Error', data);
                } else if (data.symbol && data.timestamp) {
                    // This is a bar update
                    addMessage('info', 'Bar Update', {
                        subscriber_id: data.subscriber_id,
                        symbol: data.symbol,
                        timestamp: new Date(data.timestamp * 1000).toLocaleString(),
                        open: data.open,
                        high: data.high,
                        low: data.low,
                        close: data.close,
                        volume: data.volume
                    });
                } else {
                    addMessage('info', 'Message', data);
                }
            } catch (e) {
                addMessage('error', 'Parse Error', `Failed to parse message: ${event.data}`);
            }
        };
        
        ws.onerror = function(error) {
            addMessage('error', 'WebSocket Error', 'Connection error occurred');
            console.error('WebSocket error:', error);
        };
        
        ws.onclose = function(event) {
            updateStatus('Disconnected', 'disconnected');
            addMessage('info', 'Connection', `WebSocket closed (code: ${event.code}, reason: ${event.reason || 'none'})`);
            document.getElementById('connectBtn').disabled = false;
            document.getElementById('disconnectBtn').disabled = true;
            document.getElementById('subscribeBtn').disabled = true;
            document.getElementById('unsubscribeBtn').disabled = true;
            subscriptions.clear();
            updateSubscriptionsList();
        };
        
    } catch (error) {
        updateStatus('Error', 'disconnected');
        addMessage('error', 'Connection Error', error.message);
    }
}

function disconnect() {
    if (ws) {
        ws.close();
        ws = null;
    }
}

function subscribe() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        addMessage('error', 'Error', 'Not connected!');
        return;
    }
    
    const symbol = document.getElementById('symbol').value;
    const resolution = document.getElementById('resolution').value;
    
    if (!symbol || !resolution) {
        addMessage('error', 'Error', 'Please fill in symbol and resolution');
        return;
    }
    
    const message = {
        action: 'subscribe',
        symbol: symbol,
        resolution: resolution
    };
    
    ws.send(JSON.stringify(message));
    addMessage('info', 'Sent', `Subscribe: ${JSON.stringify(message, null, 2)}`);
}

function unsubscribe() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        addMessage('error', 'Error', 'Not connected!');
        return;
    }
    
    const symbol = document.getElementById('symbol').value;
    const resolution = document.getElementById('resolution').value;
    
    if (!symbol || !resolution) {
        addMessage('error', 'Error', 'Please fill in symbol and resolution');
        return;
    }
    
    const message = {
        action: 'unsubscribe',
        symbol: symbol,
        resolution: resolution
    };
    
    ws.send(JSON.stringify(message));
    addMessage('info', 'Sent', `Unsubscribe: ${JSON.stringify(message, null, 2)}`);
}

// Allow Enter key to trigger actions
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('wsUrl').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') connect();
    });
    
    document.getElementById('symbol').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') subscribe();
    });
    
    document.getElementById('resolution').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') subscribe();
    });
});

