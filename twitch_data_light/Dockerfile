# ベースイメージ（軽量なPython環境）
FROM python:3.11-slim

# 環境変数（不要なpycファイルの生成防止、標準出力バッファリング無効化）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 作業ディレクトリを作成
WORKDIR /app

# 依存関係ファイルをコピーしインストール
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをすべてコピー
COPY . .

# ポートを公開（Flask/Gunicorn 用）
EXPOSE 5000

# Gunicorn でアプリを起動（アプリ名に応じて app:app）
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
