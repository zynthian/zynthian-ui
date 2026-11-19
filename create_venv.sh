#!/bin/bash

python3 -m venv --system-site-packages venv
source venv/bin/activate
python -m pip install --upgrade pip
if [[ "$1" == "all" ]]; then
	pip install -r requirements_all.txt
else
	pip install -r requirements.txt
fi
