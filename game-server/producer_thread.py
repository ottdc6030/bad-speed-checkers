from confluent_kafka import Producer
from threading import Thread
from time import sleep
from datetime import datetime

class ProducerThread(Thread):
    """
    Wrapper thread for handling events and pushing them to kafka without blocking the REST API
    """
    
    def __init__(self, event, config):
        """
        Constructor\n
        event is the threading event used to stop the thread from running.\n
        config is a dictionary of configuration info
        """
        super().__init__()
        self.__events = []
        self.__producer = Producer({"bootstrap.servers": config["bootstrap.servers"]})
        self.__end_trigger = event
        self.__id = config["producer_id"]
        self.__event_topic = config["event.topic"]
        self.__postgame_topic = config["postgame.topic"]
        self.__no_blanks = config["no_blanks"]

    def __wrap_value(self, value):
        return "NULL" if value is None else str(value)

    def run(self):
        """
        Repeatedly checks the events array for anything that needs pushing to kafka.\n
        The loop will only end when the stop event has been fired and there are no more events left to push.
        """

        #If the shutdown event has not been fired (or if it has, but there are still messages left to push)
        while not self.__end_trigger.wait(0.1) or len(self.__events) > 0:
            do_poll = False

            while len(self.__events) > 0:
                do_poll = True
                date, topic, key, data = self.__events.pop(0)
                key_str = f"date:{date};server-name:{self.__id};event_type:{key}" 
                self.__producer.produce(topic, data, key_str)

            if do_poll:
                self.__producer.poll(10)
                self.__producer.flush()
            else:
                sleep(1)

    def add_event(self, key, data, postgame_event=False):
        """
        Adds an event to the array to be sent to kafka later\n
        key is the event's key, data is the event value, and postgame_event indicates whether the event should go to the main events topic or the postgame topic.
        """

        time = datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")
        self.__events.append((time, self.__postgame_topic if postgame_event else self.__event_topic, key, data))

    def called_get_state(self, key, user_state_id, game=None, response=None):
        """
        Handler for preparing get_state events for kafka
        """

        # If we see a stateless reponse and we don't want to send those, don't include it
        if self.__no_blanks and response is not None and "state" not in response: return

        msg = f"key:{self.__wrap_value(key)};input-state-id:{self.__wrap_value(user_state_id)}"
        
        if game is not None:
            msg += f";game:{game.get_game_id()}"
        
        if response is None:
            msg += ";error:Invalid Key"
        else:
            msg += f";response:{self.__wrap_value(response)}"

        self.add_event("get-state", msg)

    def called_attempt_move(self, request, response=None, game=None):
        """
        Handler for preparing events where the player attempts to move
        """
        msg = f"request:{self.__wrap_value(request)};successful:{response is None}"
        
        if game is not None:
            msg += f";game:{game.get_game_id()}"
        
        if response is not None:
            msg += f";error:{response}"
        self.add_event("attempt-move", msg)

    def called_suggest_moves(self, request, error=None, game=None, response=None):
        """
        Handler for preparing events where the user asks for places to go
        """
        msg = f"request:{self.__wrap_value(request)}"

        if game is not None:
            msg += f";game:{game.get_game_id()}"
        
        if error is not None:
            msg += f";error:{error}"

        if response is not None:
            msg += f";options:{response}"
        self.add_event("suggest-move", msg)

    def called_root(self, key=None, team=None, game=None):
        """
        Handler for the times the player loads the page and/or asks for a new game
        """
        if key is None:
            msg = "action:Sent HTML"
        else:
            msg = f"action:Issued Credentials;issued-key:{key};issued-team:{team};issued-game:{game.get_game_id()}"
        self.add_event("root", msg)

    def declare_winner(self, game, data):
        """
        Handler for the postgame data, when a winner is declared for a game.
        """
        timers = data["timers"]
        msg = f'game:{game.get_game_id()};winner:{data["victor"]};red-timer:{timers["red"]};black-timer:{timers["black"]};starting-timer:{timers["start"]};'
        
        _, *pieces = data["state"].split(".")
        
        piece_counts = [0,0,0,0]

        for _, _, piece in pieces:
            index = int(piece)
            piece_counts[index] += 1
       
        msg += f'red-plain:{piece_counts[0]};red-king:{piece_counts[1]};black-plain:{piece_counts[2]};black-king:{piece_counts[3]}'
        self.add_event("game-winner", msg, True)
            
    
    def close(self):
        """
        Tells the thread to shut down as soon as it's done with all its current events.
        """
        self.__end_trigger.set()

