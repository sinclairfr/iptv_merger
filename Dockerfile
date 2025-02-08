FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Création du dossier data avec les bons droits
RUN mkdir -p /app/data && \
    chown -R 1000:1000 /app/data && \
    chmod 755 /app/data

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]