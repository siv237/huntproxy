"""Functional split of the huntproxy backend."""

from hunt.constants import logger


class BlacklistMixin:
    def blacklist_add(self, address: str, reason: str = ""):
            if not address:
                return
            self.blacklist[address] = reason or "manual"
            if address in self.ratings:
                self.ratings[address].in_blacklist = True
                self.ratings[address].blacklist_reason = reason or "manual"
            self._save_blacklist()
            self._save_state()
            self._save_working_file()
            self._emit(f"Blacklisted: {address} — {reason or 'manual'}", "warn")

    def blacklist_remove(self, address: str):
            self.blacklist.pop(address, None)
            if address in self.ratings:
                r = self.ratings[address]
                r.in_blacklist = False
                r.blacklist_reason = ""
                # Do NOT clear downloaded IP blacklist status; that is independent.
                # Re-apply IP blacklist in case egress IP is still banned.
                if r.egress_ip:
                    self._apply_ip_blacklist_to_proxy(address, r.egress_ip)
                elif r.ip_blacklist_reason:
                    # Re-evaluate; if the IP blacklist is still loaded, reason is
                    # restored, otherwise it is cleared.
                    self._apply_ip_blacklist_to_proxy(address, r.egress_ip)
            self._save_blacklist()
            self._save_state()
            self._save_working_file()
            self._emit(f"Removed from blacklist: {address}", "info")

    def _load_blacklist_file(self):
            """Load blacklist from DB (called as fallback if not loaded in _load_state)."""
            try:
                conn = self._db()
                for row in conn.execute("SELECT address, reason FROM blacklist"):
                    addr = row["address"]
                    self.blacklist[addr] = row["reason"] or ""
                    if addr in self.ratings:
                        self.ratings[addr].in_blacklist = True
                        self.ratings[addr].blacklist_reason = self.blacklist[addr]
                conn.close()
            except Exception as e:
                logger.error(f"load_blacklist db: {e}")

    def _save_blacklist(self):
            """Save blacklist to DB."""
            try:
                conn = self._db()
                conn.execute("DELETE FROM blacklist")
                conn.executemany(
                    "INSERT INTO blacklist (address, reason) VALUES (?, ?)",
                    [(addr, reason or "") for addr, reason in self.blacklist.items()],
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"save_blacklist db: {e}")
