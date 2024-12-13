FROM python:3.12
COPY requirements.txt .
COPY DBS.py .
COPY errite ./errite/
COPY config.json .
COPY rabbit.json .
COPY db.json .
COPY client.json .
COPY redis.json .
COPY twilio.json .
RUN pip install -r requirements.txt
CMD ["python", "DBS.py"]