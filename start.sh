#!/bin/bash

pkill python
python larvinen/main.py "$1" >> log.txt & disown
