#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        IMAGE COMPRESSOR PRO                                    ║
║                   A Modern Image Compression Tool                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

A sophisticated image compression utility with a modern GUI interface.
Reduces file sizes while maintaining visual quality and original dimensions.

FEATURES:
---------
• Clean GUI with image grid preview
• Individual or batch image compression
• Preserves original image dimensions
• Multiple compression algorithms (Pillow, PIL optimization)
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
2. The GUI will scan for images in the project directory
3. Select images to compress (or select all)
4. Click "Compress Selected" or "Compress All"
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
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass

# Third-party imports
try:
    from PIL import Image, ImageTk
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
    """
    Configuration settings for image compression.

    Attributes:
        quality: JPEG quality (1-100). Higher = better quality, larger file.
                 Default 85 provides ~90% perceived quality.
        png_optimize: Enable PNG optimization (removes unnecessary chunks).
        png_compress_level: PNG compression level (0-9). Higher = smaller file.
        preserve_metadata: Keep EXIF and other metadata.
        create_backup: Create backup of original files before compression.
        backup_suffix: Suffix added to backup filenames.
        output_format: Optional format conversion (None = keep original).
        progressive_jpeg: Use progressive JPEG encoding.
    """
    quality: int = 85
    png_optimize: bool = True
    png_compress_level: int = 9
    preserve_metadata: bool = False
    create_backup: bool = True
    backup_suffix: str = "_original"
    output_format: Optional[str] = None
    progressive_jpeg: bool = True


@dataclass
class ImageInfo:
    """
    Data class storing information about an image file.

    Attributes:
        path: Absolute path to the image file.
        filename: Name of the file without directory.
        original_size: File size in bytes before compression.
        compressed_size: File size in bytes after compression (None if not compressed).
        dimensions: Tuple of (width, height) in pixels.
        format: Image format (PNG, JPEG, etc.).
        has_alpha: Whether the image has an alpha channel.
        is_selected: Whether the image is selected for compression.
        thumbnail: PIL Image object for preview display.
    """
    path: Path
    filename: str
    original_size: int
    compressed_size: Optional[int] = None
    dimensions: Tuple[int, int] = (0, 0)
    format: str = ""
    has_alpha: bool = False
    is_selected: bool = False
    thumbnail: Optional[Image.Image] = None

    def get_size_display(self) -> str:
        """Return human-readable file size."""
        return format_file_size(self.original_size)

    def get_savings_display(self) -> str:
        """Return compression savings as string."""
        if self.compressed_size is None:
            return "—"
        saved = self.original_size - self.compressed_size
        percent = (saved / self.original_size) * 100 if self.original_size > 0 else 0
        return f"-{percent:.1f}%"


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def format_file_size(size_bytes: int) -> str:
    """
    Convert bytes to human-readable format.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted string like "1.5 MB" or "256 KB".
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_image_extensions() -> Tuple[str, ...]:
    """Return tuple of supported image file extensions."""
    return ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff')


def scan_for_images(directory: Path) -> List[Path]:
    """
    Recursively scan directory for image files.

    Args:
        directory: Root directory to scan.

    Returns:
        List of Path objects pointing to image files.
    """
    images = []
    extensions = get_image_extensions()

    for root, dirs, files in os.walk(directory):
        # Skip hidden directories and venv
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'venv' and d != '.venv']

        for file in files:
            if file.startswith('.'):
                continue
            if '_original' in file or '_backup' in file:
                continue

            if file.lower().endswith(extensions):
                images.append(Path(root) / file)

    return sorted(images)


def create_thumbnail(image_path: Path, size: Tuple[int, int] = (120, 120)) -> Optional[Image.Image]:
    """
    Create a thumbnail preview of an image.

    Args:
        image_path: Path to the source image.
        size: Maximum dimensions for the thumbnail.

    Returns:
        PIL Image object as thumbnail, or None on error.
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary for display
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

            # Create thumbnail maintaining aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Create padded square thumbnail
            thumb = Image.new('RGB', size, (240, 240, 240))
            offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
            thumb.paste(img, offset)

            return thumb
    except Exception as e:
        print(f"Error creating thumbnail for {image_path}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# COMPRESSION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ImageCompressor:
    """
    Core image compression engine.

    Handles the actual compression of images using various algorithms
    optimized for each image format.
    """

    def __init__(self, config: CompressionConfig = None):
        """Initialize the compressor with configuration."""
        self.config = config or CompressionConfig()

    def get_image_info(self, image_path: Path) -> ImageInfo:
        """Gather comprehensive information about an image file."""
        stat = image_path.stat()

        with Image.open(image_path) as img:
            info = ImageInfo(
                path=image_path,
                filename=image_path.name,
                original_size=stat.st_size,
                dimensions=(img.width, img.height),
                format=img.format or image_path.suffix.upper().replace('.', ''),
                has_alpha=img.mode in ('RGBA', 'LA', 'PA'),
                thumbnail=create_thumbnail(image_path)
            )

        return info

    def compress_image(
        self,
        image_path: Path,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, int, str]:
        """
        Compress an image file while preserving dimensions.

        Args:
            image_path: Path to the source image.
            output_path: Where to save compressed image.
            progress_callback: Optional function to report progress.

        Returns:
            Tuple of (success: bool, new_size: int, message: str).
        """
        if output_path is None:
            output_path = image_path

        try:
            # Create backup if configured
            if self.config.create_backup and output_path == image_path:
                backup_path = image_path.parent / f"{image_path.stem}{self.config.backup_suffix}{image_path.suffix}"
                if not backup_path.exists():
                    shutil.copy2(image_path, backup_path)
                    if progress_callback:
                        progress_callback(f"Created backup: {backup_path.name}")

            # Open and process image
            with Image.open(image_path) as img:
                original_format = img.format

                if progress_callback:
                    progress_callback(f"Processing {image_path.name} ({img.width}x{img.height})")

                # Determine output format
                output_format = self.config.output_format or original_format
                if output_format is None:
                    output_format = image_path.suffix.upper().replace('.', '')

                # Prepare save parameters based on format
                save_kwargs = self._get_save_params(img, output_format)

                # Save to buffer first to get size
                buffer = io.BytesIO()

                # Handle format-specific processing
                if output_format.upper() in ('JPEG', 'JPG'):
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

                elif output_format.upper() == 'PNG':
                    img_to_save = self._optimize_png(img)
                    img_to_save.save(buffer, format='PNG', **save_kwargs)

                elif output_format.upper() == 'WEBP':
                    img.save(buffer, format='WEBP', **save_kwargs)

                else:
                    img.save(buffer, format=output_format, **save_kwargs)

                # Get compressed size
                compressed_size = buffer.tell()

                # Only save if we achieved compression
                original_size = image_path.stat().st_size
                if compressed_size < original_size:
                    buffer.seek(0)
                    with open(output_path, 'wb') as f:
                        f.write(buffer.read())

                    savings = ((original_size - compressed_size) / original_size) * 100
                    return True, compressed_size, f"Compressed: {savings:.1f}% smaller"
                else:
                    return True, original_size, "Already optimized (no changes made)"

        except Exception as e:
            return False, 0, f"Error: {str(e)}"

    def _get_save_params(self, img: Image.Image, format: str) -> Dict:
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
            return {
                'quality': self.config.quality,
                'method': 6,
            }

        elif format_upper == 'GIF':
            return {'optimize': True}

        return {}

    def _optimize_png(self, img: Image.Image) -> Image.Image:
        """Apply PNG-specific optimizations."""
        # Check if alpha channel is actually used
        if img.mode == 'RGBA':
            alpha = img.split()[-1]
            if alpha.getextrema() == (255, 255):
                img = img.convert('RGB')

        # For images with limited colors, try palette conversion
        if img.mode == 'RGB':
            colors = img.getcolors(maxcolors=256)
            if colors is not None:
                img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=len(colors))

        return img


# ═══════════════════════════════════════════════════════════════════════════════
# GUI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class ImageCard(tk.Frame):
    """A card widget displaying an image preview with selection capability."""

    def __init__(self, parent, image_info: ImageInfo, on_select_change=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.image_info = image_info
        self.on_select_change = on_select_change
        self._photo_image = None

        self.configure(
            bg='#ffffff',
            highlightbackground='#e0e0e0',
            highlightthickness=2,
            padx=10,
            pady=10
        )

        self._setup_ui()

    def _setup_ui(self):
        """Create and arrange UI elements."""
        # Selection checkbox
        self.var = tk.BooleanVar(value=self.image_info.is_selected)
        self.checkbox = tk.Checkbutton(
            self,
            variable=self.var,
            command=self._on_checkbox_change,
            bg='#ffffff',
            activebackground='#ffffff'
        )
        self.checkbox.grid(row=0, column=0, sticky='nw')

        # Thumbnail
        self.thumb_frame = tk.Frame(self, bg='#f0f0f0', width=120, height=120)
        self.thumb_frame.grid(row=0, column=1, rowspan=3, padx=(5, 10), pady=5)
        self.thumb_frame.grid_propagate(False)

        self.thumbnail_label = tk.Label(self.thumb_frame, bg='#f0f0f0')
        if self.image_info.thumbnail:
            self._photo_image = ImageTk.PhotoImage(self.image_info.thumbnail)
            self.thumbnail_label.configure(image=self._photo_image)
        else:
            self.thumbnail_label.configure(text="No Preview")
        self.thumbnail_label.place(relx=0.5, rely=0.5, anchor='center')

        # Make thumbnail clickable
        self.thumbnail_label.bind("<Button-1>", lambda e: self._toggle_selection())
        self.thumb_frame.bind("<Button-1>", lambda e: self._toggle_selection())

        # Filename
        filename = self.image_info.filename
        if len(filename) > 22:
            filename = filename[:19] + "..."
        self.name_label = tk.Label(
            self,
            text=filename,
            font=('Helvetica', 11, 'bold'),
            bg='#ffffff',
            anchor='w'
        )
        self.name_label.grid(row=0, column=2, sticky='w', padx=5)

        # Dimensions
        dims = f"{self.image_info.dimensions[0]} × {self.image_info.dimensions[1]}"
        self.dims_label = tk.Label(
            self,
            text=dims,
            font=('Helvetica', 10),
            fg='#666666',
            bg='#ffffff',
            anchor='w'
        )
        self.dims_label.grid(row=1, column=2, sticky='w', padx=5)

        # File size
        self.size_label = tk.Label(
            self,
            text=self.image_info.get_size_display(),
            font=('Helvetica', 10),
            bg='#ffffff',
            anchor='w'
        )
        self.size_label.grid(row=2, column=2, sticky='w', padx=5)

        # Status
        self.status_label = tk.Label(
            self,
            text="—",
            font=('Helvetica', 11, 'bold'),
            fg='#999999',
            bg='#ffffff',
            width=8,
            anchor='e'
        )
        self.status_label.grid(row=0, column=3, rowspan=3, padx=10, sticky='e')

        self.grid_columnconfigure(2, weight=1)

    def _toggle_selection(self):
        """Toggle checkbox selection state."""
        self.var.set(not self.var.get())
        self._on_checkbox_change()

    def _on_checkbox_change(self):
        """Handle checkbox state change."""
        is_selected = self.var.get()
        self.image_info.is_selected = is_selected

        if is_selected:
            self.configure(highlightbackground='#3B82F6', highlightthickness=3)
        else:
            self.configure(highlightbackground='#e0e0e0', highlightthickness=2)

        if self.on_select_change:
            self.on_select_change(self.image_info.path, is_selected)

    def set_selected(self, selected: bool):
        """Programmatically set selection state."""
        self.var.set(selected)
        self._on_checkbox_change()

    def update_compression_status(self, new_size: Optional[int], message: str = ""):
        """Update the card to show compression results."""
        if new_size is not None and new_size < self.image_info.original_size:
            self.image_info.compressed_size = new_size
            savings = self.image_info.get_savings_display()
            self.status_label.configure(text=savings, fg='#22C55E')
            self.size_label.configure(text=format_file_size(new_size))
        elif message:
            self.status_label.configure(text="✓", fg='#666666')


class ScrollableImageGrid(tk.Frame):
    """Scrollable container for image cards in a grid layout."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.cards: Dict[Path, ImageCard] = {}
        self.on_selection_change = None

        # Create canvas with scrollbar
        self.canvas = tk.Canvas(self, bg='#f5f5f5', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#f5f5f5')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Bind canvas resize
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')

    def _on_canvas_configure(self, event):
        """Handle canvas resize."""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def add_image(self, image_info: ImageInfo) -> ImageCard:
        """Add an image card to the grid."""
        card = ImageCard(
            self.scrollable_frame,
            image_info,
            on_select_change=self._handle_selection_change
        )

        row = len(self.cards) // 2
        col = len(self.cards) % 2

        card.grid(row=row, column=col, padx=8, pady=8, sticky='ew')

        self.cards[image_info.path] = card

        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(1, weight=1)

        return card

    def clear(self):
        """Remove all cards from the grid."""
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()

    def select_all(self):
        """Select all image cards."""
        for card in self.cards.values():
            card.set_selected(True)

    def deselect_all(self):
        """Deselect all image cards."""
        for card in self.cards.values():
            card.set_selected(False)

    def get_selected(self) -> List[ImageInfo]:
        """Get list of selected ImageInfo objects."""
        return [card.image_info for card in self.cards.values() if card.image_info.is_selected]

    def get_card(self, path: Path) -> Optional[ImageCard]:
        """Get card by image path."""
        return self.cards.get(path)

    def _handle_selection_change(self, path: Path, selected: bool):
        """Handle selection change from a card."""
        if self.on_selection_change:
            self.on_selection_change()


class ImageCompressorApp(tk.Tk):
    """Main application window for the Image Compressor."""

    def __init__(self):
        super().__init__()

        self.title("Image Compressor Pro")
        self.geometry("950x700")
        self.minsize(800, 600)
        self.configure(bg='#f5f5f5')

        # Initialize components
        self.compressor = ImageCompressor()
        self.images: List[ImageInfo] = []
        self.project_dir = Path.cwd()

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Build UI
        self._setup_ui()

        # Load images on startup
        self.after(100, self._scan_images)

    def _setup_ui(self):
        """Create and arrange all UI components."""
        # Header
        self.header_frame = tk.Frame(self, bg='#ffffff', pady=15)
        self.header_frame.pack(fill='x', padx=0)

        header_inner = tk.Frame(self.header_frame, bg='#ffffff')
        header_inner.pack(fill='x', padx=20)

        self.title_label = tk.Label(
            header_inner,
            text="Image Compressor Pro",
            font=('Helvetica', 20, 'bold'),
            bg='#ffffff',
            fg='#1a1a1a'
        )
        self.title_label.pack(side='left')

        self.subtitle_label = tk.Label(
            header_inner,
            text="Scanning for images...",
            font=('Helvetica', 11),
            bg='#ffffff',
            fg='#666666'
        )
        self.subtitle_label.pack(side='left', padx=(15, 0))

        # Toolbar
        self.toolbar_frame = tk.Frame(self, bg='#f5f5f5', pady=10)
        self.toolbar_frame.pack(fill='x', padx=20)

        self.refresh_btn = tk.Button(
            self.toolbar_frame,
            text="↻ Refresh",
            command=self._scan_images,
            font=('Helvetica', 10),
            padx=15,
            pady=5
        )
        self.refresh_btn.pack(side='left', padx=(0, 10))

        self.select_all_btn = tk.Button(
            self.toolbar_frame,
            text="Select All",
            command=self._select_all,
            font=('Helvetica', 10),
            padx=15,
            pady=5
        )
        self.select_all_btn.pack(side='left', padx=5)

        self.deselect_all_btn = tk.Button(
            self.toolbar_frame,
            text="Deselect All",
            command=self._deselect_all,
            font=('Helvetica', 10),
            padx=15,
            pady=5
        )
        self.deselect_all_btn.pack(side='left', padx=5)

        # Image Grid
        self.image_grid = ScrollableImageGrid(self, bg='#f5f5f5')
        self.image_grid.pack(fill='both', expand=True, padx=20, pady=10)
        self.image_grid.on_selection_change = self._update_selection_count

        # Footer
        self.footer_frame = tk.Frame(self, bg='#ffffff', pady=15)
        self.footer_frame.pack(fill='x', padx=0)

        footer_inner = tk.Frame(self.footer_frame, bg='#ffffff')
        footer_inner.pack(fill='x', padx=20)

        # Selection count
        self.selection_label = tk.Label(
            footer_inner,
            text="0 images selected",
            font=('Helvetica', 11),
            bg='#ffffff'
        )
        self.selection_label.pack(side='left')

        # Quality control
        quality_frame = tk.Frame(footer_inner, bg='#ffffff')
        quality_frame.pack(side='left', padx=30)

        self.quality_label = tk.Label(
            quality_frame,
            text="Quality: 85%",
            font=('Helvetica', 10),
            bg='#ffffff'
        )
        self.quality_label.pack(side='left', padx=(0, 10))

        self.quality_var = tk.IntVar(value=85)
        self.quality_slider = ttk.Scale(
            quality_frame,
            from_=50,
            to=100,
            variable=self.quality_var,
            orient='horizontal',
            length=120,
            command=self._on_quality_change
        )
        self.quality_slider.pack(side='left')

        # Backup checkbox
        self.backup_var = tk.BooleanVar(value=True)
        self.backup_checkbox = tk.Checkbutton(
            footer_inner,
            text="Create Backups",
            variable=self.backup_var,
            font=('Helvetica', 10),
            bg='#ffffff',
            activebackground='#ffffff'
        )
        self.backup_checkbox.pack(side='left', padx=20)

        # Compress button
        self.compress_btn = tk.Button(
            footer_inner,
            text="Compress Selected",
            command=self._compress_selected,
            font=('Helvetica', 11, 'bold'),
            bg='#3B82F6',
            fg='white',
            padx=20,
            pady=8,
            relief='flat',
            cursor='hand2'
        )
        self.compress_btn.pack(side='right')

        # Progress bar (hidden by default)
        self.progress_frame = tk.Frame(self.footer_frame, bg='#ffffff')
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            length=400,
            mode='determinate'
        )
        self.progress_label = tk.Label(
            self.progress_frame,
            text="",
            font=('Helvetica', 10),
            bg='#ffffff',
            fg='#666666'
        )

    def _on_quality_change(self, value):
        """Handle quality slider change."""
        quality = int(float(value))
        self.quality_label.configure(text=f"Quality: {quality}%")
        self.compressor.config.quality = quality

    def _scan_images(self):
        """Scan project directory for images."""
        self.subtitle_label.configure(text="Scanning for images...")
        self.image_grid.clear()
        self.images.clear()

        def scan_thread():
            image_paths = scan_for_images(self.project_dir)

            for path in image_paths:
                try:
                    info = self.compressor.get_image_info(path)
                    self.images.append(info)
                    self.after(0, lambda i=info: self.image_grid.add_image(i))
                except Exception as e:
                    print(f"Error loading {path}: {e}")

            self.after(0, lambda: self.subtitle_label.configure(
                text=f"Found {len(self.images)} images in {self.project_dir.name}"
            ))

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()

    def _select_all(self):
        """Select all images."""
        self.image_grid.select_all()
        self._update_selection_count()

    def _deselect_all(self):
        """Deselect all images."""
        self.image_grid.deselect_all()
        self._update_selection_count()

    def _update_selection_count(self):
        """Update the selection count label."""
        selected = self.image_grid.get_selected()
        count = len(selected)
        total_size = sum(img.original_size for img in selected)

        if count == 0:
            self.selection_label.configure(text="0 images selected")
        else:
            self.selection_label.configure(
                text=f"{count} images selected ({format_file_size(total_size)})"
            )

    def _compress_selected(self):
        """Compress all selected images."""
        selected = self.image_grid.get_selected()

        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one image to compress.")
            return

        # Update compressor config
        self.compressor.config.create_backup = self.backup_var.get()
        self.compressor.config.quality = self.quality_var.get()

        # Show progress
        self.progress_frame.pack(fill='x', padx=20, pady=(5, 0))
        self.progress_bar.pack(side='left', padx=(0, 10))
        self.progress_label.pack(side='left')
        self.compress_btn.configure(state='disabled', text='Compressing...')

        def compress_thread():
            total = len(selected)
            total_original = 0
            total_compressed = 0

            for i, img_info in enumerate(selected):
                progress = ((i + 1) / total) * 100
                self.after(0, lambda p=progress: self.progress_bar.configure(value=p))
                self.after(0, lambda n=img_info.filename: self.progress_label.configure(
                    text=f"Compressing: {n}"
                ))

                success, new_size, message = self.compressor.compress_image(img_info.path)

                total_original += img_info.original_size
                total_compressed += new_size if success else img_info.original_size

                card = self.image_grid.get_card(img_info.path)
                if card:
                    self.after(0, lambda c=card, s=new_size if success else None, m=message:
                              c.update_compression_status(s, m))

            self.after(0, self._compression_complete)

            savings = total_original - total_compressed
            percent = (savings / total_original) * 100 if total_original > 0 else 0

            self.after(0, lambda: messagebox.showinfo(
                "Compression Complete",
                f"Compressed {total} images\n\n"
                f"Original size: {format_file_size(total_original)}\n"
                f"Compressed size: {format_file_size(total_compressed)}\n"
                f"Total savings: {format_file_size(savings)} ({percent:.1f}%)"
            ))

        thread = threading.Thread(target=compress_thread, daemon=True)
        thread.start()

    def _compression_complete(self):
        """Reset UI after compression completes."""
        self.progress_frame.pack_forget()
        self.compress_btn.configure(state='normal', text='Compress Selected')
        self.progress_bar.configure(value=0)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Application entry point."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        IMAGE COMPRESSOR PRO                                    ║
║                   Starting application...                                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)

    app = ImageCompressorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
