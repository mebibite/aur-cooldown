PREFIX  ?= /usr/local
DESTDIR ?=
BINDIR   = $(DESTDIR)$(PREFIX)/bin
DATADIR  = $(DESTDIR)$(PREFIX)/share/aur-cooldown

.PHONY: install uninstall setup-user check

install:
	install -Dm755 aur-cooldown $(BINDIR)/aur-cooldown
	install -Dm644 contrib/yay-init.lua          $(DATADIR)/yay-init.lua
	install -Dm644 contrib/nudge.zsh             $(DATADIR)/nudge.zsh
	install -Dm644 contrib/packages.example      $(DATADIR)/packages.example
	install -Dm644 contrib/revoked.example       $(DATADIR)/revoked.example
	install -Dm644 contrib/denylist-feeds.example $(DATADIR)/denylist-feeds.example

uninstall:
	rm -f  $(BINDIR)/aur-cooldown
	rm -rf $(DATADIR)

# Per-user integration: installs the shell nudge and seeds config templates into
# your home, then prints the two manual steps (they touch files you may already own,
# so we never edit ~/.zshrc or ~/.config/yay/init.lua for you).
setup-user:
	@data="$${XDG_DATA_HOME:-$$HOME/.local/share}/aur-cooldown"; \
	 conf="$${XDG_CONFIG_HOME:-$$HOME/.config}/aur-cooldown"; \
	 install -Dm644 contrib/nudge.zsh "$$data/nudge.zsh"; \
	 mkdir -p "$$conf"; \
	 [ -f "$$conf/packages" ]        || install -m644 contrib/packages.example      "$$conf/packages"; \
	 [ -f "$$conf/revoked" ]         || install -m644 contrib/revoked.example       "$$conf/revoked"; \
	 [ -f "$$conf/denylist-feeds.example" ] || install -m644 contrib/denylist-feeds.example "$$conf/denylist-feeds.example"; \
	 echo ""; \
	 echo "Installed nudge + config templates. Two manual steps remain:"; \
	 echo ""; \
	 echo "  1) Add to ~/.zshrc:"; \
	 echo "     [[ -f $$data/nudge.zsh ]] && source $$data/nudge.zsh"; \
	 echo ""; \
	 echo "  2) Merge the yay 'wall' hook into ~/.config/yay/init.lua:"; \
	 echo "     see contrib/yay-init.lua (or $(PREFIX)/share/aur-cooldown/yay-init.lua)"; \
	 echo ""; \
	 echo "  Then:  aur-cooldown observe   (and later)  aur-cooldown upgrade"

check:
	python -c "import ast,sys; ast.parse(open('aur-cooldown').read()); print('syntax OK')"
