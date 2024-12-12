FROM python:3.11
COPY requirements.txt .
COPY DBS.py .
COPY errite/ .
COPY config.json .
COPY rabbit.json .
COPY db.json .
COPY client.json .
COPY redis.json .
COPY .postgresql/ .
RUN pip install -r requirements.txt
CMD ["python", "DBS.py"]