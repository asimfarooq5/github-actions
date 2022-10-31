setup:
	python3 -m venv venv
	. ./venv/bin/activate ; pip install -r requirements-dev.txt

run:
	. ./venv/bin/activate; python3 main.py

install:
	python3 -m venv venv
	. ./venv/bin/activate; pip install -r requirements.txt

wamprocks:
	wamprocks start

flake8:
	. ./venv/bin/activate; flake8 wampapi/ sample_app/

mypy:
	. ./venv/bin/activate; mypy wampapi/ sample_app/

black-check:
	. ./venv/bin/activate; black --check ./

black:
	. ./venv/bin/activate; black ./

lint: | flake8 mypy black
