# Kokoro TTS GUI Application

A user-friendly graphical interface for the Kokoro Text-to-Speech system that allows you to upload and read PDF, TXT, and EPUB files with full audio playback controls.

## Features

- **Multi-format Support**: Upload and read PDF, TXT, and EPUB files
- **Text Preview**: See a preview of your document before reading
- **Voice Selection**: Choose from multiple high-quality voices
- **Speed Control**: Adjust reading speed from 0.5x to 2.0x
- **Audio Controls**: Play, pause, resume, and stop functionality
- **Progress Tracking**: Real-time progress bar and batch information
- **Batch Processing**: Efficient parallel processing of text chunks
- **Automatic Cleanup**: Temporary files are automatically cleaned up

## Installation

1. Make sure you have all required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. If you need to install PDF and EPUB support separately:
   ```bash
   pip install PyPDF2 ebooklib beautifulsoup4
   ```

## Usage

1. **Start the Application**:
   ```bash
   python tts_gui.py
   ```

2. **Upload a File**:
   - Click the "Browse" button
   - Select a PDF, TXT, or EPUB file
   - The text preview will show the first 2000 characters

3. **Configure Settings**:
   - Choose your preferred voice from the dropdown
   - Adjust the reading speed using the spinner control

4. **Start Reading**:
   - Click "Start Reading" to begin TTS processing
   - The application will process text in batches for optimal performance
   - Progress is shown in real-time

5. **Audio Controls**:
   - **Pause**: Temporarily stop audio playback
   - **Resume**: Continue from where you paused
   - **Stop**: Completely stop reading and reset

## Supported File Formats

### TXT Files
- Plain text files with UTF-8 encoding
- No special formatting required

### PDF Files
- Text-based PDFs (not scanned images)
- Automatically extracts text from all pages
- Handles multi-page documents

### EPUB Files
- Standard EPUB format ebooks
- Extracts text from all chapters
- Removes HTML formatting automatically

## Technical Details

### Audio Processing
- Uses Kokoro TTS pipeline for high-quality speech synthesis
- Processes text in chunks of 2 sentences for optimal performance
- Generates audio in batches of 4 chunks with parallel processing
- Automatically stitches audio with 300ms silence between chunks
- Output format: 24kHz WAV files

### Voice Options
The application includes these voice options:
- **Male voices**: am_echo, am_adam, am_eric, am_liam, am_michael, am_onyx, am_puck
- **Female voices**: af_heart, af_jessica, af_nova, af_sarah, af_sky, af_bella

### Performance
- Utilizes ThreadPoolExecutor with 4 workers for parallel audio generation
- Apple Silicon optimized for M1/M2 chips
- Automatic memory management with file cleanup
- Real-time progress tracking

## File Structure

```
batches_and_chunks/          # Temporary audio files (auto-created)
├── chunk_0.wav             # Individual audio chunks
├── chunk_1.wav
├── batch_0.wav             # Stitched batch files
└── batch_1.wav
```

## Troubleshooting

### Common Issues

1. **"TTS initialization failed"**:
   - Ensure Kokoro is properly installed: `pip install kokoro`
   - Check that you have the required model files

2. **"Failed to load file"**:
   - Verify file format is supported (PDF, TXT, EPUB)
   - Check file permissions and encoding

3. **Audio playback issues**:
   - Ensure `afplay` is available (macOS only)
   - Check system audio settings

### Performance Tips

- For large files, the application automatically processes in batches
- Pause/resume functionality works at the batch level
- Temporary files are cleaned up automatically
- Close other audio applications for best performance

## Requirements

- Python 3.7+
- macOS (for `afplay` audio playback)
- Kokoro TTS system
- tkinter (usually included with Python)
- Required packages listed in `requirements.txt`

## Example Usage

1. Load a PDF book or article
2. Select "af_sarah" voice at 1.1x speed
3. Click "Start Reading"
4. Use pause/resume as needed
5. Monitor progress in the status bar

The application will handle the rest automatically, providing a seamless reading experience with high-quality text-to-speech conversion. 