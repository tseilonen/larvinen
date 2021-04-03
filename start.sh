#!/bin/bash

pkill python
python larvinen/main.py "$1" >> data/log.txt & disown
