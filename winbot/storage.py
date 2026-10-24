import boto3

from winbot import config


def _client():
    return boto3.client("s3", region_name=config.REGION)


def original_key(doc_id, filename):
    return f"documents/{doc_id}/original/{filename}"


def pdf_key(doc_id):
    return f"documents/{doc_id}/document.pdf"


def upload_file(path, key):
    _client().upload_file(str(path), config.files_bucket(), key)


def download_file(key, path):
    _client().download_file(config.files_bucket(), key, str(path))


def presigned_url(key, content_type=None, expires=300):
    params = {"Bucket": config.files_bucket(), "Key": key}
    if content_type:
        params["ResponseContentType"] = content_type
    return _client().generate_presigned_url(
        "get_object", Params=params, ExpiresIn=expires
    )


def delete_document_files(doc_id):
    client = _client()
    bucket = config.files_bucket()
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=f"documents/{doc_id}/"):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            deleted += len(objects)
    return deleted