.PHONY: test sample serve

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

sample:
	PYTHONPATH=src python3 scripts/build_sample.py

serve: sample
	python3 -m http.server 8080 -d web
