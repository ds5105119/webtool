class AuthData:
    def __init__(self, identifier: str | None, scope: list[str] | None = None, extra: dict | None = None):
        self.identifier = identifier
        self.scope = scope
        self.extra = extra

    def get_identifier(self):
        """
        Extracts a unique identifier from the authenticated data.

        Returns:
            String identifier
        """
        return self.identifier

    def get_scope(self):
        """
        Extracts a scope from the authenticated data.

        Returns:
            list of scope
        """
        return self.scope
