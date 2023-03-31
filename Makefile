# Example: make test BINARY=packages/python/cli.py
test:
	perl t/normal.t $(BINARY)
