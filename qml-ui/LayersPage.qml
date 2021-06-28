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
    title: "Layers"

    model: newLayers.list

    delegate: Kirigami.BasicListItem {
        width: view.width
        label: model.preset_path
        onClicked: {
            layers_controller.set_current_layer_index(index)
            applicationWindow().ensureVisible(banksPage)
        }
    }
}
