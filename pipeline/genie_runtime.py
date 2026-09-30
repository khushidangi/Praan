"""Optional local Genie runtime adapter.

The adapter is deliberately capability-detected. It never reports NPU merely because
an environment variable says so: a configured command must exist and be executable.
Template mode remains the safe offline fallback until the human exports a Genie bundle.
"""

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional


class GenieRuntime:
    """Run a locally installed Genie-compatible command when available."""

    def __init__(self, bundle_path: Optional[Path] = None):
        home = Path(os.getenv("PRAAN_HOME", Path.home() / "Praan"))
        configured_bundle = bundle_path or os.getenv("PRAAN_GENIE_BUNDLE")
        self.bundle_path = Path(configured_bundle) if configured_bundle else home / "models" / "genie"
        self.command = os.getenv("PRAAN_GENIE_COMMAND", "").strip()
        self.model = os.getenv("PRAAN_GENIE_MODEL", self.bundle_path.name)
        self.last_latency_ms: Optional[float] = None
        self.last_error: Optional[str] = None

    @property
    def command_available(self) -> bool:
        if not self.command:
            return False
        executable = shlex.split(self.command)[0]
        return bool(Path(executable).exists() or shutil.which(executable))

    @property
    def available(self) -> bool:
        return self.command_available and self.bundle_path.exists()

    @property
    def provider(self) -> str:
        if not self.available:
            return "none"
        # The runtime command is the evidence; this label describes its configured backend.
        return os.getenv("PRAAN_GENIE_PROVIDER", "CPU").upper()

    def status(self) -> Dict:
        return {
            "engine": "genie" if self.available else "template",
            "provider": self.provider,
            "model": self.model if self.available else None,
            "bundle_path": str(self.bundle_path),
            "command_configured": bool(self.command),
            "command_available": self.command_available,
            "available": self.available,
            "latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
        }

    def generate(self, prompt: str) -> str:
        if not self.available:
            raise RuntimeError("Genie bundle or local command is unavailable")
        started = time.perf_counter()
        try:
            result = subprocess.run(
                shlex.split(self.command),
                input=prompt,
                text=True,
                capture_output=True,
                timeout=float(os.getenv("PRAAN_GENIE_TIMEOUT_SECONDS", "8")),
                check=True,
            )
            self.last_latency_ms = round((time.perf_counter() - started) * 1000, 1)
            self.last_error = None
            return result.stdout.strip()
        except Exception as exc:
            self.last_latency_ms = round((time.perf_counter() - started) * 1000, 1)
            self.last_error = str(exc)
            raise
