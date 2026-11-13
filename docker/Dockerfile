FROM python:3.11
WORKDIR /app
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docker/app.py docker/app.py
COPY frontend frontend
COPY images images
COPY index.faiss mapping.json ./
COPY model model
EXPOSE 5000
CMD ["python", "docker/app.py"]
