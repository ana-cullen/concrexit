from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.urls import reverse

from utils.validators import validate_file_extension


class AssociationDocumentsYear(models.Model):
    year = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(1990)],
    )
    policy_document = models.FileField(
        upload_to='documents/association/',
        validators=[validate_file_extension],
        blank=True,
    )
    annual_report = models.FileField(
        upload_to='documents/association/',
        validators=[validate_file_extension],
        blank=True,
    )
    financial_report = models.FileField(
        upload_to='documents/association/',
        validators=[validate_file_extension],
        blank=True,
    )

    def __str__(self):
        return "{}-{}".format(self.year, self.year + 1)


class MiscellaneousDocument(models.Model):
    name = models.CharField(max_length=200)
    file = models.FileField(
        upload_to='documents/miscellaneous/',
        validators=[validate_file_extension],
    )
    members_only = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('documents:miscellaneous-document', args=(self.pk,))


class GeneralMeeting(models.Model):
    minutes = models.FileField(
        upload_to='documents/meetings/minutes/',
        validators=[validate_file_extension],
        blank=True,
        null=True,
    )
    datetime = models.DateTimeField()
    location = models.CharField(max_length=200)

    def __str__(self):
        return '{}'.format(timezone.localtime(self.datetime)
                                   .strftime('%Y-%m-%d'))

    class Meta:
        ordering = ['datetime']


def meetingdocument_upload_to(instance, filename):
    return 'documents/meetings/{}/files/{}'.format(instance.meeting.pk,
                                                   filename)


class GeneralMeetingDocument(models.Model):
    meeting = models.ForeignKey(GeneralMeeting, on_delete=models.CASCADE)
    file = models.FileField(
        upload_to=meetingdocument_upload_to,
        validators=[validate_file_extension],
    )

    def __str__(self):
        return self.file.name
