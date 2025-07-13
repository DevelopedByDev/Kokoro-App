import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import threading
import subprocess
import time
import numpy as np
import soundfile as sf
import torch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json

# File format imports
import PyPDF2
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# TTS imports
from kokoro import KPipeline

class TTSApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Kokoro TTS Reader")
        self.root.geometry("800x600")
        
        # Initialize variables
        self.text_content = ""
        self.chunks = []
        self.current_batch = 0
        self.total_batches = 0
        self.is_playing = False
        self.is_paused = False
        self.current_process = None
        self.current_batch_file = None
        self.tts_thread = None
        self.kokoro = None
        self.batch_dir = "batches_and_chunks"
        
        # Initialize status variable first
        self.status_var = tk.StringVar(value="Initializing...")
        
        # Setup UI
        self.setup_ui()
        
        # Initialize TTS after UI is set up
        self.setup_tts()
        
        # Setup batch directory
        self.setup_batches_directory()
        
    def setup_tts(self):
        """Initialize the Kokoro TTS pipeline"""
        try:
            self.kokoro = KPipeline('a')  # American English
            self.status_var.set("Ready")
        except Exception as e:
            messagebox.showerror("TTS Error", f"Failed to initialize TTS: {str(e)}")
            self.status_var.set("TTS initialization failed")
    
    def setup_batches_directory(self):
        """Create the batches_and_chunks directory if it doesn't exist"""
        if not os.path.exists(self.batch_dir):
            os.makedirs(self.batch_dir)
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # File upload section
        file_frame = ttk.LabelFrame(main_frame, text="File Upload", padding="10")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="Select file:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.file_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var, state="readonly")
        self.file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(file_frame, text="Browse", command=self.browse_file).grid(row=0, column=2)
        
        # Text preview section
        text_frame = ttk.LabelFrame(main_frame, text="Text Preview", padding="10")
        text_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.text_preview = scrolledtext.ScrolledText(text_frame, height=15, wrap=tk.WORD)
        self.text_preview.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Control buttons section
        control_frame = ttk.LabelFrame(main_frame, text="Audio Controls", padding="10")
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Voice selection
        ttk.Label(control_frame, text="Voice:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.voice_var = tk.StringVar(value="am_echo")
        voice_combo = ttk.Combobox(control_frame, textvariable=self.voice_var, values=[
            "am_echo", "am_adam", "am_eric", "am_liam", "am_michael", "am_onyx", "am_puck",
            "af_heart", "af_jessica", "af_nova", "af_sarah", "af_sky", "af_bella"
        ])
        voice_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Speed selection
        ttk.Label(control_frame, text="Speed:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.speed_var = tk.DoubleVar(value=1.1)
        speed_spin = ttk.Spinbox(control_frame, from_=0.5, to=2.0, increment=0.1, 
                                textvariable=self.speed_var, width=10)
        speed_spin.grid(row=0, column=3, sticky=tk.W)
        
        # Control buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=1, column=0, columnspan=4, pady=(10, 0))
        
        self.start_btn = ttk.Button(button_frame, text="Start Reading", command=self.start_reading)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.pause_btn = ttk.Button(button_frame, text="Pause", command=self.pause_reading, state="disabled")
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.resume_btn = ttk.Button(button_frame, text="Resume", command=self.resume_reading, state="disabled")
        self.resume_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self.stop_reading, state="disabled")
        self.stop_btn.pack(side=tk.LEFT)
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.batch_info_var = tk.StringVar(value="No batches loaded")
        ttk.Label(progress_frame, textvariable=self.batch_info_var).grid(row=1, column=0, sticky=tk.W)
        
        # Status bar
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Configure grid weights for main frame
        main_frame.rowconfigure(1, weight=1)
    
    def browse_file(self):
        """Open file dialog to select a file"""
        filetypes = [
            ("All supported", "*.txt *.pdf *.epub"),
            ("Text files", "*.txt"),
            ("PDF files", "*.pdf"),
            ("EPUB files", "*.epub")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select a file to read",
            filetypes=filetypes
        )
        
        if filename:
            self.file_var.set(filename)
            self.load_file(filename)
    
    def load_file(self, filename):
        """Load and extract text from the selected file"""
        try:
            file_ext = Path(filename).suffix.lower()
            
            if file_ext == '.txt':
                self.text_content = self.read_txt_file(filename)
            elif file_ext == '.pdf':
                self.text_content = self.read_pdf_file(filename)
            elif file_ext == '.epub':
                self.text_content = self.read_epub_file(filename)
            else:
                messagebox.showerror("Error", f"Unsupported file type: {file_ext}")
                return
            
            # Update text preview
            self.text_preview.delete(1.0, tk.END)
            self.text_preview.insert(1.0, self.text_content[:2000] + "..." if len(self.text_content) > 2000 else self.text_content)
            
            # Prepare chunks
            self.chunks = self.split_text(self.text_content)
            self.total_batches = len(self.chunks) // 4 + (1 if len(self.chunks) % 4 != 0 else 0)
            
            self.batch_info_var.set(f"Loaded {len(self.chunks)} chunks, {self.total_batches} batches")
            self.status_var.set(f"File loaded: {Path(filename).name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
            self.status_var.set("Failed to load file")
    
    def read_txt_file(self, filename):
        """Read text from a plain text file"""
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read()
    
    def read_pdf_file(self, filename):
        """Read text from a PDF file"""
        text = ""
        with open(filename, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def read_epub_file(self, filename):
        """Read text from an EPUB file"""
        book = epub.read_epub(filename)
        text = ""
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                text += soup.get_text() + "\n"
        
        return text
    
    def split_text(self, text, max_sentences=2):
        """Split text into chunks for TTS processing"""
        sentences = text.split('. ')
        chunks = []
        for i in range(0, len(sentences), max_sentences):
            chunk = '. '.join(sentences[i:i+max_sentences])
            if not chunk.endswith('.'):
                chunk += '.'
            chunks.append(chunk)
        return chunks
    
    def start_reading(self):
        """Start the TTS reading process"""
        if not self.text_content:
            messagebox.showwarning("Warning", "Please load a file first")
            return
        
        if not self.kokoro:
            messagebox.showerror("Error", "TTS system not initialized")
            return
        
        self.is_playing = True
        self.is_paused = False
        self.current_batch = 0
        
        # Update button states
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        
        # Start TTS in a separate thread
        self.tts_thread = threading.Thread(target=self.run_tts)
        self.tts_thread.daemon = True
        self.tts_thread.start()
    
    def pause_reading(self):
        """Pause the current audio playback"""
        if self.current_process and self.is_playing:
            self.is_paused = True
            self.current_process.terminate()
            self.current_process = None
            
            self.pause_btn.config(state="disabled")
            self.resume_btn.config(state="normal")
            self.status_var.set("Paused")
    
    def resume_reading(self):
        """Resume audio playback from current batch"""
        if self.is_paused and self.current_batch_file:
            self.is_paused = False
            self.current_process = subprocess.Popen(['afplay', self.current_batch_file])
            
            self.pause_btn.config(state="normal")
            self.resume_btn.config(state="disabled")
            self.status_var.set("Resumed")
    
    def stop_reading(self):
        """Stop the TTS reading process"""
        self.is_playing = False
        self.is_paused = False
        
        if self.current_process:
            self.current_process.terminate()
            self.current_process = None
        
        # Update button states
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        
        self.progress_var.set(0)
        self.status_var.set("Stopped")
    
    def run_tts(self):
        """Main TTS processing method (runs in separate thread)"""
        try:
            batch_size = 4
            batches = [self.chunks[i:i + batch_size] for i in range(0, len(self.chunks), batch_size)]
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                for batch_num, batch_chunks in enumerate(batches):
                    if not self.is_playing:
                        break
                    
                    self.current_batch = batch_num
                    self.root.after(0, self.update_progress)
                    
                    # Generate audio for current batch
                    self.root.after(0, lambda: self.status_var.set(f"Generating batch {batch_num + 1}/{len(batches)}"))
                    
                    futures = []
                    batch_filenames = []
                    
                    for i, chunk in enumerate(batch_chunks):
                        chunk_index = batch_num * batch_size + i
                        filename = os.path.join(self.batch_dir, f"chunk_{chunk_index}.wav")
                        future = executor.submit(self.generate_audio, chunk, filename)
                        futures.append(future)
                        batch_filenames.append(filename)
                    
                    # Wait for all chunks to complete
                    for future in futures:
                        future.result()
                    
                    if not self.is_playing:
                        break
                    
                    # Stitch audio files
                    stitched_filename = os.path.join(self.batch_dir, f"batch_{batch_num}.wav")
                    self.stitch_audio_files(batch_filenames, stitched_filename)
                    self.current_batch_file = stitched_filename
                    
                    # Play audio
                    self.root.after(0, lambda: self.status_var.set(f"Playing batch {batch_num + 1}/{len(batches)}"))
                    self.current_process = subprocess.Popen(['afplay', stitched_filename])
                    
                    # Wait for playback to finish
                    while self.current_process and self.current_process.poll() is None:
                        if not self.is_playing:
                            self.current_process.terminate()
                            break
                        time.sleep(0.1)
                    
                    # Clean up files
                    self.cleanup_files([stitched_filename] + batch_filenames)
            
            if self.is_playing:
                self.root.after(0, self.reading_completed)
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("TTS Error", f"An error occurred: {str(e)}"))
            self.root.after(0, self.stop_reading)
    
    def generate_audio(self, chunk, filename):
        """Generate audio for a text chunk"""
        audio_segments = list(self.kokoro(chunk, voice=self.voice_var.get(), speed=self.speed_var.get()))
        full_audio = torch.cat([torch.tensor(audio) for _, _, audio in audio_segments])
        samples = full_audio.numpy()
        sf.write(filename, samples, 24000, format="WAV")
        return filename
    
    def stitch_audio_files(self, filenames, output_filename, silence_ms=300):
        """Stitch multiple audio files together with silence"""
        all_audio = []
        silence = np.zeros(int(silence_ms * 24000 / 1000), dtype=np.float32)
        
        for i, filename in enumerate(filenames):
            if os.path.exists(filename):
                audio, sr = sf.read(filename)
                all_audio.append(audio)
                if i < len(filenames) - 1:
                    all_audio.append(silence)
        
        stitched_audio = np.concatenate(all_audio)
        sf.write(output_filename, stitched_audio, 24000)
    
    def cleanup_files(self, filenames):
        """Delete audio files to free up space"""
        for filename in filenames:
            if os.path.exists(filename):
                os.remove(filename)
    
    def update_progress(self):
        """Update progress bar and batch info"""
        if self.total_batches > 0:
            progress = (self.current_batch / self.total_batches) * 100
            self.progress_var.set(progress)
            self.batch_info_var.set(f"Batch {self.current_batch + 1} of {self.total_batches}")
    
    def reading_completed(self):
        """Called when reading is completed"""
        self.stop_reading()
        self.status_var.set("Reading completed")
        messagebox.showinfo("Complete", "Reading completed successfully!")

def main():
    root = tk.Tk()
    app = TTSApplication(root)
    root.mainloop()

if __name__ == "__main__":
    main() 