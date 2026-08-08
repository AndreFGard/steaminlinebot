from abc import ABC, abstractmethod


class IUserRepository(ABC):
    """Data access for Telegram users and country preferences."""

    @abstractmethod
    def delete_user(self, user_id: int) -> int: ...

    # TODO: standardize a way to prefer larger countries (eg. US over Antartica, both are matches of "en")
    @abstractmethod
    def get_country_by_language(self, language: str) -> str | None:
        """Return the alpha2 country code for a language-tag match. A match is said so when the language is a prefix of such."""
        ...

    @abstractmethod
    def get_user_country(self, user_id: int) -> str | None: ...

    @abstractmethod
    def upsert_user_country(self, user_id: int, country_code: str) -> bool: ...
