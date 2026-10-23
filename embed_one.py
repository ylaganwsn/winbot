import json

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")

text = "RDS is the most expensive service."

response = client.invoke_model(
    modelId="amazon.titan-embed-text-v2:0",
    body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
    contentType="application/json",
    accept="application/json",
)

result = json.loads(response["body"].read())
vector = result["embedding"]

print("Length:", len(vector))
print("First 5 numbers:", vector[:5])