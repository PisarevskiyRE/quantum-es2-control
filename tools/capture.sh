#!/usr/bin/env bash
# Capture usbmon traffic for one action: tools/capture.sh NAME  (Ctrl+C to stop)
# Needs the wireshark group (falls back to `sg`) and the device bus number (default usbmon3).
set -euo pipefail
name="${1:?usage: tools/capture.sh NAME [usbmonN]}"
bus="${2:-usbmon3}"
out="$(dirname "$0")/../captures/${name}.pcapng"
echo "Capturing ${bus} -> ${out}  (Ctrl+C to stop)"
if id -nG | grep -qw wireshark; then
  dumpcap -i "$bus" -w "$out"
else
  sg wireshark -c "dumpcap -i $bus -w $out"
fi
