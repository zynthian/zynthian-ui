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

ZComponents.SelectorPage {
    id: root
    title: "Banks"

    model: newBank.selector_list
    currentIndex: newBank.current_index

    delegate: Kirigami.BasicListItem {
        width: view.width
        label: model.display
        onClicked: {
            newBank.current_index = index;
            newBank.activate_index(index);
            applicationWindow().ensureVisible(presetsPage);
        }
    }
}
