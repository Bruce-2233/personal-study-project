FROM python:3.11
WORKDIR /app
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docker/app.py docker/app.py
COPY shoe_retrieval.py .
COPY frontend frontend
COPY shoes_images/image1 shoes_images/image1
COPY shoes_images/image2 shoes_images/image2
COPY shoes_images/image3 shoes_images/image3
COPY shoes_images/image4 shoes_images/image4
COPY shoes_images/image5 shoes_images/image5
COPY shoes_images/image6 shoes_images/image6
COPY shoes_images/cleaned_dataset/dataset.jsonl shoes_images/cleaned_dataset/dataset.jsonl
COPY shoes_images/cleaned_dataset/retrieval_evaluation_merged/queries.json shoes_images/cleaned_dataset/retrieval_evaluation_merged/queries.json
COPY shoes_images/cleaned_dataset/retrieval_evaluation_merged/qrels.txt shoes_images/cleaned_dataset/retrieval_evaluation_merged/qrels.txt
COPY model model
EXPOSE 5000
CMD ["python", "docker/app.py"]
