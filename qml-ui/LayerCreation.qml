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

ZComponents.MainRowLayout {
    id: root

    ZComponents.SelectorPage {
        selector: zynthian.engine
        Layout.minimumWidth: mainRowLayout.width
            Layout.maximumWidth: Layout.minimumWidth
        onItemActivated: root.activateItem(midiChanPage)
    }

	ZComponents.SelectorPage {
		id: midiChanPage
		selector: zynthian.midi_chan
		visible: false
		Layout.minimumWidth: mainRowLayout.width
		Layout.maximumWidth: Layout.minimumWidth
		onItemActivated: {
			applicationWindow().makeLastVisible(layersPage)
			applicationWindow().pageStack.layers.pop()
		}
	}
}

