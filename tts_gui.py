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
import asyncio
import platform
import psutil
from threading import Event
import queue
from collections import deque
import tempfile
import pyaudio
import wave

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
        self.root.title("🎙️ Kokoro TTS Reader")
        self.root.geometry("1000x700")
        self.root.minsize(900, 650)
        
        # M1 Pro optimizations
        self.setup_m1_optimizations()
        
        # Initialize variables
        self.text_content = ""
        self.chunks = []
        self.current_chunk_index = 0
        self.total_chunks = 0
        self.is_playing = False
        self.is_paused = False
        self.tts_thread = None
        self.kokoro = None
        self.batch_dir = "batches_and_chunks"
        
        # Continuous audio streaming system
        self.audio_stream_queue = queue.Queue(maxsize=50)  # Audio data queue
        self.generation_queue = queue.Queue()
        self.stop_event = Event()
        self.pause_event = Event()
        self.generation_workers = []
        self.audio_stream = None
        self.pyaudio_instance = None
        self.stream_thread = None
        
        # Audio parameters
        self.sample_rate = 24000
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paFloat32
        
        # Buffer management
        self.generation_ahead = 15  # Generate this many chunks ahead
        self.played_chunks = 0
        
        # Initialize status variable first
        self.status_var = tk.StringVar(value="🚀 Initializing...")
        self.progress_text_var = tk.StringVar(value="Ready to load a file")
        
        # Setup modern UI theme
        self.setup_modern_theme()
        
        # Setup UI
        self.setup_ui()
        
        # Initialize TTS after UI is set up
        self.setup_tts()
        
        # Setup batch directory
        self.setup_batches_directory()
        
        # Initialize PyAudio
        self.setup_audio_system()
        
        # Start streaming workers
        self.start_streaming_workers()
        
    def setup_m1_optimizations(self):
        """Setup M1 Pro specific optimizations"""
        self.cpu_count = psutil.cpu_count(logical=False)  # Physical cores
        self.max_workers = min(8, self.cpu_count)  # M1 Pro has 8 performance cores
        
        # Enable MPS if available and properly supported
        try:
            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                self.device = torch.device("mps")
                print("🚀 MPS (Metal Performance Shaders) enabled")
            else:
                self.device = torch.device("cpu")
                print("⚠️ MPS not available, using CPU")
        except (AttributeError, ImportError) as e:
            print(f"⚠️ MPS support error: {e}")
            self.device = torch.device("cpu")
            
        # Optimize generation parameters
        self.generation_batch_size = 8 if self.device.type == "mps" else 4
        
    def setup_modern_theme(self):
        """Setup modern dark theme"""
        style = ttk.Style()
        
        # Configure modern theme
        style.theme_use('clam')
        
        # Color scheme
        self.colors = {
            'bg': '#1e1e1e',
            'fg': '#ffffff',
            'select_bg': '#404040',
            'select_fg': '#ffffff',
            'button_bg': '#0d7377',
            'button_fg': '#ffffff',
            'accent': '#14a085',
            'warning': '#f39c12',
            'error': '#e74c3c',
            'success': '#27ae60',
            'text_bg': '#2d2d2d',
            'frame_bg': '#252525'
        }
        
        # Configure styles
        style.configure('Modern.TFrame', background=self.colors['bg'])
        style.configure('Modern.TLabel', background=self.colors['bg'], foreground=self.colors['fg'])
        style.configure('Modern.TButton', background=self.colors['button_bg'], foreground=self.colors['button_fg'])
        style.configure('Modern.TEntry', fieldbackground=self.colors['text_bg'], foreground=self.colors['fg'])
        style.configure('Modern.TCombobox', fieldbackground=self.colors['text_bg'], foreground=self.colors['fg'])
        style.configure('Modern.TSpinbox', fieldbackground=self.colors['text_bg'], foreground=self.colors['fg'])
        style.configure('Modern.TLabelframe', background=self.colors['frame_bg'], foreground=self.colors['fg'])
        style.configure('Modern.TLabelframe.Label', background=self.colors['frame_bg'], foreground=self.colors['fg'])
        style.configure('Modern.TProgressbar', background=self.colors['accent'])
        style.layout('Modern.TProgressbar',
                    [('Horizontal.Progressbar.trough',
                      {'children': [('Horizontal.Progressbar.pbar',
                                   {'side': 'left', 'sticky': 'ns'})],
                       'sticky': 'nswe'})])
        
        # Configure root window
        self.root.configure(bg=self.colors['bg'])
        
    def setup_audio_system(self):
        """Initialize PyAudio for continuous audio streaming"""
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            print("🎵 PyAudio initialized successfully")
        except Exception as e:
            print(f"❌ PyAudio initialization failed: {e}")
            self.pyaudio_instance = None
            
    def start_streaming_workers(self):
        """Start streaming audio generation and playback workers"""
        # Start generation workers
        for i in range(self.max_workers):
            worker = threading.Thread(target=self.streaming_generation_worker, daemon=True)
            worker.start()
            self.generation_workers.append(worker)
            
        # Start continuous audio stream thread
        self.stream_thread = threading.Thread(target=self.continuous_audio_stream, daemon=True)
        self.stream_thread.start()
        
    def streaming_generation_worker(self):
        """Worker thread for continuous audio generation"""
        while not self.stop_event.is_set():
            try:
                task = self.generation_queue.get(timeout=1)
                if task is None:
                    break
                    
                chunk_index, chunk_text = task
                
                # Generate audio with device optimization
                with torch.no_grad():
                    try:
                        audio_segments = list(self.kokoro(chunk_text, voice=self.voice_var.get(), speed=self.speed_var.get()))
                        
                        # Process audio tensors with proper error handling
                        if self.device.type == "mps":
                            try:
                                full_audio = torch.cat([audio.detach().clone().to(self.device) for _, _, audio in audio_segments])
                                samples = full_audio.cpu().numpy()
                            except RuntimeError as e:
                                print(f"⚠️ MPS processing error, falling back to CPU: {e}")
                                full_audio = torch.cat([audio.detach().clone() for _, _, audio in audio_segments])
                                samples = full_audio.numpy()
                        else:
                            full_audio = torch.cat([audio.detach().clone() for _, _, audio in audio_segments])
                            samples = full_audio.numpy()
                            
                        # Ensure samples are float32 and normalized
                        samples = samples.astype(np.float32)
                        if len(samples.shape) > 1:
                            samples = samples.flatten()
                        
                        # Add to audio stream queue
                        self.audio_stream_queue.put((chunk_index, samples))
                        
                        # Update progress
                        progress = (chunk_index + 1) / self.total_chunks * 100
                        self.root.after(0, lambda p=progress: self.progress_var.set(p))
                        
                    except Exception as e:
                        print(f"❌ Audio generation error for chunk {chunk_index}: {e}")
                        
                self.generation_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Generation worker error: {e}")
                
    def continuous_audio_stream(self):
        """Continuous audio streaming thread using PyAudio"""
        if not self.pyaudio_instance:
            print("❌ PyAudio not available, falling back to file-based playback")
            return
            
        audio_buffer = {}  # chunk_index -> audio_data
        next_chunk_to_play = 0
        
        # Create audio stream
        try:
            stream = self.pyaudio_instance.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size
            )
            
            print("🎵 Continuous audio stream started")
            
            while not self.stop_event.is_set():
                try:
                    # Get generated audio chunks
                    try:
                        chunk_index, audio_data = self.audio_stream_queue.get(timeout=0.1)
                        audio_buffer[chunk_index] = audio_data
                    except queue.Empty:
                        pass
                    
                    # Play audio if ready and not paused
                    if (self.is_playing and not self.is_paused and 
                        next_chunk_to_play in audio_buffer):
                        
                        audio_data = audio_buffer[next_chunk_to_play]
                        
                        # Update status
                        self.root.after(0, lambda idx=next_chunk_to_play: 
                                       self.status_var.set(f"🎵 Playing chunk {idx + 1}/{self.total_chunks}"))
                        
                        # Stream audio data in small chunks for smooth playback
                        for i in range(0, len(audio_data), self.chunk_size):
                            if self.stop_event.is_set() or not self.is_playing:
                                break
                                
                            # Wait if paused
                            while self.is_paused and not self.stop_event.is_set():
                                time.sleep(0.01)
                                
                            if self.stop_event.is_set() or not self.is_playing:
                                break
                                
                            chunk = audio_data[i:i + self.chunk_size]
                            if len(chunk) < self.chunk_size:
                                # Pad with zeros if needed
                                chunk = np.pad(chunk, (0, self.chunk_size - len(chunk)), mode='constant')
                            
                            # Write to audio stream
                            stream.write(chunk.astype(np.float32).tobytes())
                        
                        # Clean up and move to next chunk
                        del audio_buffer[next_chunk_to_play]
                        next_chunk_to_play += 1
                        self.played_chunks = next_chunk_to_play
                        
                        # Check if we've finished all chunks
                        if next_chunk_to_play >= self.total_chunks:
                            self.root.after(0, self.reading_completed)
                            break
                    
                    # Small delay to prevent excessive CPU usage
                    time.sleep(0.001)
                    
                except Exception as e:
                    print(f"❌ Audio streaming error: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"❌ Failed to create audio stream: {e}")
            
        finally:
            # Cleanup
            try:
                if 'stream' in locals():
                    stream.stop_stream()
                    stream.close()
            except:
                pass
    
    def setup_tts(self):
        """Initialize the Kokoro TTS pipeline"""
        try:
            self.kokoro = KPipeline('a')  # American English
            self.status_var.set("✅ Ready")
        except Exception as e:
            messagebox.showerror("TTS Error", f"Failed to initialize TTS: {str(e)}")
            self.status_var.set("❌ TTS initialization failed")
    
    def setup_batches_directory(self):
        """Create the batches_and_chunks directory if it doesn't exist"""
        if not os.path.exists(self.batch_dir):
            os.makedirs(self.batch_dir)
    
    def setup_ui(self):
        """Setup the modern user interface"""
        # Main container with modern styling
        main_frame = ttk.Frame(self.root, style='Modern.TFrame', padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Header section
        header_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        header_frame.columnconfigure(1, weight=1)
        
        # App title with icon
        title_label = ttk.Label(header_frame, text="🎙️ Kokoro TTS Reader", 
                               style='Modern.TLabel', font=('Helvetica', 24, 'bold'))
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # System info
        system_info = f"🚀 M1 Pro | {self.max_workers} workers | MPS: {'✅' if self.device.type == 'mps' else '❌'}"
        info_label = ttk.Label(header_frame, text=system_info, 
                              style='Modern.TLabel', font=('Helvetica', 10))
        info_label.grid(row=0, column=1, sticky=tk.E)
        
        # File upload section with modern styling
        file_frame = ttk.LabelFrame(main_frame, text="📁 File Upload", style='Modern.TLabelframe', padding="15")
        file_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        file_frame.columnconfigure(1, weight=1)
        
        # File selection with better layout
        file_label = ttk.Label(file_frame, text="Select file:", style='Modern.TLabel', font=('Helvetica', 11))
        file_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 15))
        
        self.file_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var, state="readonly", 
                                   style='Modern.TEntry', font=('Helvetica', 10))
        self.file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15))
        
        browse_btn = ttk.Button(file_frame, text="📂 Browse", command=self.browse_file, 
                               style='Modern.TButton', width=12)
        browse_btn.grid(row=0, column=2)
        
        # Text preview with better styling
        text_frame = ttk.LabelFrame(main_frame, text="📖 Text Preview", style='Modern.TLabelframe', padding="15")
        text_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Custom text widget with dark theme
        self.text_preview = scrolledtext.ScrolledText(
            text_frame, 
            height=12, 
            wrap=tk.WORD,
            bg=self.colors['text_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            selectbackground=self.colors['select_bg'],
            selectforeground=self.colors['select_fg'],
            font=('Helvetica', 11),
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10
        )
        self.text_preview.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Control panel with modern layout
        control_frame = ttk.LabelFrame(main_frame, text="🎛️ Audio Controls", style='Modern.TLabelframe', padding="15")
        control_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        control_frame.columnconfigure(4, weight=1)
        
        # Voice selection with better styling
        voice_label = ttk.Label(control_frame, text="🎭 Voice:", style='Modern.TLabel', font=('Helvetica', 11))
        voice_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.voice_var = tk.StringVar(value="am_echo")
        voice_combo = ttk.Combobox(control_frame, textvariable=self.voice_var, 
                                  style='Modern.TCombobox', width=15, font=('Helvetica', 10),
                                  values=[
                                      "am_echo", "am_adam", "am_eric", "am_liam", "am_michael", "am_onyx", "am_puck",
                                      "af_heart", "af_jessica", "af_nova", "af_sarah", "af_sky", "af_bella"
                                  ])
        voice_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 25))
        
        # Speed control with better styling
        speed_label = ttk.Label(control_frame, text="⚡ Speed:", style='Modern.TLabel', font=('Helvetica', 11))
        speed_label.grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        
        self.speed_var = tk.DoubleVar(value=1.1)
        speed_spin = ttk.Spinbox(control_frame, from_=0.5, to=2.0, increment=0.1, 
                                textvariable=self.speed_var, width=8, style='Modern.TSpinbox',
                                font=('Helvetica', 10))
        speed_spin.grid(row=0, column=3, sticky=tk.W)
        
        # Control buttons with modern styling
        button_frame = ttk.Frame(control_frame, style='Modern.TFrame')
        button_frame.grid(row=1, column=0, columnspan=5, pady=(20, 0))
        
        # Modern button styling
        button_style = {'width': 12, 'style': 'Modern.TButton'}
        
        self.start_btn = ttk.Button(button_frame, text="▶️ Start", command=self.start_reading, **button_style)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.pause_btn = ttk.Button(button_frame, text="⏸️ Pause", command=self.pause_reading, 
                                   state="disabled", **button_style)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.resume_btn = ttk.Button(button_frame, text="▶️ Resume", command=self.resume_reading, 
                                    state="disabled", **button_style)
        self.resume_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="⏹️ Stop", command=self.stop_reading, 
                                  state="disabled", **button_style)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Progress section with modern styling
        progress_frame = ttk.LabelFrame(main_frame, text="📊 Progress", style='Modern.TLabelframe', padding="15")
        progress_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          mode='determinate', style='Modern.TProgressbar')
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        # Progress text
        self.batch_info_var = tk.StringVar(value="📄 No file loaded")
        progress_label = ttk.Label(progress_frame, textvariable=self.batch_info_var, 
                                  style='Modern.TLabel', font=('Helvetica', 10))
        progress_label.grid(row=1, column=0, sticky=tk.W)
        
        # Status bar with modern styling
        status_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        status_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)
        
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, 
                              style='Modern.TLabel', font=('Helvetica', 10, 'italic'),
                              relief=tk.SUNKEN, anchor=tk.W, padding=(10, 5))
        status_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Configure grid weights for main frame
        main_frame.rowconfigure(2, weight=1)
    
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
            
            # Prepare chunks
            self.chunks = self.split_text(self.text_content)
            self.total_chunks = len(self.chunks)
            
            self.batch_info_var.set(f"📄 {len(self.chunks)} chunks ready for streaming")
            self.status_var.set(f"📁 File loaded: {Path(filename).name}")
            
            # Update UI
            self.text_preview.delete(1.0, tk.END)
            self.text_preview.insert(1.0, self.text_content[:2000] + "..." if len(self.text_content) > 2000 else self.text_content)
            self.start_btn.config(state="normal")
            self.progress_var.set(0)
            
            # Enable start button
            self.start_btn.config(state="normal")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
            self.status_var.set("❌ Failed to load file")
    
    def read_txt_file(self, filename):
        """Read text from .txt file"""
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read()
    
    def read_pdf_file(self, filename):
        """Read text from PDF file"""
        text = ""
        with open(filename, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    
    def read_epub_file(self, filename):
        """Read text from EPUB file"""
        book = epub.read_epub(filename)
        text = ""
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text += soup.get_text()
        return text
    
    def split_text(self, text, max_sentences=2):
        """Split text into chunks for streaming processing"""
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < 300:  # Smaller chunks for streaming
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def start_reading(self):
        """Start reading the text with streaming TTS"""
        if not self.text_content:
            messagebox.showwarning("No Text", "Please load a text file first!")
            return
        
        if not self.kokoro:
            messagebox.showerror("TTS Error", "TTS system not initialized!")
            return
        
        # Reset streaming state
        self.is_playing = True
        self.is_paused = False
        self.current_chunk_index = 0
        self.stop_event.clear()
        
        # Clear queues
        while not self.generation_queue.empty():
            try:
                self.generation_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.audio_stream_queue.empty():
            try:
                self.audio_stream_queue.get_nowait()
            except queue.Empty:
                break
        
        # Update UI
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        
        # Start streaming TTS in background thread
        self.tts_thread = threading.Thread(target=self.run_streaming_tts, daemon=True)
        self.tts_thread.start()
        
        self.status_var.set("🚀 Starting streaming TTS...")
        
    def run_streaming_tts(self):
        """Main streaming TTS processing method"""
        try:
            self.root.after(0, lambda: self.status_var.set("🔄 Queuing chunks for generation..."))
            
            # Queue all chunks for generation
            for i, chunk in enumerate(self.chunks):
                if not self.is_playing or self.stop_event.is_set():
                    break
                self.generation_queue.put((i, chunk))
            
            self.root.after(0, lambda: self.status_var.set("🎵 Streaming audio generation started..."))
            
            # The streaming workers will handle the rest automatically
            # Just wait for completion or stop signal
            while self.is_playing and not self.stop_event.is_set():
                time.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Streaming TTS error: {e}")
            self.root.after(0, lambda: messagebox.showerror("TTS Error", f"Streaming TTS failed: {str(e)}"))
            self.root.after(0, self.stop_reading)
    
    def pause_reading(self):
        """Pause audio playback"""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self.pause_btn.config(state="disabled")
            self.resume_btn.config(state="normal")
            self.status_var.set("⏸️ Paused")
            
    def resume_reading(self):
        """Resume audio playback"""
        if self.is_playing and self.is_paused:
            self.is_paused = False
            self.pause_btn.config(state="normal")
            self.resume_btn.config(state="disabled")
            self.status_var.set("▶️ Resumed")
    
    def stop_reading(self):
        """Stop the TTS reading process"""
        self.is_playing = False
        self.is_paused = False
        self.stop_event.set()
        
        # Clear queues
        while not self.generation_queue.empty():
            try:
                self.generation_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.audio_stream_queue.empty():
            try:
                self.audio_stream_queue.get_nowait()
            except queue.Empty:
                break
        
        # Update button states
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        
        self.progress_var.set(0)
        self.status_var.set("⏹️ Stopped")
    
    def update_chunk_progress(self, chunk_progress):
        """Update progress for individual chunk completion"""
        # This method is no longer directly used in the new streaming system
        pass
    
    def reading_completed(self):
        """Called when reading is completed"""
        self.stop_reading()
        self.status_var.set("🎉 Reading completed!")
        self.batch_info_var.set("✅ All chunks completed successfully")
        messagebox.showinfo("Complete", "🎉 Reading completed successfully!")
        
    def cleanup_audio_system(self):
        """Cleanup PyAudio resources"""
        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
                print("🎵 PyAudio terminated successfully")
        except Exception as e:
            print(f"⚠️ PyAudio cleanup error: {e}")

def main():
    root = tk.Tk()
    app = TTSApplication(root)
    
    # Handle window close event
    def on_closing():
        app.stop_reading()
        app.cleanup_audio_system()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_closing()

if __name__ == "__main__":
    main() 