# Author: Nic Wolfe <nic@wolfeden.ca>
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
from sickbeard import logger, helpers

MIN_DB_VERSION = 1 # oldest db version we support migrating from
MAX_DB_VERSION = 6

def backupDatabase(version):
    logger.log(u"Backing up database before upgrade")
    if not helpers.backupVersionedFile(db.dbFilename(), version):
        logger.log_error_and_exit(u"Database backup failed, abort upgrading database")
    else:
        logger.log(u"Proceeding with upgrade")


# Add new migrations at the bottom of the list; subclass the previous migration.
class InitialSchema(db.SchemaUpgrade):
    def test(self):
        return self.hasTable("lastUpdate")

    def execute(self):

        if not self.hasTable("lastUpdate") and not self.hasTable("db_version"):
            queries = [
                ("CREATE TABLE lastUpdate (provider TEXT, time NUMERIC);",),
                ("CREATE TABLE lastSearch (provider TEXT, time NUMERIC);",),
                ("CREATE TABLE db_version (db_version INTEGER);",),
                ("CREATE TABLE scene_exceptions (exception_id INTEGER PRIMARY KEY, indexer_id INTEGER KEY, show_name TEXT, season NUMERIC, custom NUMERIC);",),
                ("CREATE TABLE scene_names (indexer_id INTEGER, name TEXT);",),
                ("CREATE TABLE network_timezones (network_name TEXT PRIMARY KEY, timezone TEXT);",),
                ("CREATE TABLE scene_exceptions_refresh (list TEXT PRIMARY KEY, last_refreshed INTEGER);",),
                ("INSERT INTO db_version (db_version) VALUES (6)",),
            ]
            for query in queries:
                if len(query) == 1:
                    self.connection.action(query[0])
                else:
                    self.connection.action(query[0], query[1:])
        else:
            cur_db_version = self.checkDBVersion()

            if cur_db_version < MIN_DB_VERSION:
                logger.log_error_and_exit(u"Your cache database version (" + str(cur_db_version) + ") is too old to migrate from what this version of Sick Beard supports (" + \
                                          str(MIN_DB_VERSION) + ").\n" + \
                                          "Upgrade using a previous version (tag) build 496 to build 501 of Sick Beard first or remove database file to begin fresh."
                                          )

            if cur_db_version > MAX_DB_VERSION:
                logger.log_error_and_exit(u"Your cache database version (" + str(cur_db_version) + ") has been incremented past what this version of Sick Beard supports (" + \
                                          str(MAX_DB_VERSION) + ").\n" + \
                                          "If you have used other forks of Sick Beard, your database may be unusable due to their modifications."
                                          )

class AddSceneExceptions(InitialSchema):
    def test(self):
        return self.hasTable("scene_exceptions")

    def execute(self):
        self.connection.action(
            "CREATE TABLE scene_exceptions (exception_id INTEGER PRIMARY KEY, tvdb_id INTEGER KEY, show_name TEXT)")

class AddSceneNameCache(AddSceneExceptions):
    def test(self):
        return self.hasTable("scene_names")

    def execute(self):
        self.connection.action("CREATE TABLE scene_names (tvdb_id INTEGER, name TEXT)")


class AddNetworkTimezones(AddSceneNameCache):
    def test(self):
        return self.hasTable("network_timezones")

    def execute(self):
        self.connection.action("CREATE TABLE network_timezones (network_name TEXT PRIMARY KEY, timezone TEXT)")

class AddLastSearch(AddNetworkTimezones):
    def test(self):
        return self.hasTable("lastSearch")

    def execute(self):
        self.connection.action("CREATE TABLE lastSearch (provider TEXT, time NUMERIC)")

class AddSceneExceptionsSeasons(AddLastSearch):
    def test(self):
        return self.checkDBVersion() >= 2

    def execute(self):
        backupDatabase(self.checkDBVersion())

        if not self.hasColumn("scene_exceptions", "season"):
            self.addColumn("scene_exceptions", "season", "NUMERIC", -1)

        self.incDBVersion()

class AddSceneExceptionsCustom(AddSceneExceptionsSeasons):
    def test(self):
        return self.checkDBVersion() >= 3

    def execute(self):
        backupDatabase(self.checkDBVersion())

        if not self.hasColumn("scene_exceptions", "custom"):
            self.addColumn("scene_exceptions", "custom", "NUMERIC", 0)

        self.incDBVersion()

class AddSceneExceptionsRefresh(AddSceneExceptionsCustom):
    def test(self):
        return self.checkDBVersion() >= 4

    def execute(self):
        backupDatabase(self.checkDBVersion())

        if self.hasTable("scene_exceptions_refresh"):
            self.connection.action(
                "CREATE TABLE scene_exceptions_refresh (list TEXT PRIMARY KEY, last_refreshed INTEGER)")

        self.incDBVersion()

class MigrateTvdbidToIndexerIdInScheneNames(AddSceneExceptionsRefresh):
    def test(self):
        return self.checkDBVersion() >= 5
 
    def execute(self):
        backupDatabase(self.checkDBVersion())

        if not self.hasColumn("scene_names", "indexer_id"):
            self.connection.action("ALTER TABLE scene_names RENAME TO tmp_scene_names")
            self.connection.action("CREATE TABLE scene_names (indexer_id INTEGER, name TEXT)")
            self.connection.action("INSERT INTO scene_names(indexer_id, name) SELECT tvdb_id, name FROM tmp_scene_names")
            self.connection.action("DROP TABLE tmp_scene_names")

        self.incDBVersion()

class MigrateTvdbidToIndexerIdInSceneExceptions(MigrateTvdbidToIndexerIdInScheneNames):
    def test(self):
        return self.checkDBVersion() >= 6

    def execute(self):
        backupDatabase(self.checkDBVersion())

        if not self.hasColumn("scene_exceptions", "indexer_id"):
            self.connection.action("ALTER TABLE scene_exceptions RENAME TO tmp_scene_exceptions")
            self.connection.action("CREATE TABLE scene_exceptions (exception_id INTEGER PRIMARY KEY, indexer_id INTEGER KEY, show_name TEXT)")
            self.connection.action("INSERT INTO scene_exceptions(exception_id, indexer_id, show_name) SELECT exception_id, tvdb_id, show_name FROM tmp_scene_exceptions")
            self.connection.action("DROP TABLE tmp_scene_exceptions")

        self.incDBVersion()

