import concurrent.futures
import itertools
from typing import Dict, List

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel
from boto3.dynamodb.conditions import Key

logger = Logger()


class ShortUrl(BaseModel):
    url: str
    url_alias: str


class UrlsTable:
    def __init__(self, total_segments=25):
        self._table_name = "urls"
        self._dynamodb = boto3.resource("dynamodb")
        self._urls_table = self._dynamodb.Table(self._table_name)
        self._total_segments = total_segments

    def put_url(self, url: ShortUrl):
        self._urls_table.put_item(
            Item=url.dict(),
            ConditionExpression="url_alias <> :url_alias",
            ExpressionAttributeValues={":url_alias": url.url_alias},
        )

    def get_url(self, url_alias: str) -> ShortUrl:
        response = self._urls_table.query(KeyConditionExpression=Key("url_alias").eq(url_alias))
        if len(response["Items"]) < 1:
            raise UrlNotFoundError(f"url {url_alias} hasn't been found")
        item = response["Items"][0]
        return ShortUrl(url_alias=item["url_alias"], url=item["url"])

    def scan_urls(self) -> List[Dict[str, str]]:
        return [
            ShortUrl(url=item["url"], url_alias=item["url_alias"]).dict()
            for item in parallel_scan_table(
                self._dynamodb.meta.client, self._total_segments, TableName=self._table_name
            )
        ]


def parallel_scan_table(dynamo_client, total_segments, *, TableName, **kwargs):
    """
    Generates all the items in a DynamoDB table.

    Source: https://alexwlchan.net/2020/05/getting-every-item-from-a-dynamodb-table-with-python/

    :param dynamo_client: A boto3 client for DynamoDB.
    :param TableName: The name of the table to scan.

    Other keyword arguments will be passed directly to the Scan operation.
    See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.scan

    This does a Parallel Scan operation over the table.

    """
    # How many segments to divide the table into?  As long as this is >= to the
    # number of threads used by the ThreadPoolExecutor, the exact number doesn't
    # seem to matter.

    # How many scans to run in parallel?  If you set this really high you could
    # overwhelm the table read capacity, but otherwise I don't change this much.
    max_scans_in_parallel = 5

    # Schedule an initial scan for each segment of the table.  We read each
    # segment in a separate thread, then look to see if there are more rows to
    # read -- and if so, we schedule another scan.
    tasks_to_do = [
        {
            **kwargs,
            "TableName": TableName,
            "Segment": segment,
            "TotalSegments": total_segments,
        }
        for segment in range(total_segments)
    ]

    # Make the list an iterator, so the same tasks don't get run repeatedly.
    scans_to_run = iter(tasks_to_do)

    with concurrent.futures.ThreadPoolExecutor() as executor:

        # Schedule the initial batch of futures.  Here we assume that
        # max_scans_in_parallel < total_segments, so there's no risk that
        # the queue will throw an Empty exception.
        futures = {
            executor.submit(dynamo_client.scan, **scan_params): scan_params
            for scan_params in itertools.islice(scans_to_run, max_scans_in_parallel)
        }

        while futures:
            # Wait for the first future to complete.
            done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)

            for fut in done:
                yield from fut.result()["Items"]

                scan_params = futures.pop(fut)

                # A Scan reads up to N items, and tells you where it got to in
                # the LastEvaluatedKey.  You pass this key to the next Scan operation,
                # and it continues where it left off.
                try:
                    scan_params["ExclusiveStartKey"] = fut.result()["LastEvaluatedKey"]
                except KeyError:
                    break
                tasks_to_do.append(scan_params)

            # Schedule the next batch of futures.  At some point we might run out
            # of entries in the queue if we've finished scanning the table, so
            # we need to spot that and not throw.
            for scan_params in itertools.islice(scans_to_run, len(done)):
                futures[executor.submit(dynamo_client.scan, **scan_params)] = scan_params


class UrlNotFoundError(Exception):
    pass
