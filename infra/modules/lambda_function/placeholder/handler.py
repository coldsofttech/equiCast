"""Bootstrap-only placeholder. Used solely so `aws_lambda_function` has a
valid initial deployment package at `terraform apply` time — the real
application code is deployed out-of-band afterwards (see the `lifecycle
{ ignore_changes = [...] }` block in this module's main.tf), never by
re-running Terraform."""


def handler(event, context):
    return {"statusCode": 200, "body": "placeholder - real code not deployed yet"}
