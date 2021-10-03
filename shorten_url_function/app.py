from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver
from aws_lambda_powertools.utilities.parser import parse, ValidationError

from url import ShortUrl

logger = Logger()
tracer = Tracer()
app = ApiGatewayResolver()  # by default API Gateway REST API (v1)


@app.get("/urls")
def get_urls():
    return ["https://awslabs.github.io/aws-lambda-powertools-python/latest/core/event_handler/api_gateway/"]


@app.post("/urls")
def create_short_url():
    try:
        parsed_payload: ShortUrl = parse(event=app.current_event.json_body, model=ShortUrl)
        return parsed_payload.dict()
    except ValidationError:
        return {
            "status_code": 400,
            "message": "Invalid payload"
        }



@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    return app.resolve(event, context)
