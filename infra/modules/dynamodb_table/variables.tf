variable "table_name" {
  description = "Name of the DynamoDB table."
  type        = string
}

variable "hash_key" {
  description = "Name of the partition key attribute (always string-typed)."
  type        = string
}
