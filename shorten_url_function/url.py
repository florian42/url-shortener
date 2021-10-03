from aws_lambda_powertools.utilities.parser import BaseModel


class ShortUrl(BaseModel):
    url: str
    name: str

