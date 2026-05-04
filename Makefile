.PHONY: build clean install

build:
	pyinstaller --onefile --name agent-wiki main.py
	@echo "Binary: dist/agent-wiki"

clean:
	rm -rf dist/ build/ agent-wiki.spec

install: build
	cp dist/agent-wiki /usr/local/bin/agent-wiki
	@echo "Installed to /usr/local/bin/agent-wiki"
