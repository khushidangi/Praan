# Probe Firmware

## Hardware Status
⚠️ **Arduino hardware not yet available** - implementation pending

## Planned Implementation
- Arduino UNO or compatible board
- 4 gas sensors: H2S, CO, O2, LEL
- LED + buzzer for dead-man's-switch alert
- USB serial communication at 115200 baud
- 2-second polling interval

## Simulated Mode
For development and demo without hardware, use the simulated probe in `backend/simulated_probe.py`
