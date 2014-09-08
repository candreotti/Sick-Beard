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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement

import datetime
import threading

import sickbeard

from sickbeard import db, scheduler
from sickbeard import search_queue
from sickbeard import logger
from sickbeard import ui
from sickbeard import common

class DownloadableSearchScheduler(scheduler.Scheduler):

    def forceSearch(self):
        self.action._set_last_DownloadableSearch(1)
        self.lastRun = datetime.datetime.fromordinal(1)

    def nextRun(self):
        if self.action._last_DownloadableSearch <= 1:
            return datetime.date.today()
        else:
            return datetime.date.fromordinal(self.action._last_DownloadableSearch + self.action.cycleTime)

class DownloadableSearcher:

    def __init__(self):

        self._last_DownloadableSearch = self._get_last_DownloadableSearch()

        self.cycleTime = sickbeard.DOWNLOADABLE_SEARCH_FREQUENCY/60/24
        self.lock = threading.Lock()
        self.amActive = False
        self.amPaused = False
        self.amWaiting = False

        self._resetPI()

    def _resetPI(self):
        self.percentDone = 0
        self.currentSearchInfo = {'title': 'Initializing'}

    def getProgressIndicator(self):
        if self.amActive:
            return ui.ProgressIndicator(self.percentDone, self.currentSearchInfo)
        else:
            return None

    def am_running(self):
        logger.log(u"amWaiting: " + str(self.amWaiting) + ", amActive: " + str(self.amActive), logger.DEBUG)
        return (not self.amWaiting) and self.amActive

    def searchDownloadable(self, which_shows=None):

        if self.amActive:
            logger.log(u"Downloadable search is still running, not starting it again", logger.DEBUG)
            return

        if which_shows:
            show_list = which_shows
        else:
            show_list = sickbeard.showList

        self._get_last_DownloadableSearch()

        curDate = datetime.date.today().toordinal()
        fromDate = datetime.date.fromordinal(1)

        if not which_shows and not curDate - self._last_DownloadableSearch >= self.cycleTime:
            logger.log(u"Running limited Downloadable search on recently missed episodes only")
            fromDate = datetime.date.today() - datetime.timedelta(days=7)

        self.amActive = True
        self.amPaused = False

        # go through non air-by-date shows and see if they need any episodes
        for curShow in show_list:

            segments = self._get_segments(curShow, fromDate)

            for season, segment in segments.items():
                self.currentSearchInfo = {'title': curShow.name + " Season " + str(season)}

                download_search_queue_item = search_queue.DownloadSearchQueueItem(curShow, segment)
                sickbeard.searchQueueScheduler.action.add_item(download_search_queue_item)  # @UndefinedVariable
            else:
                logger.log(u"Nothing is available for " + str(curShow.name) + ", skipping this season",
                           logger.DEBUG)

        # don't consider this an actual downloadable search if we only did recent eps
        # or if we only did certain shows
        if fromDate == datetime.date.fromordinal(1) and not which_shows:
            self._set_last_DownloadableSearch(curDate)

        self.amActive = False
        self._resetPI()

    def _get_last_DownloadableSearch(self):

        logger.log(u"Retrieving the last check time from the DB", logger.DEBUG)

        myDB = db.DBConnection()
        sqlResults = myDB.select("SELECT * FROM info")

        if len(sqlResults) == 0:
            last_DownloadableSearch = 1
        elif sqlResults[0]["last_DownloadableSearch"] == None or sqlResults[0]["last_DownloadableSearch"] == "":
            last_DownloadableSearch = 1
        else:
            last_DownloadableSearch = int(sqlResults[0]["last_DownloadableSearch"])
            if last_DownloadableSearch > datetime.date.today().toordinal():
                last_DownloadableSearch = 1

        self._last_DownloadableSearch = last_DownloadableSearch
        return self._last_DownloadableSearch

    def _get_segments(self, show, fromDate):
        anyQualities, bestQualities = common.Quality.splitQuality(show.quality)  #@UnusedVariable

        logger.log(u"Seeing if we need anything from " + show.name)

        myDB = db.DBConnection()
        if show.air_by_date:
            sqlResults = myDB.select(
                "SELECT ep.status, ep.season, ep.episode FROM tv_episodes ep, tv_shows show WHERE season != 0 AND ep.showid = show.indexer_id AND ep.airdate > ? AND ep.showid = ? AND show.air_by_date = 1",
                [fromDate.toordinal(), show.indexerid])
        else:
            sqlResults = myDB.select(
                "SELECT status, season, episode FROM tv_episodes WHERE showid = ? AND season > 0 and airdate > ?",
                [show.indexerid, fromDate.toordinal()])

        # check through the list of statuses to see if we want any
        downloadable = {}
        for result in sqlResults:
            curCompositeStatus = int(result["status"])
            curStatus, curQuality = common.Quality.splitCompositeStatus(curCompositeStatus)

            if bestQualities:
                highestBestQuality = max(bestQualities)
            else:
                highestBestQuality = 0

            # if we need a better one then say yes
            if curStatus == common.SKIPPED:

                epObj = show.getEpisode(int(result["season"]), int(result["episode"]))
                if epObj.season not in downloadable:
                    downloadable[epObj.season] = [epObj]
                else:
                    downloadable[epObj.season].append(epObj)

        return downloadable

    def _set_last_DownloadableSearch(self, when):

        logger.log(u"Setting the last downloadable search in the DB to " + str(when), logger.DEBUG)

        myDB = db.DBConnection()
        sqlResults = myDB.select("SELECT * FROM info")

        if len(sqlResults) == 0:
            myDB.action("INSERT INTO info (last_downloadablesearch, last_backlog, last_indexer, last_proper_search) VALUES (?,?,?,?)", [str(when), 0, 0, 0])
        else:
            myDB.action("UPDATE info SET last_downloadablesearch=" + str(when))


    def run(self, force=False):
        try:
            self.searchDownloadable()
        except:
            self.amActive = False
            raise
