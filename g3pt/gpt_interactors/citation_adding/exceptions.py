from dataclasses import dataclass

from g3pt.exceptions import ScientistGPTException


@dataclass
class ServerErrorCitationException(ScientistGPTException):
    """
    Error raised server wasn't able to respond.
    """
    status_code: int
    text: str

    def __str__(self):
        return f"Request failed with status code {self.status_code}, error: {self.text}"