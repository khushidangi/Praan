"""Text-to-speech pipeline using Meta MMS-TTS.

License: CC-BY-NC-4.0 (non-commercial use only)
This is acceptable for a hackathon prototype but must be replaced
with a commercially-licensed TTS for production deployment.
"""

import numpy as np
from pathlib import Path
from typing import Optional
import wave
import io


class VoiceGenerator:
    """Wraps MMS-TTS for local-language voice synthesis.

    TODO: Integrate actual MMS-TTS ONNX model when available.
    For now, uses placeholder/silence generation.
    """

    def __init__(self, model_path: Optional[Path] = None, language: str = "hi"):
        """Initialize voice generator.

        Args:
            model_path: Path to MMS-TTS ONNX model file
            language: Language code (e.g., "hi" for Hindi)
        """
        self.model_path = model_path
        self.language = language
        self.sample_rate = 16000  # MMS-TTS standard sample rate

        if model_path and model_path.exists():
            self._load_model()
        else:
            print(f"[VoiceGenerator] TTS model not found at {model_path}")
            print("[VoiceGenerator] Using silent placeholder audio")

    def _load_model(self):
        """Load MMS-TTS ONNX model (placeholder)."""
        # TODO: Load ONNX model via onnxruntime
        # import onnxruntime as ort
        # self.session = ort.InferenceSession(str(self.model_path))
        pass

    def synthesize(self, text: str, output_path: Optional[Path] = None) -> bytes:
        """Synthesize speech from text.

        Args:
            text: Text to speak
            output_path: If provided, save WAV file to this path

        Returns:
            WAV audio data as bytes
        """
        # TODO: Replace with actual TTS inference
        # For now, generate 2 seconds of silence as placeholder
        duration_sec = 2.0
        audio = self._generate_placeholder(duration_sec)

        # Convert to WAV bytes
        wav_bytes = self._to_wav_bytes(audio)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(wav_bytes)

        return wav_bytes

    def _generate_placeholder(self, duration_sec: float) -> np.ndarray:
        """Generate placeholder audio (silence with tone markers).

        In a real implementation, this would be replaced by actual TTS synthesis.
        """
        num_samples = int(duration_sec * self.sample_rate)
        
        # Generate a simple tone sequence to indicate "audio would play here"
        # 440 Hz tone for 0.1 seconds at start and end
        tone_samples = int(0.1 * self.sample_rate)
        t = np.linspace(0, 0.1, tone_samples)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        
        # Silence in the middle
        silence = np.zeros(num_samples - 2 * tone_samples, dtype=np.float32)
        
        audio = np.concatenate([tone, silence, tone])
        return audio

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert audio array to WAV format bytes."""
        # Ensure audio is in int16 range
        audio_int16 = (audio * 32767).astype(np.int16)

        # Create WAV file in memory
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return buffer.getvalue()


# ──────────────────────────────────────────────────────────────────────
# CLI testing interface
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test voice synthesis")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--output", type=Path, help="Output WAV file path")
    parser.add_argument("--language", default="hi", help="Language code")

    args = parser.parse_args()

    generator = VoiceGenerator(language=args.language)
    
    print(f"Synthesizing: {args.text}")
    audio_bytes = generator.synthesize(args.text, output_path=args.output)
    
    if args.output:
        print(f"Saved to: {args.output} ({len(audio_bytes)} bytes)")
    else:
        print(f"Generated {len(audio_bytes)} bytes of audio")
