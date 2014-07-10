# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of SickBeard.
#
# SickBeard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickBeard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickBeard.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
import time
import datetime
import threading
import traceback

import sickbeard
from sickbeard import logger
from sickbeard import db
from sickbeard import common
from sickbeard import helpers
from sickbeard import exceptions
from sickbeard.exceptions import ex
from sickbeard.search import pickBestResult, snatchEpisode
from sickbeard import generic_queue

class DailySearcher():
    def __init__(self):
        self.lock = threading.Lock()

        self.amActive = False

    def run(self, force=False):

        self.amActive = True

        # remove names from cache that link back to active shows that we watch
        sickbeard.name_cache.syncNameCache()

        logger.log(u"Searching for coming episodes and 1 weeks worth of previously WANTED episodes ...")

        fromDate = datetime.date.today() - datetime.timedelta(weeks=1)
        curDate = datetime.date.today()

        myDB = db.DBConnection()
        sqlResults = myDB.select("SELECT * FROM tv_episodes WHERE status in (?,?) AND airdate >= ? AND airdate <= ?",
                                 [common.UNAIRED, common.WANTED, fromDate.toordinal(), curDate.toordinal()])

        todaysEps = {}
        for sqlEp in sqlResults:

            try:
                show = helpers.findCertainShow(sickbeard.showList, int(sqlEp["showid"]))
            except exceptions.MultipleShowObjectsException:
                logger.log(u"ERROR: expected to find a single show matching " + sqlEp["showid"])
                return None

            if show == None:
                logger.log(u"Unable to find the show with ID " + str(
                    sqlEp["showid"]) + " in your show list! DB value was " + str(sqlEp), logger.ERROR)
                return None

            ep = show.getEpisode(sqlEp["season"], sqlEp["episode"])
            with ep.lock:
                if ep.show.paused:
                    ep.status = common.SKIPPED
                else:
                    if ep.status == common.UNAIRED:
                        logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to WANTED")
                        ep.status = common.WANTED

                ep.saveToDB()

                if ep.status == common.WANTED:
                    if show not in todaysEps:
                        todaysEps[show] = [ep]
                    else:
                        todaysEps[show].append(ep)

        if len(todaysEps):
            for show in todaysEps:
                segment = todaysEps[show]
                dailysearch_queue_item = sickbeard.search_queue.DailySearchQueueItem(show, segment)
                sickbeard.searchQueueScheduler.action.add_item(dailysearch_queue_item)  #@UndefinedVariable
        else:
            logger.log(u"Could not find any needed episodes to search for ...")
