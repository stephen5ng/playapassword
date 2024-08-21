#!/bin/bash -e

. $CUBE_DIR/cube_env/bin/activate

trap 'kill $(jobs -p)' EXIT

./app.py &

#python -X tracemalloc=5 ./pygamegameasync.py
python ./pygamegameasync.py "$1"
