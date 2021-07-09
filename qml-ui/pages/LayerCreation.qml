/* -*- coding: utf-8 -*-
******************************************************************************
ZYNTHIAN PROJECT: Zynthian Qt GUI

Main Class and Program for Zynthian GUI

Copyright (C) 2021 Marco Martin <mart@kde.org>

******************************************************************************

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

For a full copy of the GNU General Public License see the LICENSE.txt file.

******************************************************************************
*/

import QtQuick 2.10
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import org.kde.kirigami 2.4 as Kirigami

import "../components" as ZComponents

ZComponents.MainRowLayout {
    id: root

    ZComponents.SelectorPage {
        id: enginePage
        selectorId: "engine"
        implicitWidth: root.width
    }

    ZComponents.SelectorPage {
        id: midiChanPage
        title: "Midi Channel"
        selectorId: "midi_chan"
        visible: false
        implicitWidth: root.width
    }

    data: [
        Connections {
            target: zynthian

            onCurrent_modal_screen_idChanged: {
                switch (zynthian.current_modal_screen_id) {
                case "engine":
                    root.activateItem(enginePage)
                    break;
                case "midi_chan":
                default:
                    root.activateItem(midiChanPage)
                    break;
                }
            }
        }
    ]
}
