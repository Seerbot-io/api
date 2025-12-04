let ws = null;
let subscriptions = new Map(); // Map<channel, {type, params}>

// Auto-detect WebSocket URL based on current page location
function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws`;
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
    const timeEl = document.getElementById('currentTime');
    if (timeEl) {
        timeEl.textContent = new Date().toLocaleTimeString();
    }
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
    
    // Special formatting for token_info messages
    let bodyContent = '';
    if (type === 'info' && title === 'Token Info Update' && body.logo_url !== undefined) {
        bodyContent = formatTokenInfoMessage(body);
    } else {
        bodyContent = typeof body === 'string' ? body : JSON.stringify(body, null, 2);
    }
    
    messageDiv.innerHTML = `
        <div class="message-header">
            <span>${title}</span>
            <span class="message-time">${time}</span>
        </div>
        <div class="message-body">${bodyContent}</div>
    `;
    
    messagesDiv.insertBefore(messageDiv, messagesDiv.firstChild);
    
    // Keep only last 50 messages
    while (messagesDiv.children.length > 50) {
        messagesDiv.removeChild(messagesDiv.lastChild);
    }
}

function formatTokenInfoMessage(data) {
    const logoHtml = data.logo_url ? 
        `<div class="token-logo-container">
            <img src="${data.logo_url}" alt="${data.symbol}" class="token-logo" onerror="this.style.display='none'">
        </div>` : '';
    
    const formatNumber = (num) => {
        if (num === null || num === undefined) return 'N/A';
        if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
        if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
        if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
        return num.toFixed(6);
    };
    
    const formatPrice = (price) => {
        if (price === null || price === undefined) return 'N/A';
        return price.toFixed(6);
    };
    
    const formatPercentage = (pct) => {
        if (pct === null || pct === undefined) return 'N/A';
        const sign = pct >= 0 ? '+' : '';
        return `${sign}${pct.toFixed(2)}%`;
    };
    
    const formatChange = (change) => {
        if (change === null || change === undefined) return 'N/A';
        const sign = change >= 0 ? '+' : '';
        return `${sign}$${change.toFixed(6)}`;
    };
    
    const changeColor = data.change_24h >= 0 ? '#4caf50' : '#f44336';
    
    return `
${logoHtml}
<div class="token-info-grid">
    <div class="token-info-item">
        <span class="token-info-label">Symbol:</span>
        <span class="token-info-value">${data.symbol || 'N/A'}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">Name:</span>
        <span class="token-info-value">${data.name || 'N/A'}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">Price:</span>
        <span class="token-info-value">$${formatPrice(data.price)}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">24h Change:</span>
        <span class="token-info-value" style="color: ${changeColor}">${formatChange(data.change_24h)}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">Market Cap:</span>
        <span class="token-info-value">$${formatNumber(data.market_cap)}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">24h %:</span>
        <span class="token-info-value" style="color: ${changeColor}">${formatPercentage(data.price_change_percentage_24h)}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">7d %:</span>
        <span class="token-info-value" style="color: ${data.price_change_percentage_7d >= 0 ? '#4caf50' : '#f44336'}">${formatPercentage(data.price_change_percentage_7d)}</span>
    </div>
    <div class="token-info-item">
        <span class="token-info-label">30d %:</span>
        <span class="token-info-value" style="color: ${data.price_change_percentage_30d >= 0 ? '#4caf50' : '#f44336'}">${formatPercentage(data.price_change_percentage_30d)}</span>
    </div>
</div>
<div class="token-info-raw">
    <details>
        <summary>Raw JSON</summary>
        <pre>${JSON.stringify(data, null, 2)}</pre>
    </details>
</div>
    `.trim();
}

function updateSubscriptionsList() {
    const listDiv = document.getElementById('subscriptionsList');
    if (subscriptions.size === 0) {
        listDiv.innerHTML = '<div style="color: #666; font-style: italic;">No active subscriptions</div>';
    } else {
        listDiv.innerHTML = Array.from(subscriptions.entries()).map(([channel, info]) => `
            <div class="subscription-item">
                <div class="subscription-info">
                    <span class="subscription-id">${channel}</span>
                    <small style="display: block; color: #666; font-size: 12px; margin-top: 5px;">Type: ${info.type}</small>
                </div>
                <button class="clear-btn" onclick="unsubscribeChannel('${channel}')" style="margin-left: 10px;">Unsubscribe</button>
            </div>
        `).join('');
    }
}

function updateChannelForm() {
    const channelType = document.getElementById('channelType').value;
    const barsForm = document.getElementById('barsForm');
    const tokenForm = document.getElementById('tokenForm');
    
    if (channelType === 'ohlc') {
        barsForm.style.display = 'block';
        tokenForm.style.display = 'none';
    } else if (channelType === 'token_info') {
        barsForm.style.display = 'none';
        tokenForm.style.display = 'block';
    }
}

function buildChannel() {
    const channelType = document.getElementById('channelType').value;
    
    if (channelType === 'ohlc') {
        const symbol = document.getElementById('barsSymbol').value.trim();
        const resolution = document.getElementById('resolution').value;
        
        if (!symbol || !resolution) {
            return null;
        }
        
        // Convert slashes to underscores for channel format
        const channelSymbol = symbol.replace(/\//g, '_');
        return `ohlc:${channelSymbol}|${resolution}`;
    } else if (channelType === 'token_info') {
        const symbol = document.getElementById('tokenSymbol').value.trim();
        
        if (!symbol) {
            return null;
        }
        
        return `token_info:${symbol}`;
    }
    
    return null;
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
                    const channel = data.channel;
                    const channelType = data.type || data.channel.split(':')[0];
                    subscriptions.set(channel, { type: channelType });
                    updateSubscriptionsList();
                    addMessage('success', 'Subscription', data);
                } else if (data.status === 'unsubscribed') {
                    subscriptions.delete(data.channel);
                    updateSubscriptionsList();
                    addMessage('info', 'Unsubscription', data);
                } else if (data.status === 'already_subscribed') {
                    addMessage('info', 'Subscription', data);
                } else if (data.error) {
                    addMessage('error', 'Error', data);
                } else if (data.channel && data.type && data.data) {
                    // This is a channel update
                    if (data.type === 'ohlc') {
                        const barData = data.data;
                        addMessage('info', 'Bar Update', {
                            channel: data.channel,
                            symbol: barData.symbol,
                            timestamp: new Date(barData.timestamp * 1000).toLocaleString(),
                            open: barData.open,
                            high: barData.high,
                            low: barData.low,
                            close: barData.close,
                            volume: barData.volume
                        });
                    } else if (data.type === 'token_info') {
                        const tokenData = data.data;
                        addMessage('info', 'Token Info Update', {
                            channel: data.channel,
                            symbol: tokenData.symbol,
                            name: tokenData.name,
                            logo_url: tokenData.logo_url,
                            price: tokenData.price,
                            change_24h: tokenData.change_24h,
                            market_cap: tokenData.market_cap,
                            price_change_percentage_24h: tokenData.price_change_percentage_24h,
                            price_change_percentage_7d: tokenData.price_change_percentage_7d,
                            price_change_percentage_30d: tokenData.price_change_percentage_30d
                        });
                    } else {
                        addMessage('info', 'Update', data);
                    }
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
    
    const channel = buildChannel();
    
    if (!channel) {
        addMessage('error', 'Error', 'Please fill in all required fields');
        return;
    }
    
    const message = {
        action: 'subscribe',
        channel: channel
    };
    
    ws.send(JSON.stringify(message));
    addMessage('info', 'Sent', `Subscribe: ${JSON.stringify(message, null, 2)}`);
}

function unsubscribe() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        addMessage('error', 'Error', 'Not connected!');
        return;
    }
    
    const channel = buildChannel();
    
    if (!channel) {
        addMessage('error', 'Error', 'Please fill in all required fields');
        return;
    }
    
    unsubscribeChannel(channel);
}

function unsubscribeChannel(channel) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        addMessage('error', 'Error', 'Not connected!');
        return;
    }
    
    const message = {
        action: 'unsubscribe',
        channel: channel
    };
    
    ws.send(JSON.stringify(message));
    addMessage('info', 'Sent', `Unsubscribe: ${JSON.stringify(message, null, 2)}`);
}

// Allow Enter key to trigger actions
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('wsUrl').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') connect();
    });
    
    const barsSymbolEl = document.getElementById('barsSymbol');
    if (barsSymbolEl) {
        barsSymbolEl.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') subscribe();
        });
    }
    
    const tokenSymbolEl = document.getElementById('tokenSymbol');
    if (tokenSymbolEl) {
        tokenSymbolEl.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') subscribe();
        });
    }
    
    const resolutionEl = document.getElementById('resolution');
    if (resolutionEl) {
        resolutionEl.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') subscribe();
        });
    }
    
    // Initialize form display
    updateChannelForm();
});