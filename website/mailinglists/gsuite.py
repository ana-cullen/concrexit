"""GSuite syncing helpers defined by the mailinglists package"""

from time import sleep

from django.utils.datastructures import ImmutableList
from googleapiclient.errors import HttpError

from mailinglists.models import MailingList
from mailinglists.services import get_automatic_lists
from utils.google_api import get_directory_api

from django.conf import settings


class GroupData:
    def __init__(self, name, description, moderated=False, archived=False,
                 prefix='', aliases=ImmutableList([]),
                 addresses=ImmutableList([])):
        super().__init__()
        self.moderated = moderated
        self.archived = archived
        self.prefix = prefix
        self.name = name
        self.description = description
        self.aliases = aliases
        self.addresses = addresses


def create_group(group):
    """
    Create a new group based on the provided data
    :param group: group data
    """
    directory_api = get_directory_api()
    directory_api.groups().insert(
        body={
            'email': f'{group.name}@{settings.GSUITE_DOMAIN}',
            'name': group.name,
            'description': group.description,
        },
    ).execute()
    # Wait for mailinglist creation to complete
    # Docs say we need to wait a minute, but since we always update lists
    # an error in the list members update is not a problem
    sleep(0.5)
    update_group_members(group)


def update_group(old_name, group):
    """
    Update a group based on the provided name and data
    :param old_name: old group name
    :param group: new group data
    """
    directory_api = get_directory_api()
    directory_api.groups().update(
        groupKey=f'{old_name}@{settings.GSUITE_DOMAIN}',
        body={
            'email': f'{group.name}@{settings.GSUITE_DOMAIN}',
            'name': group.name,
            'description': group.description,
        }
    )
    update_group_aliases(group)
    update_group_members(group)


def update_group_aliases(group: GroupData):
    """
    Update the aliases of a group based on existing values
    :param group: group data
    """
    directory_api = get_directory_api()
    aliases_response = directory_api.groups().aliases().list(
        groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
    ).execute()

    existing_aliases = [a['alias'] for a in
                        aliases_response.get('aliases', [])]
    new_aliases = [f'{a}@{settings.GSUITE_DOMAIN}' for a in group.aliases]

    remove_list = [x for x in existing_aliases if x not in new_aliases]
    insert_list = [x for x in new_aliases if x not in existing_aliases]

    for remove_alias in remove_list:
        try:
            directory_api.groups().aliases().delete(
                groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
                alias=remove_alias
            ).execute()
        except HttpError:
            pass  # Ignore error, API returned failing value

    for insert_alias in insert_list:
        try:
            directory_api.groups().aliases().insert(
                groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
                body={
                    'alias': insert_alias
                }
            ).execute()
        except HttpError:
            pass  # Ignore error, API returned failing value


def delete_group(group: GroupData):
    """
    Removes the specified list from
    :param group: group data
    """
    directory_api = get_directory_api()
    directory_api.groups().delete(
        groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
    ).execute()


def update_group_members(group: GroupData):
    """
    Update the group members of the specified group based
    on the existing members
    :param group: group data
    """
    directory_api = get_directory_api()
    try:
        members_response = directory_api.members().list(
            groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
        ).execute()
        members_list = members_response.get('members', [])
        while 'nextPageToken' in members_response:
            members_response = directory_api.members().list(
                groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
                pageToken=members_response['nextPageToken']
            ).execute()
            members_list += members_response.get('members', [])

        existing_members = [m['email'] for m in members_list]
    except HttpError:
        return  # the list does not exist or something else is wrong
    new_members = list(group.addresses)

    remove_list = [x for x in existing_members if x not in new_members]
    insert_list = [x for x in new_members if x not in existing_members]

    for remove_member in remove_list:
        try:
            directory_api.members().delete(
                groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
                memberKey=remove_member
            ).execute()
        except HttpError:
            pass  # Ignore error, API returned failing value

    for insert_member in insert_list:
        try:
            directory_api.members().insert(
                groupKey=f'{group.name}@{settings.GSUITE_DOMAIN}',
                body={
                    'email': insert_member,
                    'role': 'MEMBER'
                }
            ).execute()
        except HttpError:
            pass  # Ignore error, API returned failing value


def mailinglist_to_group(mailinglist: MailingList) -> GroupData:
    """Convert a mailinglist model to everything we need for GSuite"""
    return GroupData(
        moderated=mailinglist.moderated,
        archived=mailinglist.archived,
        prefix=mailinglist.prefix,
        name=mailinglist.name,
        description=mailinglist.description,
        aliases=[x.alias for x in mailinglist.aliases.all()],
        addresses=mailinglist.all_addresses()
    )


def _automatic_to_group(automatic_list) -> GroupData:
    """Convert an automatic mailinglist to a GSuite Group data obj"""
    return GroupData(
        moderated=automatic_list['moderated'],
        archived=automatic_list['archived'],
        prefix=automatic_list['prefix'],
        name=automatic_list['name'],
        description=automatic_list['description'],
        aliases=automatic_list['aliases'],
        addresses=automatic_list['addresses']
    )


def sync_mailinglists(lists=None):
    """
    Sync mailing lists with GSuite
    :param lists: optional parameter to determine which lists to sync
    """
    directory_api = get_directory_api()

    if lists is None:
        lists = [
                    mailinglist_to_group(l) for l in MailingList.objects.all()
                ] + [
                    _automatic_to_group(l) for l in
                    get_automatic_lists()
                ]

    try:
        groups_response = directory_api.groups().list(
            domain=settings.GSUITE_DOMAIN
        ).execute()
        groups_list = groups_response.get('groups', [])
        while 'nextPageToken' in groups_response:
            groups_response = directory_api.groups().list(
                domain=settings.GSUITE_DOMAIN,
                pageToken=groups_response['nextPageToken']
            ).execute()
            groups_list += groups_response.get('groups', [])
        existing_groups = [g['name'] for g in groups_list]
    except HttpError:
        return  # there are no lists or something went wrong

    new_groups = [g.name for g in lists]

    remove_list = [x for x in existing_groups if x not in new_groups]
    insert_list = [x for x in new_groups if x not in existing_groups]

    for l in lists:
        if l.name in remove_list:
            delete_group(l)
        elif l.name in insert_list:
            create_group(l)
        else:
            update_group(l.name, l)
