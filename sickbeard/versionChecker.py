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

import os
import platform
import shutil
import subprocess
import re
import urllib
import zipfile
import tarfile
import stat
import traceback

import sickbeard
from sickbeard import helpers, notifiers
from sickbeard import ui
from sickbeard import logger
from sickbeard.exceptions import ex
from sickbeard import encodingKludge as ek

class CheckVersion():
    """
    Version check class meant to run as a thread object with the sr scheduler.
    """

    def __init__(self):
        self.install_type = self.find_install_type()

        if self.install_type == 'win':
            self.updater = WindowsUpdateManager()
        elif self.install_type == 'git':
            self.updater = GitUpdateManager()
        elif self.install_type == 'source':
            self.updater = SourceUpdateManager()
        else:
            self.updater = None

    def run(self, force=False):
        # set current branch version
        sickbeard.BRANCH = self.get_branch()

        if self.check_for_new_version(force):
            if sickbeard.AUTO_UPDATE:
                logger.log(u"New update found for SickBeard, starting auto-updater ...")
                ui.notifications.message('New update found for SickBeard, starting auto-updater')
                if sickbeard.versionCheckScheduler.action.update():
                    logger.log(u"Update was successful!")
                    ui.notifications.message('Update was successful')
                    sickbeard.events.put(sickbeard.events.SystemEvent.RESTART)

    def find_install_type(self):
        """
        Determines how this copy of sr was installed.

        returns: type of installation. Possible values are:
            'win': any compiled windows build
            'git': running from source using git
            'source': running from source without git
        """

        # check if we're a windows build
        if sickbeard.BRANCH.startswith('build '):
            install_type = 'win'
        elif os.path.isdir(ek.ek(os.path.join, sickbeard.PROG_DIR, u'.git')):
            install_type = 'git'
        else:
            install_type = 'source'

        return install_type

    def check_for_new_version(self, force=False):
        """
        Checks the internet for a newer version.

        returns: bool, True for new version or False for no new version.

        force: if true the VERSION_NOTIFY setting will be ignored and a check will be forced
        """

        if not sickbeard.VERSION_NOTIFY and not sickbeard.AUTO_UPDATE and not force:
            logger.log(u"Version checking is disabled, not checking for the newest version")
            return False

        if not sickbeard.AUTO_UPDATE:
            logger.log(u"Checking if " + self.install_type + " needs an update")
        if not self.updater.need_update():
            sickbeard.NEWEST_VERSION_STRING = None
            if not sickbeard.AUTO_UPDATE:
                logger.log(u"No update needed")

            if force:
                ui.notifications.message('No update needed')
            return False

        self.updater.set_newest_text()
        return True

    def update(self):
        # update branch with current config branch value
        self.updater.branch = sickbeard.BRANCH

        # check for updates
        if self.updater.need_update():
            return self.updater.update()

    def list_remote_branches(self):
        return self.updater.list_remote_branches()

    def get_branch(self):
        return self.updater.branch


class UpdateManager():
    def get_github_org(self):
        return 'gborri'

    def get_github_repo(self):
        return sickbeard.GIT_REPO

    def get_update_url(self):
        return sickbeard.WEB_ROOT + "/home/update/?pid=" + str(sickbeard.PID)


class WindowsUpdateManager(UpdateManager):
    def __init__(self):
        self.github_org = self.get_github_org()
        self.github_repo = self.get_github_repo()

        self.branch = sickbeard.BRANCH
        if sickbeard.BRANCH == '':
            self.branch = self._find_installed_branch()

        self._cur_version = None
        self._cur_commit_hash = None
        self._newest_version = None

        self.gc_url = 'http://code.google.com/p/sickbeard/downloads/list'
        self.version_url = 'https://raw.github.com/' + self.github_org + '/' + self.github_repo + '/' + self.branch + '/updates.txt'

    def _find_installed_version(self):
        version = ''

        try:
            version = sickbeard.BRANCH
            return int(version[6:])
        except ValueError:
            logger.log(u"Unknown SickBeard Windows binary release: " + version, logger.ERROR)
            return None

    def _find_installed_branch(self):
        return 'windows_binaries'

    def _find_newest_version(self, whole_link=False):
        """
        Checks git for the newest Windows binary build. Returns either the
        build number or the entire build URL depending on whole_link's value.

        whole_link: If True, returns the entire URL to the release. If False, it returns
                    only the build number. default: False
        """

        regex = ".*SickBeard\-win32\-alpha\-build(\d+)(?:\.\d+)?\.zip"

        version_url_data = helpers.getURL(self.version_url)
        if not version_url_data:
            return

        for curLine in version_url_data.splitlines():
            logger.log(u"checking line " + curLine, logger.DEBUG)
            match = re.match(regex, curLine)
            if match:
                logger.log(u"found a match", logger.DEBUG)
                if whole_link:
                    return curLine.strip()
                else:
                    return int(match.group(1))

    def need_update(self):
        if self.branch != self._find_installed_branch():
            logger.log(u"Branch checkout: " + self._find_installed_branch() + "->" + self.branch, logger.DEBUG)
            return True

        self._cur_version = self._find_installed_version()
        self._newest_version = self._find_newest_version()

        logger.log(u"newest version: " + repr(self._newest_version), logger.DEBUG)
        if self._newest_version and self._newest_version > self._cur_version:
            return True

        return False

    def set_newest_text(self):

        sickbeard.NEWEST_VERSION_STRING = None

        if not self._cur_version:
            newest_text = "Unknown SickBeard Windows binary version. Not updating with original version."
        else:
            newest_text = 'There is a <a href="' + self.gc_url + '" onclick="window.open(this.href); return false;">newer version available</a> (build ' + str(
                self._newest_version) + ')'
            newest_text += "&mdash; <a href=\"" + self.get_update_url() + "\">Update Now</a>"

        sickbeard.NEWEST_VERSION_STRING = newest_text

    def update(self):

        zip_download_url = self._find_newest_version(True)
        logger.log(u"new_link: " + repr(zip_download_url), logger.DEBUG)

        if not zip_download_url:
            logger.log(u"Unable to find a new version link on google code, not updating")
            return False

        try:
            # prepare the update dir
            sr_update_dir = ek.ek(os.path.join, sickbeard.PROG_DIR, u'sr-update')

            if os.path.isdir(sr_update_dir):
                logger.log(u"Clearing out update folder " + sr_update_dir + " before extracting")
                shutil.rmtree(sr_update_dir)

            logger.log(u"Creating update folder " + sr_update_dir + " before extracting")
            os.makedirs(sr_update_dir)

            # retrieve file
            logger.log(u"Downloading update from " + zip_download_url)
            zip_download_path = os.path.join(sr_update_dir, u'sr-update.zip')
            urllib.urlretrieve(zip_download_url, zip_download_path)

            if not ek.ek(os.path.isfile, zip_download_path):
                logger.log(u"Unable to retrieve new version from " + zip_download_url + ", can't update", logger.ERROR)
                return False

            if not ek.ek(zipfile.is_zipfile, zip_download_path):
                logger.log(u"Retrieved version from " + zip_download_url + " is corrupt, can't update", logger.ERROR)
                return False

            # extract to sr-update dir
            logger.log(u"Unzipping from " + str(zip_download_path) + " to " + sr_update_dir)
            update_zip = zipfile.ZipFile(zip_download_path, 'r')
            update_zip.extractall(sr_update_dir)
            update_zip.close()

            # delete the zip
            logger.log(u"Deleting zip file from " + str(zip_download_path))
            os.remove(zip_download_path)

            # find update dir name
            update_dir_contents = [x for x in os.listdir(sr_update_dir) if
                                   os.path.isdir(os.path.join(sr_update_dir, x))]

            if len(update_dir_contents) != 1:
                logger.log(u"Invalid update data, update failed. Maybe try deleting your sr-update folder?",
                           logger.ERROR)
                return False

            content_dir = os.path.join(sr_update_dir, update_dir_contents[0])
            old_update_path = os.path.join(content_dir, u'updater.exe')
            new_update_path = os.path.join(sickbeard.PROG_DIR, u'updater.exe')
            logger.log(u"Copying new update.exe file from " + old_update_path + " to " + new_update_path)
            shutil.move(old_update_path, new_update_path)

            # Notify update successful
            notifiers.notify_git_update(sickbeard.NEWEST_VERSION_STRING)

        except Exception, e:
            logger.log(u"Error while trying to update: " + ex(e), logger.ERROR)
            return False

        return True

    def list_remote_branches(self):
        return ['windows_binaries']


class GitUpdateManager(UpdateManager):
    def __init__(self):
        self._git_path = self._find_working_git()
        self.github_org = self.get_github_org()
        self.github_repo = self.get_github_repo()

        self.branch = sickbeard.BRANCH
        if sickbeard.BRANCH == '':
            self.branch = self._find_installed_branch()

        self._cur_commit_hash = None
        self._newest_commit_hash = None
        self._num_commits_behind = 0
        self._num_commits_ahead = 0

    def _git_error(self):
        error_message = 'Unable to find your git executable - Shutdown SickBeard and EITHER set git_path in your config.ini OR delete your .git folder and run from source to enable updates.'
        sickbeard.NEWEST_VERSION_STRING = error_message

    def _find_working_git(self):
        test_cmd = 'version'

        if sickbeard.GIT_PATH:
            main_git = '"' + sickbeard.GIT_PATH + '"'
        else:
            main_git = 'git'

        logger.log(u"Checking if we can use git commands: " + main_git + ' ' + test_cmd, logger.DEBUG)
        output, err, exit_status = self._run_git(main_git, test_cmd)

        if exit_status == 0:
            logger.log(u"Using: " + main_git, logger.DEBUG)
            return main_git
        else:
            logger.log(u"Not using: " + main_git, logger.DEBUG)

        # trying alternatives

        alternative_git = []

        # osx people who start sr from launchd have a broken path, so try a hail-mary attempt for them
        if platform.system().lower() == 'darwin':
            alternative_git.append('/usr/local/git/bin/git')

        if platform.system().lower() == 'windows':
            if main_git != main_git.lower():
                alternative_git.append(main_git.lower())

        if alternative_git:
            logger.log(u"Trying known alternative git locations", logger.DEBUG)

            for cur_git in alternative_git:
                logger.log(u"Checking if we can use git commands: " + cur_git + ' ' + test_cmd, logger.DEBUG)
                output, err, exit_status = self._run_git(cur_git, test_cmd)

                if exit_status == 0:
                    logger.log(u"Using: " + cur_git, logger.DEBUG)
                    return cur_git
                else:
                    logger.log(u"Not using: " + cur_git, logger.DEBUG)

        # Still haven't found a working git
        error_message = 'Unable to find your git executable - Shutdown SickBeard and EITHER set git_path in your config.ini OR delete your .git folder and run from source to enable updates.'
        sickbeard.NEWEST_VERSION_STRING = error_message

        return None

    def _run_git(self, git_path, args):

        output = err = exit_status = None

        if not git_path:
            logger.log(u"No git specified, can't use git commands", logger.ERROR)
            exit_status = 1
            return (output, err, exit_status)

        cmd = git_path + ' ' + args

        try:
            logger.log(u"Executing " + cmd + " with your shell in " + sickbeard.PROG_DIR, logger.DEBUG)
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 shell=True, cwd=sickbeard.PROG_DIR)
            output, err = p.communicate()
            exit_status = p.returncode

            if output:
                output = output.strip()
            logger.log(u"git output: " + str(output), logger.DEBUG)

        except OSError:
            logger.log(u"Command " + cmd + " didn't work")
            exit_status = 1

        if exit_status == 0:
            logger.log(cmd + u" : returned successful", logger.DEBUG)
            exit_status = 0

        elif exit_status == 1:
            logger.log(cmd + u" returned : " + str(output), logger.ERROR)
            exit_status = 1

        elif exit_status == 128 or 'fatal:' in output or err:
            logger.log(cmd + u" returned : " + str(output), logger.ERROR)
            exit_status = 128

        else:
            logger.log(cmd + u" returned : " + str(output) + u", treat as error for now", logger.ERROR)
            exit_status = 1

        return (output, err, exit_status)

    def _find_installed_version(self):
        """
        Attempts to find the currently installed version of Sick Beard.

        Uses git show to get commit version.

        Returns: True for success or False for failure
        """

        output, err, exit_status = self._run_git(self._git_path, 'rev-parse HEAD')  # @UnusedVariable

        if exit_status == 0 and output:
            cur_commit_hash = output.strip()
            if not re.match('^[a-z0-9]+$', cur_commit_hash):
                logger.log(u"Output doesn't look like a hash, not using it", logger.ERROR)
                return False
            self._cur_commit_hash = cur_commit_hash
            sickbeard.CUR_COMMIT_HASH = str(cur_commit_hash)
            return True
        else:
            return False

    def _find_installed_branch(self):
        branch_info, err, exit_status = self._run_git(self._git_path, 'symbolic-ref -q HEAD')  # @UnusedVariable
        if exit_status == 0 and branch_info:
            branch = branch_info.strip().replace('refs/heads/', '', 1)
            if branch:
                return branch
                
        return ""
        
    def _check_github_for_update(self):
        """
        Uses git commands to check if there is a newer version that the provided
        commit hash. If there is a newer version it sets _num_commits_behind.
        """

        self._num_commits_behind = 0
        self._num_commits_ahead = 0

        # update remote origin url
        self.update_remote_origin()

        # get all new info from github
        output, err, exit_status = self._run_git(self._git_path, 'fetch %s' % sickbeard.GIT_REMOTE)

        if not exit_status == 0:
            logger.log(u"Unable to contact github, can't check for update", logger.ERROR)
            return

        # get latest commit_hash from remote
        output, err, exit_status = self._run_git(self._git_path, 'rev-parse --verify --quiet "@{upstream}"')

        if exit_status == 0 and output:
            cur_commit_hash = output.strip()

            if not re.match('^[a-z0-9]+$', cur_commit_hash):
                logger.log(u"Output doesn't look like a hash, not using it", logger.DEBUG)
                return

            else:
                self._newest_commit_hash = cur_commit_hash
        else:
            logger.log(u"git didn't return newest commit hash", logger.DEBUG)
            return

        # get number of commits behind and ahead (option --count not supported git < 1.7.2)
        output, err, exit_status = self._run_git(self._git_path, 'rev-list --left-right "@{upstream}"...HEAD')

        if exit_status == 0 and output:

            try:
                self._num_commits_behind = int(output.count("<"))
                self._num_commits_ahead = int(output.count(">"))

            except:
                logger.log(u"git didn't return numbers for behind and ahead, not using it", logger.DEBUG)
                return

        logger.log(u"cur_commit = " + str(self._cur_commit_hash) + u", newest_commit = " + str(self._newest_commit_hash)
                   + u", num_commits_behind = " + str(self._num_commits_behind) + u", num_commits_ahead = " + str(
            self._num_commits_ahead), logger.DEBUG)

    def set_newest_text(self):

        # if we're up to date then don't set this
        sickbeard.NEWEST_VERSION_STRING = None

        if self._num_commits_ahead:
            logger.log(u"Local branch is ahead of " + self.branch + ". Automatic update not possible.", logger.ERROR)
            newest_text = "Local branch is ahead of " + self.branch + ". Automatic update not possible."

        elif self._num_commits_behind > 0:

            base_url = 'http://github.com/' + self.github_org + '/' + self.github_repo
            if self._newest_commit_hash:
                url = base_url + '/compare/' + self._cur_commit_hash + '...' + self._newest_commit_hash
            else:
                url = base_url + '/commits/'

            newest_text = 'There is a <a href="' + url + '" onclick="window.open(this.href); return false;">newer version available</a> '
            newest_text += " (you're " + str(self._num_commits_behind) + " commit"
            if self._num_commits_behind > 1:
                newest_text += 's'
            newest_text += ' behind)' + "&mdash; <a href=\"" + self.get_update_url() + "\">Update Now</a>"

        else:
            return

        sickbeard.NEWEST_VERSION_STRING = newest_text

    def need_update(self):

        if self.branch != self._find_installed_branch():
            logger.log(u"Branch checkout: " + self._find_installed_branch() + "->" + self.branch, logger.DEBUG)
            return True

        self._find_installed_version()
        if not self._cur_commit_hash:
            return True
        else:
            try:
                self._check_github_for_update()
            except Exception, e:
                logger.log(u"Unable to contact github, can't check for update: " + repr(e), logger.ERROR)
                return False

            if self._num_commits_behind > 0:
                return True

        return False

    def update(self):
        """
        Calls git pull origin <branch> in order to update Sick Beard. Returns a bool depending
        on the call's success.
        """

        # update remote origin url
        self.update_remote_origin()

        if self.branch == self._find_installed_branch():
            output, err, exit_status = self._run_git(self._git_path, 'pull -f %s %s' % (sickbeard.GIT_REMOTE, self.branch))  # @UnusedVariable
        else:
            output, err, exit_status = self._run_git(self._git_path, 'checkout -f ' + self.branch)  # @UnusedVariable

        if exit_status == 0:
            self._find_installed_version()

            # Notify update successful
            if sickbeard.NOTIFY_ON_UPDATE:
                notifiers.notify_git_update(sickbeard.CUR_COMMIT_HASH if sickbeard.CUR_COMMIT_HASH else "")
            return True

        return False

    def list_remote_branches(self):
        # update remote origin url
        self.update_remote_origin()

        branches, err, exit_status = self._run_git(self._git_path, 'ls-remote --heads %s' % sickbeard.GIT_REMOTE)  # @UnusedVariable
        if exit_status == 0 and branches:
            return re.findall('\S+\Wrefs/heads/(.*)', branches)
        return []

    def update_remote_origin(self):
        self._run_git(self._git_path, 'config remote.origin.url %s' % sickbeard.GIT_REMOTE_URL)

class SourceUpdateManager(UpdateManager):
    def __init__(self):
        self.github_org = self.get_github_org()
        self.github_repo = self.get_github_repo()

        self.branch = sickbeard.BRANCH
        if sickbeard.BRANCH == '':
            self.branch = self._find_installed_branch()

        self._cur_commit_hash = sickbeard.CUR_COMMIT_HASH
        self._newest_commit_hash = None
        self._num_commits_behind = 0

    def _find_installed_branch(self):
        if sickbeard.CUR_COMMIT_BRANCH == "":
            return "ThePirateBay"
        else:
            return sickbeard.CUR_COMMIT_BRANCH
        
    def need_update(self):
        # need this to run first to set self._newest_commit_hash
        try:
            self._check_github_for_update()
        except Exception, e:
            logger.log(u"Unable to contact github, can't check for update: " + repr(e), logger.ERROR)
            return False

        if self.branch != self._find_installed_branch():
            logger.log(u"Branch checkout: " + self._find_installed_branch() + "->" + self.branch, logger.DEBUG)
            return True

        if not self._cur_commit_hash or self._num_commits_behind > 0:
            return True

        return False

    def _check_github_for_update(self):
        """
        Uses pygithub to ask github if there is a newer version that the provided
        commit hash. If there is a newer version it sets Sick Beard's version text.

        commit_hash: hash that we're checking against
        """

        self._num_commits_behind = 0
        self._newest_commit_hash = None

        # try to get newest commit hash and commits behind directly by comparing branch and current commit
        if self._cur_commit_hash:
            branch_compared = sickbeard.gh.compare(base=self.branch, head=self._cur_commit_hash)
            self._newest_commit_hash = branch_compared.base_commit.sha
            self._num_commits_behind = branch_compared.behind_by

        # fall back and iterate over last 100 (items per page in gh_api) commits
        if not self._newest_commit_hash:

            for curCommit in sickbeard.gh.get_commits():
                if not self._newest_commit_hash:
                    self._newest_commit_hash = curCommit.sha
                    if not self._cur_commit_hash:
                        break

                if curCommit.sha == self._cur_commit_hash:
                    break

                # when _cur_commit_hash doesn't match anything _num_commits_behind == 100
                self._num_commits_behind += 1

        logger.log(u"cur_commit = " + str(self._cur_commit_hash) + u", newest_commit = " + str(self._newest_commit_hash)
                   + u", num_commits_behind = " + str(self._num_commits_behind), logger.DEBUG)

    def set_newest_text(self):

        # if we're up to date then don't set this
        sickbeard.NEWEST_VERSION_STRING = None

        if not self._cur_commit_hash:
            logger.log(u"Unknown current version number, don't know if we should update or not", logger.DEBUG)

            newest_text = "Unknown current version number: If you've never used the Sick Beard upgrade system before then current version is not set."
            newest_text += "&mdash; <a href=\"" + self.get_update_url() + "\">Update Now</a>"

        elif self._num_commits_behind > 0:
            base_url = 'http://github.com/' + self.github_org + '/' + self.github_repo
            if self._newest_commit_hash:
                url = base_url + '/compare/' + self._cur_commit_hash + '...' + self._newest_commit_hash
            else:
                url = base_url + '/commits/'

            newest_text = 'There is a <a href="' + url + '" onclick="window.open(this.href); return false;">newer version available</a>'
            newest_text += " (you're " + str(self._num_commits_behind) + " commit"
            if self._num_commits_behind > 1:
                newest_text += "s"
            newest_text += " behind)" + "&mdash; <a href=\"" + self.get_update_url() + "\">Update Now</a>"
        else:
            return

        sickbeard.NEWEST_VERSION_STRING = newest_text

    def update(self):
        """
        Downloads the latest source tarball from github and installs it over the existing version.
        """

        base_url = 'http://github.com/' + self.github_org + '/' + self.github_repo
        tar_download_url = base_url + '/tarball/' + self.branch

        try:
            # prepare the update dir
            sr_update_dir = ek.ek(os.path.join, sickbeard.PROG_DIR, u'sr-update')

            if os.path.isdir(sr_update_dir):
                logger.log(u"Clearing out update folder " + sr_update_dir + " before extracting")
                shutil.rmtree(sr_update_dir)

            logger.log(u"Creating update folder " + sr_update_dir + " before extracting")
            os.makedirs(sr_update_dir)

            # retrieve file
            logger.log(u"Downloading update from " + repr(tar_download_url))
            tar_download_path = os.path.join(sr_update_dir, u'sr-update.tar')
            urllib.urlretrieve(tar_download_url, tar_download_path)

            if not ek.ek(os.path.isfile, tar_download_path):
                logger.log(u"Unable to retrieve new version from " + tar_download_url + ", can't update", logger.ERROR)
                return False

            if not ek.ek(tarfile.is_tarfile, tar_download_path):
                logger.log(u"Retrieved version from " + tar_download_url + " is corrupt, can't update", logger.ERROR)
                return False

            # extract to sr-update dir
            logger.log(u"Extracting file " + tar_download_path)
            tar = tarfile.open(tar_download_path)
            tar.extractall(sr_update_dir)
            tar.close()

            # delete .tar.gz
            logger.log(u"Deleting file " + tar_download_path)
            os.remove(tar_download_path)

            # find update dir name
            update_dir_contents = [x for x in os.listdir(sr_update_dir) if
                                   os.path.isdir(os.path.join(sr_update_dir, x))]
            if len(update_dir_contents) != 1:
                logger.log(u"Invalid update data, update failed: " + str(update_dir_contents), logger.ERROR)
                return False
            content_dir = os.path.join(sr_update_dir, update_dir_contents[0])

            # walk temp folder and move files to main folder
            logger.log(u"Moving files from " + content_dir + " to " + sickbeard.PROG_DIR)
            for dirname, dirnames, filenames in os.walk(content_dir):  # @UnusedVariable
                dirname = dirname[len(content_dir) + 1:]
                for curfile in filenames:
                    old_path = os.path.join(content_dir, dirname, curfile)
                    new_path = os.path.join(sickbeard.PROG_DIR, dirname, curfile)

                    # Avoid DLL access problem on WIN32/64
                    # These files needing to be updated manually
                    #or find a way to kill the access from memory
                    if curfile in ('unrar.dll', 'unrar64.dll'):
                        try:
                            os.chmod(new_path, stat.S_IWRITE)
                            os.remove(new_path)
                            os.renames(old_path, new_path)
                        except Exception, e:
                            logger.log(u"Unable to update " + new_path + ': ' + ex(e), logger.DEBUG)
                            os.remove(old_path)  # Trash the updated file without moving in new path
                        continue

                    if os.path.isfile(new_path):
                        os.remove(new_path)
                    os.renames(old_path, new_path)

            sickbeard.CUR_COMMIT_HASH = self._newest_commit_hash
            sickbeard.CUR_COMMIT_BRANCH = self.branch
            
        except Exception, e:
            logger.log(u"Error while trying to update: " + ex(e), logger.ERROR)
            logger.log(u"Traceback: " + traceback.format_exc(), logger.DEBUG)
            return False

        # Notify update successful
        notifiers.notify_git_update(sickbeard.NEWEST_VERSION_STRING)

        return True

    def list_remote_branches(self):
        return [x.name for x in sickbeard.gh.get_branches() if x]
