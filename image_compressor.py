#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        IMAGE COMPRESSOR PRO                                    ║
║                   A Modern Image Compression Tool                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

A sophisticated image compression utility with a modern web-based GUI interface.
Reduces file sizes while maintaining visual quality and original dimensions.

FEATURES:
---------
• Modern web-based GUI (works in any browser)
• Grid view with image previews
• Individual or batch image compression
• Preserves original image dimensions
• Multiple compression algorithms
• Real-time compression statistics
• Before/after file size comparison
• Backup original files option

SUPPORTED FORMATS:
------------------
• PNG  - Uses optimization + quantization for best results
• JPEG - Quality-based compression (configurable)
• WebP - Modern format with excellent compression
• GIF  - Palette optimization

COMPRESSION APPROACH:
---------------------
For ~90% quality retention while maximizing compression:

PNG Files:
  - Uses Pillow's optimize flag
  - Applies palette quantization where appropriate
  - Strips unnecessary metadata
  - Maintains alpha channel if present

JPEG Files:
  - Quality setting of 85-90 (configurable)
  - Subsampling optimization
  - Progressive encoding option

USAGE:
------
1. Run the script: python image_compressor.py
2. Open http://localhost:8080 in your browser
3. Select images to compress (or select all)
4. Click "Compress Selected"
5. Review compression results

DEPENDENCIES:
-------------
• Python 3.8+
• Pillow (PIL Fork) - pip install Pillow

AUTHOR: Image Compressor Pro
VERSION: 1.0.0
LICENSE: MIT
"""

import os
import sys
import io
import json
import shutil
import base64
import threading
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

# Third-party imports
try:
    from PIL import Image
except ImportError as e:
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         MISSING DEPENDENCIES                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Please install the required dependencies:

    pip install Pillow

Error details: {e}
""")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CompressionConfig:
    """Configuration settings for image compression."""
    quality: int = 85
    png_optimize: bool = True
    png_compress_level: int = 9
    create_backup: bool = True
    backup_suffix: str = "_original"
    progressive_jpeg: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def format_file_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_image_extensions() -> Tuple[str, ...]:
    """Return tuple of supported image file extensions."""
    return ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff')


def scan_for_images(directory: Path) -> List[Path]:
    """Recursively scan directory for image files."""
    images = []
    extensions = get_image_extensions()

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '.venv', 'node_modules')]

        for file in files:
            if file.startswith('.'):
                continue
            if '_original' in file or '_backup' in file:
                continue

            if file.lower().endswith(extensions):
                images.append(Path(root) / file)

    return sorted(images)


def create_thumbnail_base64(image_path: Path, size: Tuple[int, int] = (150, 150)) -> str:
    """Create a base64-encoded thumbnail preview of an image."""
    try:
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGBA', img.size, (240, 240, 240, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Create padded square thumbnail
            thumb = Image.new('RGB', size, (250, 250, 250))
            offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
            thumb.paste(img, offset)

            buffer = io.BytesIO()
            thumb.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error creating thumbnail for {image_path}: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# COMPRESSION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ImageCompressor:
    """Core image compression engine."""

    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()

    def get_image_info(self, image_path: Path) -> Dict:
        """Gather comprehensive information about an image file."""
        stat = image_path.stat()

        with Image.open(image_path) as img:
            return {
                'path': str(image_path),
                'filename': image_path.name,
                'original_size': stat.st_size,
                'size_display': format_file_size(stat.st_size),
                'dimensions': f"{img.width} × {img.height}",
                'width': img.width,
                'height': img.height,
                'format': img.format or image_path.suffix.upper().replace('.', ''),
                'thumbnail': create_thumbnail_base64(image_path)
            }

    def compress_image(self, image_path: Path) -> Tuple[bool, int, str]:
        """Compress an image file while preserving dimensions."""
        try:
            original_size = image_path.stat().st_size

            # Create backup if configured
            if self.config.create_backup:
                backup_path = image_path.parent / f"{image_path.stem}{self.config.backup_suffix}{image_path.suffix}"
                if not backup_path.exists():
                    shutil.copy2(image_path, backup_path)

            with Image.open(image_path) as img:
                original_format = img.format or image_path.suffix.upper().replace('.', '')
                save_kwargs = self._get_save_params(original_format)

                buffer = io.BytesIO()

                if original_format.upper() in ('JPEG', 'JPG'):
                    if img.mode in ('RGBA', 'LA', 'PA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode in ('RGBA', 'LA'):
                            background.paste(img, mask=img.split()[-1])
                        else:
                            background.paste(img)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(buffer, format='JPEG', **save_kwargs)

                elif original_format.upper() == 'PNG':
                    img_to_save = self._optimize_png(img)
                    img_to_save.save(buffer, format='PNG', **save_kwargs)

                elif original_format.upper() == 'WEBP':
                    img.save(buffer, format='WEBP', **save_kwargs)

                else:
                    img.save(buffer, format=original_format, **save_kwargs)

                compressed_size = buffer.tell()

                if compressed_size < original_size:
                    buffer.seek(0)
                    with open(image_path, 'wb') as f:
                        f.write(buffer.read())
                    savings = ((original_size - compressed_size) / original_size) * 100
                    return True, compressed_size, f"-{savings:.1f}%"
                else:
                    return True, original_size, "Already optimized"

        except Exception as e:
            return False, 0, f"Error: {str(e)}"

    def _get_save_params(self, format: str) -> Dict:
        """Get format-specific save parameters."""
        format_upper = format.upper()

        if format_upper in ('JPEG', 'JPG'):
            return {
                'quality': self.config.quality,
                'optimize': True,
                'progressive': self.config.progressive_jpeg,
            }
        elif format_upper == 'PNG':
            return {
                'optimize': self.config.png_optimize,
                'compress_level': self.config.png_compress_level,
            }
        elif format_upper == 'WEBP':
            return {'quality': self.config.quality, 'method': 6}
        elif format_upper == 'GIF':
            return {'optimize': True}
        return {}

    def _optimize_png(self, img: Image.Image) -> Image.Image:
        """Apply PNG-specific optimizations."""
        if img.mode == 'RGBA':
            alpha = img.split()[-1]
            if alpha.getextrema() == (255, 255):
                img = img.convert('RGB')

        if img.mode == 'RGB':
            colors = img.getcolors(maxcolors=256)
            if colors is not None:
                img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=len(colors))

        return img


# ═══════════════════════════════════════════════════════════════════════════════
# WEB SERVER
# ═══════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Compressor Pro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
            min-height: 100vh;
        }

        .header {
            background: white;
            padding: 20px 40px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            font-size: 24px;
            font-weight: 600;
            color: #1d1d1f;
        }

        .header p {
            color: #86868b;
            font-size: 14px;
            margin-top: 4px;
        }

        .toolbar {
            display: flex;
            gap: 12px;
            padding: 20px 40px;
            background: #f5f5f7;
            flex-wrap: wrap;
            align-items: center;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: #0071e3;
            color: white;
        }

        .btn-primary:hover {
            background: #0077ed;
        }

        .btn-primary:disabled {
            background: #86868b;
            cursor: not-allowed;
        }

        .btn-secondary {
            background: white;
            color: #1d1d1f;
            border: 1px solid #d2d2d7;
        }

        .btn-secondary:hover {
            background: #f5f5f7;
        }

        .controls {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-left: auto;
        }

        .quality-control {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .quality-control input[type="range"] {
            width: 120px;
            accent-color: #0071e3;
        }

        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            cursor: pointer;
        }

        .checkbox-label input {
            width: 18px;
            height: 18px;
            accent-color: #0071e3;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 16px;
            padding: 0 40px 40px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 16px;
            display: flex;
            gap: 16px;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: all 0.2s;
            cursor: pointer;
            border: 2px solid transparent;
        }

        .card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .card.selected {
            border-color: #0071e3;
            background: #f0f7ff;
        }

        .card-checkbox {
            width: 22px;
            height: 22px;
            accent-color: #0071e3;
            cursor: pointer;
        }

        .card-thumbnail {
            width: 100px;
            height: 100px;
            border-radius: 8px;
            object-fit: cover;
            background: #f5f5f7;
        }

        .card-info {
            flex: 1;
            min-width: 0;
        }

        .card-filename {
            font-weight: 600;
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }

        .card-meta {
            color: #86868b;
            font-size: 13px;
            margin-bottom: 2px;
        }

        .card-status {
            font-weight: 600;
            font-size: 14px;
            min-width: 70px;
            text-align: right;
        }

        .card-status.success {
            color: #34c759;
        }

        .card-status.neutral {
            color: #86868b;
        }

        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 16px 40px;
            box-shadow: 0 -1px 3px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .selection-info {
            font-size: 14px;
            color: #1d1d1f;
        }

        .progress-container {
            flex: 1;
            display: none;
        }

        .progress-container.active {
            display: block;
        }

        .progress-bar {
            height: 6px;
            background: #e5e5ea;
            border-radius: 3px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: #0071e3;
            width: 0%;
            transition: width 0.3s;
        }

        .progress-text {
            font-size: 12px;
            color: #86868b;
            margin-top: 4px;
        }

        .spacer {
            flex: 1;
        }

        .summary {
            background: #f0f7ff;
            border: 1px solid #0071e3;
            border-radius: 8px;
            padding: 16px 24px;
            margin: 0 40px 100px;
            display: none;
        }

        .summary.visible {
            display: block;
        }

        .summary h3 {
            color: #0071e3;
            margin-bottom: 8px;
        }

        .summary p {
            color: #1d1d1f;
            font-size: 14px;
        }

        .empty-state {
            text-align: center;
            padding: 60px 40px;
            color: #86868b;
        }

        .empty-state h2 {
            font-size: 20px;
            margin-bottom: 8px;
            color: #1d1d1f;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Image Compressor Pro</h1>
        <p id="subtitle">Loading images...</p>
    </div>

    <div class="toolbar">
        <button class="btn btn-secondary" onclick="refreshImages()">↻ Refresh</button>
        <button class="btn btn-secondary" onclick="selectAll()">Select All</button>
        <button class="btn btn-secondary" onclick="deselectAll()">Deselect All</button>

        <div class="controls">
            <div class="quality-control">
                <span>Quality:</span>
                <input type="range" id="quality" min="50" max="100" value="85" oninput="updateQualityLabel()">
                <span id="quality-label">85%</span>
            </div>

            <label class="checkbox-label">
                <input type="checkbox" id="backup" checked>
                Create Backups
            </label>
        </div>
    </div>

    <div class="grid" id="image-grid"></div>

    <div class="summary" id="summary">
        <h3>Compression Complete</h3>
        <p id="summary-text"></p>
    </div>

    <div class="footer">
        <span class="selection-info" id="selection-info">0 images selected</span>

        <div class="progress-container" id="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <div class="progress-text" id="progress-text">Compressing...</div>
        </div>

        <div class="spacer"></div>

        <button class="btn btn-primary" id="compress-btn" onclick="compressSelected()">
            Compress Selected
        </button>
    </div>

    <script>
        let images = [];
        let selectedPaths = new Set();

        async function loadImages() {
            try {
                const response = await fetch('/api/images');
                images = await response.json();
                renderGrid();
                document.getElementById('subtitle').textContent =
                    `Found ${images.length} images in project`;
            } catch (error) {
                console.error('Error loading images:', error);
            }
        }

        function renderGrid() {
            const grid = document.getElementById('image-grid');

            if (images.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state" style="grid-column: 1 / -1;">
                        <h2>No images found</h2>
                        <p>No image files were found in the project directory.</p>
                    </div>
                `;
                return;
            }

            grid.innerHTML = images.map((img, index) => `
                <div class="card ${selectedPaths.has(img.path) ? 'selected' : ''}"
                     onclick="toggleSelect('${img.path}')" data-path="${img.path}">
                    <input type="checkbox" class="card-checkbox"
                           ${selectedPaths.has(img.path) ? 'checked' : ''}
                           onclick="event.stopPropagation(); toggleSelect('${img.path}')">
                    <img class="card-thumbnail"
                         src="data:image/jpeg;base64,${img.thumbnail}"
                         alt="${img.filename}">
                    <div class="card-info">
                        <div class="card-filename" title="${img.filename}">${img.filename}</div>
                        <div class="card-meta">${img.dimensions}</div>
                        <div class="card-meta" id="size-${index}">${img.size_display}</div>
                    </div>
                    <div class="card-status neutral" id="status-${index}">—</div>
                </div>
            `).join('');
        }

        function toggleSelect(path) {
            if (selectedPaths.has(path)) {
                selectedPaths.delete(path);
            } else {
                selectedPaths.add(path);
            }
            updateUI();
        }

        function selectAll() {
            images.forEach(img => selectedPaths.add(img.path));
            updateUI();
        }

        function deselectAll() {
            selectedPaths.clear();
            updateUI();
        }

        function updateUI() {
            // Update cards
            document.querySelectorAll('.card').forEach(card => {
                const path = card.dataset.path;
                const isSelected = selectedPaths.has(path);
                card.classList.toggle('selected', isSelected);
                card.querySelector('.card-checkbox').checked = isSelected;
            });

            // Update selection info
            const totalSize = images
                .filter(img => selectedPaths.has(img.path))
                .reduce((sum, img) => sum + img.original_size, 0);

            const sizeStr = formatSize(totalSize);
            document.getElementById('selection-info').textContent =
                `${selectedPaths.size} images selected${selectedPaths.size > 0 ? ' (' + sizeStr + ')' : ''}`;
        }

        function formatSize(bytes) {
            const units = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while (bytes >= 1024 && i < units.length - 1) {
                bytes /= 1024;
                i++;
            }
            return bytes.toFixed(1) + ' ' + units[i];
        }

        function updateQualityLabel() {
            const value = document.getElementById('quality').value;
            document.getElementById('quality-label').textContent = value + '%';
        }

        async function compressSelected() {
            if (selectedPaths.size === 0) {
                alert('Please select at least one image to compress.');
                return;
            }

            const btn = document.getElementById('compress-btn');
            const progressContainer = document.getElementById('progress-container');
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');

            btn.disabled = true;
            btn.textContent = 'Compressing...';
            progressContainer.classList.add('active');

            const paths = Array.from(selectedPaths);
            const quality = document.getElementById('quality').value;
            const backup = document.getElementById('backup').checked;

            let totalOriginal = 0;
            let totalCompressed = 0;

            for (let i = 0; i < paths.length; i++) {
                const path = paths[i];
                const imgIndex = images.findIndex(img => img.path === path);

                progressFill.style.width = ((i + 1) / paths.length * 100) + '%';
                progressText.textContent = `Compressing ${i + 1}/${paths.length}: ${images[imgIndex].filename}`;

                try {
                    const response = await fetch('/api/compress', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({path, quality: parseInt(quality), backup})
                    });

                    const result = await response.json();

                    totalOriginal += images[imgIndex].original_size;
                    totalCompressed += result.new_size;

                    // Update UI
                    const statusEl = document.getElementById('status-' + imgIndex);
                    const sizeEl = document.getElementById('size-' + imgIndex);

                    if (result.success) {
                        statusEl.textContent = result.savings;
                        statusEl.className = 'card-status ' + (result.savings.startsWith('-') ? 'success' : 'neutral');
                        sizeEl.textContent = formatSize(result.new_size);
                    } else {
                        statusEl.textContent = 'Error';
                        statusEl.className = 'card-status neutral';
                    }
                } catch (error) {
                    console.error('Error compressing:', error);
                }
            }

            btn.disabled = false;
            btn.textContent = 'Compress Selected';
            progressContainer.classList.remove('active');

            // Show summary
            const saved = totalOriginal - totalCompressed;
            const percent = totalOriginal > 0 ? (saved / totalOriginal * 100).toFixed(1) : 0;

            document.getElementById('summary-text').textContent =
                `Compressed ${paths.length} images. ` +
                `Original: ${formatSize(totalOriginal)} → Compressed: ${formatSize(totalCompressed)}. ` +
                `Saved: ${formatSize(saved)} (${percent}%)`;
            document.getElementById('summary').classList.add('visible');

            setTimeout(() => {
                document.getElementById('summary').classList.remove('visible');
            }, 10000);
        }

        function refreshImages() {
            selectedPaths.clear();
            document.getElementById('summary').classList.remove('visible');
            loadImages();
        }

        // Load images on page load
        loadImages();
    </script>
</body>
</html>
'''


class CompressorHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the image compressor web interface."""

    compressor = ImageCompressor()
    project_dir = Path.cwd()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())

        elif parsed.path == '/api/images':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            image_paths = scan_for_images(self.project_dir)
            images_data = []

            for path in image_paths:
                try:
                    info = self.compressor.get_image_info(path)
                    images_data.append(info)
                except Exception as e:
                    print(f"Error loading {path}: {e}")

            self.wfile.write(json.dumps(images_data).encode())

        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)

        if parsed.path == '/api/compress':
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))

            path = Path(post_data['path'])
            quality = post_data.get('quality', 85)
            backup = post_data.get('backup', True)

            self.compressor.config.quality = quality
            self.compressor.config.create_backup = backup

            success, new_size, savings = self.compressor.compress_image(path)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            result = {
                'success': success,
                'new_size': new_size,
                'savings': savings
            }
            self.wfile.write(json.dumps(result).encode())

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    """Application entry point."""
    port = 8080
    server_address = ('', port)

    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        IMAGE COMPRESSOR PRO                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

  Server running at: http://localhost:{port}

  Opening browser...

  Press Ctrl+C to stop the server.

""")

    httpd = HTTPServer(server_address, CompressorHandler)

    # Open browser after a short delay
    def open_browser():
        webbrowser.open(f'http://localhost:{port}')

    timer = threading.Timer(0.5, open_browser)
    timer.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
