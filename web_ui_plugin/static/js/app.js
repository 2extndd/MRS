// MercariSearcher Web UI JavaScript

// Auto-refresh dashboard every 30 seconds
if (window.location.pathname === '/') {
    setInterval(() => {
        location.reload();
    }, 30000);
}

// Format timestamps
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
    toast.style.zIndex = '9999';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// API helper
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        showToast('API call failed: ' + error.message, 'danger');
        return null;
    }
}

console.log('MercariSearcher Web UI loaded');
