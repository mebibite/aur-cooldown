PREFIX  ?= /usr/local
DESTDIR ?=
BINDIR   = $(DESTDIR)$(PREFIX)/bin
SHAREDIR = $(DESTDIR)$(PREFIX)/share/aur-cooldown
ZSHCOMP  = $(DESTDIR)$(PREFIX)/share/zsh/site-functions
BASHCOMP = $(DESTDIR)$(PREFIX)/share/bash-completion/completions

.PHONY: install uninstall check test

install:
	install -Dm755 aur-cooldown                    $(BINDIR)/aur-cooldown
	install -Dm644 contrib/nudge.sh                $(SHAREDIR)/nudge.sh
	install -Dm644 contrib/yay-init.lua            $(SHAREDIR)/yay-init.lua
	install -Dm644 contrib/packages.example        $(SHAREDIR)/packages.example
	install -Dm644 contrib/revoked.example         $(SHAREDIR)/revoked.example
	install -Dm644 contrib/denylist-feeds.example  $(SHAREDIR)/denylist-feeds.example
	install -Dm644 contrib/config.example          $(SHAREDIR)/config.example
	install -Dm644 contrib/completions/_aur-cooldown       $(ZSHCOMP)/_aur-cooldown
	install -Dm644 contrib/completions/aur-cooldown.bash   $(BASHCOMP)/aur-cooldown
	@echo
	@echo 'Installed. Finish per-user setup with:  aur-cooldown setup'
	@echo '(preview it first with:  aur-cooldown setup --print)'

uninstall:
	rm -f  $(BINDIR)/aur-cooldown
	rm -f  $(ZSHCOMP)/_aur-cooldown
	rm -f  $(BASHCOMP)/aur-cooldown
	rm -rf $(SHAREDIR)

check:
	python -m py_compile aur-cooldown && echo OK

test:
	python -m pytest
