import json

import boto3

from winbot import config

_client = boto3.client("bedrock-runtime", region_name=config.REGION)


def embed(text):
    response = _client.invoke_model(
        modelId=config.EMBED_MODEL_ID,
        body=json.dumps(
            {
                "inputText": text,
                "dimensions": config.EMBED_DIMENSIONS,
                "normalize": True,
            }
        ),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]