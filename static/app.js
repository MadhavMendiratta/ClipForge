/**
 * StreamForge — shared UI utilities
 */

// ── Sidebar toggle (mobile) ────────────────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const isOpen = !sidebar.classList.contains('-translate-x-full');
    if (isOpen) {
        sidebar.classList.add('-translate-x-full');
        overlay.classList.add('hidden');
    } else {
        sidebar.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
    }
}

// ── Toast notifications ─────────────────────────────────────────────────────
window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const colors = {
        success: 'bg-emerald-600',
        error: 'bg-red-600',
        info: 'bg-brand-600',
        warning: 'bg-amber-600',
    };

    const icons = {
        success: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
        error: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
        info: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        warning: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
    };

    const toast = document.createElement('div');
    toast.className = `toast pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg text-white text-sm font-medium ${colors[type] || colors.info}`;
    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 4000);
};

// ── Copy to clipboard helper ────────────────────────────────────────────────
window.copyToClipboard = function(text) {
    navigator.clipboard.writeText(text).then(() => {
        window.showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        // fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        window.showToast('Copied to clipboard!', 'success');
    });
};

// ── Global keyboard shortcut ────────────────────────────────────────────────
document.addEventListener('keydown', function(e) {
    // Cmd/Ctrl + K → focus search (reserved for future)
    // Escape → close modals
    if (e.key === 'Escape') {
        const modal = document.getElementById('createModal');
        if (modal && !modal.classList.contains('hidden')) {
            closeCreateModal?.();
        }
    }
});

console.log('%c⚡ StreamForge', 'color: #4c6ef5; font-weight: bold; font-size: 14px;');
