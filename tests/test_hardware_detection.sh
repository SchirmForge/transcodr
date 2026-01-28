#!/bin/bash
# Quick system check for hardware acceleration capabilities

echo "========================================"
echo "Hardware Acceleration Detection"
echo "========================================"

echo -e "\n[1] Checking PCI Devices"
echo "----------------------------------------"
if command -v lspci &> /dev/null; then
    echo "VGA Controllers:"
    lspci | grep -i vga
    echo -e "\nDisplay Controllers:"
    lspci | grep -i display
else
    echo "⚠ lspci not found"
fi

echo -e "\n[2] Checking DRI Devices"
echo "----------------------------------------"
if [ -d /dev/dri ]; then
    echo "✓ /dev/dri exists"
    ls -la /dev/dri/
else
    echo "✗ /dev/dri not found"
fi

echo -e "\n[3] Checking NVIDIA"
echo "----------------------------------------"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi -L
else
    echo "✗ nvidia-smi not found"
fi

echo -e "\n[4] Checking AMD (ROCm)"
echo "----------------------------------------"
if command -v rocm-smi &> /dev/null; then
    rocm-smi --showproductname
else
    echo "✗ rocm-smi not found (ROCm not installed)"
fi

echo -e "\n[5] Checking VAAPI"
echo "----------------------------------------"
if command -v vainfo &> /dev/null; then
    vainfo 2>&1 | grep -E "VAProfile|error"
else
    echo "✗ vainfo not found (install: sudo apt install vainfo)"
fi

echo -e "\n[6] Checking FFmpeg hwaccels"
echo "----------------------------------------"
if command -v ffmpeg &> /dev/null; then
    ffmpeg -hwaccels 2>/dev/null
else
    echo "✗ FFmpeg not found"
fi

echo -e "\n========================================"
echo "Run 'python tests/manual_test_ffmpeg.py' for detailed analysis"
echo "========================================"
