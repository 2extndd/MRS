/* MercariSearcher - Advanced Web UI with Auto-Refresh (from KS1) */

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    console.log('✅ MercariSearcher Web UI loaded successfully');
});

function initializeApp() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize sidebar toggle for mobile
    initializeSidebar();

    // Initialize search functionality
    initializeSearch();

    // Initialize form validation
    initializeFormValidation();

    // Initialize auto-refresh for dashboard (KEY FEATURE!)
    initializeAutoRefresh();
}

function initializeSidebar() {
    const sidebarToggle = document.querySelector('[data-bs-target="#sidebar"]');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });

        document.addEventListener('click', function(event) {
            if (window.innerWidth <= 768) {
                if (!sidebar.contains(event.target) && !sidebarToggle.contains(event.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }
}

function initializeSearch() {
    const testSearchBtn = document.getElementById('test-search-btn');
    if (testSearchBtn) {
        testSearchBtn.addEventListener('click', testSearchUrl);
    }

    const runSearchBtn = document.getElementById('run-search-btn');
    if (runSearchBtn) {
        runSearchBtn.addEventListener('click', runSearch);
    }
}

function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

// ===== AUTO-REFRESH FUNCTIONALITY (Main feature from KS1!) =====
function initializeAutoRefresh() {
    // Only auto-refresh dashboard page
    if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
        console.log('🔄 Auto-refresh enabled for dashboard');

        // Refresh stats every 10 seconds
        setInterval(function() {
            refreshDashboardStats();
        }, 10000); // 10 seconds

        // Refresh recent items every 30 seconds
        setInterval(function() {
            refreshRecentItems();
        }, 30000); // 30 seconds
    }
}

function refreshDashboardStats() {
    // Don't refresh if user is typing or focusing on input
    if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
        return;
    }

    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update stat cards
                updateStatCard('total-items', data.database.total_items || 0);
                updateStatCard('active-queries', data.database.active_searches || 0);
                updateStatCard('api-requests', data.total_api_requests || 0);

                // Update uptime
                const uptimeEl = document.querySelector('.uptime-display');
                if (uptimeEl && data.uptime_formatted) {
                    uptimeEl.textContent = data.uptime_formatted;
                }

                console.log('✅ Dashboard stats refreshed', data.timestamp);
            }
        })
        .catch(error => {
            console.error('❌ Error refreshing stats:', error);
        });
}

function refreshRecentItems() {
    // Don't refresh if user is typing
    if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
        return;
    }

    fetch('/api/recent-items')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.items) {
                updateRecentItemsDisplay(data.items);
                console.log(`✅ Recent items refreshed: ${data.items.length} items`);
            }
        })
        .catch(error => {
            console.error('❌ Error refreshing recent items:', error);
        });
}

function updateStatCard(id, value) {
    const card = document.getElementById(id);
    if (card) {
        // Add smooth fade effect
        card.style.opacity = '0.6';
        setTimeout(() => {
            card.textContent = value.toLocaleString();
            card.style.opacity = '1';
        }, 150);
    }
}

function updateRecentItemsDisplay(items) {
    const container = document.getElementById('recent-items-container');
    if (!container) return;

    // Clear and rebuild (smooth transition)
    container.innerHTML = '';

    items.slice(0, 30).forEach(item => {
        const card = createItemCard(item);
        container.appendChild(card);
    });
}

function createItemCard(item) {
    const col = document.createElement('div');
    col.className = 'col-6 col-md-3 col-lg-2 mb-3 fade-in';

    const imageUrl = item.image_url || 'https://via.placeholder.com/300x300/cccccc/666666?text=No+Image';
    const price = item.price ? `¥${item.price.toLocaleString()}` : 'Price N/A';
    const title = (item.title || 'No title').substring(0, 40) + (item.title && item.title.length > 40 ? '...' : '');

    col.innerHTML = `
        <div class="card item-card h-100">
            <img src="${escapeHtml(imageUrl)}" class="card-img-top" alt="${escapeHtml(title)}" style="aspect-ratio: 4/5; object-fit: cover;">
            <div class="card-body p-2">
                <p class="card-text small mb-1" style="font-size: 0.75rem;">${escapeHtml(title)}</p>
                <p class="card-text text-primary fw-bold mb-1" style="font-size: 0.85rem;">${escapeHtml(price)}</p>
                ${item.search_name ? `<span class="badge bg-secondary" style="font-size: 0.65rem;">${escapeHtml(item.search_name)}</span>` : ''}
            </div>
        </div>
    `;

    return col;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== API Functions =====
function testSearchUrl() {
    const urlInput = document.getElementById('search-url');
    const testBtn = document.getElementById('test-search-btn');

    if (!urlInput || !urlInput.value) {
        showAlert('Please enter a search URL', 'warning');
        return;
    }

    const originalText = testBtn.innerHTML;
    testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
    testBtn.disabled = true;

    fetch('/api/search/test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: urlInput.value })
    })
    .then(response => response.json())
    .then(data => {
        if (data.valid) {
            showAlert('✅ URL is valid! ' + (data.test_results ?
                `Found ${data.test_results.items_found} items.` : ''), 'success');

            if (data.test_results && data.test_results.sample_titles) {
                const titles = data.test_results.sample_titles.join(', ');
                showAlert(`Sample items: ${titles}`, 'info');
            }
        } else {
            showAlert('❌ URL validation failed: ' + (data.error || 'Unknown error'), 'danger');
        }

        if (data.test_error) {
            showAlert('⚠️ Test search failed: ' + data.test_error, 'warning');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('❌ Error testing URL: ' + error.message, 'danger');
    })
    .finally(() => {
        testBtn.innerHTML = originalText;
        testBtn.disabled = false;
    });
}

function runSearch() {
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running...';
    btn.disabled = true;

    fetch('/api/force-scan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success || data.new_items !== undefined) {
            showAlert(`✅ Search completed! Found ${data.new_items || 0} new items.`, 'success');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showAlert('❌ Search failed: ' + (data.error || 'Unknown error'), 'danger');
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('❌ Error running search: ' + error.message, 'danger');
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

function sendTestNotification() {
    fetch('/api/notifications/test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('✅ Test notification sent successfully!', 'success');
        } else {
            showAlert('❌ Failed to send test notification: ' + (data.error || 'Unknown error'), 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('❌ Error sending test notification: ' + error.message, 'danger');
    });
}

function deleteQuery(queryId) {
    if (confirm('⚠️ Are you sure you want to delete this query?')) {
        fetch(`/api/queries/${queryId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('✅ Query deleted successfully!', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showAlert('❌ Failed to delete query: ' + (data.error || 'Unknown error'), 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('❌ Error deleting query: ' + error.message, 'danger');
        });
    }
}

function toggleQuery(queryId) {
    fetch(`/api/queries/${queryId}/toggle`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('✅ Query toggled successfully!', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showAlert('❌ Failed to toggle query: ' + (data.error || 'Unknown error'), 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('❌ Error toggling query: ' + error.message, 'danger');
    });
}

// ===== Utility Functions =====
function showAlert(message, type = 'info') {
    // Remove existing auto-dismiss alerts
    const existingAlerts = document.querySelectorAll('.alert.auto-dismiss');
    existingAlerts.forEach(alert => alert.remove());

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show auto-dismiss`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    const container = document.querySelector('.container-fluid');
    if (container && container.firstChild) {
        container.insertBefore(alertDiv, container.firstChild);
    } else {
        document.body.insertBefore(alertDiv, document.body.firstChild);
    }

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.classList.remove('show');
            setTimeout(() => alertDiv.remove(), 150);
        }
    }, 5000);
}

function formatPrice(price, currency = 'JPY') {
    if (!price || price === 0) return 'Price N/A';
    return new Intl.NumberFormat('ja-JP').format(price) + ' ' + currency;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('ja-JP') + ' ' + date.toLocaleTimeString('ja-JP', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showAlert('✅ Copied to clipboard!', 'success');
    }).catch(function(err) {
        console.error('Could not copy text: ', err);
        showAlert('❌ Failed to copy to clipboard', 'danger');
    });
}

// Export functions for global use
window.testSearchUrl = testSearchUrl;
window.runSearch = runSearch;
window.sendTestNotification = sendTestNotification;
window.deleteQuery = deleteQuery;
window.toggleQuery = toggleQuery;
window.showAlert = showAlert;
window.copyToClipboard = copyToClipboard;
window.formatPrice = formatPrice;
window.formatDate = formatDate;

// Clear all items function
window.clearAllItems = function() {
    if (!confirm('Are you sure you want to DELETE ALL ITEMS from database?\n\nThis will:\n1. Delete all items\n2. Start a new scan\n\nThis action cannot be undone!')) {
        return;
    }
    
    if (!confirm('FINAL WARNING: All items will be permanently deleted. Continue?')) {
        return;
    }
    
    fetch('/api/clear-all-items', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            // Reload page after 2 seconds
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        alert('Error: ' + error);
    });
};
