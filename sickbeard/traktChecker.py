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
import time
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

        try:
            # add shows from trakt.tv watchlist
            if sickbeard.TRAKT_USE_WATCHLIST:
                self.todoWanted = []  # its about to all get re-added
                if len(sickbeard.ROOT_DIRS.split('|')) < 2:
                    logger.log(u"No default root directory", logger.ERROR)
                    returnd
                if not self._getShowWatchlist():
                   return
                if not self._getEpisodeWatchlist():
                    return
                if not self._getShowProgress():
                    return
                if not self._getEpisodeWatched():
                    return

            self.removeShowFromWatchList()
            self.updateShows()
            self.removeEpisodeFromWatchList()
            self.updateEpisodes()
            self.updateWantedList()
            self.addEpisodeToWatchList()
            self.addShowToWatchList()


            # sync trakt.tv library with sickbeard library
            if sickbeard.TRAKT_SYNC:
                self.syncLibrary()
        except Exception:
            logger.log(traceback.format_exc(), logger.DEBUG)

    def findShow(self, indexerid):
        library = TraktCall("user/library/shows/all.json/%API%/" + sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_API,
                            sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)

        results = filter(lambda x: int(x['tvdb_id']) == int(indexerid), library)
        if len(results) == 0:
            return None
        else:
            return results[0]

    def syncLibrary(self):
        logger.log(u"Syncing library to trakt.tv show library", logger.DEBUG)
        if sickbeard.showList:
            for myShow in sickbeard.showList:
                self.addShowToTraktLibrary(myShow)

    def removeShowFromTraktLibrary(self, show_obj):
        if not self.findShow(show_obj.indexerid):
            return

        # URL parameters
        data = {
            'tvdb_id': show_obj.indexerid,
            'title': show_obj.name,
            'year': show_obj.startyear,
        }

        if data is not None:
            logger.log(u"Removing " + show_obj.name + " from trakt.tv library", logger.DEBUG)
            TraktCall("show/unlibrary/%API%", sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD,
                      data)

    def addShowToTraktLibrary(self, show_obj):
        """
        Sends a request to trakt indicating that the given show and all its episodes is part of our library.

        show_obj: The TVShow object to add to trakt
        """

        if self.findShow(show_obj.indexerid):
            return

        # URL parameters
        data = {
            'tvdb_id': show_obj.indexerid,
            'title': show_obj.name,
            'year': show_obj.startyear,
        }

        if data is not None:
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

            for show in self.EpisodeWatchlist:
                for episode in show["episodes"]:
                    newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])
                    if newShow is not None:

                        ep_obj = newShow.getEpisode(int(episode["season"]), int(episode["number"]))
                        if ep_obj is not None:
					
                            if ep_obj.status != WANTED and ep_obj.status != UNKNOWN and ep_obj.status not in Quality.SNATCHED and ep_obj.status not in Quality.SNATCHED_PROPER:
                                if self.episode_in_watchlist(show["imdb_id"], episode["season"], episode["number"]):
                                    logger.log(u"Removing episode: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + ", Season " + str(episode["season"]) + ", Episode " + str(episode["number"]) + ", Status " + str(ep_obj.status) + " from Watchlist", logger.DEBUG)
                                    if not self.update_watchlist("episode", "remove", show["imdb_id"], episode["season"], episode["number"]):
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
            for show in self.ShowWatchlist:
                newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])
                if (newShow is not None) and (newShow.status == "Ended"):
                    if self.show_full_watched(newShow):
                        logger.log(u"Deleting show: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + " from SickBeard", logger.DEBUG)
                        newShow.deleteShow()
                        logger.log(u"Removing show: Indexer " + str(newShow.indexer) + ", indexer_id " + str(newShow.indexerid) + ", Title " + str(newShow.name) + " from Watchlist", logger.DEBUG)
                        if not self.update_watchlist("show", "remove", show["imdb_id"], 0, 0):
                            return False

            logger.log(u"Stop looking if some show has to be removed from watchlist", logger.DEBUG)
				
    def addEpisodeToWatchList(self, indexer_id=None):

        if sickbeard.TRAKT_REMOVE_WATCHLIST and sickbeard.USE_TRAKT:
            logger.log(u"Start looking if some WANTED episode need to be added to watchlist", logger.DEBUG)

            myDB = db.DBConnection()
            sql_selection='select tv_shows.indexer, showid, imdb_id, show_name, season, episode from tv_episodes,tv_shows where tv_shows.indexer_id = tv_episodes.showid and tv_episodes.status in ('+','.join([str(x) for x in Quality.SNATCHED + Quality.SNATCHED_PROPER + [WANTED]])+')'
            if indexer_id is None:
                episode = myDB.select(sql_selection)
            else:
                sql_selection=sql_selection+" and showid=?"
                episode = myDB.select(sql_selection, [indexer_id]) 
            if episode is not None:
                for cur_episode in episode:
                    if not self.episode_in_watchlist(cur_episode["imdb_id"], cur_episode["season"], cur_episode["episode"]):
                        logger.log(u"Episode: Indexer " + str(cur_episode["indexer"]) + ", indexer_id " + str(cur_episode["showid"])+ ", Title " +  str(cur_episode["show_name"]) + " " + str(cur_episode["season"]) + "x" + str(cur_episode["episode"]) + " should be added to watchlist", logger.DEBUG)
                        if not self.update_watchlist("episode", "add", cur_episode["imdb_id"], cur_episode["season"], cur_episode["episode"]):
                            return False

            logger.log(u"Stop looking if some WANTED episode need to be added to watchlist", logger.DEBUG)
			
    def addShowToWatchList(self):

        if sickbeard.TRAKT_REMOVE_SHOW_WATCHLIST and sickbeard.USE_TRAKT:
            logger.log(u"Start looking if some show need to be added to watchlist", logger.DEBUG)

            if sickbeard.showList is not None:
                for show in sickbeard.showList:
                    if not self.show_in_watchlist(show.imdbid):
                        logger.log(u"Show: Indexer " + str(show.indexer) + ", indexer_id " + str(show.indexerid) + ", Title " +  str(show.name) + " should be added to watchlist", logger.DEBUG)
                        if not self.update_watchlist("show", "add", show.imdbid, 0, 0):
                                return False
				
            logger.log(u"Stop looking if some show need to be added to watchlist", logger.DEBUG)

    def updateWantedList(self):

        num_of_download = sickbeard.TRAKT_NUM_EP

        if num_of_download == 0:
            return False

        logger.log(u"Start looking if having " + str(num_of_download) + " episode not watched", logger.DEBUG)

        myDB = db.DBConnection()

        sql_selection="SELECT indexer,show_name, indexer_id, season, episode, paused FROM (SELECT * FROM tv_shows s,tv_episodes e WHERE s.indexer_id = e.showid) T1 WHERE T1.paused = 0 and T1.episode_id IN (SELECT T2.episode_id FROM tv_episodes T2 WHERE T2.showid = T1.indexer_id and T2.status in (?,?,?) and T2.season!=0 and airdate is not null ORDER BY T2.season,T2.episode LIMIT 1) ORDER BY T1.show_name,season,episode"
        results = myDB.select(sql_selection,[SKIPPED,DOWNLOADABLE,FAILED])

        for cur_result in results:

            if int(cur_result["indexer"]) != int(INDEXER_TVDB):
                logger.log(u"UpdateWantedList is not working with TVRAGE indexer, Indexer: " + str(cur_result["indexer"]) + ", indexer_id: " + str(cur_result["indexer_id"]) + ", Title: " + str(cur_result["show_name"]) , logger.ERROR)
                continue

            num_op_ep=0
            season = 0
            episode = 0

            last_per_season = TraktCall("show/seasons.json/%API%/" + str(cur_result["indexer_id"]), sickbeard.TRAKT_API, sickbeard.TRAKT_USERNAME, sickbeard.TRAKT_PASSWORD)
            if not last_per_season:
                logger.log(u"Could not connect to trakt service, cannot download last season for show", logger.ERROR)
                return False

            indexer_id = str(cur_result["indexer_id"])
            show_name = (cur_result["show_name"])
            sn_sb = cur_result["season"]
            ep_sb = cur_result["episode"]

            logger.log(u"indexer_id: " + str(indexer_id) + ", Show: " + show_name + " - First skipped Episode: Season " + str(sn_sb) + ", Episode " + str(ep_sb), logger.DEBUG)

            if indexer_id not in (show["tvdb_id"] for show in self.EpisodeWatched):
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

                show_watched = [show for show in self.EpisodeWatched if show["tvdb_id"] == indexer_id]
			
                season = show_watched[0]['seasons'][0]['season']
                episode = show_watched[0]['seasons'][0]['episodes'][-1]
                logger.log(u"Last watched, Season: " + str(season) + " - Episode: " + str(episode), logger.DEBUG)

                num_of_ep = num_of_download - (self._num_ep_for_season(last_per_season, sn_sb, ep_sb) - self._num_ep_for_season(last_per_season, season, episode)) + 1

            logger.log(u"Number of Episode to Download: " + str(num_of_ep), logger.DEBUG)
            newShow = helpers.findCertainShow(sickbeard.showList, int(indexer_id))

            s = sn_sb
            e = ep_sb

            wanted = False

            for x in range(0,num_of_ep):

                last_s = [last_x_s for last_x_s in last_per_season if last_x_s['season'] == s]
                if episode == 0 or (s*100+e) <= (int(last_s[0]['season'])*100+int(last_s[0]['episodes'])): 

                    if (s*100+e) > (season*100+episode):
                        logger.log(u"Changed episode to wanted: S" + str(s) + "E"+  str(e), logger.DEBUG)
                        if newShow is not None:
                            self.setEpisodeToWanted(newShow, s, e)
                            if not self.episode_in_watchlist(newShow.imdbid, s, e):
                                if not self.update_watchlist("episode", "add", newShow.imdbid, s, e):
                                    return False
                            wanted = True
                        else:
                            self.todoWanted.append(int(indexer_id), s, e)
                    else:
                        logger.log(u"Changed episode to archived: S" + str(s) + "E"+  str(e), logger.DEBUG)
                        self.setEpisodeToArchived(newShow, s, e)
                        if self.episode_in_watchlist(newShow.imdbid, s, e):
                            if not self.update_watchlist("episode", "remove", newShow.imdbid, s, e):
                                return False

                if (s*100+e) == (int(last_s[0]['season'])*100+int(last_s[0]['episodes'])):
                    s = s + 1
                    e = 1
                else:
                    e = e + 1
				
            if wanted:
                self.startBacklog(newShow)
        logger.log(u"Stop looking if having " + str(num_of_download) + " episode not watched", logger.DEBUG)
        return True

    def updateShows(self):
        logger.log(u"Start looking if some show need to be added to SickBeard", logger.DEBUG)
        for show in self.ShowWatchlist:
            if int(sickbeard.TRAKT_METHOD_ADD) != 2:
                self.addDefaultShow(show["tvdb_id"], show["imdb_id"], show["title"], SKIPPED)
            else:
                self.addDefaultShow(show["tvdb_id"], show["imdb_id"], show["title"], WANTED)

	    if int(sickbeard.TRAKT_METHOD_ADD) == 1:
	        newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])
		if newShow is not None:
		    self.setEpisodeToWanted(newShow, 1, 1)
		    if not self.episode_in_watchlist(newShow.imdbid, 1, 1):
		        if not self.update_watchlist("episode", "add", newShow.imdbid, 1, 1):
                            return False
		    self.startBacklog(newShow)
		else:
		    self.todoWanted.append((int(show["tvdb_id"]), 1, 1))
	    self.todoWanted.append((int(show["tvdb_id"]), -1, -1)) #used to pause new shows if the settings say to
        logger.log(u"Stop looking if some show need to be added to SickBeard", logger.DEBUG)

    def updateEpisodes(self):
        """
        Sets episodes to wanted that are in trakt watchlist
        """
        logger.log(u"Start looking if some episode in WatchList has to be set WANTED", logger.DEBUG)
        for show in self.EpisodeWatchlist:
#            self.addDefaultShow(show["tvdb_id"], show["title"], SKIPPED)
            newShow = helpers.findCertainShowFromIMDB(sickbeard.showList, show["imdb_id"])
            for episode in show["episodes"]:
                if newShow is not None:
        	    epObj = newShow.getEpisode(int(episode["season"]), int(episode["number"]))
		    if epObj.status != WANTED:
                    	self.setEpisodeToWanted(newShow, episode["season"], episode["number"])
		    	if not self.episode_in_watchlist(newShow.imdbid, episode["season"], episode["number"]):
		        	if not self.update_watchlist("episode", "add", newShow.imdbid, episode["season"], episode["number"]):
                                    return False
                else:
                    self.todoWanted.append((int(show["tvdb_id"]), episode["season"], episode["number"]))
            self.startBacklog(newShow)
        logger.log(u"Stop looking if some episode in WatchList has to be set WANTED", logger.DEBUG)

    def addDefaultShow(self, indexerid, imdb_id, name, status):
        """
        Adds a new show with the default settings
        """
        showObj = helpers.findCertainShow(sickbeard.showList, int(indexerid))
        if showObj != None:
            return

        logger.log(u"Adding show " + str(indexerid))
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

            sickbeard.showQueueScheduler.action.addShow(1, int(indexerid), showPath, status,
                                                        int(sickbeard.QUALITY_DEFAULT),
                                                        int(sickbeard.FLATTEN_FOLDERS_DEFAULT))
        else:
            logger.log(u"There was an error creating the show, no root directory setting found", logger.ERROR)
            return

        if not self.show_in_watchlist(imdb_id):
            logger.log(u"Show: tvdb_id " + str(indexerid) + ", Title " +  str(name) + " should be added to watchlist", logger.DEBUG)
            if not self.update_watchlist("show", "add", imdb_id, 0, 0):
                return False

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
        if epObj == None:
            return
        with epObj.lock:
            if epObj.status not in (SKIPPED, DOWNLOADABLE, FAILED):
                return
            logger.log(u"Setting episode s" + str(s) + "e" + str(e) + " of show " + show.name + " to wanted")
            # figure out what segment the episode is in and remember it so we can backlog it
            if epObj.show.air_by_date or epObj.show.sports:
                ep_segment = str(epObj.airdate)[:7]
            else:
                ep_segment = epObj.season

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
            if not self.episode_in_watchlist(show.imdbid, episode[1], episode[2]):
                if not self.update_watchlist("episode", "add", show.imdbid,  episode[1], episode[2]):
                    return False
            self.todoWanted.remove(episode)
        self.startBacklog(show)

    def startBacklog(self, show):
        segments = [i for i in self.todoBacklog if i[0] == show]
        for segment in segments:
            cur_backlog_queue_item = search_queue.BacklogQueueItem(show, segment[1])
            sickbeard.searchQueueScheduler.action.add_item(cur_backlog_queue_item)
            logger.log(u"Starting backlog for " + show.name + " season " + str(
                segment[1]) + " because some eps were set to wanted")
            self.todoBacklog.remove(segment)

    def show_full_watched (self, show):

        logger.log(u"Checking if show: Indexer " + str(show.indexer) + "indexer_id " + str(show.indexerid) + ", Title " + str(show.name) + " is completely watched", logger.DEBUG)

        found = False

        for pshow in self.ShowProgress:
            if pshow["show"]["imdb_id"] == show.imdbid and int(pshow["progress"]["percentage"]) == 100:
                found=True
                break

        return found
	
    def update_watchlist (self, type, update, imdb_id, s, e):

        if type=="episode":
            # traktv URL parameters
            data = {
                'imdb_id': imdb_id,
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
                    'imdb_id': imdb_id
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
	
    def show_in_watchlist (self, imdb_id):

        found = False

        for show in self.ShowWatchlist:
            if show["imdb_id"] == str(imdb_id):
                found=True
                break

        return found
			
    def episode_in_watchlist (self, imdb_id, s, e):

        found = False

        for show in self.EpisodeWatchlist:
        	for episode in show["episodes"]:
		    if s==episode["season"] and e==episode["number"] and show["imdb_id"]==str(imdb_id):
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
	
