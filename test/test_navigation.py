#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Navigation tests
#
# Copyright (C) 2022 Brian Walton <brian@riban.co.uk>
#
#******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
#******************************************************************************
#
# This tests navigation using OSC control, reading journal output
# Zynthian must be running as a service
#
#******************************************************************************

import liblo
import pexpect

zynthian_addr = 'localhost'

#   Send a CUIA command via OSC
#   cmd: OSC path for CUIA command, e.g. /cuia/reboot
#   params: Optional parameters to send via OSC
def cuia(cmd, params=None):
    liblo.send('osc.udp://{}:1370'.format(zynthian_addr), cmd, params)


#   Flush journal buffer
def flush():
    try:
        journal.timeout = 0.1
        journal.readlines()
    except:
        pass



#   Run a test
#   title: Title of test
#   cmd: CUIA command to send to Zynthian
#   params: CUIA parameters, may be None
#   response: Expected response to be logged to journal
#   timeout: Time to wait for response before signalling test failed
#   Returns: True if test succeeds
def test(title, cmd, params, response, timeout=1):
    result = "FAILED"
    flush()
    cuia(cmd, params)
    try:
        journal.expect(response, timeout=timeout)
        result = "PASSED"
    except pexpect.TIMEOUT:
        result = "FAILED"
    except Exception as e:
        print(e)
    flush()
    print("{}: {}".format(result, title))
    return result

#confirm('Start Zynthian regression testing?')
journal = pexpect.spawn('/bin/journalctl -fu zynthian', encoding='UTF-8')

test('Enable test mode', '/cuia/test_mode', 1, 'TEST_MODE: \[1\]\r\n')

# Show mixer then clean so we know where we are starting from
if test('Navigate to mixer view', '/cuia/SCREEN_AUDIO_MIXER', None, 'TEST_MODE: zyngui.zynthian_gui_mixer\r\n') == 'FAILED':
    # May have toggled so let's try to recover
    cuia('/cuia/SCREEN_AUDIO_MIXER')
    flush()

test('Clean all', '/cuia/clean_all', 'CONFIRM', 'TEST_MODE: zyngui.zynthian_gui_main\r\n', 10)

test('Bold back should go to mixer view', '/cuia/switch_back_bold', None, 'TEST_MODE: zyngui.zynthian_gui_mixer\r\n')