
# Project Title

This project consists of two major services

    1. A web server that runs lobbies of speed checkers, reporting usage data and postgame results to a kafka server.
    2. An event consumer that reads these kafka events and saves the data of each event as CSV files.

This project was created as a final project to Microservices and Cloud Computing.

## How to Run

The project is designed in such a way that you can run it right out of the box with docker-compose. Just go to the directory where you cloned this repo's contents and then use docker-compose.

Of course, you can adjust the arguments of each dockerfile as needed.

The Dockerfiles in each folder can be edited to change the execution of the game server and event consumer. The only positional argument for each of them is the config file name, while the rest are keyword arguments.

If you intend to put this server under nginx (not included in this project), it's recommended that you use IP hashing. That way if you use multiple instances of this project at once, all REST endpoint calls from a given user will go to the same server, which is essential to play the game.

### Config File

Both services have identical copies of the same .ini config file. It's also the only positional argument when executing each service. The following variables are searched inside the file.

#### `bootstrap.servers`
This is the address of the confluent-kafka server that the producer and consumer will connect to. If you plan to run this in docker-compose, don't change the address already in the file.

#### `group.id`

This is the kafka group where the producer will produce events (and the consumer will consume events). You can change this as long as both the server and consumer match.

#### `event.topic`

This is the name of the topic that will be used to send/receive events related to the input/output of each REST endpoint. Again, keep this consistent on both sides

#### `postgame.topic`

This is the name of the topic to send/receive events related to postgame data colection. Keep this consistent on both sides.

#### `game.timer`

This is the number of seconds each player starts with when a game is created. Only the game server uses this variable.

#### `waitress.threads`

This is the number of threads Waitress should use to handle REST API calls. Onlt the game server uses this.

### Game Server Keyword Arguments

Besides the config file, the game server also has a few keyword arguments to customize the server's execution. 

#### `--ip <address>`

The address the server should bind to. If not specified, localhost is chosen. The Dockerfile has it currently set to 0.0.0.0, which should resolve to localhost if you try to access the web server on the same machine.

#### `--port <port>`

The port to bind the server to. If not specified, 8080 is chosen.

#### `--producer_id <name>`

The name the server should use when producing kafka events. If not specified, a random string 5 characters long is created.

#### `--no_blanks`

Normally, all endpoint results are pushed as events, even the abridged events that occur when the user asks for the state of the game when nothing has changed. If this flag is set, these smaller, redundant results are not reported to kafka.


### Event Consumer Keyword Arguments

The event consumer has one keyword argument

#### `--watch_topics <mode>`

The config file indicates what topics are available, but you can further choose which topics the consumer actually listens to.

There are 3 modes you can choose.

| Parameter | Description                       |
| :-------- | :-------------------------------- |
| `0`      | **Default if not specified**. Listen to both the endpoint events topic and the postgame results topic. |
| `1`      | Listen only to the endpoint events topic |
| `2`      | Listen only to the postgame results topic |


## Docker Volume and CSV files

The event consumer saves event data as CSV files into a records folder. If run through docker-compose, a volume will be created that will hold these files.

Note for each type that a ? means that the data could be null (or, pandas.NA if loading into a dataframe)

### Center_data.csv

This file sorts the data of every endpoint event in chronological order. The actual data for each event is in their respective tables.

| Column | Type | Description                       |
| :-------- | :--- | :-------------------------------- |
| `id`      | `int` | The ID of the event. IDs are unique within each event type, **but not** unique within this center table as a whole. |
| `server-name` | `string` | The name of the server that produced this event. |
| `event-type` | `string` | The type of event (and by extension, which table the event's actual data is in). |
| `date`     | `Timestamp` | The date and time at which this event was produced. |

### Root_events.csv

This file holds the data of every time a user has accessed the root endpoint, whether to load the page or request a new game.

| Column | Type | Description                       |
| :-------- | :--- | :-------------------------------- |
| `id`      | `int` | The unique ID of the event. |
| `server-name` | `string` | The name of the server that produced this event. |
| `date`     | `Timestamp` | The date and time at which this event was produced. |
| `action`     | `string` | Indicates what action was done when accessing this endpoint. Possible values are "Sent HTML" or "Issued Credentials" |
| `issued-key`     | `string?` | The authentication key that the user was given when setting them up with a new game. Not used if the action event was "Send HTML" |
| `issued-team`     | `string?` | The team that the user was assigned when setting them up with a new game. Possible values are "red" and "black". Not used if the action event was "Send HTML" |
| `issued-game`     | `string?` | The ID of the game that the user was designated. Not used if the action event was "Send HTML" |

### Get_state_events.csv

This file holds the data of every time a user has accessed the get_state endpoint.

| Column | Type | Description                       |
| :-------- | :--- | :-------------------------------- |
| `id`      | `int` | The unique ID of the event. |
| `server-name` | `string` | The name of the server that produced this event. |
| `date`     | `Timestamp` | The date and time at which this event was produced. |
| `key`     | `string` | The authentication key the player used. |
| `input-state-id`     | `string?` | The ID of the state the user had stored locally. |
| `game`     | `string?` | The ID of the game the user accessed. |
| `error`     | `string?` | The error message returned, if there was an error. |
| `board-state-data`     | `string?` | The compound string of board data returned to the user, delimited by semicolons. Not included if the user already had up-to-date information |
| `board-state-id`     | `string?` | The ID of the new state returned to the user. Not included if the user already had up-to-date information. |
| `red-timer`     | `int` | The number of seconds remaining on red team's timer.  |
| `black-timer`     | `int` | The number of seconds remaining on black team's timer.  |
| `victor`     | `string?` | The team that was declared the winner. Possible values are "red" or "black". Not included if no winner was declared yet.  |

### Attempt_move_events.csv

This file holds the data of every time a user has accessed the attempt_move endpoint.

| Column | Type | Description                       |
| :-------- | :--- | :-------------------------------- |
| `id`      | `int` | The unique ID of the event. |
| `server-name` | `string` | The name of the server that produced this event. |
| `date`     | `Timestamp` | The date and time at which this event was produced. |
| `key`     | `string` | The authentication key the player used. |
| `game`     | `string` | The ID of the game the user accessed. |
| `from-x`     | `int` | The current X coordinate of the piece the user intends to move. |
| `from-y`     | `int` | The current Y coordinate of the piece the user intends to move. |
| `to-x`     | `int` | The X coordinate to which the user wants to move the piece. |
| `to-y`     | `int` | The Y coordinate of the piece the user intends to move. |
| `successful`     | `bool` | Indicates True if the movement was a success, False if not |
| `error`     | `string?` | The error message returned, if there was an error. |


### Suggest_move_events.csv

This file holds the data of every time a user has accessed the suggest_move endpoint.

| Column | Type | Description                       |
| :-------- | :--- | :-------------------------------- |
| `id`      | `int` | The unique ID of the event. |
| `server-name` | `string` | The name of the server that produced this event. |
| `date`     | `Timestamp` | The date and time at which this event was produced. |
| `key`     | `string` | The authentication key the player used. |
| `game`     | `string?` | The ID of the game the user accessed. |
| `x`     | `int` | The current X coordinate of the piece the user intends to move. |
| `y`     | `int` | The current Y coordinate of the piece the user intends to move. |
| `options`     | `str` | A string representation of every coordinate pair the user could move to with that checker |
| `error`     | `string?` | The error message returned, if there was an error. |


### Postgame_info.csv

This file holds the data of every game that ended.

| Column | Type | Description                       |
| :-------- | :--- | :-------------------------------- |
| `id`      | `int` | The unique ID of the event. |
| `server-name` | `string` | The name of the server that produced this event. |
| `date`     | `Timestamp` | The date and time at which this event was produced. |
| `game`     | `string` | The ID of the game that ended. |
| `winner`     | `string` | The team that won. Possible values are "red" or "black" |
| `red-timer`     | `int` | The number of seconds remaining on red team's timer.  |
| `black-timer`     | `int` | The number of seconds remaining on black team's timer.  |
| `starting-timer`     | `int` | The number of seconds each team started with.  |
| `red-plain`     | `int` | The number of regular checkers red team had remaining.  |
| `red-king`     | `int` | The number of king checkers red team had remaining.  |
| `black-plain`     | `int` | The number of regular checkers black team had remaining.  |
| `black-king`     | `int` | The number of king checkers black team had remaining.  |


Thanks to readme.so for helping create a readme file
