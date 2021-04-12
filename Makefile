
init:
	pip install -r requirements.txt

test:
	./run_test.sh

dist:
	python setup.py sdist

publish:
	twine upload dist/*

# install package locally
install:
	pip install -e .

.PHONY: init test


clean:
	python3 -Bc "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]"
	python3 -Bc "import pathlib; [p.rmdir() for p in pathlib.Path('.').rglob('__pycache__')]"
