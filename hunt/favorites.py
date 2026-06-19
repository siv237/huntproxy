"""Functional split of the huntproxy backend."""

from hunt.constants import logger


class FavoritesMixin:
    def favorite_add(self, address: str):
            if not address:
                return
            self.favorites.add(address)
            if address in self.ratings:
                self.ratings[address].is_favorite = True
            self._save_favorites()
            self._save_state()
            self._emit(f"Added to favorites: {address}", "info")

    def favorite_remove(self, address: str):
            self.favorites.discard(address)
            if address in self.ratings:
                self.ratings[address].is_favorite = False
            self._save_favorites()
            self._save_state()
            self._emit(f"Removed from favorites: {address}", "info")

    def _save_favorites(self):
            """Save favorites to DB."""
            try:
                conn = self._db()
                conn.execute("DELETE FROM favorites")
                conn.executemany(
                    "INSERT OR REPLACE INTO favorites (address) VALUES (?)",
                    [(addr,) for addr in self.favorites],
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"save_favorites db: {e}")
