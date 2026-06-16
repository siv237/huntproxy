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
            bf = self.blacklist_file
            if bf.exists():
                try:
                    for line in bf.read_text().splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split(maxsplit=1)
                        addr = parts[0]
                        self.blacklist[addr] = parts[1] if len(parts) > 1 else ""
                        if addr in self.ratings:
                            self.ratings[addr].in_blacklist = True
                            self.ratings[addr].blacklist_reason = self.blacklist[addr]
                except Exception:
                    pass

    def _save_blacklist(self):
            with open(self.blacklist_file, "w") as f:
                f.write("# huntproxy blacklist (operator-curated, NOT dead proxies)\n")
                for addr, reason in sorted(self.blacklist.items()):
                    f.write(f"{addr}  {reason}\n")
