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

Kirigami.Page {
    id: root
    title: layers_controller.curlayer.preset_name

    Component.onCompleted: {
        mainView.forceActiveFocus()
        control_wrapper.active_screen_index = 0
    }
    onFocusChanged: {
        if (focus) {
            mainView.forceActiveFocus()
        }
    }

    contentItem: RowLayout {
        ColumnLayout {
            Layout.maximumWidth: Math.floor(root.width / 4)
            Layout.fillHeight: true
            ZComponents.Controller {
                title: control_wrapper.controller1.name
                max: control_wrapper.controller1.value_max
                value: control_wrapper.controller1.value
            }
            ZComponents.Controller {
                title: control_wrapper.controller2.name
                max: control_wrapper.controller2.value_max
                value: control_wrapper.controller2.value
            }
        }
        ZComponents.Card {
            leftPadding: 0
            rightPadding: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentItem: QQC2.ScrollView {
                QQC2.ScrollBar.horizontal.visible: false
                ListView {
                    id: mainView
                    keyNavigationEnabled: true
                    keyNavigationWraps: true
                    model: control_wrapper.screen_names
                    clip: true

                    delegate: Kirigami.BasicListItem {
                        label: model.display
                        checked: mainView.currentIndex == index
                        onClicked: {
                            control_wrapper.active_screen_index = index
                            mainView.currentIndex = index
                        }
                    }
                }
            }
        }
        ColumnLayout {
            Layout.maximumWidth: Math.floor(root.width / 4)
            Layout.fillHeight: true
            ZComponents.Controller {
                title: control_wrapper.controller3.name
                max: control_wrapper.controller3.value_max
                value: control_wrapper.controller3.value
            }
            ZComponents.Controller {
                title: control_wrapper.controller4.name
                max: control_wrapper.controller4.value_max
                value: control_wrapper.controller4.value
            }
        }
    }
}
