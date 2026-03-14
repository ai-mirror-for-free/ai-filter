#!/bin/bash

# 启动 conda 环境
source /root/miniforge3/bin/activate
conda activate ai

cd /Users/yangfan/project/ai-filter
uvicorn server:app --host 0.0.0.0 --port 3300