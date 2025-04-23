# votebot

A slack bot for managing elections (and voting)

## Installation
Automatically: `./install.sh`

OR manually:
```bash
python3 -m venv venv
source ./venv/bin/activate
python3 -m pip install -r requirements.txt
```

Requires the copying of `.env.template` to `.env` then filling out all keys.

## Usage
In the background: `./start.sh` 
- Equivalent to `source ./venv/bin/activate && nohup python3 app.py &`, requires `nohup`

In the foreground: `source ./venv/bin/activate && python3 app.py`

## Commands
- `/vote-create`: Create an election
- `/vote-confirm`: Confirm a vote was counted
- `/vote-check`: Check the current results of an election
- `/vote-help`: Help with using votebot

## Source Code
https://github.com/Formula-Electric-Berkeley/votebot