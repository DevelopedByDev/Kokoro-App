#!/usr/bin/env python3
"""
Practical approaches for optimizing Kokoro TTS on Apple Silicon / Neural Engine
"""

import torch
import time
from kokoro import KPipeline
import platform

def check_apple_silicon():
    """Check if running on Apple Silicon"""
    return platform.machine() == 'arm64' and platform.system() == 'Darwin'

def optimize_pytorch_for_apple_silicon():
    """Configure PyTorch for optimal Apple Silicon performance"""
    print("🔧 Configuring PyTorch for Apple Silicon optimization...")
    
    if not check_apple_silicon():
        print("⚠️  Not running on Apple Silicon")
        return False
    
    # Enable Metal Performance Shaders (MPS) if available
    if torch.backends.mps.is_available():
        print("✅ Metal Performance Shaders (MPS) available")
        print("   This provides GPU acceleration on Apple Silicon")
        device = torch.device("mps")
    else:
        print("⚠️  MPS not available, using CPU")
        device = torch.device("cpu")
    
    # Configure PyTorch settings for Apple Silicon
    torch.set_num_threads(8)  # Optimize for M1 Pro (8 performance cores)
    
    # Enable optimizations
    torch.jit.set_fusion_strategy([('STATIC', 20)])
    
    print(f"   Device: {device}")
    print(f"   CPU threads: {torch.get_num_threads()}")
    
    return device

def create_optimized_pipeline(device=None):
    """Create an optimized Kokoro pipeline"""
    print("🚀 Creating optimized Kokoro pipeline...")
    
    # Create pipeline
    pipeline = KPipeline(lang_code='a')
    
    # Move model to MPS device if available
    if device and device.type == 'mps':
        try:
            # Note: MPS support depends on model compatibility
            pipeline.model = pipeline.model.to(device)
            print("✅ Model moved to MPS device")
        except Exception as e:
            print(f"⚠️  Could not move model to MPS: {e}")
            print("   Using CPU (still optimized for Apple Silicon)")
    
    return pipeline

def benchmark_performance(pipeline, test_text=None):
    """Benchmark the pipeline performance"""
    if test_text is None:
        test_text = "Hello, this is a performance test for Kokoro TTS on Apple Silicon."
    
    print("📊 Running performance benchmark...")
    
    # Warm-up run
    print("   Warming up...")
    list(pipeline(test_text, voice='af_heart'))
    
    # Actual benchmark
    print("   Benchmarking...")
    start_time = time.time()
    
    audio_segments = list(pipeline(test_text, voice='af_heart'))
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # Calculate performance metrics
    total_audio_duration = sum(len(audio) for _, _, audio in audio_segments) / 24000  # 24kHz sample rate
    real_time_factor = total_audio_duration / processing_time
    
    print(f"   Processing time: {processing_time:.2f} seconds")
    print(f"   Audio duration: {total_audio_duration:.2f} seconds")
    print(f"   Real-time factor: {real_time_factor:.2f}x")
    
    if real_time_factor > 1.0:
        print("✅ Faster than real-time!")
    else:
        print("⚠️  Slower than real-time")
    
    return audio_segments, processing_time

def create_apple_optimized_wrapper():
    """Create a wrapper class optimized for Apple Silicon"""
    
    class AppleOptimizedKokoro:
        def __init__(self, lang_code='a'):
            print("🍎 Initializing Apple Silicon optimized Kokoro...")
            
            # Configure device and optimizations
            self.device = optimize_pytorch_for_apple_silicon()
            
            # Create optimized pipeline
            self.pipeline = create_optimized_pipeline(self.device)
            
            print("✅ Apple optimized Kokoro ready!")
        
        def synthesize(self, text, voice='af_heart', benchmark=False):
            """Synthesize speech with optional benchmarking"""
            if benchmark:
                return benchmark_performance(self.pipeline, text)
            else:
                return list(self.pipeline(text, voice=voice))
        
        def get_system_info(self):
            """Get system information relevant to performance"""
            info = {
                'platform': platform.platform(),
                'processor': platform.processor(),
                'machine': platform.machine(),
                'python_version': platform.python_version(),
                'pytorch_version': torch.__version__,
                'mps_available': torch.backends.mps.is_available(),
                'device': str(self.device) if hasattr(self, 'device') else 'unknown'
            }
            return info
    
    return AppleOptimizedKokoro

def main():
    print("🚀 Apple Silicon Kokoro TTS Optimization")
    print("=" * 50)
    
    # Check system
    if not check_apple_silicon():
        print("❌ This script is optimized for Apple Silicon Macs")
        return
    
    # Create optimized wrapper
    OptimizedKokoro = create_apple_optimized_wrapper()
    kokoro = OptimizedKokoro()
    
    # Show system info
    print("\n💻 System Information:")
    info = kokoro.get_system_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    # Test performance
    print("\n🎯 Performance Test:")
    test_text = "The Apple Neural Engine is designed to accelerate machine learning computations."
    audio_segments, processing_time = kokoro.synthesize(test_text, benchmark=True)
    
    print(f"\n📝 Summary:")
    print(f"   • Processed {len(audio_segments)} audio segments")
    print(f"   • Total processing time: {processing_time:.2f}s")
    print(f"   • Optimized for Apple Silicon M1 Pro")
    print(f"   • Using: {info['device']}")
    
    # Save audio
    import soundfile as sf
    full_audio = torch.cat([torch.tensor(audio) for _, _, audio in audio_segments])
    sf.write('optimized_output.wav', full_audio.numpy(), 24000)
    print(f"   • Audio saved as 'optimized_output.wav'")

if __name__ == "__main__":
    main() 