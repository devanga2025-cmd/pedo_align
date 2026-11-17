// PEDO ALIGN - Doctor Portal JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // 1. Mobile Sidebar Toggle
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (mobileMenuBtn && sidebar && sidebarOverlay) {
        mobileMenuBtn.addEventListener('click', function() {
            sidebar.classList.toggle('-translate-x-full');
            sidebarOverlay.classList.toggle('hidden');
        });

        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.add('-translate-x-full');
            sidebarOverlay.classList.add('hidden');
        });
    }

    // 2. Notification Bell Dropdown
    const notifBtn = document.getElementById('notifDropdownBtn');
    const notifMenu = document.getElementById('notifDropdownMenu');
    if (notifBtn && notifMenu) {
        notifBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            notifMenu.classList.toggle('hidden');
        });
        document.addEventListener('click', function(e) {
            if (!notifMenu.contains(e.target) && !notifBtn.contains(e.target)) {
                notifMenu.classList.add('hidden');
            }
        });
    }

    // 3. User Profile Dropdown
    const profileBtn = document.getElementById('userProfileBtn');
    const profileMenu = document.getElementById('userProfileMenu');
    if (profileBtn && profileMenu) {
        profileBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            profileMenu.classList.toggle('hidden');
        });
        document.addEventListener('click', function(e) {
            if (!profileMenu.contains(e.target) && !profileBtn.contains(e.target)) {
                profileMenu.classList.add('hidden');
            }
        });
    }

    // 4. Auto-dismiss alerts
    const alerts = document.querySelectorAll('.auto-dismiss-alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // 5. Before & After Slider logic
    initComparisonSliders();
});

// Copy to clipboard helper (with HTTP / insecure context fallback)
function copyToClipboard(text, elemId) {
    function showFeedback() {
        const elem = elemId ? document.getElementById(elemId) : null;
        if (elem) {
            const originalHTML = elem.innerHTML;
            elem.innerHTML = '<i class="fa-solid fa-check text-emerald-500"></i> Copied!';
            setTimeout(function() {
                elem.innerHTML = originalHTML;
            }, 2000);
        } else {
            alert("Code copied to clipboard: " + text);
        }
    }

    function fallbackCopy(str) {
        try {
            const textArea = document.createElement("textarea");
            textArea.value = str;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            showFeedback();
        } catch (err) {
            alert("Copied: " + str);
        }
    }

    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(text).then(showFeedback).catch(function(err) {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

// Image Zoom Modal helper
function openImageModal(imgSrc, title) {
    const modal = document.getElementById('globalImageModal');
    const modalImg = document.getElementById('globalModalImage');
    const modalTitle = document.getElementById('globalModalTitle');
    if (modal && modalImg) {
        modalImg.src = imgSrc;
        if (modalTitle) modalTitle.innerText = title || 'Dental Photo Examination';
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeImageModal() {
    const modal = document.getElementById('globalImageModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// Side-by-Side Before/After Slider
function initComparisonSliders() {
    const containers = document.querySelectorAll('.compare-container');
    containers.forEach(function(container) {
        const afterImgWrapper = container.querySelector('.compare-image-after');
        const handle = container.querySelector('.compare-slider-handle');
        if (!afterImgWrapper || !handle) return;

        let isDragging = false;

        function updateSlider(x) {
            const rect = container.getBoundingClientRect();
            let pos = ((x - rect.left) / rect.width) * 100;
            if (pos < 0) pos = 0;
            if (pos > 100) pos = 100;
            afterImgWrapper.style.width = pos + '%';
            handle.style.left = pos + '%';
        }

        handle.addEventListener('mousedown', () => isDragging = true);
        window.addEventListener('mouseup', () => isDragging = false);
        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            updateSlider(e.clientX);
        });

        // Touch support for tablet / mobile
        handle.addEventListener('touchstart', () => isDragging = true);
        window.addEventListener('touchend', () => isDragging = false);
        window.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            updateSlider(e.touches[0].clientX);
        });
    });
}

// Global phone number strict validation: max 10 digits, numbers only, no alphabets
(function initPhoneValidation() {
    function isPhoneField(el) {
        if (!el || el.tagName !== 'INPUT') return false;
        if (el.name === 'q' || el.type === 'search') return false;
        var name = (el.name || '').toLowerCase();
        var id = (el.id || '').toLowerCase();
        var type = (el.type || '').toLowerCase();
        return type === 'tel' || name.includes('phone') || name.includes('mobile') || id.includes('phone') || id.includes('mobile');
    }

    document.addEventListener('input', function(e) {
        if (isPhoneField(e.target)) {
            var digits = e.target.value.replace(/\D/g, '').slice(0, 10);
            if (e.target.value !== digits) {
                e.target.value = digits;
            }
        }
    }, true);

    document.addEventListener('keypress', function(e) {
        if (isPhoneField(e.target)) {
            if (!/\d/.test(e.key) && !e.ctrlKey && !e.metaKey && e.key.length === 1) {
                e.preventDefault();
            }
            if (e.target.value.length >= 10 && e.target.selectionStart === e.target.selectionEnd && !e.ctrlKey && !e.metaKey && e.key.length === 1) {
                e.preventDefault();
            }
        }
    }, true);

    document.addEventListener('paste', function(e) {
        if (isPhoneField(e.target)) {
            e.preventDefault();
            var text = (e.clipboardData || window.clipboardData).getData('text') || '';
            var digits = text.replace(/\D/g, '');
            var currentVal = e.target.value;
            var start = e.target.selectionStart || 0;
            var end = e.target.selectionEnd || 0;
            var newVal = (currentVal.slice(0, start) + digits + currentVal.slice(end)).replace(/\D/g, '').slice(0, 10);
            e.target.value = newVal;
            e.target.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }, true);
})();

// Reusable Password Visibility Toggle Helper
function togglePasswordVisibility(targetInputOrId, iconElemOrId, event) {
    if (event) {
        if (typeof event.preventDefault === 'function') event.preventDefault();
        if (typeof event.stopPropagation === 'function') event.stopPropagation();
    }

    var input = typeof targetInputOrId === 'string' ? document.getElementById(targetInputOrId) : targetInputOrId;
    if (!input) return;

    var isPassword = (input.type === 'password') || (input.getAttribute('type') === 'password');
    var nextType = isPassword ? 'text' : 'password';

    try {
        input.type = nextType;
    } catch (e) {}
    try {
        input.setAttribute('type', nextType);
    } catch (e) {}

    var icon = null;
    if (iconElemOrId) {
        icon = typeof iconElemOrId === 'string' ? document.getElementById(iconElemOrId) : iconElemOrId;
    }
    if (!icon) {
        var container = input.closest('.relative') || input.parentElement;
        if (container) {
            icon = container.querySelector('.fa-eye, .fa-eye-slash');
        }
    }

    if (icon) {
        if (nextType === 'text') {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
            if (icon.parentElement && icon.parentElement.tagName === 'BUTTON') {
                icon.parentElement.setAttribute('title', 'Hide password');
                icon.parentElement.setAttribute('aria-label', 'Hide password');
            }
        } else {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
            if (icon.parentElement && icon.parentElement.tagName === 'BUTTON') {
                icon.parentElement.setAttribute('title', 'Show password');
                icon.parentElement.setAttribute('aria-label', 'Show password');
            }
        }
    }
}

// Global click listener for password toggle buttons (avoids double execution if onclick is present)
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-toggle-password], .password-toggle-btn');
    if (!btn) return;
    if (btn.hasAttribute('onclick')) return; // Avoid double invocation

    e.preventDefault();
    e.stopPropagation();

    var targetId = btn.getAttribute('data-toggle-password');
    var targetInput = targetId ? document.getElementById(targetId) : null;
    if (!targetInput) {
        var container = btn.closest('.relative') || btn.parentElement;
        if (container) {
            targetInput = container.querySelector('input');
        }
    }
    if (!targetInput) return;

    var icon = btn.querySelector('.fa-eye, .fa-eye-slash') || btn;
    togglePasswordVisibility(targetInput, icon, e);
});
