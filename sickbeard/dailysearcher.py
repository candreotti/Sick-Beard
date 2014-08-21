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


class DailySearcher():
    def __init__(self):
        self.lock = threading.Lock()
        self.amActive = False

    def run(self, force=False):

        self.amActive = True

        didSearch = False

        providers = [x for x in sickbeard.providers.sortedProviderList() if x.isActive() and not x.backlog_only]
        for curProviderCount, curProvider in enumerate(providers):

            logger.log(u"Updating [" + curProvider.name + "] RSS cache ...")

            try:
                curProvider.cache.updateCache()
            except exceptions.AuthException, e:
                logger.log(u"Authentication error: " + ex(e), logger.ERROR)
                continue
            except Exception, e:
                logger.log(u"Error while updating cache for " + curProvider.name + ", skipping: " + ex(e), logger.ERROR)
                logger.log(traceback.format_exc(), logger.DEBUG)
                continue

            didSearch = True

        if didSearch:
            logger.log(u"Searching for coming episodes and 1 weeks worth of previously WANTED episodes ...")

            fromDate = datetime.date.today() - datetime.timedelta(weeks=1)
            curDate = datetime.date.today()

            myDB = db.DBConnection()
            sqlResults = myDB.select("SELECT * FROM tv_episodes WHERE status in (?,?,?,?) AND airdate >= ? AND airdate <= ?",
                                     [common.UNAIRED, common.WANTED, common.SKIPPED, common.DOWNLOADABLE, fromDate.toordinal(), curDate.toordinal()])

            sql_l = []
            for sqlEp in sqlResults:
                try:
                    show = helpers.findCertainShow(sickbeard.showList, int(sqlEp["showid"]))
                except exceptions.MultipleShowObjectsException:
                    logger.log(u"ERROR: expected to find a single show matching " + sqlEp["showid"])
                    continue
                except exceptions.ShowNotFoundException:
                    logger.log(u"ERROR: No show found" + sqlEp["showid"])
                    continue

                ep = show.getEpisode(int(sqlEp["season"]), int(sqlEp["episode"]))
                with ep.lock:
                    if ep.show.paused:
                        ep.status = common.SKIPPED
                    else:
                        if ep.status == common.UNAIRED:

                            myDB = db.DBConnection()
                            sql_selection="SELECT show_name, indexer_id, season, episode, paused FROM (SELECT * FROM tv_shows s,tv_episodes e WHERE s.indexer_id = e.showid) T1 WHERE T1.paused = 0 and T1.episode_id IN (SELECT T2.episode_id FROM tv_episodes T2 WHERE T2.showid = T1.indexer_id and T2.status in (?,?,?,?) and T2.season!=0 ORDER BY T2.season,T2.episode LIMIT 1) ORDER BY T1.show_name,season,episode"
                            results = myDB.select(sql_selection, [common.SNATCHED, common.WANTED, common.SKIPPED, common.DOWNLOADABLE])

                            show_sk = [show for show in results if show["indexer_id"] == sqlEp["showid"]]
                            if not show_sk or not sickbeard.USE_TRAKT:
                                logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to WANTED")
                                ep.status = common.WANTED
                            else:
                                sn_sk = show_sk[0]["season"]
                                ep_sk = show_sk[0]["episode"]
                                if (int(sn_sk)*100+int(ep_sk)) < (int(sqlEp["season"])*100+int(sqlEp["episode"])) or not show_sk:
                                    logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to WANTED, due to trakt integration")
                                    ep.status = common.SKIPPED
                                else:
                                    logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to WANTED")
                                    ep.status = common.WANTED

                    sql_l.append(ep.get_sql())

                    if ep.status in (common.WANTED, common.SKIPPED, common.DOWNLOADABLE):
                        dailysearch_queue_item = sickbeard.search_queue.DailySearchQueueItem(show, [ep])
                        sickbeard.searchQueueScheduler.action.add_item(dailysearch_queue_item)
            else:
                logger.log(u"Could not find any wanted episodes for the last 7 days to search for")

            if len(sql_l) > 0:
                myDB = db.DBConnection()
                myDB.mass_action(sql_l)

        else:
            logger.log(
                u"No NZB/Torrent providers found or enabled in the sickbeard config. Please check your settings.",
                logger.ERROR)

        self.amActive = False
