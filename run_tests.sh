#!/bin/bash

source venv/bin/activate

export ZYNTEST_LOG=INFO
python3 -m unittest discover -s zynlibs/zynseq/tests -v

