import soundfile as sf
from kokoro import KPipeline
import subprocess
import threading
import time
import numpy as np
import os
import torch
from concurrent.futures import ThreadPoolExecutor

def setup_batches_chunks_directory():
    """Create the batches_and_chunks directory if it doesn't exist"""
    batch_dir = "batches_and_chunks"
    if not os.path.exists(batch_dir):
        os.makedirs(batch_dir)
        print(f"📁 Created directory: {batch_dir}")
    else:
        print(f"📁 Using existing directory: {batch_dir}")
    return batch_dir

def split_text(text, max_sentences=2):
    sentences = text.split('. ')
    chunks = []
    for i in range(0, len(sentences), max_sentences):
        chunk = '. '.join(sentences[i:i+max_sentences])
        if not chunk.endswith('.'):
            chunk += '.'
        chunks.append(chunk)
    return chunks

def generate_audio(kokoro, chunk, filename):
    """Generate audio for a chunk and save to file"""
    print(f"🔄 Generating: {chunk[:50]}...")
    audio_segments = list(kokoro(chunk, voice="af_echo", speed=1.0))
    
    # Concatenate all audio segments 
    full_audio = torch.cat([torch.tensor(audio) for _, _, audio in audio_segments])
    
    # Convert to numpy and save
    samples = full_audio.numpy()
    sample_rate = 24000  # Kokoro uses 24kHz
    sf.write(filename, samples, sample_rate, format="WAV")
    print(f"✅ Generated: {filename}")
    return filename

def create_silence(duration_ms, sample_rate=24000):
    """Create silence audio data"""
    duration_samples = int(duration_ms * sample_rate / 1000)
    return np.zeros(duration_samples, dtype=np.float32)

def stitch_audio_files(filenames, output_filename, silence_ms=300, sample_rate=24000):
    """Stitch multiple audio files together with silence between them"""
    print(f"🔗 Stitching {len(filenames)} audio files...")
    
    all_audio = []
    silence = create_silence(silence_ms, sample_rate)
    
    for i, filename in enumerate(filenames):
        if os.path.exists(filename):
            audio, sr = sf.read(filename)
            all_audio.append(audio)
            
            # Add silence between chunks (but not after the last one)
            if i < len(filenames) - 1:
                all_audio.append(silence)
    
    # Concatenate all audio
    stitched_audio = np.concatenate(all_audio)
    sf.write(output_filename, stitched_audio, sample_rate)
    print(f"✅ Stitched audio saved as: {output_filename}")
    return output_filename

def play_audio_async(filename):
    """Play audio file asynchronously using afplay"""
    print(f"🔊 Playing: {filename}")
    return subprocess.Popen(['afplay', filename])

def cleanup_files(filenames):
    """Delete audio files to free up space"""
    for filename in filenames:
        if os.path.exists(filename):
            os.remove(filename)
            print(f"🗑️ Deleted: {filename}")

# Setup batches and chunks directory
batch_dir = setup_batches_chunks_directory()

kokoro = KPipeline('a')  # 'a' for American English

with open("test_texts/Accelerando.txt", "r") as file:
    text = file.read()

chunks = split_text(text)
print(f"📝 Split text into {len(chunks)} chunks")

# Process chunks in batches of 4
batch_size = 4
batches = [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]
print(f"🗂️ Created {len(batches)} batches of up to {batch_size} chunks each")

# Use ThreadPoolExecutor with 4 workers for parallel generation
with ThreadPoolExecutor(max_workers=4) as executor:
    current_audio_process = None
    
    for batch_num, batch_chunks in enumerate(batches):
        print(f"\n🚀 Processing batch {batch_num + 1}/{len(batches)} ({len(batch_chunks)} chunks)")
        
        # Generate all chunks in current batch in parallel
        futures = []
        batch_filenames = []
        
        for i, chunk in enumerate(batch_chunks):
            chunk_index = batch_num * batch_size + i
            filename = os.path.join(batch_dir, f"chunk_{chunk_index}.wav")
            future = executor.submit(generate_audio, kokoro, chunk, filename)
            futures.append(future)
            batch_filenames.append(filename)
        
        # Wait for all chunks in batch to complete generation
        print(f"⏳ Waiting for batch {batch_num + 1} generation to complete...")
        for future in futures:
            future.result()
        print(f"✅ Batch {batch_num + 1} generation completed!")
        
        # Create stitched audio filename
        stitched_filename = os.path.join(batch_dir, f"batch_{batch_num}.wav")
        
        # Stitch audio files together with 300ms silence
        stitch_audio_files(batch_filenames, stitched_filename, silence_ms=300)
        
        # Wait for previous audio to finish before starting new batch
        if current_audio_process is not None:
            print("⏳ Waiting for previous batch to finish playing...")
            current_audio_process.wait()
            
            # Clean up previous batch files
            if batch_num > 0:
                prev_stitched = os.path.join(batch_dir, f"batch_{batch_num - 1}.wav")
                prev_chunk_files = [os.path.join(batch_dir, f"chunk_{(batch_num - 1) * batch_size + j}.wav") 
                                  for j in range(min(batch_size, len(batches[batch_num - 1])))]
                cleanup_files([prev_stitched] + prev_chunk_files)
        
        # Start playing current batch asynchronously
        current_audio_process = play_audio_async(stitched_filename)
        print(f"🎵 Started playing batch {batch_num + 1}")
    
    # Wait for final batch to finish and clean up
    if current_audio_process is not None:
        print("\n⏳ Waiting for final batch to finish...")
        current_audio_process.wait()
        
        # Clean up final batch files
        final_batch_num = len(batches) - 1
        final_stitched = os.path.join(batch_dir, f"batch_{final_batch_num}.wav")
        final_chunk_files = [os.path.join(batch_dir, f"chunk_{final_batch_num * batch_size + j}.wav") 
                           for j in range(len(batches[final_batch_num]))]
        cleanup_files([final_stitched] + final_chunk_files)

print("🎉 All audio has been generated, played, and cleaned up!")    
