.PHONY: build test install clean

build:
	cargo build --release
	@echo "Binary: target/release/agent-wiki"

test:
	cargo test

install: build
	cp target/release/agent-wiki /usr/local/bin/agent-wiki
	@echo "Installed to /usr/local/bin/agent-wiki"

clean:
	cargo clean
