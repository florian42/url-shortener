from typing import Any, Dict, List

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver, Response
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, InternalServerError, NotFoundError
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from redirect_html_string import get_redirect_content
from urls_table import ShortUrl, UrlNotFoundError, UrlsTable

logger = Logger()
tracer = Tracer()
app = ApiGatewayResolver()  # by default API Gateway REST API (v1)

urls_table = UrlsTable()


@app.get("/urls")
def get_urls() -> List[Dict[str, str]]:
    try:
        return urls_table.scan_urls()
    except (ValidationError, ClientError) as error:
        raise BadRequestError(str(error))
    except Exception as error:
        raise InternalServerError(str(error))


@app.post("/urls")
def create_short_url() -> Response:
    try:
        parsed_url: ShortUrl = parse(event=app.current_event.json_body, model=ShortUrl)
        urls_table.put_url(parsed_url)
        return Response(status_code=204, body=None, content_type="application/json")
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise BadRequestError("This short url already exists, only admins can edit.")
        raise BadRequestError(str(error))
    except ValidationError as error:
        raise BadRequestError(str(error))
    except Exception as error:
        raise InternalServerError(str(error))


@app.get("/<url_alias>")
def get_short_url(url_alias: str) -> Response:
    try:
        short_url = urls_table.get_url(url_alias)
        custom_headers = {
            "Location": short_url.url,
            "Cache-Control": "max-age=0, public, s-max-age=900, stale-if-error: 86400",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        }
        return Response(
            status_code=301, content_type="text/html", headers=custom_headers, body=get_redirect_content(short_url.url)
        )
    except UrlNotFoundError as error:
        raise NotFoundError(str(error))
    except (ValidationError, ClientError) as error:
        raise BadRequestError(str(error))
    except Exception as error:
        raise InternalServerError(str(error))


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext) -> Dict[str, Any]:
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    return app.resolve(event, context)
