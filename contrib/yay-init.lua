-- aur-cooldown "wall" — yay v13 Lua hook.
-- Merge this into your ~/.config/yay/init.lua (see https://jguer.space/blog/2026-06-15-yay-v13).
--
-- Holds any AUR upgrade whose newest revision is less than 7 days old, using the
-- AUR RPC LastModified timestamp (server-set, un-forgeable). This makes `yay -Syu`
-- never pull anything younger than a week. Slow-moving packages simply wait a week
-- and then upgrade normally.
--
-- Packages that release MORE than once a week are perpetually <7d old and would be
-- pinned forever by this wall alone; the `aur-cooldown` tool advances those to the
-- newest revision that HAS already aged >= 7 days. Such packages stay listed as
-- "pre-excluded" here — that is expected.

yay.create_autocmd("UpgradeSelect", {
  desc = "hold AUR upgrades younger than 7 days",
  callback = function(event)
    local exclude = {}
    local cutoff = os.time() - (7 * 24 * 60 * 60) -- one week
    for _, pkg in ipairs(event.data.upgrades) do
      if pkg.repository == "aur" and pkg.last_modified >= cutoff then
        yay.log.warn("holding recent AUR upgrade:", pkg.name)
        table.insert(exclude, pkg.name)
      end
    end
    return { exclude = exclude, skip_menu = false }
  end,
})
