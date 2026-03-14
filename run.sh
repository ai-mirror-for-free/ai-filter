# 启动 conda 环境
source /root/miniforge3/bin/activate
conda activate ai

uvicorn main:app --host 0.0.0.0 --port 3300