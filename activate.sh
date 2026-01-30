#!/bin/bash
# Activate the videotranscode conda environment
# Usage: source activate.sh

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Error: conda not found. Please install miniconda or anaconda."
    return 1 2>/dev/null || exit 1
fi

# Activate the environment
conda activate videotranscode

# Verify activation
if [ "$CONDA_DEFAULT_ENV" = "videotranscode" ]; then
    echo "✓ Activated conda environment: videotranscode"
    echo "  Python: $(which python)"
    echo "  Version: $(python --version)"
else
    echo "Error: Failed to activate videotranscode environment"
    echo "Create it with: conda create -n videotranscode python=3.12"
    return 1 2>/dev/null || exit 1
fi
