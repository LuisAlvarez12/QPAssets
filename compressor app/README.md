# Image Compressor Pro

A modern web-based image compression tool that reduces file sizes while maintaining ~90% visual quality and preserving original dimensions.

## Quick Start

```bash
cd "compressor app"

# First time setup
~/.pyenv/versions/3.10.12/bin/python -m venv .venv
source .venv/bin/activate
pip install Pillow

# Run the compressor
python image_compressor.py
```

Or simply:
```bash
cd "compressor app"
./run_compressor.sh
```

Your browser will automatically open to `http://localhost:8080`.

## Requirements

- Python 3.8+ (Python 3.10.12 via pyenv recommended)
- Pillow library

## Usage

1. **Start the server:**
   ```bash
   cd "compressor app"
   ./run_compressor.sh
   ```

2. **Use the web interface:**
   - The app automatically scans the parent directory for images
   - Click on image cards to select them (or use "Select All")
   - Adjust the **Quality** slider (default 85% = ~90% visual quality)
   - Toggle **Create Backups** to keep original files
   - Click **Compress Selected**

3. **Stop the server:** Press `Ctrl+C` in the terminal

## Features

| Feature | Description |
|---------|-------------|
| Grid View | Thumbnail previews of all images |
| Batch Compression | Compress multiple images at once |
| Quality Control | Adjustable quality slider (50-100%) |
| Backup Option | Automatically saves originals as `*_original.png` |
| Progress Tracking | Real-time progress bar and status |
| Compression Stats | Shows savings percentage for each image |

## Supported Formats

- **PNG** - Optimization + palette quantization
- **JPEG** - Quality-based compression with progressive encoding
- **WebP** - Modern format with excellent compression
- **GIF** - Palette optimization
- **BMP/TIFF** - Basic optimization

## Compression Strategy

### PNG Files
- Removes unnecessary metadata chunks
- Converts unused alpha channels to RGB
- Applies palette quantization for images with ≤256 colors
- Uses maximum compression level (9)

### JPEG Files
- Quality setting (default 85%)
- Progressive encoding for better perceived loading
- Huffman table optimization

### Key Behavior
- **Dimensions are always preserved** (no resizing)
- Only overwrites if compressed size is smaller
- Skips files already named `*_original.*` or `*_backup.*`

## File Structure

```
QPAssets/
├── compressor app/
│   ├── image_compressor.py    # Main application
│   ├── run_compressor.sh      # Launch script
│   ├── requirements.txt       # Python dependencies
│   ├── README.md              # This file
│   └── .venv/                 # Virtual environment (created on first run)
├── assets/
│   └── images/                # Images to compress
├── layout/
│   └── images/                # More images to compress
└── .gitignore
```

## Troubleshooting

### Port already in use
If port 8080 is busy, edit `image_compressor.py` and change:
```python
port = 8080  # Change to 8081 or another port
```

### Browser doesn't open
Manually navigate to: `http://localhost:8080`

### Virtual environment issues
Recreate the virtual environment:
```bash
cd "compressor app"
rm -rf .venv
~/.pyenv/versions/3.10.12/bin/python -m venv .venv
source .venv/bin/activate
pip install Pillow
```
