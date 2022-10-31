setup:
	python3 -m venv venv
	. ./venv/bin/activate ; pip install -r ../requirements-dev.txt

test_db:
	docker-compose -f docker-compose-test.yml up

clean:
	docker-compose -f docker-compose-test-db.yml down

pytest:
	wamprocks start & . ./venv/bin/activate; pytest -s -v

router:
	sudo snap install wamprocks

