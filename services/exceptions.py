"""Erros de mesclagem com mensagem amigável e detalhe técnico para log."""


class MergeError(Exception):
    """Falha controlada na validação ou no processamento."""

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        self.user_message = user_message
        self.detail = detail or user_message
        super().__init__(self.user_message)
