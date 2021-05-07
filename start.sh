#!/bin/bash

# Kill previously running Lärvinen processes
ps aux | grep "python larvinen.py" | grep -v "grep" | awk '{print $2}' | xargs kill -15 2> /dev/null

# Start a new one
python larvinen.py "$@" &>> data/log.txt & disown
