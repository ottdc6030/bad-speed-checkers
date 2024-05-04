from argparse import ArgumentParser, FileType
from configparser import ConfigParser
from operator import itemgetter
from typing import Literal
from flask import Flask, request, render_template
from threading import Thread, Event, Lock

from waitress import serve

from game_logic import State

from producer_thread import ProducerThread

from random_string import random_string, verify_string

import signal

app = Flask(__name__)
app.url_map.strict_slashes = False

active_games:list[State] = []
started_games:list[State] = [] #The difference: started games literally just got activated, so they should be spared a second to allow red player their full time.


games_by_key: dict[str, State] = dict()

waiting_game:State | None = None #Variable for a game where only one person has joined so far. It takes two to play.
waiting_lock = Lock() #Can't haven multiple threads reading/writing to the same variable at the same time.

producer = None

@app.after_request
def add_headers(response):
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With"
    response.headers['Access-Control-Allow-Methods'] = "POST, GET"
    return response



@app.route("/get_state/<key>/", methods=["GET"])
@app.route("/get_state/<key>/<user_state_id>", methods=["GET"])
def get_state(key, user_state_id=None):
    """
    Endpoint for existing players to get the newest state of their game.\n
    user_state_id is the passed by the user so the server knows whether their game board is up to date (and thus if they need to send a new board)
    """

    game = games_by_key.get(key)

    if game is None:
        producer.called_get_state(key, user_state_id)
        return {"error": "Access Denied"}, 403

    response, call_winner_event = game.to_dict(user_state_id)
    producer.called_get_state(key, user_state_id, game, response)
    
    # If the winner was just calculated, we need an event for that too
    if call_winner_event:
        if "state" not in response:
            response["state"] = game.to_dict()[0]["state"]
        producer.declare_winner(game, response)

    return response, 200


move_destructor = itemgetter("key","old_x","old_y","new_x","new_y")

@app.route("/attempt_move", methods = ["POST"])
def attempt_move():
    """
    Endpoint for existing players requesting to move a checker from one space to another, including jumps.
    """
    try:
        key, old_x, old_y, new_x, new_y = move_destructor(request.json)
    except:
        producer.called_attempt_move(request.json,"Request Body missing fields")
        return {"error": "Invalid request"}, 400
    
    state = games_by_key.get(key)
    
    if state is None:
        producer.called_attempt_move(request.json,"Invalid Key", state)
        return {"error": "Access Denied"}, 403

    send = state.attempt_move(key, old_x, old_y, new_x, new_y)
    producer.called_attempt_move(request.json, None if send[1] == 200 else send[0], state)
    return send

suggestion_destructor = itemgetter("x","y","key")

@app.route("/suggest_moves", methods = ["POST"])
def ask_for_moves() -> tuple[dict[str, str], Literal[400,403]] | tuple[list[tuple[int, int]], Literal[200]]:
    """
    If a user clicks on a checker, this endpoint tells the user what spaces they can move to using that checker
    """
    try:
        x, y, key = suggestion_destructor(request.json)
    except:
        producer.called_suggest_moves(request.json, "Request Body missing fields")
        return {"error": "Invalid request"}, 400
    
    
    game = games_by_key.get(key)
    if game is None:
        producer.called_suggest_moves(request.json, "Invalid Key")
        return {"error": "Access Denied"}, 403
    
    moves = game.get_moves(key, x, y)
    if moves[1] == 200:
        error = None
        data = moves[0]
    else:
        error = moves[0]["error"]
        data = None
    producer.called_suggest_moves(request.json, error, game, data)
    return moves

@app.route("/", methods = ["GET", "POST"])
def handle_client():
    """
    The root endpoint. If using the GET method, the HTML page is sent.\n
    If using POST, the server will find a game for the user to join.
    """
    if request.method == "GET":
        producer.called_root()
        return render_template("game.html")
        
    global waiting_game
    with waiting_lock:
        #Existing game is waiting for a player 2. Put them there.
        if waiting_game is not None: 
            game = waiting_game
            waiting_game = None
            started_games.append(game)
            team = "black"
        #New game
        else: 
            waiting_game = State()
            game = waiting_game
            team = "red"
    
    key = game.get_keys(games_by_key)[team]
    game.join(key)

    producer.called_root(key, team, game)

    return ({
        "key": key,
        "team": team
    }, 200)


def read_args():
    """
    Handler for parsing execution arguments and reading the config file.
    """
    arg_parser = ArgumentParser()
    arg_parser.add_argument('config_file', type=FileType('r')) #File to read for more consistent values across all containers
    arg_parser.add_argument('--ip', default="localhost") #IP to run the flask server on
    arg_parser.add_argument('--port', type=int, default=8080) #Local port to bind to for the flask server
    arg_parser.add_argument('--producer_id', default=random_string(5)) #Id used to indicate that all produced events came from this specific container.
    arg_parser.add_argument('--no_blanks', action="store_true") #If set, get_state events without a change on the board (not the timer, the board) will not be sent to the producer thread.
    args = arg_parser.parse_args()

    config={
        "flask.ip": args.ip,
        "flask.port": args.port,
        "producer_id": args.producer_id,
        "no_blanks": args.no_blanks
    }

    config_parser = ConfigParser()
    config_parser.read_file(args.config_file)
    config.update(config_parser["kafka"])
    config.update(config_parser["waitress"])
    config.update(config_parser["game"])
    
    return config

def off_trigger(signum, frame):
    """
    Docker doesn't normally pass keyboard interrupts into its containers, so this thing has to exist to handle signals.
    """    
    raise KeyboardInterrupt("THIS IS NORMAL")


if __name__ == "__main__":
    config = read_args()
    State.set_default_timer(config.get("game.timer") or 360)

    stop_trigger = Event()

    signal.signal(signal.SIGTERM, off_trigger)
    
    producer = ProducerThread(stop_trigger, config)

    #background thread for running timers and purging finished games.
    def every_second_thread():
        while not stop_trigger.wait(1.0):
            purge_list:list[State] = []
            # Decrement timers for running games, removing any games that are long over.
            for game in active_games:
                if game.decrement_timer():
                    purge_list.append(game)
            
            for game in purge_list:
                active_games.remove(game)
                keys = game.get_keys()
                for key in keys.values():
                    del games_by_key[key]
            
            # Recently created games that were spared from the clock this time can be decremented next second
            while len(started_games) > 0:
                game = started_games.pop(0)
                active_games.append(game)

    second_thread = Thread(target=every_second_thread, daemon=True)
    second_thread.start()
    producer.start()

    try:
        #print(config)
        serve(app, host=config["flask.ip"], port=config["flask.port"], threads=config["waitress.threads"])
    except KeyboardInterrupt:
        print("INTERRUPT ON GAME SERVER CALLED")
        pass
    finally:
        print("FINAL ON GAME SERVER CALLED")
        stop_trigger.set()
