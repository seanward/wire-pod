#!/bin/bash
source /Users/sward/miniconda3/etc/profile.d/conda.sh  # Typically found in your Conda installation’s root: e.g., ~/miniconda3/etc/profile.d/conda.sh
conda activate vector
python /Users/sward/src/wire-pod/chipper/plugins/agent/agent.py -t "$@"
