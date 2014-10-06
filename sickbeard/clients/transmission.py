# Author: Mr_Orange <mr_orange@hotmail.it>
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

import re
import json
from base64 import b64encode

import sickbeard
from sickbeard import logger
from sickbeard.clients.generic import GenericClient
from sickbeard.name_parser.parser import NameParser, InvalidNameException, InvalidShowException
from sickbeard import helpers


class TransmissionAPI(GenericClient):
    def __init__(self, host=None, username=None, password=None):

        super(TransmissionAPI, self).__init__('Transmission', host, username, password)

        self.url = self.host + 'transmission/rpc'

    def _get_auth(self):

        post_data = json.dumps({'method': 'session-get', })

        try:
            self.response = self.session.post(self.url, data=post_data.encode('utf-8'), verify=sickbeard.TORRENT_VERIFY_CERT)
            self.auth = re.search('X-Transmission-Session-Id:\s*(\w+)', self.response.text).group(1)
        except:
            return None

        self.session.headers.update({'x-transmission-session-id': self.auth})

        #Validating Transmission authorization
        post_data = json.dumps({'arguments': {},
                                'method': 'session-get',
        })
        self._request(method='post', data=post_data)

        return self.auth

    def _add_torrent_uri(self, result):

        if not self._torrent_is_downloading(result):

            arguments = {'filename': result.url,
                         'paused': 1 if sickbeard.TORRENT_PAUSED else 0,
                         'download-dir': sickbeard.TORRENT_PATH
            }
            post_data = json.dumps({'arguments': arguments,
                                    'method': 'torrent-add',
            })
            self._request(method='post', data=post_data)

            if not self.response.json()['result'] == "success":
                return False

            arguments = {'ids': [result.hash],
                         'files-unwanted': []
            }
            post_data = json.dumps({'arguments': arguments,
                                    'method': 'torrent-set',
            })
            self._request(method='post', data=post_data)
    
            if not self.response.json()['result'] == "success":
                return False

        file_list = self._get_file_list_in_torrent(result)

        if not file_list:
            return False

        wantedFile = []

        for epObj in result.episodes:
            index = 0
            for name_file in file_list['arguments']['torrents'][0]['files']:
                try:
                    name_file["name"] = name_file["name"].split('/')[1]
                    myParser = NameParser(showObj=result.show, convert=True)
                    parse_result = myParser.parse(name_file["name"])
                except InvalidNameException:
                    logger.log(u"Unable to parse the filename " + str(name_file["name"]) + " into a valid episode", logger.DEBUG)
                    return False
                except InvalidShowException:
                    logger.log(u"Unable to parse the filename " + str(name_file["name"]) + " into a valid show", logger.DEBUG)
                    return False

                if not parse_result or not parse_result.series_name:
                    continue

		if epObj.episode in parse_result.episode_numbers and epObj.season == parse_result.season_number:
                    wantedFile.append(index)
                index += 1

        logger.log(u"wantedFile list: " + str(wantedFile), logger.DEBUG)
        if wantedFile:
            arguments = {'ids': [result.hash],
                         'files-wanted': wantedFile
            }
            post_data = json.dumps({'arguments': arguments,
                        'method': 'torrent-set',
            })
            self._request(method='post', data=post_data)

            return self.response.json()['result'] == "success"
        else:
            self.remove_torrent_downloaded(result.hash) 
            return False

    def _get_file_list_in_torrent (self, result):

        arguments = {'ids': [result.hash],
                     'fields': ["files"]
        }
        post_data = json.dumps({'arguments': arguments,
                            'method': 'torrent-get',
        })
        self._request(method='post', data=post_data)

        if self.response.json()['result'] == "success":
            return self.response.json()
        else:
            return []

    def _add_torrent_file(self, result):

        if not self._torrent_is_downloading(result):

            arguments = {'metainfo': b64encode(result.content),
                         'paused': 1 if sickbeard.TORRENT_PAUSED else 0,
                         'download-dir': sickbeard.TORRENT_PATH
            }
            post_data = json.dumps({'arguments': arguments,
                                    'method': 'torrent-add',
            })
            self._request(method='post', data=post_data)

            if not self.response.json()['result'] == "success":
                return False

            arguments = {'ids': [result.hash],
                         'files-unwanted': []
            }
            post_data = json.dumps({'arguments': arguments,
                                    'method': 'torrent-set',
            })
            self._request(method='post', data=post_data)
    
            if not self.response.json()['result'] == "success":
                return False

        file_list = self._get_file_list_in_torrent(result)

        if not file_list:
            return False

        wantedFile = []

        for epObj in result.episodes:
            index = 0
            for name_file in file_list['arguments']['torrents'][0]['files']:
                try:
                    if '/' in name_file["name"]:
                        name_file["name"] = name_file["name"].split('/')[1]
                    myParser = NameParser(showObj=result.show, convert=True)
                    parse_result = myParser.parse(name_file["name"])
                except InvalidNameException:
                    logger.log(u"Unable to parse the filename " + str(name_file["name"]) + " into a valid episode", logger.DEBUG)
                    return False
                except InvalidShowException:
                    logger.log(u"Unable to parse the filename " + str(name_file["name"]) + " into a valid show", logger.DEBUG)
                    return False

                if not parse_result or not parse_result.series_name:
                    continue

		if epObj.episode in parse_result.episode_numbers and epObj.season == parse_result.season_number:
                    wantedFile.append(index)
                index += 1

        if wantedFile:
            arguments = {'ids': [result.hash],
                         'files-wanted': wantedFile
            }
            post_data = json.dumps({'arguments': arguments,
                        'method': 'torrent-set',
            })
            self._request(method='post', data=post_data)

            return self.response.json()['result'] == "success"
        else:
            self.remove_torrent_downloaded(result.hash) 
            return False

    def _set_torrent_ratio(self, result):

        ratio = None
        if result.ratio:
            ratio = result.ratio

        mode = 0
        if ratio:
            if float(ratio) == -1:
                ratio = 0
                mode = 2
            elif float(ratio) >= 0:
                ratio = float(ratio)
                mode = 1  # Stop seeding at seedRatioLimit

        arguments = {'ids': [result.hash],
                     'seedRatioLimit': ratio,
                     'seedRatioMode': mode
        }
        post_data = json.dumps({'arguments': arguments,
                                'method': 'torrent-set',
        })
        self._request(method='post', data=post_data)

        return self.response.json()['result'] == "success"

    def _set_torrent_seed_time(self, result):

        if sickbeard.TORRENT_SEED_TIME:
            time = int(60 * float(sickbeard.TORRENT_SEED_TIME))
            arguments = {'ids': [result.hash],
                         'seedIdleLimit': time,
                         'seedIdleMode': 1
            }

            post_data = json.dumps({'arguments': arguments,
                                'method': 'torrent-set',
            })
            self._request(method='post', data=post_data)

            return self.response.json()['result'] == "success"
        else:
            return True

    def _set_torrent_priority(self, result):

        arguments = {'ids': [result.hash]}

        if result.priority == -1:
            arguments['priority-low'] = []
        elif result.priority == 1:
            # set high priority for all files in torrent
            arguments['priority-high'] = []
            # move torrent to the top if the queue
            arguments['queuePosition'] = 0
            if sickbeard.TORRENT_HIGH_BANDWIDTH:
                arguments['bandwidthPriority'] = 1
        else:
            arguments['priority-normal'] = []
        
        post_data = json.dumps({'arguments': arguments,
                                'method': 'torrent-set',
                                })       
        self._request(method='post', data=post_data)            
        
        return self.response.json()['result'] == "success"    

    def _torrent_is_downloading(self, result):

        arguments = { 'ids': [result.hash],
                      'fields': [ "id", "name", "hashString"]
                      }
        post_data = json.dumps({ 'arguments': arguments,
                                 'method': 'torrent-get',
                                 })
        self._request(method='post', data=post_data)

        if self.response.json()['result'] == "success" and self.response.json()['arguments']['torrents']:
            logger.log(u"torrent found, result" + str(self.response.json()), logger.DEBUG)
            return True
        else:
            logger.log(u"torrent not found, result" + str(self.response.json()), logger.DEBUG)
            return False
	
    def remove_torrent_downloaded(self,hash):

        arguments = { 'ids': [hash]
                      }        
        post_data = json.dumps({'arguments': arguments,
                                'method': 'torrent-remove',
                                })
        self._request(method='post', data=post_data)
        
        return self.response.json()['result'] == "success"


api = TransmissionAPI()
