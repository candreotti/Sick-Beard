# Author: Frank Fenton
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

import os
import traceback

import sickbeard
from sickbeard import encodingKludge as ek
from sickbeard import logger
from sickbeard import helpers
from sickbeard import search_queue
from sickbeard import db
from sickbeard.common import SNATCHED, SNATCHED_PROPER, DOWNLOADED, DOWNLOADABLE, SKIPPED, UNAIRED, IGNORED, ARCHIVED, WANTED, UNKNOWN, FAILED
from common import Quality, qualityPresetStrings, statusStrings
from lib.trakt import *
from indexers.indexer_config import INDEXER_TVDB, INDEXER_TVRAGE


class TraktChecker():
    def __init__(self):
        self.todoWanted = []
        self.todoBacklog = []
        self.ShowWatchlist = []
        self.EpisodeWatchlist = []
        self.ShowProgress = []
        self.EpisodeWatched = []

    def run(self, force=False):
        if not sickbeard.USE_TRAKT:
            return

        if not self._getShowWatchlist():
            return
        if not self._getEpisodeWatchlist():
            return
        if not self._getShowProgress():
            return
        if not self._getEpisodeWatched():
            return

        try:
            # add shows from trakt.tv watchlist
            if sickbeard.TRAKT_USE_WATCHLIST:
                self.todoWanted = []  # its about to all get re-added
                if len(sickbeard.ROOT_DIRS.split('|')) < 2:
                    logger.log(u"No default root directory", logger.ERROR)
                    return
                self.updateShows()
                self.updateEpisodes()
                self.updateWantedList()

            if sickbeard.TRAKT_REMOVE_SHOW_WATCHLIST:
                self.removeShowFromWatchList()
                self.addShowToWatchList()

            if sickbeard.TRAKT_REMOVE_WATCHLIST:
                self.removeEpisodeFromWatchList()
                self.addEpisodeToWatchList()

            # sync trakt.tv library with sickbeard library
            if sickbeard.TRAKT_SYNC:
                self.syncLibrary()
        except Exception:
            logger.log(traceback.format_exc(), logger.DEBUG)

    def findShow(self, indexer, indexerid):
        library = TraktCall("user/library/shows/all.json/%API%/" + sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)

        if library == 'NULL':
            logger.log(u"No shows found in your library, aborting library update", logger.DEBUG)
            return

        if not library:
            logger.log(u"Could not connect to trakt service, aborting library check", logger.ERROR)
            return

        return filter(lambda x: int(indexerid) in [int(x['tvdb_id']) or 0, int(x['tvrage_id'])] or 0, library)

    def syncLibrary(self):
        logger.log(u"Syncing Trakt.tv show library", logger.DEBUG)

        for myShow in sickbeard.showList:
            self.addShowToTraktLibrary(myShow)

    def removeShowFromTraktLibrary(self, show_obj):
        data = {}
        if self.findShow(show_obj.indexer, show_obj.indexerid):
            # URL parameters
            data['tvdb_id'] = helpers.mapIndexersToShow(show_obj)[1]
            data['title'] = show_obj.name
            data['year'] = show_obj.startyear

        if len(data):
            logger.log(u"Removing " + show_obj.name + " from trakt.tv library", logger.DEBUG)
            TraktCall("show/unlibrary/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD,
                      data)

    def addShowToTraktLibrary(self, show_obj):
        """
        Sends a request to trakt indicating that the given show and all its episodes is part of our library.

        show_obj: The TVShow object to add to trakt
        """

        data = {}

        if not self.findShow(show_obj.indexer, show_obj.indexerid):
            # URL parameters
            data['tvdb_id'] = helpers.mapIndexersToShow(show_obj)[1]
            data['title'] = show_obj.name
            data['year'] = show_obj.startyear

        if len(data):
            logger.log(u"Adding " + show_obj.name + " to trakt.tv library", logger.DEBUG)
            TraktCall("show/library/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD,
                      data)

    def _getEpisodeWatchlist(self):
        
        self.EpisodeWatchlist = TraktCall("user/watchlist/episodes.json/%API%/" + sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)
        if self.EpisodeWatchlist is None:
            logger.log(u"Could not connect to trakt service, cannot download Episode Watchlist", logger.ERROR)
            return False

        return True

    def _getShowWatchlist(self):

        self.ShowWatchlist = TraktCall("user/watchlist/shows.json/%API%/" + sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)
        if self.ShowWatchlist is None:
            logger.log(u"Could not connect to trakt service, cannot download Show Watchlist", logger.ERROR)
            return False

        return True

    def _getShowProgress(self):

        self.ShowProgress = TraktCall("user/progress/watched.json/%API%/" + sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)
        if self.ShowProgress is None:
            logger.log(u"Could not connect to trakt service, cannot download show progress", logger.ERROR)
            return False

        return True

    def _getEpisodeWatched(self):

        self.EpisodeWatched = TraktCall("user/library/shows/watched.json/%API%/" + sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)
        if self.EpisodeWatched is None:
            logger.log(u"Could not connect to trakt service, cannot download show from library", logger.ERROR)
            return False

        return True

    def refreshEpisodeWatchlist(self):

       if not self._getEpisodeWatchlist():
           return False

       return True

    def refreshShowWatchlist(self):

       if not self._getShowWatchlist():
           return False
       
       return True

    def removeEpisodeFromWatchList(self):

        if sickbeard.TRAKT_REMOVE_WATCHLIST and sickbeard.USE_TRAKT:
            logger.log(u"Start looking if some episode has to be removed from watchlist", logger.DEBUG)
            if self.EpisodeWatchlist == 'NULL':
                logger.log(u"Episode watchlist is empty", logger.DEBUG)
                return True 
            for show in self.EpisodeWatchlist:
                logger.log(u"show: " + str(show), logger.WARNING)
                for episode in show["episodes"]:
                    newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])
                    if newShow is not None:
                        ep_obj = newShow.getEpisode(int(episode["season"]), int(episode["number"]))
                        if ep_obj is not None:
                            if ep_obj.status != WANTED and ep_obj.status != UNKNOWN and ep_obj.status not in Quality.SNATCHED and ep_obj.status not in Quality.SNATCHED_PROPER:
                                if self.episode_in_watchlist(newShow, episode["season"], episode["number"]):
                                    logger.log(u"Removing episode: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + ", Season " + str(episode["season"]) + ", Episode " + str(episode["number"]) + ", Status " + str(ep_obj.status) + " from Watchlist", logger.DEBUG)
                                    if not self.update_watchlist("episode", "remove", newShow, episode["season"], episode["number"]):
                                        return False
                        else:
                            logger.log(u"Episode: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + ", Season " + str(episode["season"]) + ", Episode" + str(episode["number"]) + " not in Sickberad ShowList", logger.DEBUG)
                            continue
                    else:
                        logger.log(u"Show: tvdb_id " + str(show["tvdb_id"]) + ", Title " + str(show["title"]) + " not in Sickberad ShowList", logger.DEBUG)
                        continue

            logger.log(u"Stop looking if some episode has to be removed from watchlist", logger.DEBUG)

    def removeShowFromWatchList(self):

        if sickbeard.TRAKT_REMOVE_SHOW_WATCHLIST and sickbeard.USE_TRAKT:
            logger.log(u"Start looking if some show has to be removed from watchlist", logger.DEBUG)
            if self.ShowWatchlist == 'NULL':
                logger.log(u"Show watchlist is empty", logger.WARNING)
                return True 
            for show in self.ShowWatchlist:
                newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])
                if (newShow is not None) and (newShow.status == "Ended"):
                    if self.show_full_watched(newShow):
                        logger.log(u"Deleting show: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + " from SickBeard", logger.DEBUG)
                        newShow.deleteShow()
                        logger.log(u"Removing show: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + " from Watchlist", logger.DEBUG)
                        if not self.update_watchlist("show", "remove", newShow, 0, 0):
                            return False

            logger.log(u"Stop looking if some show has to be removed from watchlist", logger.DEBUG)
				
    def addEpisodeToWatchList(self, indexer_id=None):

        if sickbeard.TRAKT_REMOVE_WATCHLIST and sickbeard.USE_TRAKT:
            logger.log(u"Start looking if some WANTED episode need to be added to watchlist", logger.DEBUG)

            myDB = db.DBConnection()
            sql_selection='select tv_shows.indexer, showid, show_name, season, episode from tv_episodes,tv_shows where tv_shows.indexer_id = tv_episodes.showid and tv_episodes.status in ('+','.join([str(x) for x in Quality.SNATCHED + Quality.SNATCHED_PROPER + [WANTED]])+')'
            if indexer_id is None:
                episodes = myDB.select(sql_selection)
            else:
                sql_selection=sql_selection+" and showid=?"
                episodes = myDB.select(sql_selection, [indexer_id]) 
            if episodes is not None:
                for cur_episode in episodes:
                    newShow = helpers.findCertainShow(sickbeard.showList, int(cur_episode["showid"])) 
                    if not self.episode_in_watchlist(newShow, cur_episode["season"], cur_episode["episode"]):
                        logger.log(u"Episode: Indexer " + str(cur_episode["indexer"]) + ", indexer_id " + str(cur_episode["showid"])+ ", Title " +  str(cur_episode["show_name"]) + " " + str(cur_episode["season"]) + "x" + str(cur_episode["episode"]) + " should be added to watchlist", logger.DEBUG)
                        if not self.update_watchlist("episode", "add", newShow, cur_episode["season"], cur_episode["episode"]):
                            return False

            logger.log(u"Stop looking if some WANTED episode need to be added to watchlist", logger.DEBUG)
			
    def addShowToWatchList(self):

        if sickbeard.TRAKT_REMOVE_SHOW_WATCHLIST and sickbeard.USE_TRAKT:
            logger.log(u"Start looking if some show need to be added to watchlist", logger.DEBUG)

            if sickbeard.showList is not None:
                for show in sickbeard.showList:
                    if not self.show_in_watchlist(show):
                        logger.log(u"Show: Indexer " + str(show.indexer) + ", indexer_id " + str(show.indexerid) + ", Title " +  str(show.name) + " should be added to watchlist", logger.DEBUG)
                        if not self.update_watchlist("show", "add", show, 0, 0):
                                return False
				
            logger.log(u"Stop looking if some show need to be added to watchlist", logger.DEBUG)

    def updateWantedList(self, indexer_id = None, paused=False):

        num_of_download = sickbeard.TRAKT_NUM_EP

        if num_of_download == 0 or self.EpisodeWatched == 'NULL':
            return True

        logger.log(u"Start looking if having " + str(num_of_download) + " episode not watched", logger.DEBUG)

        if paused == False:
            p=0
        else:
            p=1

        myDB = db.DBConnection()

        sql_selection="SELECT indexer,show_name, indexer_id, season, episode, paused FROM (SELECT * FROM tv_shows s,tv_episodes e WHERE s.indexer_id = e.showid) T1 WHERE T1.paused = ? and T1.episode_id IN (SELECT T2.episode_id FROM tv_episodes T2 WHERE T2.showid = T1.indexer_id and T2.status in (?,?,?) and T2.season!=0 and airdate is not null ORDER BY T2.season,T2.episode LIMIT 1)"

        if indexer_id is not None:
            sql_selection=sql_selection + " and indexer_id = " + str(indexer_id)

	sql_selection=sql_selection + " ORDER BY T1.show_name,season,episode"

        results = myDB.select(sql_selection,[p,SKIPPED,DOWNLOADABLE,FAILED])

        for cur_result in results:

            indexer_id = str(cur_result["indexer_id"])
            show_name = (cur_result["show_name"])
            sn_sb = cur_result["season"]
            ep_sb = cur_result["episode"]

            newShow = helpers.findCertainShow(sickbeard.showList, int(indexer_id))
            tvdb_id = str(helpers.mapIndexersToShow(newShow)[1])

            num_op_ep=0
            season = 0
            episode = 0

            last_per_season = TraktCall("show/seasons.json/%API%/" + str(tvdb_id), sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)
            if not last_per_season:
                logger.log(u"Could not connect to trakt service, cannot download last season for show", logger.ERROR)
                return False

            logger.log(u"indexer_id: " + str(indexer_id) + ", Show: " + show_name + " - First skipped Episode: Season " + str(sn_sb) + ", Episode " + str(ep_sb), logger.DEBUG)

            if tvdb_id not in (show["tvdb_id"] for show in self.EpisodeWatched):
                logger.log(u"Show not founded in Watched list", logger.DEBUG)
                if (sn_sb*100+ep_sb) > 100+num_of_download:
                    logger.log(u"First " + str(num_of_download) + " episode already downloaded", logger.DEBUG)
                    continue
                else:
                    sn_sb = 1
                    ep_sb = 1
                    num_of_ep = num_of_download
                    episode = 0
            else:
                logger.log(u"Show founded in Watched list", logger.DEBUG)

                show_watched = [show for show in self.EpisodeWatched if show["tvdb_id"] == tvdb_id]
			
                season = show_watched[0]['seasons'][0]['season']
                episode = show_watched[0]['seasons'][0]['episodes'][-1]
                logger.log(u"Last watched, Season: " + str(season) + " - Episode: " + str(episode), logger.DEBUG)

                num_of_ep = num_of_download - (self._num_ep_for_season(last_per_season, sn_sb, ep_sb) - self._num_ep_for_season(last_per_season, season, episode)) + 1

            logger.log(u"Number of Episode to Download: " + str(num_of_ep), logger.DEBUG)

            s = sn_sb
            e = ep_sb

            wanted = False

            for x in range(0,num_of_ep):

                last_s = [last_x_s for last_x_s in last_per_season if last_x_s['season'] == s]
                if last_s is None:
                    break
                if episode == 0 or (s*100+e) <= (int(last_s[0]['season'])*100+int(last_s[0]['episodes'])): 

                    if (s*100+e) > (season*100+episode):
                        if not paused:
                            if newShow is not None:
                                self.setEpisodeToWanted(newShow, s, e)
                                if not self.episode_in_watchlist(newShow, s, e):
                                    if not self.update_watchlist("episode", "add", newShow, s, e):
                                        return False
                                wanted = True
                            else:
                                self.todoWanted.append(int(indexer_id), s, e)
                    else:
                        self.setEpisodeToIgnored(newShow, s, e)
                        if self.episode_in_watchlist(newShow, s, e):
                            if not self.update_watchlist("episode", "remove", newShow, s, e):
                                return False
                    e = e + 1

                elif (s*100+e) == (int(last_s[0]['season'])*100+int(last_s[0]['episodes'])):
                    s = s + 1
                    e = 1
				
            if wanted:
                self.startBacklog(newShow)
        logger.log(u"Stop looking if having " + str(num_of_download) + " episode not watched", logger.DEBUG)
        return True

    def updateShows(self):
        logger.log(u"Start looking if some show need to be added to SickBeard", logger.DEBUG)
        if self.ShowWatchlist == 'NULL':
            logger.log(u"Show watchlist is empty", logger.DEBUG)
            return True
        for show in self.ShowWatchlist:
            indexer = int(sickbeard.TRAKT_DEFAULT_INDEXER)
            if indexer == INDEXER_TVRAGE:
                indexer_id = int(show["tvrage_id"])
            else:
                indexer_id = int(show["tvdb_id"])

            if int(sickbeard.TRAKT_METHOD_ADD) != 2:
                self.addDefaultShow(indexer, indexer_id, show["title"], SKIPPED)
            else:
                self.addDefaultShow(indexer, indexer_id, show["title"], WANTED)

            if int(sickbeard.TRAKT_METHOD_ADD) == 1:
                newShow = helpers.findCertainShow(sickbeard.showList, indexer_id)
                if newShow is not None:
                    self.setEpisodeToWanted(newShow, 1, 1)
                    if not self.episode_in_watchlist(newShow, 1, 1):
                        if not self.update_watchlist("episode", "add", newShow, 1, 1):
                            return False
                    self.startBacklog(newShow)
                else:
                    self.todoWanted.append((indexer_id, 1, 1))
            self.todoWanted.append((indexer_id, -1, -1))  # used to pause new shows if the settings say to
        logger.log(u"Stop looking if some show need to be added to SickBeard", logger.DEBUG)

    def updateEpisodes(self):
        """
        Sets episodes to wanted that are in trakt watchlist
        """
        logger.log(u"Start looking if some episode in WatchList has to be set WANTED", logger.DEBUG)
        if self.EpisodeWatchlist == 'NULL':
            logger.log(u"Episode watchlist is empty", logger.DEBUG)
            return 

        for show in self.EpisodeWatchlist:

            #self.addDefaultShow(indexer, indexer_id, show["title"], SKIPPED)
            newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])

            try:
                for episode in show["episodes"]:
                    if newShow is not None:
                        epObj = newShow.getEpisode(int(episode["season"]), int(episode["number"]))
                        if epObj.status != WANTED:
                            self.setEpisodeToWanted(newShow, episode["season"], episode["number"])
                            if not self.episode_in_watchlist(newShow, episode["season"], episode["number"]):
                                if not self.update_watchlist("episode", "add", newShow, episode["season"], episode["number"]):
                                    return False
                    else:
                        self.todoWanted.append((indexer_id, episode["season"], episode["number"]))
                self.startBacklog(newShow)
            except TypeError:
                logger.log(u"Could not parse the output from trakt for " + show["title"], logger.DEBUG)
                return False

        return True

        logger.log(u"Stop looking if some episode in WatchList has to be set WANTED", logger.DEBUG)

    def addDefaultShow(self, indexer, indexer_id, name, status):
        """
        Adds a new show with the default settings
        """
        if not helpers.findCertainShow(sickbeard.showList, int(indexer_id)):
            logger.log(u"Adding show " + str(indexer_id))
            root_dirs = sickbeard.ROOT_DIRS.split('|')

            try:
                location = root_dirs[int(root_dirs[0]) + 1]
            except:
                location = None

            if location:
                showPath = ek.ek(os.path.join, location, helpers.sanitizeFileName(name))
                dir_exists = helpers.makeDir(showPath)
                if not dir_exists:
                    logger.log(u"Unable to create the folder " + showPath + ", can't add the show", logger.ERROR)
                    return
                else:
                    helpers.chmodAsParent(showPath)

                sickbeard.showQueueScheduler.action.addShow(int(indexer), int(indexer_id), showPath, status,
                                                            int(sickbeard.QUALITY_DEFAULT),
                                                            int(sickbeard.FLATTEN_FOLDERS_DEFAULT))
            else:
                logger.log(u"There was an error creating the show, no root directory setting found", logger.ERROR)
                return

    def setEpisodeToIgnored(self, show, s, e):
        """
        Sets an episode to ignored, only is it is currently skipped or Downloadable
        """
        epObj = show.getEpisode(int(s), int(e))
        if epObj == None:
            return
        with epObj.lock:
            if epObj.status not in (SKIPPED, DOWNLOADABLE, FAILED):
                return
            logger.log(u"Setting episode s"+str(s)+"e"+str(e)+" of show " + show.name + " to ignored")

            epObj.status = IGNORED
            epObj.saveToDB()


    def setEpisodeToWanted(self, show, s, e):
        """
        Sets an episode to wanted, only is it is currently skipped or Downloadable
        """
        epObj = show.getEpisode(int(s), int(e))
        if epObj:

            ep_segment = {}

            with epObj.lock:
                if epObj.status not in (SKIPPED, DOWNLOADABLE):
                    return

                logger.log(u"Setting episode s" + str(s) + "e" + str(e) + " of show " + show.name + " to wanted")
                # figure out what segment the episode is in and remember it so we can backlog it

                if epObj.season in ep_segment:
                    ep_segment[epObj.season].append(epObj)
                else:
                    ep_segment[epObj.season] = [epObj]

                epObj.status = WANTED
                epObj.saveToDB()

                backlog = (show, ep_segment)
                if self.todoBacklog.count(backlog) == 0:
                    self.todoBacklog.append(backlog)


    def manageNewShow(self, show):
        episodes = [i for i in self.todoWanted if i[0] == show.indexerid]
        for episode in episodes:
            self.todoWanted.remove(episode)
            if episode[1] == -1 and sickbeard.TRAKT_START_PAUSED:
                show.paused = 1
                continue
            self.setEpisodeToWanted(show, episode[1], episode[2])
            if not self.episode_in_watchlist(show, episode[1], episode[2]):
                if not self.update_watchlist("episode", "add", show,  episode[1], episode[2]):
                    return False
            self.todoWanted.remove(episode)
        self.startBacklog(show)

    def startBacklog(self, show):
        segments = [i for i in self.todoBacklog if i[0] == show]
        for segment in segments:
            cur_backlog_queue_item = search_queue.BacklogQueueItem(show, segment[1])
            sickbeard.searchQueueScheduler.action.add_item(cur_backlog_queue_item)

            for season in segment[1]:
                logger.log(u"Starting backlog for " + show.name + " season " + str(
                    season) + " because some eps were set to wanted")
                self.todoBacklog.remove(segment)

    def show_full_watched (self, show_obj):

        logger.log(u"Checking if show: Indexer " + str(show_obj.indexer) + "indexer_id " + str(show_obj.indexerid) + ", Title " + str(show_obj.name) + " is completely watched", logger.DEBUG)

        found = False
        if self.ShowProgress == 'NULL':
            logger.log(u"Show progress is empty", logger.DEBUG)
            return found 

        for pshow in self.ShowProgress:

            if int(show_obj.indexer) == INDEXER_TVRAGE:
                indexer_id = int(pshow["show"]["tvrage_id"])
            else:
                indexer_id = int(pshow["show"]["tvdb_id"])

            if indexer_id == show_obj.indexerid and int(pshow["progress"]["percentage"]) == 100:
                found=True
                break

        return found
	
    def update_watchlist (self, type, update, show_obj, s, e):

        if type=="episode":
            # traktv URL parameters
            data = {
                'tvdb_id': helpers.mapIndexersToShow(show_obj)[1],
                'episodes': [ {
                    'season': s,
                    'episode': e
                    } ]
                }
            if update=="add" and sickbeard.TRAKT_REMOVE_WATCHLIST:
                result=TraktCall("show/episode/watchlist/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD, data)
            elif update=="remove" and sickbeard.TRAKT_REMOVE_WATCHLIST:
                result=TraktCall("show/episode/unwatchlist/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD, data)
            if not self._getEpisodeWatchlist():
                return False
        elif type=="show":
            # traktv URL parameters
            data = {
                'shows': [ {
                    'tvdb_id': helpers.mapIndexersToShow(show_obj)[1]
                    } ]
                }
            if update=="add"  and sickbeard.TRAKT_REMOVE_SHOW_WATCHLIST:
                result=TraktCall("show/watchlist/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD, data)
            elif update=="remove" and sickbeard.TRAKT_REMOVE_SHOW_WATCHLIST:
            	result=TraktCall("show/unwatchlist/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD, data)
            if not self._getShowWatchlist():
                return False
        else:
            logger.log(u"Error invoking update_watchlist procedure, check parameter", logger.ERROR)
            return False

        return True
	
    def show_in_watchlist (self, show_obj):

        found = False
        if self.ShowWatchlist == 'NULL':
            logger.log(u"Show watchlist is empty", logger.DEBUG)
            return found 

        for show in self.ShowWatchlist:

            if int(show_obj.indexer) == INDEXER_TVRAGE:
                indexer_id = int(show["tvrage_id"])
            else:
                indexer_id = int(show["tvdb_id"])

            if indexer_id == show_obj.indexerid:
                found=True
                break

        return found
			
    def episode_in_watchlist (self, show_obj, s, e):

        found = False
        if self.EpisodeWatchlist == 'NULL':
            logger.log(u"Episode watchlist is empty", logger.DEBUG)
            return found 

        for show in self.EpisodeWatchlist:

            if show_obj.indexer == int(INDEXER_TVRAGE):
                indexer_id = int(show["tvrage_id"])
            else:
                indexer_id = int(show["tvdb_id"])

            for episode in show["episodes"]:
                if s==episode["season"] and e==episode["number"] and indexer_id==show_obj.indexerid:
                    found=True
                    break

        return found
			
    def _num_ep_for_season(self, show, season, episode):
		
        num_ep = 0

        for curSeason in show:

            sn = int(curSeason["season"])
            ep = int(curSeason["episodes"])

            if (sn < season):
                num_ep = num_ep + (ep)
            elif (sn == season):
                num_ep = num_ep + episode
            elif (sn == 0):
                continue
            else:
                continue

        return num_ep
	
