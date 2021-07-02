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

//NOTE: this is due to a bug in Kirigami.AbstractCard from Buster's version, Replace with Kirigami.RowLayout when possible
Kirigami.Page {
    id: root

    default property alias data: layout.data
    readonly property int currentPage: Math.floor((flickable.contentX + flickable.width/2) / flickable.width)

    property int currentIndex: 0
    readonly property Item currentItem: layout.visibleChildren[currentIndex]

    leftPadding: 0
    topPadding: 0
    bottomPadding: 0
    rightPadding: 0

    function activateItem(item) {
        let idx = flickable.itemIndex(item);
        if (idx >= 0) {
            var i;
            for (i in layout.children) {
                layout.children[i].visible = true;
                if (i == idx) {
                    break;
                }
            }
            currentIndex = idx;
        }
    }

    function ensureLastVisibleItem(item) {
        let idx = flickable.itemIndex(item);
        if (idx >= 0) {
            var i;
            for (i in layout.children) {
                layout.children[i].visible = i <= idx;
            }
        }
    }

    function goToPreviousPage() {
        if (currentPage === 0) {
            return;
        }
        slideAnim.stop();
        slideAnim.from = flickable.contentX;
        slideAnim.to = Math.max(0, Math.min(flickable.contentWidth - flickable.width, flickable.width * (root.currentPage - 1)))
        slideAnim.start();
    }

    header: QQC2.ToolBar {
        contentItem: Flickable {
            id: breadcrumbFlickable
            contentHeight: height
            contentWidth: breadcrumbLayout.width
            RowLayout {
                id: breadcrumbLayout
                spacing: 0
                Repeater {
                    model: layout.visibleChildren.length
                    QQC2.ToolButton {
                        text: (index > 0 ? "> ": "") + layout.visibleChildren[index].title
                        checked: root.currentIndex === index
                        opacity: checked ? 1 : 0.8
                        checkable: false
                        font.pointSize: 15
                        onClicked: {
                            root.currentIndex = index
                        }
                        onCheckedChanged: {
                            if (!checked) {
                                return;
                            }
                            if (x + width - breadcrumbFlickable.contentX <= breadcrumbFlickable.contentX + breadcrumbFlickable.width) {
                                return;
                            }
                            breadcrumbSlideAnim.stop();
                            breadcrumbSlideAnim.from = breadcrumbFlickable.contentX;
                            breadcrumbSlideAnim.to = Math.min(breadcrumbLayout.width - breadcrumbFlickable.width, x + breadcrumbFlickable.width - width);
                            breadcrumbSlideAnim.start();
                        }
                    }
                }
            }
            NumberAnimation {
                id: breadcrumbSlideAnim
                target: breadcrumbFlickable
                property: "contentX"
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }
    }

    onCurrentIndexChanged: {
        if (currentIndex < 0 || currentIndex >= layout.visibleChildren.length) {
            return;
        }
        slideAnim.stop();
        slideAnim.from = flickable.contentX;
        slideAnim.to = flickable.width * Math.floor((layout.visibleChildren[currentIndex].x + layout.visibleChildren[currentIndex].width/2) / flickable.width);
        print((layout.visibleChildren[currentIndex]))
        slideAnim.start();
    }

    contentItem: Flickable {
        id: flickable

        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width * Math.ceil(layout.width / width)
        contentHeight: height
        maximumFlickVelocity: 0
        property int pageDeltaIntention
        property real oldContentX
        property real moveStartContentX

        function itemIndex(item) {
            let idx = -1;
            var i;
            for (i in layout.children) {
                let candidate = layout.children[i];
                if (candidate === item) {
                    idx = i;
                    break;
                }
            }
            return idx;
        }

        function visibleItemIndex(item) {
            let idx = -1;
            var i;
            for (i in layout.visibleChildren) {
                let candidate = layout.visibleChildren[i];
                if (candidate === item) {
                    idx = i;
                    break;
                }
            }
            return idx;
        }

        onContentXChanged: {
            // Didn't move enough
            if (Math.abs(contentX - moveStartContentX) < root.width / 10) {
                pageDeltaIntention = 0;
            } else if (contentX > oldContentX && contentX > moveStartContentX) {
                pageDeltaIntention = 1;
            } else if (contentX < oldContentX && contentX < moveStartContentX) {
                pageDeltaIntention = -1;
            } else {
                pageDeltaIntention = 0;
            }
            oldContentX = contentX;
        }
        onMovementStarted: {
            pageDeltaIntention = 0;
            moveStartContentX = oldContentX = contentX;
        }
        onMovementEnded: {
            slideAnim.stop();
            slideAnim.from = flickable.contentX;
            slideAnim.to = Math.max(0, Math.min(contentWidth - width, width * (root.currentPage + pageDeltaIntention)))
            slideAnim.start();
        }
        SequentialAnimation {
            id: slideAnim
            property alias from: internalSlideAnim.from
            property alias to: internalSlideAnim.to
            NumberAnimation {
                id: internalSlideAnim
                target: flickable
                property: "contentX"
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
            ScriptAction {
                script: {
                    let itemCenter = root.currentItem.x + root.currentItem.width/2;
                    if (itemCenter >= flickable.contentX && itemCenter <= flickable.contentX + flickable.width) {
                        return;
                    }
                    root.currentIndex = flickable.visibleItemIndex(layout.childAt(Math.floor(flickable.contentX + flickable.width/2), 10))
                }
            }
        }

        RowLayout {
            id: layout
            spacing: 0
            height: flickable.height
            onChildrenChanged: {
                var i;
                for (i in children) {
                    children[i].Layout.fillHeight = true;
                }
            }
        }
    }
}
