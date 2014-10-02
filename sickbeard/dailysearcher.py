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

        logger.log(u"Searching for new released episodes ...")

        curDate = datetime.date.today().toordinal()

        myDB = db.DBConnection()
        sqlResults = myDB.select("SELECT * FROM tv_episodes WHERE status = ? AND season > 0 AND airdate <= ?",
                                 [common.UNAIRED, curDate])

        sql_l = []
        show = None

        for sqlEp in sqlResults:
            try:
                if not show or int(sqlEp["showid"]) != show.indexerid:
                    show = helpers.findCertainShow(sickbeard.showList, int(sqlEp["showid"]))

                # for when there is orphaned series in the database but not loaded into our showlist
                if not show:
                    continue

            except exceptions.MultipleShowObjectsException:
                logger.log(u"ERROR: expected to find a single show matching " + sqlEp["showid"])
                continue

            ep = show.getEpisode(int(sqlEp["season"]), int(sqlEp["episode"]))
            if ep.status == common.UNAIRED:
                with ep.lock:
                    if ep.show.paused:
                        ep.status = common.SKIPPED
                    else:
                        if ep.status == common.UNAIRED:
                            myDB = db.DBConnection()
                            sql_selection="SELECT show_name, indexer_id, season, episode, paused FROM (SELECT * FROM tv_shows s,tv_episodes e WHERE s.indexer_id = e.showid) T1 WHERE T1.paused = 0 and T1.episode_id IN (SELECT T2.episode_id FROM tv_episodes T2 WHERE T2.showid = T1.indexer_id and T2.status in (?,?) and T2.season!=0 ORDER BY T2.season,T2.episode LIMIT 1) ORDER BY T1.show_name,season,episode"
                            results = myDB.select(sql_selection, [common.SKIPPED, common.DOWNLOADABLE])
                            show_sk = [tshow for tshow in results if tshow["indexer_id"] == sqlEp["showid"]]
                            if not show_sk or not sickbeard.USE_TRAKT:
                                logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to WANTED")
                                ep.status = common.WANTED                         
                            else:
                                sn_sk = show_sk[0]["season"]
                                ep_sk = show_sk[0]["episode"]
                                if (int(sn_sk)*100+int(ep_sk)) < (int(sqlEp["season"])*100+int(sqlEp["episode"])) or not show_sk:
                                    logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to SKIPPED, due to trakt integration")
                                    ep.status = common.SKIPPED
                                else:
                                    logger.log(u"New episode " + ep.prettyName() + " airs today, setting status to WANTED")
                                    ep.status = common.WANTED

                sql_l.append(ep.get_sql())
        else:
            logger.log(u"No new released episodes found ...")

        if len(sql_l) > 0:
            myDB = db.DBConnection()
            myDB.mass_action(sql_l)

        # queue episode for daily search
        dailysearch_queue_item = sickbeard.search_queue.DailySearchQueueItem()
        sickbeard.searchQueueScheduler.action.add_item(dailysearch_queue_item)

        self.amActive = False