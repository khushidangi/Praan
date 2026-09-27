#!/usr/bin/env python3
"""Launch script for Praan safety system."""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def run_backend(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI backend server."""
    import uvicorn
    print(f"Starting Praan backend on http://{host}:{port}")
    print(f"Field Unit Dashboard: http://{host}:{port}/dashboard")
    print(f"City Layer Dashboard: http://{host}:{port}/city")
    print(f"API Documentation: http://{host}:{port}/docs")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


def run_tests():
    """Run the test suite."""
    import pytest
    print("Running Praan test suite...")
    sys.exit(pytest.main(["-v", "tests/"]))


def run_simulated_probe(scenario: str = "safe"):
    """Run simulated probe in standalone mode."""
    from backend.simulated_probe import SimulatedProbe
    import time
    import json
    
    probe = SimulatedProbe(scenario=scenario)
    print(f"Simulated probe started (scenario: {scenario})")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            frame = probe.read_frame()
            print(json.dumps(frame, indent=2))
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Praan: Pre-entry safety intelligence system"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Backend command
    backend_parser = subparsers.add_parser("backend", help="Run the backend server")
    backend_parser.add_argument("--host", default="0.0.0.0", help="Host address")
    backend_parser.add_argument("--port", type=int, default=8000, help="Port number")
    
    # Test command
    subparsers.add_parser("test", help="Run test suite")
    
    # Simulated probe command
    probe_parser = subparsers.add_parser("probe", help="Run simulated probe")
    probe_parser.add_argument(
        "--scenario",
        choices=["safe", "h2s_buildup", "o2_depletion", "sensor_fault", "mixed_hazard"],
        default="safe",
        help="Simulation scenario"
    )
    
    args = parser.parse_args()
    
    if args.command == "backend":
        run_backend(host=args.host, port=args.port)
    elif args.command == "test":
        run_tests()
    elif args.command == "probe":
        run_simulated_probe(scenario=args.scenario)
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python run.py backend     # Start the backend server")
        print("  python run.py test        # Run tests")
        print("  python run.py probe       # Run simulated probe standalone")


if __name__ == "__main__":
    main()
