/**
 *
 *  SPDX-FileCopyrightText: 2021 Marco Martin <mart@kde.org>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

import QtQuick 2.10
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
import org.kde.kirigami 2.4 as Kirigami

import "components" as ZComponents

Kirigami.PageRow {
    id: root

    defaultColumnWidth: root.width
    globalToolBar.style: Kirigami.ApplicationHeaderStyle.Breadcrumb

    initialPage: ZComponents.SelectorPage {
        selector: zynthian.engine
        onItemActivated: root.push(midiChanComponent)
    }

    Component {
        id: midiChanComponent
        ZComponents.SelectorPage {
            selector: zynthian.midi_chan
            onItemActivated: {
                applicationWindow().makeLastVisible(layersPage)
                applicationWindow().pageStack.layers.pop()
            }
        }
    }
}

