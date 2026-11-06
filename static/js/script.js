/**
 * NoticeShield - Frontend Interactive Script
 * Provides drag-and-drop file upload, instant previews, verification loader,
 * and quick-test demo helpers for hackathon evaluations.
 */

document.addEventListener('DOMContentLoaded', function () {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('notice_file');
    const previewContainer = document.getElementById('preview-container');
    const previewImage = document.getElementById('preview-image');
    const previewPdfText = document.getElementById('preview-pdf-text');
    const fileNameDisplay = document.getElementById('file-name-display');
    const verifyForm = document.getElementById('verify-form');
    const verifyBtn = document.getElementById('verify-btn');
    const loadingOverlay = document.getElementById('loading-overlay');

    if (dropzone && fileInput) {
        // Click to browse
        dropzone.addEventListener('click', () => fileInput.click());

        // Drag events
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('dragover');
            }, false);
        });

        // Drop handler
        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                fileInput.files = files;
                handleFileSelect(files[0]);
            }
        });

        // Change handler
        fileInput.addEventListener('change', function () {
            if (this.files.length > 0) {
                handleFileSelect(this.files[0]);
            }
        });
    }

    function handleFileSelect(file) {
        if (!file) return;

        if (fileNameDisplay) {
            fileNameDisplay.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        }

        if (previewContainer) {
            previewContainer.classList.remove('d-none');
        }

        const ext = file.name.split('.').pop().toLowerCase();
        if (['jpg', 'jpeg', 'png', 'webp'].includes(ext)) {
            const reader = new FileReader();
            reader.onload = function (e) {
                if (previewImage) {
                    previewImage.src = e.target.result;
                    previewImage.classList.remove('d-none');
                }
                if (previewPdfText) {
                    previewPdfText.classList.add('d-none');
                }
            };
            reader.readAsDataURL(file);
        } else if (ext === 'pdf') {
            if (previewImage) previewImage.classList.add('d-none');
            if (previewPdfText) {
                previewPdfText.classList.remove('d-none');
                previewPdfText.textContent = `PDF Document Ready: ${file.name}`;
            }
        }
    }

    // Show loading spinner when form is submitted
    if (verifyForm && verifyBtn) {
        verifyForm.addEventListener('submit', function () {
            if (loadingOverlay) {
                loadingOverlay.classList.remove('d-none');
            }
            verifyBtn.disabled = true;
            verifyBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                Verifying Cryptography & OCR...
            `;
        });
    }
});
