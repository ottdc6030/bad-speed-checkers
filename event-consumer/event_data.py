import pandas as pd
from operator import itemgetter
from pathlib import Path

import json

main_handlers = dict()
message_count = 0

def parse_timer(timer_str):
    """
    Concerts an MM:SS string into the number of seconds.
    """
    if ":" not in timer_str:
        return int(timer_str)
    minutes, seconds = timer_str.split(":")
    return (int(minutes) * 60) + int(seconds)

def make_frame(filename, columns):
    """
    Creates a dataframe with the given columns. If a file of the same name already exists, the newest id is checked to avoid duplicates.
    """
    df = pd.DataFrame({column_name: pd.Series(dtype=column_type) for column_name, column_type in columns.items()})

    filename = "/records/" + filename

    filepath = Path(filename)
    if filepath.exists():
        previous_df = pd.read_csv(filename)
        next_id = previous_df["id"].max() + 1
        add_header = False
    else:
        next_id = 0
        add_header = True

    return [df, next_id, filename, add_header]

dataframes = {
    "center": make_frame("center_data.csv", {"id": "int64", "server-name": "str", "event_type": "str", "date": "datetime64[ns]"}), #"center" is not an event type, but it keeps chronological order of every non-postgame event of all types.
    "root": make_frame("root_events.csv", {"id": "int64", "server-name": "str", "date": "datetime64[ns]","action": "str", "issued-key": "str", "issued-team": "str", "issued-game": "str"}),
    "get-state": make_frame("get_state_events.csv", {"id": "int64", "server-name": "str", "date": "datetime64[ns]", "key": "str", "input-state-id": "str","game": "str", 
                                                     "error": "str", "board-state-data": "str", "board-state-id": "str","red-timer": "float64", "black-timer": "float64", "victor": "str"}),
    "attempt-move": make_frame("attempt_move_events.csv", {"id": "int64", "server-name": "str", "date": "datetime64[ns]", "key": "str", "game": "str", "from-x": "float64", "to-x": "float64", "from-y": "float64", "to-y": "float64", "successful": "bool", "error": "str"}),
    "suggest-move": make_frame("suggest_move_events.csv", {"id": "int64", "server-name": "str", "date": "datetime64[ns]", "key": "str", "game": "str", "x": "float64", "y": "float64", "options": "str", "error": "str"}),
    "game-winner": make_frame("postgame_info.csv", {"id": "int64", "server-name": "str", "date": "datetime64[ns]", "game": "str", "winner": "str", "red-timer": "int64", "black-timer": "int64", "starting-timer": "int64", "red-plain": "int64", "red-king": "int64", "black-plain": "int64", "black-king": "int64"})
}

def reset_frames():
    """
    Erases the rows of every dataframe.
    """
    for key, data in dataframes.items():
        db, *rest = data
        dataframes[key] = [db.iloc[0:0], *rest]


def handle_get_state(value):
    """
    Additional handling for get-state events, mainly de-stringifying the response json.
    """
    response = value.pop("response", None)
    if pd.isna(response): return

    response = json.loads(response.replace("'","\""))

    board_id = response.get("stateId")
    if board_id is not None:
        value["board-state-id"] = board_id
        value["board-state-data"] = response["state"]

    timers = response.get("timers")
    if timers is not None:
        value["red-timer"] = parse_timer(timers["red"])
        value["black-timer"] = parse_timer(timers["black"])

    victor = response.get("victor")
    if victor is not None: value["victor"] = victor



def handle_attempt_move(value):
    """
    Additional handling for attempt-move events, rearranging and converting a few variables.
    """
    value["successful"] = value["successful"] == "True"
    request = value.pop("request", None)
    if pd.isna(request): return

    request = json.loads(request.replace("'","\""))
    value["key"] = request.get("key")
    value["from-x"] = request.get("old_x")
    value["from-y"] = request.get("old_y")
    value["to-x"] = request.get("new_x")
    value["to-y"] = request.get("new_y")
    
    

def handle_suggest_moves(value):
    """
    Additional handling for suggest-move events, de-stringifying the request
    """
    request = value.pop("request", None)
    if pd.isna(request): return
    request = json.loads(request.replace("'","\""))

    value["x"] = request.get("x")
    value["y"] = request.get("y")
    value["key"] = request.get("key")




def handle_postgame_result(key, value):
    """
    Handler for adding a row to the postgame dataframe
    """
    global message_count
    message_count += 1

    for timer in ["red-timer","black-timer","starting-timer"]:
        value[timer] = parse_timer(value[timer])

    value.update(key)
    append_to_frame("game-winner", value)
    


event_subhandlers = {
    "get-state": handle_get_state,
    "attempt-move": handle_attempt_move,
    "suggest-move": handle_suggest_moves,
}

def decode(value):
    """
    Takes the main data of the event string and turns it into a dictionary
    """
    if value is None: return None
    
    send = dict()

    for pair in value.decode('utf-8').split(";"):
        try:
            key, val = pair.split(":", 1)
        except:
            print("UNSPLITTABLE " + pair)
        send[key] = pd.NA if val == "NULL" else val

    return send



def append_to_frame(df_key, row_data, force_id=None):
    """
    Adds a dicationary of row data to the given dataframe.
    """
    df, next_id, *rest = dataframes[df_key]
    if force_id is not None: next_id = force_id

    row_data = {k: [v] for k, v in row_data.items()} #The requirement to wrap every value in a list is dumb, but i gotta do it
    row_data["id"] = [next_id]

    new_row = pd.DataFrame(row_data, columns=df.columns).astype(df.dtypes)
    combo = pd.concat([df, new_row], ignore_index=True)
    dataframes[df_key] = [combo, next_id + 1, *rest]
    return next_id

def handle_rest_event(key, value):
    """
    Main handler for REST API events.
    """
    event_type = key["event_type"]

    subhandler = event_subhandlers.get(event_type)
    if subhandler is not None: subhandler(value)

    global message_count
    message_count += 1

    value.update(key)
    del value["event_type"]
    
    row_id = append_to_frame(event_type, value)

    append_to_frame("center", key, row_id)


def handle_message(msg):
    """
    Takes a raw kafka event and turns it into a dataframe row to be appended to the right table.
    """

    key = decode(msg.key())
    value = decode(msg.value())

    if key is None or value is None: return

    key["date"] = pd.to_datetime(key["date"], format="%Y/%m/%d %H:%M:%S.%f")

    handler = main_handlers[msg.topic()]
    handler(key, value)

    global message_count
    if message_count > 100000: #Don't let memory clog up too much.
        message_count = 0
        save_tables(True)
    


def set_handlers(config, args):
    """
    Sets up the handlers in accordance to the config and execution arguments.
    """
    topic_arg = args.watch_topics
    
    if topic_arg != 1: main_handlers[config["postgame.topic"]] = handle_postgame_result

    if topic_arg != 2: main_handlers[config["event.topic"]] = handle_rest_event

    return [*main_handlers.keys()]


def save_tables(do_reset=False):
    """
    Writes the data in the dataframes to their respective files.\n
    If do_reset is true, the dataframes are also erased after writing
    """
    for df, _, filename, header in dataframes.values():
        print(filename + " " + str(len(df.index)))
        if len(df.index) == 0: continue #No point in writing if nothing was received.
        print("SAVING")
        df.to_csv(filename, mode="a", index=False, header=header)
    if do_reset: reset_frames()