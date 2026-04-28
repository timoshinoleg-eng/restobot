resource "yandex_iam_service_account" "tfstate" {
  name        = var.tfstate_service_account_name
  description = "Service account for Terraform remote state in Object Storage."
}

resource "yandex_resourcemanager_folder_iam_member" "tfstate_storage_admin" {
  folder_id = var.yc_folder_id
  role      = "storage.admin"
  member    = "serviceAccount:${yandex_iam_service_account.tfstate.id}"
}

resource "yandex_storage_bucket" "tfstate" {
  bucket        = var.tfstate_bucket_name
  acl           = "private"
  force_destroy = var.force_destroy_bucket

  versioning {
    enabled = true
  }

  depends_on = [yandex_resourcemanager_folder_iam_member.tfstate_storage_admin]
}

resource "yandex_iam_service_account_static_access_key" "tfstate" {
  service_account_id = yandex_iam_service_account.tfstate.id
  description        = "Static access key for Terraform S3 backend."
}
