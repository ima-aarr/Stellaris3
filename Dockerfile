# Python 3.10を使用
FROM python:3.10-slim

# 作業ディレクトリ設定
WORKDIR /app

# 必要なシステムパッケージ(ffmpeg, git, opus)をインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus-dev \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# requirements.txtをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー
COPY . .

# Bot起動
CMD ["python", "main.py"]
