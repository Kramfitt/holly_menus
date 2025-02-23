# Holly Lodge Menu System

A system for automating menu management and distribution for Holly Lodge. Handles PDF menu processing, template management, and email distribution.

## Core Features
- PDF menu processing and image conversion
- Template-based menu management
- Automated email distribution
- Season and week rotation handling

## Prerequisites

1. Python 3.8 or higher
2. Tesseract OCR for text extraction
3. Poppler for PDF processing
4. SMTP server access (e.g., Gmail)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Tesseract OCR:
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Install to: `C:\Program Files\Tesseract-OCR`
   - Add to system PATH

3. Install Poppler:
   - Download from: https://github.com/oschwartz10612/poppler-windows/releases/
   - Extract to: `C:\Poppler\Release-24.08.0-0\poppler-24.08.0`

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Update with your settings

## Usage

1. Start the web dashboard:
```bash
python run.py
```

2. Start the menu monitor:
```bash
python menu_monitor.py
```

## Components
- Web Dashboard: Menu management and system monitoring
- Menu Monitor: Processes incoming menu emails
- Menu Scheduler: Handles automated menu distribution

## Development
- Run tests: `pytest`
- Development server: `python run.py`
- Debug mode: Set `FLASK_DEBUG=1` in `.env`