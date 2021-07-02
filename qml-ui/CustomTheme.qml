/**
 *
 *  SPDX-FileCopyrightText: 2021 Marco Martin <mart@kde.org>
 *
 *  SPDX-License-Identifier = LGPL-2.0-or-later
 */

import QtQuick 2.10
import QtQuick.Layouts 1.4
import QtQuick.Controls 2.2 as QQC2
// HACK for old kirigami theme implementation that can be globally set
import org.kde.kirigami 2.0 as Kirigami


QtObject {
    id: root

    property bool darkMode: true

    onDarkModeChanged: {
        if (darkMode) {
            syncDarkTheme();
        } else {
            syncLightTheme();
        }
    }

    function syncLightTheme() {
        Kirigami.Theme.textColor = "#31363b"
        Kirigami.Theme.disabledTextColor = "#9931363b"

        Kirigami.Theme.highlightColor = "#2196F3"
        Kirigami.Theme.highlightedTextColor = "#eff0fa"
        Kirigami.Theme.backgroundColor = "#eff0f1"
        Kirigami.Theme.activeTextColor = "#0176D3"
        Kirigami.Theme.linkColor = "#2196F3"
        Kirigami.Theme.visitedLinkColor = "#2196F3"

        Kirigami.Theme.negativeTextColor = "#DA4453"
        Kirigami.Theme.neutralTextColor = "#F67400"
        Kirigami.Theme.positiveTextColor = "#27AE60"

        Kirigami.Theme.buttonTextColor = "#31363b"
        Kirigami.Theme.buttonBackgroundColor = "#eff0f1"
        Kirigami.Theme.buttonHoverColor = "#2196F3"
        Kirigami.Theme.buttonFocusColor = "#2196F3"

        Kirigami.Theme.viewTextColor = "#31363b"
        Kirigami.Theme.viewBackgroundColor = "#fcfcfc"
        Kirigami.Theme.viewHoverColor = "#2196F3"
        Kirigami.Theme.viewFocusColor = "#2196F3"

        Kirigami.Theme.selectionTextColor = "#eff0fa"
        Kirigami.Theme.selectionBackgroundColor = "#2196F3"
        Kirigami.Theme.selectionHoverColor = "#2196F3"
        Kirigami.Theme.selectionFocusColor = "#2196F3"

        Kirigami.Theme.tooltipTextColor = "#eff0f1"
        Kirigami.Theme.tooltipBackgroundColor = "#31363b"
        Kirigami.Theme.tooltipHoverColor = "#2196F3"
        Kirigami.Theme.tooltipFocusColor = "#2196F3"

        Kirigami.Theme.complementaryTextColor = "#eff0f1"
        Kirigami.Theme.complementaryBackgroundColor = "#31363b"
        Kirigami.Theme.complementaryHoverColor = "#2196F3"
        Kirigami.Theme.complementaryFocusColor = "#2196F3"
    }

    function syncDarkTheme() {
        Kirigami.Theme.textColor = "#eff0f1"
        Kirigami.Theme.disabledTextColor = "#a1a9b1"

        Kirigami.Theme.highlightColor = "#2196F3"
        Kirigami.Theme.highlightedTextColor = "#eff0fa"
        Kirigami.Theme.backgroundColor = "#31363b"
        Kirigami.Theme.activeTextColor = "#0176D3"
        Kirigami.Theme.linkColor = "#2196F3"
        Kirigami.Theme.visitedLinkColor = "#2196F3"

        Kirigami.Theme.negativeTextColor = "#DA4453"
        Kirigami.Theme.neutralTextColor = "#F67400"
        Kirigami.Theme.positiveTextColor = "#27AE60"

        Kirigami.Theme.buttonTextColor = "#fcfcfc"
        Kirigami.Theme.buttonBackgroundColor = "#31363b"
        Kirigami.Theme.buttonHoverColor = "#2196F3"
        Kirigami.Theme.buttonFocusColor = "#2196F3"

        Kirigami.Theme.viewTextColor = "#fcfcfc"
        Kirigami.Theme.viewBackgroundColor = "#1b1e20"
        Kirigami.Theme.viewHoverColor = "#2196F3"
        Kirigami.Theme.viewFocusColor = "#2196F3"

        Kirigami.Theme.selectionTextColor = "#eff0fa"
        Kirigami.Theme.selectionBackgroundColor = "#2196F3"
        Kirigami.Theme.selectionHoverColor = "#2196F3"
        Kirigami.Theme.selectionFocusColor = "#2196F3"

        Kirigami.Theme.tooltipTextColor = "#eff0f1"
        Kirigami.Theme.tooltipBackgroundColor = "#31363b"
        Kirigami.Theme.tooltipHoverColor = "#2196F3"
        Kirigami.Theme.tooltipFocusColor = "#2196F3"

        Kirigami.Theme.complementaryTextColor = "#eff0f1"
        Kirigami.Theme.complementaryBackgroundColor = "#31363b"
        Kirigami.Theme.complementaryHoverColor = "#2196F3"
        Kirigami.Theme.complementaryFocusColor = "#2196F3"
    }

    Component.onCompleted: {
        root.syncDarkTheme()
    }
}