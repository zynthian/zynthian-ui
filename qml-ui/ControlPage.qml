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
    title: zynthian.control.selector_path_element
   // title: "Control"

    Component.onCompleted: {
        mainView.forceActiveFocus()
    }
    onFocusChanged: {
        if (focus) {
            mainView.forceActiveFocus()
        }
    }

    bottomPadding: Kirigami.Units.smallSpacing
    contentItem: RowLayout {
        ColumnLayout {
            Layout.maximumWidth: Math.floor(root.width / 4)
            Layout.minimumWidth: Layout.maximumWidth
            Layout.fillHeight: true
            ZComponents.Controller {
                // FIXME: this always assumes there are always exactly 4 controllers for the entire lifetime
                controller: zynthian.control.controller(0)
            }
            ZComponents.Controller {
                controller: zynthian.control.controller(1)
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
                    model: zynthian.control.selector_list
                    currentIndex: zynthian.control.current_index
                    clip: true

                    delegate: Kirigami.BasicListItem {
                        label: model.display
                        checked: mainView.currentIndex == index
                        onClicked: {
                            zynthian.control.current_index = index;
                            zynthian.control.activate_index(index);
                        }
                    }
                }
            }
        }
        ColumnLayout {
            Layout.maximumWidth: Math.floor(root.width / 4)
            Layout.minimumWidth: Layout.maximumWidth
            Layout.fillHeight: true
            ZComponents.Controller {
                controller: zynthian.control.controller(2)
            }
            ZComponents.Controller {
                controller: zynthian.control.controller(3)
            }
        }
    }
}
