# --- Base Image ---
FROM python:3.13-slim

# --- Set UTF-8 locale for proper °C etc. ---
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# --- Create app directory ---
WORKDIR /app

# --- Install dependencies ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy the source code ---
COPY main.py config.json /app/

# --- Use non-root user for safety (optional but recommended) ---
RUN useradd -m appuser
USER appuser

# --- Run the app ---
CMD ["python", "main.py"]