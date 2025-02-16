#
# KodeBlox Copyright 2019 Sayak Mukhopadhyay
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http: //www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import functools
import logging
import threading
import tkinter as tk
from os.path import dirname, join

import semantic_version
import sys
import time

import l10n
import myNotebook as nb
from config import config, appname, appversion
import compat
from py_discord_sdk import discordsdk as dsdk

plugin_name = "DiscordPresence"

logger = logging.getLogger(f'{appname}.{plugin_name}')

_ = functools.partial(l10n.Translations.translate, context=__file__)

CLIENT_ID = 1169952579745230888

VERSION = '3.3.0'

# Add global var for Planet name (landing + around)
planet = '<Hidden>'
landingPad = '2'
cursystem = 'none'
shutdown = True

this = sys.modules[__name__]  # For holding module globals


def callback(result):
    logger.info(f'Callback: {result}')
    if result == dsdk.Result.ok:
        logger.info("Successfully set the activity!")
    elif result == dsdk.Result.transaction_aborted:
        logger.warning(f'Transaction aborted due to SDK shutting down: {result}')
    else:
        logger.error(f'Error in callback: {result}')
        raise Exception(result)


def update_presence():
    global shutdown
    if config.get_int("disable_presence") == 0 and shutdown == False:
        this.activity.state = this.presence_state
        this.activity.details = this.presence_details
        this.activity.timestamps.start = int(this.time_start)
        this.activity.assets.large_image = this.largeimage
        this.activity.assets.large_text = this.largetext
        this.activity.assets.small_image = this.smallimage
        this.activity.assets.small_text = this.smalltext
        this.activity_manager.update_activity(this.activity, callback)
    else:
        this.activity_manager.clear_activity(callback)


def plugin_prefs(parent, cmdr, is_beta):
    """
    Return a TK Frame for adding to the EDMC settings dialog.
    """
    this.disablePresence = tk.IntVar(value=config.get_int("disable_presence"))

    frame = nb.Frame(parent)
    nb.Checkbutton(frame, text="Disable Presence", variable=this.disablePresence).grid()
    nb.Label(frame, text='Version %s' % VERSION).grid(padx=10, pady=10, sticky=tk.W)

    return frame


def prefs_changed(cmdr, is_beta):
    """
    Save settings.
    """
    config.set('disable_presence', this.disablePresence.get())
    update_presence()


def plugin_start3(plugin_dir):
    this.plugin_dir = plugin_dir
    this.discord_thread = threading.Thread(target=check_run, args=(plugin_dir,))
    this.discord_thread.setDaemon(True)
    this.discord_thread.start()
    return 'DiscordPresence'


def plugin_stop():
    this.activity_manager.clear_activity(callback)
    this.call_back_thread = None


def journal_entry(cmdr, is_beta, system, station, entry, state):
    global planet
    global landingPad
    global cursystem
    global shutdown
    presence_state = this.presence_state
    presence_details = this.presence_details
    small_image = this.smallimage
    small_text = this.smalltext
    large_text = f'CMDR {cmdr}'
    shutdown = False
    landed = False
    if system != cursystem:
        this.time_start = time.time()
        cursystem = system
    if entry['event'] in ['LoadGame', 'Startup', 'StartUp']:
        presence_state = _('In system {system}').format(system=system)
        if station is None:
            presence_details = _('Flying in normal space')
            small_image = 'system'
            small_text = system
        else:
            presence_details = _('Docked at {station}').format(station=station)
            small_image = 'station'
            small_text = station
        if 'StartLanded' in entry:
            landed = entry['StartLanded']
        if 'Body' in entry and entry['Body'] != '' and landed == True:
            planet = entry['Body']
            presence_details = _('Landed on {body}').format(body=planet)
            small_image = 'planet'
            small_text = planet
        this.time_start = time.time()
    elif entry['event'] == 'Location':
        presence_state = _('In system {system}').format(system=system)
        if station is None:
            presence_details = _('Flying in normal space')
            small_image = 'system'
            small_text = system
        else:
            presence_details = _('Docked at {station}').format(station=station)
            small_image = 'station'
            small_text = station
        if 'Body' in entry and entry['Body'] != '' and landed == True:
            planet = entry['Body']
            presence_details = _('Landed on {body}').format(body=planet)
            small_image = 'planet'
            small_text = planet
        this.time_start = time.time()
    elif entry['event'] == 'StartJump':
        presence_state = _('Jumping')
        if entry['JumpType'] == 'Hyperspace':
            presence_details = _('Jumping to system {system}').format(system=entry['StarSystem'])
        elif entry['JumpType'] == 'Supercruise':
            presence_details = _('Preparing for supercruise')
    elif entry['event'] == 'SupercruiseEntry':
        presence_state = _('In system {system}').format(system=system)
        presence_details = _('Supercruising')
        small_image = 'system'
        small_text = system
    elif entry['event'] == 'SupercruiseExit':
        presence_state = _('In system {system}').format(system=system)
        presence_details = _('Flying in normal space')
    elif entry['event'] == 'FSDJump':
        presence_state = _('In system {system}').format(system=system)
        presence_details = _('Supercruising')
        small_image = 'system'
        small_text = system
    elif entry['event'] == 'Docked':
        presence_state = _('In system {system}').format(system=system)
        presence_details = _('Docked at {station}').format(station=station)
        small_image = 'station'
        this.time_start = time.time()
    elif entry['event'] == 'Undocked':
        presence_state = _('In system {system}').format(system=system)
        presence_details = _('Flying in normal space')
        small_image = 'system'
        this.time_start = time.time()
    elif entry['event'] in ['ShutDown', 'Shutdown']:
        presence_state = _('Connecting CMDR Interface')
        presence_details = ''
        small_image = ''
        small_text = ''
        shutdown = True
    elif entry['event'] == 'DockingGranted':
        landingPad = entry['LandingPad']
    elif entry['event'] == 'Music':
        if entry['MusicTrack'] == 'MainMenu':
            presence_state = _('Connecting CMDR Interface')
            presence_details = ''
    # Todo: This elif might not be executed on undocked. Functionality can be improved
    elif entry['event'] in ['Undocked', 'DockingCancelled', 'DockingTimeout']:
        presence_details = _('Flying near {station}').format(station=entry['StationName'])
    # Planetary events
    elif entry['event'] == 'ApproachBody':
        planet = entry['Body']
        presence_details = _('Approaching {body}').format(body=planet)
        small_image = 'planet'
        small_text = planet
    elif entry['event'] == 'Touchdown' and entry['PlayerControlled']:
        presence_details = _('Landed on {body}').format(body=planet)
    elif entry['event'] == 'Liftoff':
        if entry['PlayerControlled']:
            presence_details = _('Flying around {body}').format(body=planet)
        else:
            presence_details = _('In SRV on {body}, ship in orbit').format(body=planet)
    elif entry['event'] == 'LeaveBody':
        presence_details = _('Supercruising')
        small_image = 'system'
        small_text = system

    # EXTERNAL VEHICLE EVENTS
    elif entry['event'] == 'LaunchSRV':
        presence_details = _('In SRV on {body}').format(body=planet)
    elif entry['event'] == 'DockSRV':
        presence_details = _('Landed on {body}').format(body=planet)

    if presence_state != this.presence_state or presence_details != this.presence_details:
        this.presence_state = presence_state
        this.presence_details = presence_details
        this.largetext = large_text
        this.smallimage = small_image
        this.smalltext = small_text
        update_presence()
    elif shutdown == True:
        this.activity_manager.clear_activity(callback)


def check_run(plugin_dir):
    plugin_path = join(dirname(plugin_dir), plugin_name)
    retry = True
    while retry:
        time.sleep(1 / 10)
        try:
            this.app = dsdk.Discord(CLIENT_ID, dsdk.CreateFlags.no_require_discord, plugin_path)
            retry = False
        except Exception:
            pass

    this.activity_manager = this.app.get_activity_manager()
    this.activity = dsdk.Activity()

    this.activity_manager.register_steam(359320)

    this.call_back_thread = threading.Thread(target=run_callbacks)
    this.call_back_thread.setDaemon(True)
    this.call_back_thread.start()
    this.presence_state = _('Connecting CMDR Interface')
    this.presence_details = ''
    this.time_start = time.time()
    this.largeimage = 'elite'
    this.largetext = ''
    this.smallimage = ''
    this.smalltext = ''

    this.disablePresence = None

    update_presence()


def run_callbacks():
    try:
        while True:
            time.sleep(1 / 10)
            this.app.run_callbacks()
    except Exception:
        check_run(this.plugin_dir)
