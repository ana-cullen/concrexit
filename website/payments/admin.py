"""Registers admin interfaces for the payments module."""
import csv
from collections import OrderedDict

from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import model_ngettext
from django.db.models import QuerySet
from django.db.models.query_utils import Q
from django.http import HttpRequest, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django_easy_admin_object_actions.admin import ObjectActionsMixin
from django_easy_admin_object_actions.decorators import object_action

from payments import admin_views, services
from payments.forms import BankAccountAdminForm, BatchPaymentInlineAdminForm

from .models import BankAccount, Batch, Payment, PaymentUser


def _show_message(
    model_admin: ModelAdmin, request: HttpRequest, n: int, message: str, error: str
) -> None:
    if n == 0:
        model_admin.message_user(request, error, messages.ERROR)
    else:
        model_admin.message_user(
            request,
            message % {"count": n, "items": model_ngettext(model_admin.opts, n)},
            messages.SUCCESS,
        )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Manage the payments."""

    list_display = (
        "created_at",
        "amount",
        "type",
        "paid_by_link",
        "processed_by_link",
        "batch_link",
        "topic",
    )
    list_filter = ("type", "batch")
    list_select_related = ("paid_by", "processed_by", "batch")
    date_hierarchy = "created_at"
    fields = (
        "created_at",
        "amount",
        "type",
        "paid_by",
        "processed_by",
        "topic",
        "notes",
        "batch",
    )
    readonly_fields = (
        "created_at",
        "amount",
        "paid_by",
        "processed_by",
        "type",
        "topic",
        "notes",
        "batch",
    )
    search_fields = (
        "topic",
        "notes",
        "paid_by__username",
        "paid_by__first_name",
        "paid_by__last_name",
        "processed_by__username",
        "processed_by__first_name",
        "processed_by__last_name",
        "amount",
    )
    ordering = ("-created_at",)
    autocomplete_fields = ("paid_by", "processed_by")
    actions = [
        "add_to_new_batch",
        "add_to_last_batch",
        "export_csv",
    ]

    @staticmethod
    def _member_link(member: PaymentUser) -> str:
        return (
            format_html(
                "<a href='{}'>{}</a>", member.get_absolute_url(), member.get_full_name()
            )
            if member
            else None
        )

    def paid_by_link(self, obj: Payment) -> str:
        return self._member_link(obj.paid_by)

    paid_by_link.admin_order_field = "paid_by"
    paid_by_link.short_description = _("paid by")

    @staticmethod
    def _batch_link(payment: Payment, batch: Batch) -> str:
        if batch:
            return format_html(
                "<a href='{}'>{}</a>", batch.get_absolute_url(), str(batch)
            )
        if payment.type == Payment.TPAY:
            return _("No batch attached")
        return ""

    def batch_link(self, obj: Payment) -> str:
        return self._batch_link(obj, obj.batch)

    batch_link.admin_order_field = "batch"
    batch_link.short_description = _("in batch")

    def processed_by_link(self, obj: Payment) -> str:
        return self._member_link(obj.processed_by)

    processed_by_link.admin_order_field = "processed_by"
    processed_by_link.short_description = _("processed by")

    def has_delete_permission(self, request, obj=None):
        if isinstance(obj, Payment):
            if obj.batch and obj.batch.processed:
                return False
        if (
            "payment/" in request.path
            and request.POST
            and request.POST.get("action") == "delete_selected"
        ):
            for payment_id in request.POST.getlist("_selected_action"):
                payment = Payment.objects.get(id=payment_id)
                if payment.batch and payment.batch.processed:
                    return False

        return super().has_delete_permission(request, obj)

    def get_field_queryset(self, db, db_field, request):
        if str(db_field) == "payments.Payment.batch":
            return Batch.objects.filter(processed=False)
        return super().get_field_queryset(db, db_field, request)

    def get_readonly_fields(self, request: HttpRequest, obj: Payment = None):
        if not obj:
            return "created_at", "processed_by", "batch"
        if obj.type == Payment.TPAY and not (obj.batch and obj.batch.processed):
            return (
                "created_at",
                "amount",
                "type",
                "paid_by",
                "processed_by",
                "notes",
                "topic",
            )
        return super().get_readonly_fields(request, obj)

    def get_actions(self, request: HttpRequest) -> OrderedDict:
        """Get the actions for the payments.

        Hide the processing actions if the right permissions are missing
        """
        actions = super().get_actions(request)
        if not request.user.has_perm("payments.process_batches"):
            del actions["add_to_new_batch"]
            del actions["add_to_last_batch"]

        return actions

    def add_to_new_batch(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Add selected TPAY payments to a new batch."""
        tpays = queryset.filter(type=Payment.TPAY)
        if len(tpays) > 0:
            batch = Batch.objects.create()
            tpays.update(batch=batch)
        _show_message(
            self,
            request,
            len(tpays),
            _("Successfully added {} payments to new batch").format(len(tpays)),
            _("No payments using Thalia Pay are selected, no batch is created"),
        )

    add_to_new_batch.short_description = _(
        "Add selected Thalia Pay payments to a new batch"
    )

    def add_to_last_batch(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Add selected TPAY payments to the last batch."""
        tpays = queryset.filter(type=Payment.TPAY)
        if len(tpays) > 0:
            batch = Batch.objects.last()
            if batch is None:
                self.message_user(request, _("No batches available."), messages.ERROR)
            elif not batch.processed:
                batch.save()
                tpays.update(batch=batch)
                self.message_user(
                    request,
                    _("Successfully added {} payments to {}").format(len(tpays), batch),
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    _("The last batch {} is already processed").format(batch),
                    messages.ERROR,
                )
        else:
            self.message_user(
                request,
                _("No payments using Thalia Pay are selected, no batch is created"),
                messages.ERROR,
            )

    add_to_last_batch.short_description = _(
        "Add selected Thalia Pay payments to the last batch"
    )

    def get_urls(self) -> list:
        urls = super().get_urls()
        custom_urls = [
            path(
                "<str:app_label>/<str:model_name>/<payable>/create/",
                self.admin_site.admin_view(admin_views.PaymentAdminView.as_view()),
                name="payments_payment_create",
            ),
        ]
        return custom_urls + urls

    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        """Export a CSV of payments.

        :param request: Request
        :param queryset: Items to be exported
        """
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment;filename="payments.csv"'
        writer = csv.writer(response)
        headers = [
            _("created"),
            _("amount"),
            _("type"),
            _("processor"),
            _("payer id"),
            _("payer name"),
            _("notes"),
        ]
        writer.writerow([capfirst(x) for x in headers])
        for payment in queryset:
            writer.writerow(
                [
                    payment.created_at,
                    payment.amount,
                    payment.get_type_display(),
                    payment.processed_by.get_full_name()
                    if payment.processed_by
                    else "-",
                    payment.paid_by.pk if payment.paid_by else "-",
                    payment.paid_by.get_full_name() if payment.paid_by else "-",
                    payment.notes,
                ]
            )
        return response

    export_csv.short_description = _("Export")


class ValidAccountFilter(admin.SimpleListFilter):
    """Filter the memberships by whether they are active or not."""

    title = _("mandates")
    parameter_name = "active"

    def lookups(self, request, model_admin) -> tuple:
        return (
            ("valid", _("Valid")),
            ("invalid", _("Invalid")),
            ("none", _("None")),
        )

    def queryset(self, request, queryset) -> QuerySet:
        now = timezone.now()

        if self.value() == "valid":
            return queryset.filter(
                Q(valid_from__lte=now) & Q(valid_until=None) | Q(valid_until__lt=now)
            )

        if self.value() == "invalid":
            return queryset.filter(valid_until__gte=now)

        if self.value() == "none":
            return queryset.filter(valid_from=None)

        return queryset


class PaymentsInline(admin.TabularInline):
    """The inline for payments in the Batch admin."""

    model = Payment
    readonly_fields = (
        "topic",
        "paid_by",
        "amount",
        "created_at",
        "notes",
    )
    form = BatchPaymentInlineAdminForm
    extra = 0
    max_num = 0
    can_delete = False

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj and obj.processed:
            fields.remove("remove_batch")
        return fields


@admin.register(Batch)
class BatchAdmin(ObjectActionsMixin, admin.ModelAdmin):
    """Manage payment batches."""

    inlines = (PaymentsInline,)
    list_display = (
        "id",
        "description",
        "withdrawal_date",
        "start_date",
        "end_date",
        "total_amount",
        "payments_count",
        "processing_date",
        "processed",
    )
    fields = (
        "id",
        "description",
        "withdrawal_date",
        "processed",
        "processing_date",
        "total_amount",
    )
    search_fields = (
        "id",
        "description",
        "withdrawal_date",
    )

    def get_readonly_fields(self, request: HttpRequest, obj: Batch = None):
        default_fields = (
            "id",
            "processed",
            "processing_date",
            "total_amount",
        )
        if obj and obj.processed:
            return (
                "description",
                "withdrawal_date",
            ) + default_fields
        return default_fields

    def has_delete_permission(self, request, obj=None):
        if isinstance(obj, Batch):
            if obj.processed:
                return False
        if (
            "batch/" in request.path
            and request.POST
            and request.POST.get("action") == "delete_selected"
        ):
            for payment_id in request.POST.getlist("_selected_action"):
                if Batch.objects.get(id=payment_id).processed:
                    return False

        return super().has_delete_permission(request, obj)

    def get_urls(self) -> list:
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/export/",
                self.admin_site.admin_view(admin_views.BatchExportAdminView.as_view()),
                name="payments_batch_export",
            ),
            path(
                "<int:pk>/export-topic/",
                self.admin_site.admin_view(
                    admin_views.BatchTopicExportAdminView.as_view()
                ),
                name="payments_batch_export_topic",
            ),
            path(
                "<int:pk>/topic-description/",
                self.admin_site.admin_view(
                    admin_views.BatchTopicDescriptionAdminView.as_view()
                ),
                name="payments_batch_topic_description",
            ),
            path(
                "new_filled/",
                self.admin_site.admin_view(
                    admin_views.BatchNewFilledAdminView.as_view()
                ),
                name="payments_batch_new_batch_filled",
            ),
        ]
        return custom_urls + urls

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if instance.batch and not instance.batch.processed:
                instance.batch = None
            instance.save()
        formset.save_m2m()

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str = None,
        form_url: str = "",
        extra_context: dict = None,
    ) -> HttpResponse:
        """Render the change formview.

        Only allow when the batch has not been processed yet.
        """
        extra_context = extra_context or {}
        obj = None
        if object_id is not None and request.user.has_perm("payments.process_batches"):
            obj = Batch.objects.get(id=object_id)

        extra_context["batch"] = obj
        return super().changeform_view(request, object_id, form_url, extra_context)

    @object_action(
        label=_("Process"),
        permission="payments.process_batches",
        condition=lambda _, obj: not obj.processed,
        display_as_disabled_if_condition_not_met=True,
        log_message=_("Processed"),
        perform_after_saving=True,
    )
    def process_batch_obj(self, request, obj):
        """Process the selected batches."""
        services.process_batch(obj)
        messages.success(request, _("Batch processed."))
        return True

    object_actions_after_fieldsets = ("process_batch_obj",)


@admin.register(BankAccount)
class BankAccountAdmin(ObjectActionsMixin, admin.ModelAdmin):
    """Manage bank accounts."""

    list_display = ("iban", "owner_link", "last_used", "valid_from", "valid_until")
    fields = (
        "created_at",
        "last_used",
        "owner",
        "iban",
        "bic",
        "initials",
        "last_name",
        "mandate_no",
        "valid_from",
        "valid_until",
        "signature",
        "can_be_revoked",
    )
    readonly_fields = (
        "created_at",
        "can_be_revoked",
    )
    search_fields = ("owner__username", "owner__first_name", "owner__last_name", "iban")
    autocomplete_fields = ("owner",)
    form = BankAccountAdminForm

    def owner_link(self, obj: BankAccount) -> str:
        if obj.owner:
            return format_html(
                "<a href='{}'>{}</a>",
                reverse("admin:auth_user_change", args=[obj.owner.pk]),
                obj.owner.get_full_name(),
            )
        return ""

    owner_link.admin_order_field = "owner"
    owner_link.short_description = _("owner")

    def can_be_revoked(self, obj: BankAccount):
        return obj.can_be_revoked

    can_be_revoked.boolean = True

    @object_action(
        label=_("Revoke"),
        permission="payments.change_bankaccount",
        condition=lambda _, obj: obj.can_be_revoked,
        display_as_disabled_if_condition_not_met=True,
        log_message=_("Revoked"),
        perform_after_saving=True,
    )
    def revoke(self, request, obj):
        """Process the selected batches."""
        if obj.valid_until != timezone.now().date():
            obj.valid_until = timezone.now().date()
            obj.save()
            messages.success(request, _("Revoked bank account."))
            return True

    @object_action(
        label=_("Update last used"),
        permission="payments.change_bankaccount",
        log_message=_("Last used updated"),
        perform_after_saving=True,
    )
    def update_last_used(self, request, obj):
        """Process the selected batches."""
        if obj.last_used != timezone.now().date():
            obj.last_used = timezone.now().date()
            obj.save()
            messages.success(request, _("Update last used date."))
            return True

    object_actions_after_fieldsets = (
        "revoke",
        "update_last_used",
    )

    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment;filename="accounts.csv"'
        writer = csv.writer(response)
        headers = [
            _("created"),
            _("name"),
            _("reference"),
            _("IBAN"),
            _("BIC"),
            _("valid from"),
            _("valid until"),
            _("signature"),
        ]
        writer.writerow([capfirst(x) for x in headers])
        for account in queryset:
            writer.writerow(
                [
                    account.created_at,
                    account.name,
                    account.mandate_no,
                    account.iban,
                    account.bic or "",
                    account.valid_from or "",
                    account.valid_until or "",
                    account.signature or "",
                ]
            )
        return response

    export_csv.short_description = _("Export")


class BankAccountInline(admin.TabularInline):
    model = BankAccount
    fields = (
        "iban",
        "bic",
        "mandate_no",
        "valid_from",
        "valid_until",
        "last_used",
    )
    show_change_link = True

    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    fk_name = "paid_by"
    fields = (
        "created_at",
        "type",
        "amount",
        "topic",
        "notes",
        "batch",
    )
    ordering = ("-created_at",)

    show_change_link = True

    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ThaliaPayAllowedFilter(admin.SimpleListFilter):
    title = _("Thalia Pay allowed")
    parameter_name = "tpay_allowed"

    def lookups(self, request, model_admin):
        return ("1", _("Yes")), ("0", _("No"))

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(tpay_allowed=True)
        if self.value() == "0":
            return queryset.exclude(tpay_allowed=True)
        return queryset


class ThaliaPayEnabledFilter(admin.SimpleListFilter):
    title = _("Thalia Pay enabled")
    parameter_name = "tpay_enabled"

    def lookups(self, request, model_admin):
        return ("1", _("Yes")), ("0", _("No"))

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(tpay_enabled=True)
        if self.value() == "0":
            return queryset.exclude(tpay_enabled=True)
        return queryset


class ThaliaPayBalanceFilter(admin.SimpleListFilter):
    title = _("Thalia Pay balance")
    parameter_name = "tpay_balance"

    def lookups(self, request, model_admin):
        return (
            ("0", "€0,00"),
            ("1", ">€0.00"),
        )

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(tpay_balance=0)
        if self.value() == "1":
            return queryset.exclude(tpay_balance=0)
        return queryset


@admin.register(PaymentUser)
class PaymentUserAdmin(ObjectActionsMixin, admin.ModelAdmin):
    list_display = (
        "__str__",
        "email",
        "get_tpay_allowed",
        "get_tpay_enabled",
        "get_tpay_balance",
    )
    list_filter = [
        ThaliaPayAllowedFilter,
        ThaliaPayEnabledFilter,
        ThaliaPayBalanceFilter,
    ]

    inlines = [BankAccountInline, PaymentInline]

    fields = (
        "user_link",
        "get_tpay_allowed",
        "get_tpay_enabled",
        "get_tpay_balance",
    )

    readonly_fields = (
        "user_link",
        "get_tpay_allowed",
        "get_tpay_enabled",
        "get_tpay_balance",
    )

    search_fields = (
        "first_name",
        "last_name",
        "username",
        "email",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related("bank_accounts", "paid_payment_set")
        queryset = queryset.select_properties(
            "tpay_balance",
            "tpay_enabled",
            "tpay_allowed",
        )
        return queryset

    def get_tpay_balance(self, obj):
        return f"€ {obj.tpay_balance:.2f}" if obj.tpay_enabled else "-"

    get_tpay_balance.short_description = _("balance")

    def get_tpay_enabled(self, obj):
        return obj.tpay_enabled

    get_tpay_enabled.short_description = _("Thalia Pay enabled")
    get_tpay_enabled.boolean = True

    def get_tpay_allowed(self, obj):
        return obj.tpay_allowed

    get_tpay_allowed.short_description = _("Thalia Pay allowed")
    get_tpay_allowed.boolean = True

    def user_link(self, obj):
        return (
            format_html(
                "<a href='{}'>{}</a>",
                reverse("admin:auth_user_change", args=[obj.pk]),
                obj.get_full_name(),
            )
            if obj
            else ""
        )

    user_link.admin_order_field = "user"
    user_link.short_description = _("user")

    @object_action(
        label=_("Disallow Thalia Pay"),
        permission="payments.change_paymentuser",
        condition=lambda _, obj: obj.tpay_allowed,
        display_as_disabled_if_condition_not_met=True,
        log_message=_("Disallowed Thalia Pay"),
    )
    def disallow_thalia_pay(self, request, obj):
        if obj.tpay_allowed:
            obj.disallow_tpay()
            messages.success(request, _("Disallowed Thalia Pay."))
            return True

    @object_action(
        label=_("Allow Thalia Pay"),
        permission="payments.change_paymentuser",
        condition=lambda _, obj: not obj.tpay_allowed,
        display_as_disabled_if_condition_not_met=True,
        log_message=_("Allowed Thalia Pay"),
    )
    def allow_thalia_pay(self, request, obj):
        if not obj.tpay_allowed:
            obj.allow_tpay()
            messages.success(request, _("Disallowed Thalia Pay."))
            return True

    object_actions_after_related_objects = [
        "disallow_thalia_pay",
        "allow_thalia_pay",
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
