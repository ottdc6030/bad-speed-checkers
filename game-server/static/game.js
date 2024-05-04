const preservedData = {}


const CHECKERS_KEY = "checkers-key";
const CHECKERS_TEAM = "checkers-team";
const CHECKERS_STATE_ID = "checkers-state-id";

window.addEventListener('load', onLoadGame)

/**
 * Called on page load. Get existing game information (if it exists and is still valid), or get information for a new game from the server.
 */
function onLoadGame() {
    const cachedTeam = sessionStorage.getItem(CHECKERS_TEAM), cachedKey = sessionStorage.getItem(CHECKERS_KEY);
    if (cachedTeam) preservedData[CHECKERS_TEAM] = cachedTeam;
    if (cachedKey) preservedData[CHECKERS_KEY] = cachedKey;

    preservedData.boardElement = document.getElementById("checker-board");
    preservedData.bannerElement = document.getElementById("victory-banner");
    async function newGame() {
        const response = await fetch("/", {method:"POST"})
        const data = await response.json()
        preservedData.interval = setInterval(checkState, 500);
        createBoard(data);
    };

    async function tryCurrentGame() {
        //Check state of currently-saved game.
        const response = await fetch("/get_state/" + cachedKey);
        //If success, render board, then apply state
        if (response.ok) {
            createBoard({key: cachedKey, team: cachedTeam });
            const data = await response.json();
            //console.log(data);
            refresh_state(data);
            preservedData.interval = setInterval(checkState, 500);
            return;
        }
        //If failure, clear cached credentials and run new game.
        await newGame();
    }

    //console.log(!!cachedKey)
    if (cachedKey) {
        tryCurrentGame()
    }
    else {
        newGame(); 
    }
}


/**
 * Obtains the numeric coordinates for a given checkerboard square
 * @param {HTMLElement} element The element representing a checker board square.
 * @param {boolean} xFirst If true, the X coordinate (column) will be the first element in the array. If false (default), Y (row) will be the first element instead.
 * @returns a 2-element integer array reprecenting the cell's coordinates. The order depends on the value of xFirst
 */
function extractCoordinates(element, xFirst=false) {
    const coordinate = typeof element == "string" ? element : element.id.substring(4)
    let first, second;
    if (xFirst) {
        first = 1;
        second = 0;
    }
    else {
        first = 0;
        second = 1;
    }
    return [Number.parseInt(coordinate[first]), Number.parseInt(coordinate[second])]
}


/**
 * Listener function for handling clicks on the game board
 * @param event The event containing the clicked element
 */
async function onClick(event) {
    let square = event.srcElement

    //If we clicked on the checker directly, find its square.
    while (!square.classList.contains("square")) {
        square = square.parentElement
    }

    const [row, column] = extractCoordinates(square)

    //If a highlighted square was clicked, attempt a move.
    if (square.classList.contains("highlighted")) {
        const currentCell = preservedData["selectedCell"];
        if (!currentCell) return;
        const [oldRow, oldColumn] = extractCoordinates(currentCell)

        const response = await fetch("/attempt_move", {
            headers: {
                "Content-Type": "application/json"
            },
            method: "POST",
            body: JSON.stringify({
                "key": preservedData[CHECKERS_KEY],
                "old_x": oldColumn,
                "old_y": oldRow,
                "new_x": column,
                "new_y": row
            })
        })
        purge_selection(false)
        //console.log(response)
        return
    }
   
    //If we clicked on a non-highlighted square, consult the server for possible moves.
    const response = await fetch("/suggest_moves", {
        headers: {
            "Content-Type": "application/json"
        },
        method: "POST",
        body: JSON.stringify({
            "key": preservedData[CHECKERS_KEY],
            "x": column,
            "y": row
        })
    })

    const data = await response.json()

    preservedData["selectedCell"] = data.length == 0 ? null : row + "" + column

    //Change which squares are highlighted to indicate where the selected checker can move.
    for (const cell of preservedData.boardElement.getElementsByClassName("square")) {;
        const coords = extractCoordinates(cell, true)
        cell.classList.remove("highlighted")
        
        if (response.ok && data.some(array => array[0] == coords[0] && array[1] == coords[1])) {
            cell.classList.add("highlighted")
        }
    }
    
    //console.log(data)
}


/**
 * Helper function for creating an HTML element visualizing a checker
 * @param {0 | 1 | 2 | 3} team The integer representing the checker. 0 and 1 represent red pieces (1 being a king), while 2 and 3 represent black pieces (3 being a king).
 * @returns A new HTML element to display the checker with.
 */
function create_checker(team) {
    const checker = document.createElement("div")
    checker.classList.add("checker",(team < 2 ? "red" : "black"))
    if (team % 2 == 1) {
        const kingText = document.createElement("h1")
        kingText.textContent = "K"
        checker.appendChild(kingText)
    }
    return checker;
}

/**
 * Eliminates all highlighting from all squares on the game board
 * @param {boolean} purge_children If true (default), all checker elements on the board are deleted as well (to prepare for rendering a new state)
 */
function purge_selection(purge_children=true) {
    for (const cell of preservedData.boardElement.getElementsByClassName("square")) {
        //console.log(cell.id)
        while (purge_children && cell.lastChild){
             cell.removeChild(cell.lastChild)
        }
        cell.classList.remove("highlighted")
    }
}

/**
 * Interval function used to repeatedly grab information about the game to keep the visuals somewhat real-time.
 * This is called by an interval every half-second.
 */
async function checkState() {
    const stateId = preservedData[CHECKERS_STATE_ID]
    const key = preservedData[CHECKERS_KEY];
    const result = await fetch("/get_state/" + key + (stateId ? "/" + stateId : ""));
    if (result.ok){
        refresh_state(await result.json())
    }
}

/**
 * Handles the received state of the game, rendering it to the game board as well as updating the timer.
 * @param {{stateId?: string, state?: string, timers: {"red": string, "black": string}, victor?: "red" | "black"}} param0 An object representing the data to render on the page
 * @returns 
 */
function refresh_state({stateId, state, timers, victor}) {
    if (stateId) preservedData[CHECKERS_STATE_ID] = stateId

    for (const [team, value] of Object.entries(timers)) { //TIMERS ARE ALWAYS SENT
        if (team == "start") continue
        const clock = document.getElementById(team + "clock");
        clock.innerText = value
    }

    if (victor) {
        clearInterval(preservedData.interval);
        sessionStorage.clear()
        preservedData.boardElement.removeEventListener("click", onClick)
        preservedData.bannerElement.innerText = victor == preservedData[CHECKERS_TEAM] ? "You win!" : "Better luck next time..."
        preservedData.bannerElement.style.display = null;
    }

    if (!state) return;

    if (!victor) {
        preservedData.bannerElement.style.display= "none"
    }

    purge_selection();

    const [whoseTurn, ...pieces] = state.split(".");

    const redBox = document.getElementById("redbox"), blackBox = document.getElementById("blackbox")

    const marker = document.createElement("h1");
    marker.textContent = "X";


    while (blackBox.lastChild) blackBox.removeChild(blackBox.lastChild)
    while (redBox.lastChild) redBox.removeChild(redBox.lastChild)

    if (whoseTurn == "0") {
        redBox.appendChild(marker)
    }
    else {
        blackBox.appendChild(marker)
    }

    for (const [row, column, team] of pieces) {
        const cell = document.getElementById("cell" + row + column)
        const teamNum = Number.parseInt(team)
        cell.replaceChildren(create_checker(teamNum))
    }  
}


/**
 * Function for creating the game board. In order to have the user's pieces start at the bottom, the board must be dynamically created.
 * @param {{"key": string, "team": string}} param0 an object with a property holding an identification key, and a team label.
 */
function createBoard({key, team}) {
    //console.log(key, team)
    preservedData[CHECKERS_KEY] = key
    preservedData[CHECKERS_TEAM] = team
    sessionStorage.setItem(CHECKERS_KEY, key)
    sessionStorage.setItem(CHECKERS_TEAM, team)

    let startIndex, endIndex, increment;
    
    const {boardElement} = preservedData;
    boardElement.addEventListener("click", onClick);

    //Unlikely the board would actually have children, but can't hurt to clear them out first.
    while (boardElement.lastChild) {
        boardElement.removeChild(boardElement.lastChild);
    }

    //Orientation depends on the team. The user's checkers should always start at the bottom, "facing" the user.

    const redPOV = team == "red";

    if (redPOV){
        startIndex = 7;
        endIndex = -1;
        increment = -1;
    }
    else {
        startIndex = 0;
        endIndex = 8;
        increment = 1;
    }

    for (let r = startIndex; r != endIndex; r += increment) {
        const row = document.createElement("div");
        row.className = "row"
        row.id = "row" + r
        let firstColor, secondColor;
        if ((r % 2 == 0) != redPOV) {
            firstColor = "dark"
            secondColor = "light"
        }
        else {
            firstColor = "light"
            secondColor = "dark"
        }

        const columnIdPrefix = "cell" + r;

        for (let c = startIndex, columnIncrement = increment * 2; c != endIndex; c += columnIncrement) {
            const columnOne = document.createElement("div"), columnTwo = document.createElement("div");
            columnOne.className = "square " + firstColor;
            columnTwo.className = "square " + secondColor;

            columnOne.id = columnIdPrefix + c;
            columnTwo.id = columnIdPrefix + (c+increment);

            row.appendChild(columnOne);
            row.appendChild(columnTwo);
        }

        boardElement.appendChild(row);
    }

    const redLabel = document.getElementById("redlabel"), blackLabel = document.getElementById("blacklabel");
    if (redPOV) {
        redLabel.innerText = "You";
        blackLabel.innerText = "Them";
    }
    else {
        redLabel.innerText = "Them";
        blackLabel.innerText = "You";
    }
}

