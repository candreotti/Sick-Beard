Sick Beard
=====

This fork is based on mr-orange ThePirateBay branch https://github.com/mr-orange/Sick-Beard

Feature list of this branch:
- Support for TNTVillage torrent provider
- Language default to IT for new show/importing existing shows (if available on TVDB)
- Automatic remove of downloaded torrent on trasmission client
- trackt intregration enhancement: watched episode on show added on sickbeard are marked as Ignored
- trackt intregration enhancement: always have a numebr (configurable) of unwatched episode for not paused show
- Chech availability of torrent file and mark episode to DOWNLOADABLE
- With Trasmission client you can download single episode also for multi episode torrent file 

*SickBeard TPB is currently an alpha release. There may be severe bugs in it and at any given time it may not work at all.*

Sick Beard TPB is a PVR for torrent and newsgroup users. It watches for new episodes of your favorite shows and when they are posted it downloads them, sorts and renames them, and optionally generates metadata for them. It retrieves show information from theTVDB.com and TVRage.com.

FEATURES:
- automatically retrieves new episode torrent or nzb files
- can scan your existing library and then download any old seasons or episodes you're missing
- can watch for better versions and upgrade your existing episodes (to from TV DVD/BluRay for example)
- XBMC library updates, poster/fanart downloads, and NFO/TBN generation
- configurable episode renaming
- sends NZBs directly to SABnzbd, prioritizes and categorizes them properly
- available for any platform, uses simple HTTP interface
- can notify XBMC, Growl, or Twitter when new episodes are available
- specials and double episode support
- Automatic XEM Scene Numbering/Naming for seasons/episodes
- Episode Status Manager now allows for mass failing seasons/episodes to force retrying.
- DVD Order numbering for returning the results in DVD order instead of Air-By-Date order.
- Improved Failed handling code for shows.
- DupeKey/DupeScore for NZBGet 12+
- Searches both TheTVDB.com, TVRage.com and AniDB.net for shows, seasons, episodes
- Importing of existing video files now allows you to choose which indexer you wish to have SickBeard search its show info from.
- Your tvshow.nfo files are now tagged with a indexer key so that SickBeard can easily tell if the shows info comes from TheTVDB or TVRage.
- Sports shows are now able to be searched for..

## Dependencies

To run SickBeard from source you will need Python 2.6+ and Cheetah 2.1.0+.
