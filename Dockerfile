# Temel Python imajını kullan (GÜNCEL VERSİYON)
FROM python:3.9-slim-bullseye

# Çalışma dizinini /app olarak ayarla
WORKDIR /app

# Gerekli bağımlılıkları kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Flask uygulamanızın çalışacağı varsayılan port
EXPOSE 8000