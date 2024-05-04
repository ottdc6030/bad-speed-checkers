FROM python:3.10

EXPOSE 8080

WORKDIR /event-consumer

COPY requirements.txt /event-consumer
COPY event_consumer.py /event-consumer
COPY event_data.py /event-consumer

COPY random_string.py /event-consumer
COPY server_config.ini /event-consumer

RUN pip install -r requirements.txt

CMD ["python", "-u", "event_consumer.py", "server_config.ini"]