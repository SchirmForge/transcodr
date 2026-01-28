#!/bin/bash
# Verify VAAPI is working correctly

set -e

echo "========================================"
echo "VAAPI Verification"
echo "========================================"

# Check VAAPI device
echo ""
echo "1. VAAPI Devices:"
ls -la /dev/dri/

# Check VAAPI profiles
echo ""
echo "2. VAAPI Profiles:"
vainfo 2>&1 | grep -A 50 "VAProfile"

# Check FFmpeg VAAPI support
echo ""
echo "3. FFmpeg VAAPI Encoders:"
ffmpeg -hide_banner -encoders 2>&1 | grep vaapi

echo ""
echo "4. FFmpeg Hardware Acceleration:"
ffmpeg -hide_banner -hwaccels

# Test VAAPI encoding with a simple command
echo ""
echo "5. Testing VAAPI encoding (5 second test)..."
TEST_INPUT="/tmp/vaapi_test_input.mp4"
TEST_OUTPUT="/tmp/vaapi_test_output.mp4"

# Create test input if needed
if [ ! -f "$TEST_INPUT" ]; then
    echo "Creating test input video..."
    ffmpeg -y -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 \
        -c:v libx264 -preset ultrafast -crf 23 "$TEST_INPUT" 2>&1 | tail -n 3
fi

echo ""
echo "Testing CPU encoding (baseline)..."
time ffmpeg -y -i "$TEST_INPUT" -c:v libx265 -preset ultrafast -f null - 2>&1 | tail -n 10

echo ""
echo "Testing VAAPI encoding..."
time ffmpeg -y -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 \
    -i "$TEST_INPUT" -vf 'format=nv12,hwupload' \
    -c:v hevc_vaapi -qp 25 \
    -f null - 2>&1 | tail -n 10

echo ""
echo "========================================"
echo "✓ VAAPI verification complete"
echo "========================================"
echo ""
echo "If you see 'hevc_vaapi' encoder output above, VAAPI is working!"
echo "The VAAPI encoding should be faster than CPU encoding."
