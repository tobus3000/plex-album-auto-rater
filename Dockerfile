FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY plex_album_auto_rater.py .

CMD ["python", "plex_album_auto_rater.py"]
