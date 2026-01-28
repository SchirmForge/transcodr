#!/bin/bash
# Create a small test video for testing encoding

set -e

OUTPUT_FILE="${1:-tests/fixtures/test_video.mp4}"
DURATION="${2:-10}"

echo "Creating test video..."
echo "Output: $OUTPUT_FILE"
echo "Duration: ${DURATION}s"

# Create fixtures directory if needed
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Generate test video with FFmpeg
# - 10 seconds duration
# - 1280x720 resolution
# - H.264 codec
# - Test pattern with moving timestamp

ffmpeg -y \
    -f lavfi -i testsrc=duration=${DURATION}:size=1280x720:rate=30 \
    -f lavfi -i sine=frequency=1000:duration=${DURATION} \
    -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
    -c:a aac -b:a 128k \
    "$OUTPUT_FILE"

echo "✓ Test video created: $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"

# Show video info
echo ""
echo "Video information:"
ffprobe -v quiet -print_format json -show_format -show_streams "$OUTPUT_FILE" | \
    python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Duration: {data['format']['duration']}s\"); print(f\"Size: {int(data['format']['size'])/1024/1024:.1f}MB\"); [print(f\"Codec: {s['codec_name']} ({s['codec_type']})\") for s in data['streams']]"
