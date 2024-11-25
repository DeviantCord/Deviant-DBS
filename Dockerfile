FROM python:3.11
ADD requirements.txt .
ADD DBS.py .
ADD errite/ .
ADD config.json .
ADD rabbit.json .
ADD db.json .
ADD client.json .
ADD redis.json .
ADD .postgresql/ .
RUN pip install -r requirements.txt
CMD ["python", "DBS.py"]