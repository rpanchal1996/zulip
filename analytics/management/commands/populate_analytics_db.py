from __future__ import absolute_import, print_function

from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import BaseCount, InstallationCount, RealmCount, \
    UserCount, StreamCount
from analytics.lib.counts import COUNT_STATS, CountStat, do_drop_all_analytics_tables
from analytics.lib.fixtures import generate_time_series_data
from analytics.lib.time_utils import time_range
from zerver.lib.timestamp import floor_to_day
from zerver.models import Realm, UserProfile, Stream, Message, Client

from datetime import datetime, timedelta

from six.moves import zip
from typing import Any, List, Optional, Text, Type, Union

class Command(BaseCommand):
    help = """Populates analytics tables with randomly generated data."""

    DAYS_OF_DATA = 100

    def create_user(self, email, full_name, is_staff, date_joined, realm):
        # type: (Text, Text, Text, bool, datetime, Realm) -> UserProfile
        return UserProfile.objects.create(
            email=email, full_name=full_name, is_staff=is_staff,
            realm=realm, short_name=full_name, pointer=-1, last_pointer_updater='none',
            api_key='42', date_joined=date_joined)

    def generate_fixture_data(self, stat, business_hours_base, non_business_hours_base,
                              growth, autocorrelation, spikiness, holiday_rate=0):
        # type: (CountStat, float, float, float, float, float, float) -> List[int]
        return generate_time_series_data(
            days=self.DAYS_OF_DATA, business_hours_base=business_hours_base,
            non_business_hours_base=non_business_hours_base, growth=growth,
            autocorrelation=autocorrelation, spikiness=spikiness, holiday_rate=holiday_rate,
            frequency=stat.frequency, is_gauge=(stat.interval == CountStat.GAUGE))

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        do_drop_all_analytics_tables()
        # I believe this also deletes any objects with this realm as a foreign key
        Realm.objects.filter(string_id='analytics').delete()
        Client.objects.filter(name__endswith='_').delete()

        installation_time = timezone.now() - timedelta(days=self.DAYS_OF_DATA)
        last_end_time = floor_to_day(timezone.now())
        realm = Realm.objects.create(
            string_id='analytics', name='Analytics', domain='analytics.ds',
            date_created=installation_time)
        shylock = self.create_user('shylock@analytics.ds', 'Shylock', True, installation_time, realm)

        def insert_fixture_data(stat, fixture_data, table):
            # type: (CountStat, Dict[Optional[str], List[int]], Type[BaseCount]) -> None
            end_times = time_range(last_end_time, last_end_time, stat.frequency,
                                   len(list(fixture_data.values())[0]))
            if table == RealmCount:
                id_args = {'realm': realm}
            if table == UserCount:
                id_args = {'realm': realm, 'user': shylock}
            for subgroup, values in fixture_data.items():
                table.objects.bulk_create([
                    table(property=stat.property, subgroup=subgroup, end_time=end_time,
                          value=value, **id_args)
                    for end_time, value in zip(end_times, values) if value != 0])

        stat = COUNT_STATS['active_users:is_bot:day']
        realm_data = {
            'false': self.generate_fixture_data(stat, .1, .03, 3, .5, 3),
            'true': self.generate_fixture_data(stat, .01, 0, 1, 0, 1)
        } # type: Dict[Optional[str], List[int]]
        insert_fixture_data(stat, realm_data, RealmCount)

        stat = COUNT_STATS['messages_sent:is_bot:hour']
        user_data = {'false': self.generate_fixture_data(stat, 2, 1, 1.5, .6, 8, holiday_rate=.1)}
        insert_fixture_data(stat, user_data, UserCount)
        realm_data = {'false': self.generate_fixture_data(stat, 35, 15, 6, .6, 4),
                      'true': self.generate_fixture_data(stat, 15, 15, 3, .4, 2)}
        insert_fixture_data(stat, realm_data, RealmCount)

        stat = COUNT_STATS['messages_sent:message_type:day']
        user_data = {
            'public_stream': self.generate_fixture_data(stat, 1.5, 1, 3, .6, 8),
            'private_message': self.generate_fixture_data(stat, .5, .3, 1, .6, 8)}
        insert_fixture_data(stat, user_data, UserCount)
        realm_data = {
            'public_stream': self.generate_fixture_data(stat, 30, 8, 5, .6, 4),
            'private_stream': self.generate_fixture_data(stat, 7, 7, 5, .6, 4),
            'private_message': self.generate_fixture_data(stat, 13, 5, 5, .6, 4)}
        insert_fixture_data(stat, realm_data, RealmCount)

        website_ = Client.objects.create(name='website_')
        API_ = Client.objects.create(name='API_')
        android_ = Client.objects.create(name='android_')
        iOS_ = Client.objects.create(name='iOS_')
        react_native_ = Client.objects.create(name='react_native_')
        electron_ = Client.objects.create(name='electron_')
        barnowl_ = Client.objects.create(name='barnowl_')
        plan9_ = Client.objects.create(name='plan9_')

        stat = COUNT_STATS['messages_sent:client:day']
        user_data = {
            website_.id: self.generate_fixture_data(stat, 2, 1, 1.5, .6, 8),
            barnowl_.id: self.generate_fixture_data(stat, 0, .3, 1.5, .6, 8)}
        insert_fixture_data(stat, user_data, UserCount)
        realm_data = {
            website_.id: self.generate_fixture_data(stat, 30, 20, 5, .6, 3),
            API_.id: self.generate_fixture_data(stat, 5, 5, 5, .6, 3),
            android_.id: self.generate_fixture_data(stat, 5, 5, 2, .6, 3),
            iOS_.id: self.generate_fixture_data(stat, 5, 5, 2, .6, 3),
            react_native_.id: self.generate_fixture_data(stat, 5, 5, 10, .6, 3),
            electron_.id: self.generate_fixture_data(stat, 5, 3, 8, .6, 3),
            barnowl_.id: self.generate_fixture_data(stat, 1, 1, 3, .6, 3),
            plan9_.id: self.generate_fixture_data(stat, 0, 0, 0, 0, 0, 0)}
        insert_fixture_data(stat, realm_data, RealmCount)

        # TODO: messages_sent_to_stream:is_bot
