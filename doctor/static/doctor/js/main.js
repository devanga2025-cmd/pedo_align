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
