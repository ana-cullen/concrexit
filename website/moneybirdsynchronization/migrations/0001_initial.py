# Generated by Django 4.1.7 on 2023-04-06 10:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("members", "0044_alter_profile_photo"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("payments", "0020_alter_payment_paid_by_alter_payment_processed_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="MoneybirdPayment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "moneybird_financial_statement_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="moneybird financial statement id",
                    ),
                ),
                (
                    "moneybird_financial_mutation_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="moneybird financial mutation id",
                    ),
                ),
                (
                    "payment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moneybird_payment",
                        to="payments.payment",
                        verbose_name="payment",
                    ),
                ),
            ],
            options={
                "verbose_name": "moneybird payment",
                "verbose_name_plural": "moneybird payments",
            },
        ),
        migrations.CreateModel(
            name="MoneybirdContact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "moneybird_id",
                    models.IntegerField(
                        blank=True, null=True, verbose_name="Moneybird ID"
                    ),
                ),
                (
                    "moneybird_version",
                    models.IntegerField(
                        blank=True, null=True, verbose_name="Moneybird version"
                    ),
                ),
                (
                    "member",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moneybird_contact",
                        to="members.member",
                        verbose_name="member",
                    ),
                ),
            ],
            options={
                "verbose_name": "moneybird contact",
                "verbose_name_plural": "moneybird contacts",
            },
        ),
        migrations.CreateModel(
            name="MoneybirdExternalInvoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("object_id", models.CharField(max_length=255)),
                (
                    "moneybird_invoice_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="moneybird invoice id",
                    ),
                ),
                (
                    "moneybird_details_attribute_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="moneybird details attribute id",
                    ),
                ),
                (
                    "payable_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "verbose_name": "moneybird external invoice",
                "verbose_name_plural": "moneybird external invoices",
                "unique_together": {("payable_model", "object_id")},
            },
        ),
    ]
