FROM python:3.11-slim

# Install Chromium, Xvfb, and Playwright system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    xvfb \
    fonts-liberation \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxrandr2 \
    libnss3 \
    libnspr4 \
    libu2f-udev \
    && rm -rf /var/lib/apt/lists/*

# Set Chromium as the Playwright browser
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ENV DISPLAY=:99

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (uses system Chromium)
RUN playwright install chromium

# Copy application code
COPY . .

# Start Xvfb virtual display + the FastAPI server
# sleep 1 ensures Xvfb is ready before Python starts
CMD Xvfb :99 -screen 0 1280x800x24 -ac +extension RANDR & \
    sleep 1 && \
    python agent_service.py