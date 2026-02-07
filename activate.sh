#!/bin/bash
# Activate the transcodr conda environment
# Usage: source activate.sh

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Error: conda not found. Please install miniconda or anaconda."
    return 1 2>/dev/null || exit 1
fi

# Activate the environment
conda activate transcodr

# Verify activation
if [ "$CONDA_DEFAULT_ENV" = "transcodr" ]; then
    echo "✓ Activated conda environment: transcodr"
    echo "  Python: $(which python)"
    echo "  Version: $(python --version)"
else
    echo "Error: Failed to activate transcodr environment"
    echo "Create it with: conda create -n transcodr python=3.12"
    return 1 2>/dev/null || exit 1
fi
