FROM python:3.10

EXPOSE 8080

WORKDIR /game-server

COPY requirements.txt /game-server
COPY game_server.py /game-server
COPY game_logic.py /game-server
COPY producer_thread.py /game-server

ADD templates /game-server/templates/
ADD static /game-server/static/
COPY random_string.py /game-server
COPY server_config.ini /game-server

RUN pip install -r requirements.txt

CMD ["python", "-u", "game_server.py", "server_config.ini", "--ip", "0.0.0.0"]