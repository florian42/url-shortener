import json
import os
from typing import Dict, Optional, Any
from unittest import TestCase

import boto3
import pytest
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.typing.lambda_client_context import LambdaClientContext
from aws_lambda_powertools.utilities.typing.lambda_cognito_identity import LambdaCognitoIdentity
from moto import mock_dynamodb2
from url import ShortUrl


@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'


def build_apigw_event(path: str, body: Optional[Dict[str, any]] = None, http_method: Optional[str] = "GET",
                      query_string_parameters=None):
    """ Generates API GW Event"""

    if query_string_parameters is None:
        query_string_parameters = {}
    return {
        "body": json.dumps(body),
        "resource": "/{proxy+}",
        "requestContext": {
            "resourceId": "123456",
            "apiId": "1234567890",
            "resourcePath": "/{proxy+}",
            "httpMethod": "POST",
            "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
            "accountId": "123456789012",
            "identity": {
                "apiKey": "",
                "userArn": "",
                "cognitoAuthenticationType": "",
                "caller": "",
                "userAgent": "Custom User Agent String",
                "user": "",
                "cognitoIdentityPoolId": "",
                "cognitoIdentityId": "",
                "cognitoAuthenticationProvider": "",
                "sourceIp": "127.0.0.1",
                "accountId": "",
            },
            "stage": "prod",
            "functionName": "bla"
        },
        "queryStringParameters": query_string_parameters,
        "headers": {
            "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
            "Accept-Language": "en-US,en;q=0.8",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Mobile-Viewer": "false",
            "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
            "CloudFront-Viewer-Country": "US",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "X-Forwarded-Port": "443",
            "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "Cache-Control": "max-age=0",
            "User-Agent": "Custom User Agent String",
            "CloudFront-Forwarded-Proto": "https",
            "Accept-Encoding": "gzip, deflate, sdch",
        },
        "pathParameters": {"proxy": "/examplepath"},
        "httpMethod": http_method,
        "stageVariables": {"baz": "qux"},
        "path": path,
    }


class MockContext(LambdaContext):
    def __init__(self):
        self._function_name = "Test"
        self._function_version = "V1"
        self._invoked_function_arn = "arn"
        self._memory_limit_in_mb = 1024
        self._aws_request_id = "1234"
        self._log_group_name = "log group"
        self._log_stream_name = "log stream"
        self._identity = LambdaCognitoIdentity()
        self._client_context = LambdaClientContext()


def create_urls_table(dynamo_db):
    table = dynamo_db.create_table(
        TableName='urls',
        KeySchema=[
            {
                'AttributeName': 'name',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'url',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'name',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'url',
                'AttributeType': 'S'
            }
        ]
    )

    # Wait until the table exists.
    table.meta.client.get_waiter('table_exists').wait(TableName='urls')
    assert table.table_status == 'ACTIVE'

    return table


@mock_dynamodb2
class TestLambdaHandler(TestCase):
    def setUp(self):
        """
        Create database resource and mock table
        """
        self.dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
        self.table = create_urls_table(self.dynamodb)

    def tearDown(self):
        """
        Delete database resource and mock table
        """
        self.table.delete()
        self.dynamodb = None

    def test_get_urls(self):
        from shorten_url_function import app
        short_url = ShortUrl(name="mock", url="https://flo.fish")
        self.table.put_item(Item=short_url.dict())

        ret = app.lambda_handler(build_apigw_event("/urls", query_string_parameters={"segments": "1"}), MockContext())
        data = json.loads(ret["body"])

        assert ret["statusCode"] == 200
        assert data == [short_url.dict()]


def test_create_url():
    from shorten_url_function import app
    url = ShortUrl(url="https://flo.fish", name="flo")
    ret = app.lambda_handler(build_apigw_event("/urls", http_method="POST", body=url.dict()), MockContext())
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data == url
