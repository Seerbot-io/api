let ws = null;
let noticesWs = null; // Separate WebSocket for notices
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
    } else if (type === 'info' && title === 'Notice Received' && body.title !== undefined) {
        bodyContent = formatNoticeMessage(body);
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

function formatNoticeMessage(data) {
    const iconHtml = data.icon ? 
        `<div class="notice-icon-container">
            <img src="${data.icon}" alt="Notice icon" class="notice-icon" onerror="this.style.display='none'">
        </div>` : '';
    
    const typeColors = {
        'info': '#2196F3',
        'account': '#FF9800',
        'signal': '#4CAF50'
    };
    const typeColor = typeColors[data.type] || '#666';
    
    const metaDataHtml = data.meta_data && Object.keys(data.meta_data).length > 0 ?
        `<div class="notice-meta">
            <strong>Metadata:</strong>
            <pre style="margin: 5px 0; padding: 8px; background: #f5f5f5; border-radius: 4px; font-size: 12px;">${JSON.stringify(data.meta_data, null, 2)}</pre>
        </div>` : '';
    
    return `
${iconHtml}
<div class="notice-content">
    <div class="notice-header-info">
        <span class="notice-type" style="background: ${typeColor}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase;">${data.type || 'info'}</span>
        <span class="notice-id" style="color: #666; font-size: 12px;">ID: ${data.id}</span>
    </div>
    <div class="notice-title" style="font-size: 16px; font-weight: bold; margin: 10px 0 5px 0; color: #333;">${data.title || 'No title'}</div>
    <div class="notice-message" style="margin: 5px 0; color: #555; line-height: 1.5;">${data.message || 'No message'}</div>
    ${metaDataHtml}
    <div class="notice-dates" style="margin-top: 10px; font-size: 11px; color: #999;">
        <div>Created: ${data.createdAt || data.created_at || 'N/A'}</div>
        <div>Updated: ${data.updatedAt || data.updated_at || 'N/A'}</div>
    </div>
</div>
    `.trim();
}

function formatTokenInfoMessage(data) {
    const logoHtml = data.logo_url ? 
        `<div class="token-logo-container">
            <img src="${data.logo_url}" alt="${data.symbol}" class="token-logo" onerror="this.style.display='none'">
        </div>` : '';
    
    // Helper to convert string to number safely
    const toNumber = (val) => {
        if (val === null || val === undefined || val === '') return 0;
        if (typeof val === 'number') return val;
        if (typeof val === 'string') {
            const parsed = parseFloat(val);
            return isNaN(parsed) ? 0 : parsed;
        }
        return 0;
    };
    
    const formatNumber = (num) => {
        if (num === null || num === undefined || num === '') return 'N/A';
        const n = toNumber(num);
        if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(2) + 'K';
        return n.toFixed(6);
    };
    
    const formatPrice = (price) => {
        if (price === null || price === undefined || price === '') return 'N/A';
        const p = toNumber(price);
        return p.toFixed(6);
    };
    
    const formatChange = (change) => {
        if (change === null || change === undefined || change === '') return 'N/A';
        const c = toNumber(change);
        const sign = c >= 0 ? '+' : '';
        return `${sign}$${c.toFixed(6)}`;
    };
    
    const changeValue = toNumber(data.change_24h);
    const changeColor = changeValue >= 0 ? '#4caf50' : '#f44336';
    
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
    const noticesForm = document.getElementById('noticesForm');
    const subscribeBtn = document.getElementById('subscribeBtn');
    const unsubscribeBtn = document.getElementById('unsubscribeBtn');
    
    if (channelType === 'ohlc') {
        barsForm.style.display = 'block';
        tokenForm.style.display = 'none';
        noticesForm.style.display = 'none';
        subscribeBtn.style.display = 'inline-block';
        unsubscribeBtn.style.display = 'inline-block';
    } else if (channelType === 'token_info') {
        barsForm.style.display = 'none';
        tokenForm.style.display = 'block';
        noticesForm.style.display = 'none';
        subscribeBtn.style.display = 'inline-block';
        unsubscribeBtn.style.display = 'inline-block';
    } else if (channelType === 'notices') {
        barsForm.style.display = 'none';
        tokenForm.style.display = 'none';
        noticesForm.style.display = 'block';
        subscribeBtn.style.display = 'none';
        unsubscribeBtn.style.display = 'none';
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
    const channelType = document.getElementById('channelType').value;
    
    // Handle notices WebSocket separately
    if (channelType === 'notices') {
        connectNotices();
        return;
    }
    
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
                            market_cap: tokenData.market_cap
                        });
                    } else {
                        addMessage('info', 'Update', data);
                    }
                } else {
                    addMessage('info', 'Message', data);
                }
            } catch (e) {
                console.error('Error processing message:', e, event.data);
                addMessage('error', 'Parse Error', `Failed to process message: ${e.message}\n\nRaw data: ${event.data}`);
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
    const channelType = document.getElementById('channelType').value;
    
    // Handle notices WebSocket separately
    if (channelType === 'notices') {
        disconnectNotices();
        return;
    }
    
    if (ws) {
        ws.close();
        ws = null;
    }
}

function connectNotices() {
    if (noticesWs && noticesWs.readyState === WebSocket.OPEN) {
        addMessage('error', 'Error', 'Already connected to notices!');
        return;
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const lastNoticeId = document.getElementById('lastNoticeId').value || '0';
    const url = `${protocol}//${host}/user/notices/ws?last_notice_id=${lastNoticeId}`;
    
    updateStatus('Connecting to notices...', 'connecting');
    addMessage('info', 'Connection', `Connecting to notices WebSocket: ${url}...`);
    
    try {
        noticesWs = new WebSocket(url);
        
        noticesWs.onopen = function() {
            updateStatus('Connected (Notices)', 'connected');
            addMessage('success', 'Connection', 'Notices WebSocket connected successfully!');
            document.getElementById('connectBtn').disabled = true;
            document.getElementById('disconnectBtn').disabled = false;
        };
        
        noticesWs.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'notice' && data.data) {
                    const notice = data.data;
                    addMessage('info', 'Notice Received', {
                        id: notice.id,
                        type: notice.type,
                        icon: notice.icon,
                        title: notice.title,
                        message: notice.message,
                        createdAt: notice.createdAt || notice.created_at,
                        updatedAt: notice.updatedAt || notice.updated_at,
                        meta_data: notice.meta_data
                    });
                } else {
                    addMessage('info', 'Message', data);
                }
            } catch (e) {
                console.error('Error processing notice message:', e, event.data);
                addMessage('error', 'Parse Error', `Failed to process message: ${e.message}\n\nRaw data: ${event.data}`);
            }
        };
        
        noticesWs.onerror = function(error) {
            addMessage('error', 'WebSocket Error', 'Notices connection error occurred');
            console.error('Notices WebSocket error:', error);
        };
        
        noticesWs.onclose = function(event) {
            updateStatus('Disconnected', 'disconnected');
            addMessage('info', 'Connection', `Notices WebSocket closed (code: ${event.code}, reason: ${event.reason || 'none'})`);
            document.getElementById('connectBtn').disabled = false;
            document.getElementById('disconnectBtn').disabled = true;
        };
        
    } catch (error) {
        updateStatus('Error', 'disconnected');
        addMessage('error', 'Connection Error', error.message);
    }
}

function disconnectNotices() {
    if (noticesWs) {
        noticesWs.close();
        noticesWs = null;
    }
}

function subscribe() {
    const channelType = document.getElementById('channelType').value;
    
    if (channelType === 'notices') {
        addMessage('info', 'Info', 'Notices WebSocket automatically receives all notices. No subscription needed.');
        return;
    }
    
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
    const channelType = document.getElementById('channelType').value;
    
    if (channelType === 'notices') {
        addMessage('info', 'Info', 'Notices WebSocket automatically receives all notices. Disconnect to stop receiving.');
        return;
    }
    
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