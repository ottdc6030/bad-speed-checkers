RED_PIECE = 0
RED_KING = 1
BLACK_PIECE = 2
BLACK_KING = 3

RED_TEAM = 0
BLACK_TEAM = 1

EVEN_ROWS = (0,2,4,6)
ODD_ROWS = (1,3,5,7)


WAITING_RED = 0 #Waiting for red player to join
WAITING_BLACK = 1 #Waiting for black player to join
RUNNING = 2 #Active game
ENDED = 3 #Game over

from typing import Literal

from random_string import random_string


def timer_string(value):
    """
    Turns the value into a MM:SS string. enough said.
    """
    minutes = value // 60
    seconds = value % 60
    return str(minutes) + ":" + str(seconds).rjust(2,"0")


class State:
    
    __starting_timer = 360

    def set_default_timer(timer):
        State.__starting_timer = int(timer)

    def __init__(self):
        self.__grid = [] # 8x8 2-d array holding the state of the board.
        self.__timers = [State.__starting_timer, State.__starting_timer] # timers for each person. Slot 0 belongs to red, 1 to black.
        self.__whose_turn = RED_TEAM
        self.__jump_only_location = None #If someone is chaining jumps, this records where that jumping checker is, so the user ONLY can go again on that checker.
        self.__keys = None
        self.__phase = WAITING_RED
        self.__remaining_pulses = 4 # Tracker so a game's data doesn't immediately vanish on completion. We want the users to be able to see that they won/lost.
        self.__state_id = random_string(13)
        self.__spare_a_second = False
        self.__victor = None
        self.__game_id = random_string(13)


        # Starting initial state. 3 rows of checkers, each side at the back from their perspective.
        for i in range(8):
            self.__grid.append([None] * 8)

        for i in EVEN_ROWS:
            self.__grid[0][i] = RED_PIECE
            self.__grid[2][i] = RED_PIECE
            self.__grid[-2][i] = BLACK_PIECE

        for i in ODD_ROWS:
            self.__grid[1][i] = RED_PIECE
            self.__grid[-1][i] = BLACK_PIECE
            self.__grid[-3][i] = BLACK_PIECE  

    def get_game_id(self):
        return self.__game_id

    def get_keys(self, game_map=None) -> dict[Literal["red", "black"], str]:
        """
        Creates or generates a dict of keys for each team. Players must use these keys in order to play.\n
        game_map is a map with all the currently-used keys inside. Good for preventing duplicates.
        """    
        if self.__keys is not None:
            return {
                "red": self.__keys[0],
                "black": self.__keys[1],
            }
        
        red_key = None
        black_key = None

        while red_key is None or black_key is None:
            key = random_string()
            if game_map is not None:
                if key in game_map: continue
                game_map[key] = self
                
            if red_key is None:
                red_key = key
            else:
                black_key = key

        self.__keys = [red_key, black_key]

        return {
            "red" : red_key,
            "black": black_key
        }
    
    def join(self, key):
        """
        Confirms that a player is ready to play.
        Returns True if the user's key is valid for this game, false if not.
        """
        try:
            index = self.__keys.index(key)
        except ValueError:
            return False

        if (self.__phase == WAITING_RED and index == 0) or (self.__phase == WAITING_BLACK and index == 1):
            self.__phase += 1
        return True



    def decrement_timer(self):
        """
        Lowers the timer for whoever's turn it currently is.\n
        If the game is already over, the pre-destruction timer is decremented instead\n
        Returns true if the game should be destroyed and removed from the main map, false if not.
        """
        if self.__phase < RUNNING: return False

        if self.__phase == ENDED:
            self.__remaining_pulses -= 1
            return self.__remaining_pulses < 0
        
        # Don't decrement if the turn literally just changed
        if self.__spare_a_second:
            self.__spare_a_second = False
            return False

        team = self.__whose_turn
        value = self.__timers[team] - 1
        self.__timers[team] = value

        if value == 0:
            self.__phase = ENDED

        return False
    

    def get_winner(self) -> tuple[Literal["red","black"], bool] | None:
        """
        Calculates the winner based on the timers (or if the timers are fine, the game board.)\n
        If there's no winner yet, returns None\n
        If there is, the first returned value is the team that won. The second value is a boolean that indicates if the result was just now calculated (true), or previously saved (false)
        """
        if self.__victor is not None:
            return "red" if self.__victor == 0 else "black", False

        #Check for disqualifications by timer
        red_timer, black_timer = self.__timers
        if red_timer <= 0 and black_timer <= 0: return -1, None #Ideally, -1 should never be returned.
        if red_timer <= 0: 
            self.__victor = 1
            self.__phase = ENDED
            return "black", True
        if black_timer <= 0: 
            self.__victor = 0
            self.__phase = ENDED
            return "red", True

        #Check for remining pieces
        red_remaining = False
        black_remaining = False

        for row in self.__grid:
            for value in row:
                if value is None: continue
                red_remaining = red_remaining or value < BLACK_PIECE
                black_remaining = black_remaining or value > RED_KING
                
                #If both players have at least one piece, the game isn't over
                if red_remaining and black_remaining: return None 

        if red_remaining: 
            self.__victor = 0
            self.__phase = ENDED
            return "red", True
        else: 
            self.__victor = 1
            self.__phase = ENDED
            return "black", True
    
    def __generate_moves(self, team, x, y) -> list[tuple[int, int]] | None:
        """
        Generates a list of all possible moves for a given user wanting to move a checker at a specific point\n
        Each tuple returned has (X, Y) coordinates.
        """
        piece = self.__grid[y][x]
        if piece is None:
            return None
        
        piece_team = piece // 2

        if team != piece_team:
            return None
        
        isKing = piece % 2 == 1

        valid_directions = []

        jump_location = self.__jump_only_location

        if jump_location is not None and (jump_location[0] != x or jump_location[1] != y): # If they just did a jump, don't let the user repeat their turn on any piece other than the one used to jump.
            return valid_directions

        for diff_x, diff_y in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            new_x = x + diff_x
            new_y = y + diff_y

            if not isKing: #Only proceed if it's in the right direction (not backwards)
                going_backwards = new_y < y if piece_team == RED_TEAM else new_y > y
                if going_backwards:
                    continue

            if new_x < 0 or new_x >= 8 or new_y < 0 or new_y >= 8: #out of bounds for regular movement, let alone a jump
                continue

            other_piece = self.__grid[new_y][new_x]

            if other_piece is None: #open spot, can be directly moved to...If we're not only looking for jump movements
                if jump_location is None: valid_directions.append((new_x,new_y))
                continue

            #At this point the regular move is invalid. What about a jump?

            if (other_piece // 2) == piece_team: #You can't jump over your own pieces
                continue

            jump_x = new_x + diff_x
            jump_y = new_y + diff_y

            if jump_x < 0 or jump_x >= 8 or jump_y < 0 or jump_y >= 8 or self.__grid[jump_y][jump_x] is not None: #is jump space out of bounds or occupied?
                continue

            valid_directions.append((jump_x,jump_y))

        return valid_directions
    

    def get_moves(self, user_key, x, y) -> tuple[dict[Literal["error"], str], Literal[400, 403]] | tuple[list[tuple[int, int]], Literal[200]]:
        """
        Gets all possible moves from a given user at a given space.
        """
        try:
            team = self.__keys.index(user_key)
        except ValueError:
            return {"error": "Access Denied"}, 403
        
        if self.__victor is not None:
            return {"error": "The game is already over"}, 400
        
        if self.__whose_turn != team:
            return {"error": "It's not your turn"}, 400
        
        list = self.__generate_moves(team, x, y) or []

        return (list, 200)

    
    def attempt_move(self, user_key, old_x, old_y, new_x, new_y) -> tuple[dict[str, str], Literal[403, 400, 200]]:
        """
        Determines if the user is allowed to move from one space to another, including jumps.
        """
        try:
            team = self.__keys.index(user_key)
        except ValueError:
            return {"error": "Access Denied"}, 403
        
        if self.__victor is not None:
            return {"error": "The game is already over"}, 400
        
        if self.__whose_turn != team:
            return {"error": "It's not your turn"}, 400
        
        is_valid = False

        moves = self.__generate_moves(team, old_x, old_y)

        if moves is not None: 
            for suggested_x, suggested_y in moves:
                if new_x == suggested_x and new_y == suggested_y:
                    is_valid = True
                    break

        if not is_valid: return {"error": "Invalid request"}, 400

        checker_value = self.__grid[old_y][old_x]
        self.__grid[old_y][old_x] = None

        if checker_value % 2 == 0 and new_y == (0 if team == BLACK_TEAM else 7): checker_value += 1 # King me

        self.__grid[new_y][new_x] = checker_value

        do_rotation = True
        
        # jump logic
        space_difference_y = new_y - old_y
        if abs(space_difference_y) == 2:
            space_difference_y //= 2
            space_difference_x = (new_x - old_x) // 2
            self.__grid[new_y - space_difference_y][new_x - space_difference_x] = None
            
            # Check to see if the user can jump again with that same piece. If so, don't switch turns and let the user jump again.
            self.__jump_only_location = (new_x, new_y)
            new_moves = self.__generate_moves(team, new_x, new_y)
        
            do_rotation = new_moves is None or len(new_moves) == 0
        
        if do_rotation:
            self.__jump_only_location = None
            self.__whose_turn = (self.__whose_turn + 1) % 2
            self.__spare_a_second = True

        self.__state_id = random_string(13) #Refresh state number on change
        return "Accepted", 200
    

    def to_dict(self, id=None):
        """
        Takes the game's state, board and timer, and returns it as a dictionary.\n
        The boolean in the return value indicates whether the winner was just calculated (true) or was previously saved (false)
        If the user passes a state id and that ID is up to date, the game board isn't sent to save time and traffic.
        """
        send = dict()
        # Only provide board data if the user's version is out of date. Less data to send.
        if self.__phase >= RUNNING and (id is None or id != self.__state_id):
            send["stateId"] = self.__state_id
            spaces = [str(self.__whose_turn)]
            for y, row in enumerate(self.__grid):
                for x, space in enumerate(row):
                    if space is not None: spaces.append(str(y) + str(x) + str(space))
            send["state"] = ".".join(spaces)

        send["timers"] = {
            "red": timer_string(self.__timers[0]),
            "black": timer_string(self.__timers[1]),
            "start": State.__starting_timer
        }

        victor = self.get_winner()
        winner_just_calculated = False

        if victor is not None:
            send["victor"] = victor[0]
            winner_just_calculated = victor[1]

        return send, winner_just_calculated
            
        
        
