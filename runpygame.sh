#!/bin/bash

. $CUBE_DIR/cube_env/bin/activate

trap 'kill $(jobs -p)' EXIT

./app.py &

python ./pygamegameasync.py --game "$1"
