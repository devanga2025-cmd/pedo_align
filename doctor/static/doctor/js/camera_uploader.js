/**
 * PEDO ALIGN - Live Clinical Camera & Dual Gallery Uploader
 * Supports live rear-camera streaming, viewfinder framing, capture, rotation,
 * retake, confirmation, and fallback to gallery selection across Android, iOS & Desktop.
 */

let cameraActiveStream = null;
let currentFacingMode = 'environment'; // Default rear camera
let targetInputId = null;
let targetPreviewImgId = null;
let targetPlaceholderId = null;
let capturedRotation = 0;
let capturedCanvas = null;

/**
 * Open the Live Camera Modal for a specific input and preview slot
 * @param {string} inputId - ID of the target <input type="file">
 * @param {string} previewImgId - ID of the <img> element to show preview in
 * @param {string} placeholderId - ID of the placeholder element to hide
 * @param {string} slotTitle - Descriptive title for the camera modal header
 */
async function openLiveCamera(inputId, previewImgId, placeholderId, slotTitle) {
    targetInputId = inputId;
    targetPreviewImgId = previewImgId || null;
    targetPlaceholderId = placeholderId || null;
    capturedRotation = 0;

    const modal = document.getElementById('liveCameraModal');
    const titleEl = document.getElementById('cameraModalTitle');
    const badgeEl = document.getElementById('cameraFacingBadge');
    const video = document.getElementById('cameraStreamVideo');
    const errorBox = document.getElementById('cameraErrorBox');
    const reviewContainer = document.getElementById('cameraReviewContainer');
    const viewfinder = document.getElementById('cameraViewfinderOverlay');
    const liveControls = document.getElementById('cameraLiveControls');
    const reviewControls = document.getElementById('cameraReviewControls');
    const spinner = document.getElementById('cameraLoadingSpinner');

    if (!modal) return;

    // Reset views
    if (titleEl) titleEl.textContent = slotTitle || 'Live Clinical Camera';
    if (badgeEl) badgeEl.textContent = currentFacingMode === 'environment' ? 'Rear Camera (Clinical View)' : 'Front Camera';
    if (errorBox) errorBox.classList.add('hidden');
    if (reviewContainer) reviewContainer.classList.add('hidden');
    if (viewfinder) viewfinder.classList.remove('hidden');
    if (liveControls) liveControls.classList.remove('hidden');
    if (reviewControls) reviewControls.classList.add('hidden');
    if (spinner) spinner.classList.remove('hidden');

    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Request stream
    await startCameraStream();
}

/**
 * Start or restart the camera stream with current facing mode
 */
async function startCameraStream() {
    const video = document.getElementById('cameraStreamVideo');
    const spinner = document.getElementById('cameraLoadingSpinner');
    const errorBox = document.getElementById('cameraErrorBox');
    const errorMsg = document.getElementById('cameraErrorMessage');
    const badgeEl = document.getElementById('cameraFacingBadge');

    stopActiveStream();

    if (spinner) spinner.classList.remove('hidden');
    if (errorBox) errorBox.classList.add('hidden');

    // Check mediaDevices support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (spinner) spinner.classList.add('hidden');
        if (errorBox) {
            errorBox.classList.remove('hidden');
            if (errorMsg) errorMsg.textContent = 'Camera API is not supported in this browser. Please use Gallery upload or update your browser.';
        }
        return;
    }

    try {
        const constraints = {
            video: {
                facingMode: { ideal: currentFacingMode },
                width: { ideal: 1920, max: 3840 },
                height: { ideal: 1080, max: 2160 }
            },
            audio: false
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        cameraActiveStream = stream;

        if (video) {
            video.srcObject = stream;
            video.onloadedmetadata = () => {
                video.play().catch(e => console.warn('Video play error:', e));
                if (spinner) spinner.classList.add('hidden');
            };
        }

        if (badgeEl) {
            badgeEl.textContent = currentFacingMode === 'environment' ? 'Rear Camera (Clinical View)' : 'Front Camera';
        }

    } catch (err) {
        console.error('Camera stream access failed:', err);
        if (spinner) spinner.classList.add('hidden');
        if (errorBox) {
            errorBox.classList.remove('hidden');
            let friendlyMessage = 'Camera permissions are blocked or another application is using the camera.';
            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                friendlyMessage = 'Camera permission was denied. Please allow camera access in your browser settings to take live clinical photos.';
            } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                friendlyMessage = 'No camera device was detected on your system. Please select a photo from your gallery.';
            } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
                friendlyMessage = 'Camera is currently locked by another application. Please close other camera apps and try again.';
            }
            if (errorMsg) errorMsg.textContent = friendlyMessage;
        }
    }
}

/**
 * Switch between Rear and Front cameras
 */
async function flipCamera() {
    currentFacingMode = currentFacingMode === 'environment' ? 'user' : 'environment';
    const flipText = document.getElementById('flipBtnText');
    if (flipText) flipText.textContent = currentFacingMode === 'environment' ? 'Front' : 'Rear';
    await startCameraStream();
}

/**
 * Capture frame from live video feed onto high-res canvas
 */
function captureLivePhoto() {
    const video = document.getElementById('cameraStreamVideo');
    const reviewContainer = document.getElementById('cameraReviewContainer');
    const reviewImg = document.getElementById('cameraReviewImg');
    const viewfinder = document.getElementById('cameraViewfinderOverlay');
    const liveControls = document.getElementById('cameraLiveControls');
    const reviewControls = document.getElementById('cameraReviewControls');

    if (!video || !video.videoWidth) {
        alert('Camera stream is still initializing. Please wait a moment and try again.');
        return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    
    // Draw raw high-resolution frame
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    capturedCanvas = canvas;
    capturedRotation = 0;

    // Show in review container
    if (reviewImg) {
        reviewImg.src = canvas.toDataURL('image/jpeg', 0.95);
    }
    if (reviewContainer) reviewContainer.classList.remove('hidden');
    if (viewfinder) viewfinder.classList.add('hidden');
    if (liveControls) liveControls.classList.add('hidden');
    if (reviewControls) reviewControls.classList.remove('hidden');
}

/**
 * Rotate the captured snapshot 90 degrees clockwise
 */
function rotateLivePhoto() {
    if (!capturedCanvas) return;

    capturedRotation = (capturedRotation + 90) % 360;

    const srcCanvas = capturedCanvas;
    const rotatedCanvas = document.createElement('canvas');
    // Swap width and height for 90 or 270 deg
    rotatedCanvas.width = srcCanvas.height;
    rotatedCanvas.height = srcCanvas.width;

    const ctx = rotatedCanvas.getContext('2d');
    ctx.translate(rotatedCanvas.width / 2, rotatedCanvas.height / 2);
    ctx.rotate((90 * Math.PI) / 180);
    ctx.drawImage(srcCanvas, -srcCanvas.width / 2, -srcCanvas.height / 2);

    capturedCanvas = rotatedCanvas;

    const reviewImg = document.getElementById('cameraReviewImg');
    if (reviewImg) {
        reviewImg.src = rotatedCanvas.toDataURL('image/jpeg', 0.95);
    }
}

/**
 * Discard snapshot and resume live video
 */
function retakeLivePhoto() {
    const reviewContainer = document.getElementById('cameraReviewContainer');
    const viewfinder = document.getElementById('cameraViewfinderOverlay');
    const liveControls = document.getElementById('cameraLiveControls');
    const reviewControls = document.getElementById('cameraReviewControls');

    if (reviewContainer) reviewContainer.classList.add('hidden');
    if (viewfinder) viewfinder.classList.remove('hidden');
    if (liveControls) liveControls.classList.remove('hidden');
    if (reviewControls) reviewControls.classList.add('hidden');

    capturedCanvas = null;
    capturedRotation = 0;
}

/**
 * Confirm snapshot: Convert to JPEG file, populate target <input type="file"> via DataTransfer,
 * update thumbnail preview, and close modal.
 */
function confirmLivePhoto() {
    if (!capturedCanvas || !targetInputId) {
        closeLiveCamera();
        return;
    }

    capturedCanvas.toBlob((blob) => {
        if (!blob) {
            alert('Failed to generate image file. Please retake the photo.');
            return;
        }

        const fileName = `clinical_photo_${Date.now()}.jpg`;
        const file = new File([blob], fileName, { type: 'image/jpeg' });

        const targetInput = document.getElementById(targetInputId);
        if (targetInput) {
            try {
                const dt = new DataTransfer();
                // If the input allows multiple files (like preopPhotosInput), check if existing files should be preserved
                if (targetInput.multiple && targetInput.files.length > 0) {
                    for (let i = 0; i < targetInput.files.length; i++) {
                        dt.items.add(targetInput.files[i]);
                    }
                }
                dt.items.add(file);
                targetInput.files = dt.files;
            } catch (e) {
                console.warn('DataTransfer not fully supported, fallback to assignment:', e);
            }

            // Dispatch change event to trigger existing thumbnail/preview handlers
            targetInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Update direct preview elements if supplied
        if (targetPreviewImgId) {
            const previewImg = document.getElementById(targetPreviewImgId);
            if (previewImg) {
                previewImg.src = URL.createObjectURL(blob);
                previewImg.classList.remove('hidden');
            }
        }
        if (targetPlaceholderId) {
            const placeholder = document.getElementById(targetPlaceholderId);
            if (placeholder) {
                placeholder.classList.add('hidden');
            }
        }

        closeLiveCamera();

    }, 'image/jpeg', 0.95);
}

/**
 * Cleanly stop all active camera video tracks
 */
function stopActiveStream() {
    if (cameraActiveStream) {
        cameraActiveStream.getTracks().forEach(track => {
            try {
                track.stop();
            } catch (e) {}
        });
        cameraActiveStream = null;
    }
    const video = document.getElementById('cameraStreamVideo');
    if (video) {
        video.srcObject = null;
    }
}

/**
 * Close the live camera modal and release hardware
 */
function closeLiveCamera() {
    stopActiveStream();
    const modal = document.getElementById('liveCameraModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
    capturedCanvas = null;
    capturedRotation = 0;
}

/**
 * Open device gallery / file manager for target file input
 * @param {string} inputId - ID of the target <input type="file">
 */
function openGallery(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    // Ensure capture attribute is removed so it opens the gallery/file picker
    input.removeAttribute('capture');
    input.click();
}

/**
 * Trigger gallery fallback from inside the camera modal
 */
function triggerCurrentGalleryFallback() {
    const id = targetInputId;
    closeLiveCamera();
    if (id) {
        openGallery(id);
    }
}

/**
 * Open system native camera (direct OS camera app) as secondary option
 * @param {string} inputId
 */
function openSystemCamera(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.setAttribute('capture', 'environment');
    input.click();
}

/**
 * Helper to show immediate thumbnail preview from any file input
 */
function previewClinicalFile(input, previewImgId, placeholderId) {
    if (!input || !input.files || !input.files[0]) return;
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = function(e) {
        if (previewImgId) {
            const img = document.getElementById(previewImgId);
            if (img) {
                img.src = e.target.result;
                img.classList.remove('hidden');
            }
        }
        if (placeholderId) {
            const ph = document.getElementById(placeholderId);
            if (ph) {
                ph.classList.add('hidden');
            }
        }
    };
    reader.readAsDataURL(file);
}

// Bind Escape key to close live camera modal
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modal = document.getElementById('liveCameraModal');
        if (modal && !modal.classList.contains('hidden')) {
            closeLiveCamera();
        }
    }
});
