Sick Beard
=====

This fork is based on mr-orange ThePirateBay branch https://github.com/mr-orange/Sick-Beard

Feature list of this branch:
- Support for TNTVillage torrent provider
- Language default to IT for new show/importing existing shows (if available on TVDB)
- Automatic remove of downloaded torrent on trasmission client
- Added search for file name in not dotted notation
- trackt intregration enhancement: watched episode on show added on sickbeard are marked as Archived
- trackt intregration enhancement: always have a numebr (configurable) of unwatched episode for not paused show
- Chech availability of torrent file and mark episode to DOWNLOADABLE

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
- can notify XBMC, Growl, or Twitter when new episodes are downloaded
- specials and double episode support
- Automatic XEM Scene Numbering/Naming for seasons/episodes
- Failed handling now attempts to snatch a different release and excludes failed releases from future snatch attempts.
- Episode Status Manager now allows for mass failing seasons/episodes to force retrying to download new releases.
- DVD Order numbering for returning the results in DVD order instead of Air-By-Date order.
- Improved Failed handling code for both NZB and Torrent downloads.
- DupeKey/DupeScore for NZBGet 12+
- Searches both TheTVDB.com and TVRage.com for shows, seasons, episodes
- Importing of existing video files now allows you to choose which indexer you wish to have SickBeard download its show info from.
- Your tvshow.nfo files are now tagged with a indexer key so that SickBeard can easily tell if the shows info comes from TheTVDB or TVRage.
- Failed download handling has been improved now for both NZB and Torrents.
- Sports shows are now able to be searched for and downloaded by both NZB and Torrent providers.

## Dependencies

To run Sick Beard from source you will need Python 2.6+ and Cheetah 2.1.0+. The [binary releases][googledownloads] are standalone.
