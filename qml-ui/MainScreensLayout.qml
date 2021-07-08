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

import QtQuick 2.11
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import QtQuick.Window 2.1
import org.kde.kirigami 2.6 as Kirigami

import "components" as ZComponents
import "pages" as Pages

ZComponents.MainRowLayout {
    id: root
    data: [
        Connections {
            target: zynthian
            onCurrent_screen_idChanged: {
                print("SCREEN ID CHANGED: "+zynthian.current_screen_id);
                var i;
                for (i in root.items) {
                    let child = root.items[i];
                    if (child.selectorId === zynthian.current_screen_id) {
                        root.activateItem(child);
                        return;
                    }
                }
                print("Non managed screen " + zynthian.current_screen_id)
            }
        }
    ]
}
