dev:
	pip install --upgrade pip pre-commit poetry
	pre-commit install

format:
	poetry run isort shorten_url_function tests
	poetry run black shorten_url_function tests

lint: format
	poetry run flake8 shorten_url_function/* tests/*

security-baseline:
	poetry run bandit --baseline bandit.baseline -r aws_lambda_powertools

complexity-baseline:
	$(info Maintenability index)
	poetry run radon mi aws_lambda_powertools
	$(info Cyclomatic complexity index)
	poetry run xenon --max-absolute C --max-modules A --max-average A aws_lambda_powertools
