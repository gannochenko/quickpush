install:
	@python -m venv .venv
	@source ./.venv/bin/activate
	@pip3 install -r requirements.txt

activate:
	@source ./.venv/bin/activate

run:
	@python ./main.py branch --f=/Users/s.gannochenko/proj/foo
