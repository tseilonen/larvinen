#!/bin/bash

pkill python
python main.py "$1" >> log.txt & disown
