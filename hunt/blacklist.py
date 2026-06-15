"""Functional split of the huntproxy backend."""



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
                self.ratings[address].in_blacklist = False
                self.ratings[address].blacklist_reason = ""
                self.ratings[address].ip_blacklist_reason = ""
                self.ratings[address].ip_blacklist_hits = 0
                self.ratings[address].ip_blacklist_sources = []
                self.ratings[address].last_status = "ok"  # optimistic, will be re-checked
            self._save_blacklist()
            self._save_state()
            self._save_working_file()
            self._emit(f"Removed from blacklist: {address}", "info")

    def _load_blacklist_file(self):
            bf = self.blacklist_file
            if bf.exists():
                try:
                    for line in bf.read_text().splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split(maxsplit=1)
                        self.blacklist[parts[0]] = parts[1] if len(parts) > 1 else ""
                except Exception:
                    pass

    def _save_blacklist(self):
            with open(self.blacklist_file, "w") as f:
                f.write(f"# huntproxy blacklist (operator-curated, NOT dead proxies)\n")
                for addr, reason in sorted(self.blacklist.items()):
                    f.write(f"{addr}  {reason}\n")
