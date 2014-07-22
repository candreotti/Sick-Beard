# Author: Tyler Fenby <tylerfenby@gmail.com>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

from sickbeard import db
from sickbeard.common import Quality
from sickbeard import logger, helpers


def backupDatabase(version):
    logger.log(u"Backing up database before upgrade")
    if not helpers.backupVersionedFile(db.dbFilename(), version):
        logger.log_error_and_exit(u"Database backup failed, abort upgrading database")
    else:
        logger.log(u"Proceeding with upgrade")

# Add new migrations at the bottom of the list; subclass the previous migration.
class InitialSchema(db.SchemaUpgrade):
    def test(self):
        return self.hasTable('failed')

    def execute(self):
        queries = [
            ('CREATE TABLE failed (release TEXT);',),
            ('CREATE TABLE db_version (db_version INTEGER);',),
            ('INSERT INTO db_version (db_version) VALUES (1)', ),
        ]
        for query in queries:
            if len(query) == 1:
                self.connection.action(query[0])
            else:
                self.connection.action(query[0], query[1:])


class SizeAndProvider(InitialSchema):
    def test(self):
        return self.hasColumn('failed', 'size') and self.hasColumn('failed', 'provider')

    def execute(self):
        self.addColumn('failed', 'size')
        self.addColumn('failed', 'provider', 'TEXT', '')


class History(SizeAndProvider):
    """Snatch history that can't be modified by the user"""

    def test(self):
        return self.hasTable('history')

    def execute(self):
        self.connection.action('CREATE TABLE history (date NUMERIC, ' +
                               'size NUMERIC, release TEXT, provider TEXT);')


class HistoryStatus(History):
    """Store episode status before snatch to revert to if necessary"""

    def test(self):
        return self.hasColumn('history', 'old_status')

    def execute(self):
        self.addColumn('history', 'old_status', 'NUMERIC', Quality.NONE)
        self.addColumn('history', 'showid', 'NUMERIC', '-1')
        self.addColumn('history', 'season', 'NUMERIC', '-1')
        self.addColumn('history', 'episode', 'NUMERIC', '-1')

class HistoryShowId(History):
    """Store episode status before snatch to revert to if necessary"""

    def test(self):
        return self.checkDBVersion() >= 2

    def execute(self):
        backupDatabase(self.checkDBVersion())

        if not self.hasColumn("history", "showid"):
            self.connection.action("ALTER TABLE history RENAME TO tmp_history")
            self.connection.action("CREATE TABLE history (date NUMERIC, size NUMERIC, release TEXT, provider TEXT, showid NUMERIC, season NUMERIC, episode NUMERIC, old_status NUMERIC)")
            self.connection.action("INSERT INTO history(date, size, release, provider, showid, season, episode, old_status) SELECT date, size, release, provider, showtvdbid, season, episode, old_status FROM tmp_history")
            self.connection.action("DROP TABLE tmp_history")

        self.incDBVersion()

