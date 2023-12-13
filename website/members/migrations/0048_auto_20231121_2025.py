# Generated by Django 4.2.7 on 2023-11-21 19:25

from django.db import migrations
from django.db.models import Exists, OuterRef


def deregister_recent_benefactors_from_oldmembers_mailinglist(apps, schema_editor):
    """Deregister all benefactors since 2017 from the oldmembers mailinglist.

    We've changed the oldmembers list to include everyone with the 'receive_oldmembers'
    preference set, regardless of whether they have been a member in the past. Newly made
    benefactors are automatically excluded, and any existing members or benefactors are
    included. This is because for many people, we don't have a complete history of their
    memberships.

    To prevent recently created benefactors (of which we do have a complete history) from
    being included in the oldmembers list, we need to set their 'receive_oldmembers' False.
    """
    Profile = apps.get_model("members", "Profile")
    Member = apps.get_model("members", "Member")
    Membership = apps.get_model("members", "Membership")

    # Get people made after the initial migration (+- 2016-12-06) who have only been a benefactor.
    benefactors = (
        Member.objects.filter(date_joined__gte="2017-01-01")
        .filter(
            Exists(Membership.objects.filter(user=OuterRef("pk"), type="benefactor"))
        )
        .exclude(
            Exists(
                Membership.objects.filter(user=OuterRef("pk"), type="member"),
            )
        )
    )

    # Set 'receive_oldmembers' to False for all benefactors since 2017
    Profile.objects.filter(user__in=benefactors).update(receive_oldmembers=False)


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0048_alter_profile_photo"),
    ]

    operations = [
        migrations.RunPython(
            deregister_recent_benefactors_from_oldmembers_mailinglist,
            migrations.RunPython.noop,
        )
    ]
