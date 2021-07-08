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

        Kirigami.Theme.highlightColor = applicationWindow().palette.highlight
        Kirigami.Theme.highlightedTextColor = "#eff0fa"
        Kirigami.Theme.backgroundColor = "#eff0f1"
        Kirigami.Theme.activeTextColor = "#0176D3"
        Kirigami.Theme.linkColor = applicationWindow().palette.highlight
        Kirigami.Theme.visitedLinkColor = applicationWindow().palette.highlight

        Kirigami.Theme.negativeTextColor = "#DA4453"
        Kirigami.Theme.neutralTextColor = "#F67400"
        Kirigami.Theme.positiveTextColor = "#27AE60"

        Kirigami.Theme.buttonTextColor = "#31363b"
        Kirigami.Theme.buttonBackgroundColor = "#eff0f1"
        Kirigami.Theme.buttonHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.buttonFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.viewTextColor = "#31363b"
        Kirigami.Theme.viewBackgroundColor = "#fcfcfc"
        Kirigami.Theme.viewHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.viewFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.selectionTextColor = "#eff0fa"
        Kirigami.Theme.selectionBackgroundColor = applicationWindow().palette.highlight
        Kirigami.Theme.selectionHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.selectionFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.tooltipTextColor = "#eff0f1"
        Kirigami.Theme.tooltipBackgroundColor = "#31363b"
        Kirigami.Theme.tooltipHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.tooltipFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.complementaryTextColor = "#eff0f1"
        Kirigami.Theme.complementaryBackgroundColor = "#31363b"
        Kirigami.Theme.complementaryHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.complementaryFocusColor = applicationWindow().palette.highlight
    }

    function syncDarkTheme() {
        Kirigami.Theme.textColor = applicationWindow().palette.windowText
        Kirigami.Theme.disabledTextColor = "#a1a9b1"

        Kirigami.Theme.highlightColor = applicationWindow().palette.highlight
        Kirigami.Theme.highlightedTextColor = applicationWindow().palette.highlightedText
        Kirigami.Theme.backgroundColor = applicationWindow().palette.window
        Kirigami.Theme.activeTextColor = applicationWindow().palette.brightText
        Kirigami.Theme.linkColor = applicationWindow().palette.link
        Kirigami.Theme.visitedLinkColor = applicationWindow().palette.linkVisited

        Kirigami.Theme.negativeTextColor = "#DA4453"
        Kirigami.Theme.neutralTextColor = "#F67400"
        Kirigami.Theme.positiveTextColor = "#27AE60"

        Kirigami.Theme.buttonTextColor = pplicationWindow().palette.buttonText
        Kirigami.Theme.buttonBackgroundColor = applicationWindow().palette.button
        Kirigami.Theme.buttonHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.buttonFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.viewTextColor = applicationWindow().palette.text
        Kirigami.Theme.viewBackgroundColor = applicationWindow().palette.base
        Kirigami.Theme.viewHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.viewFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.selectionTextColor = applicationWindow().palette.highlightedText
        Kirigami.Theme.selectionBackgroundColor = applicationWindow().palette.highlight
        Kirigami.Theme.selectionHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.selectionFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.tooltipTextColor = applicationWindow().palette.toolTipText
        Kirigami.Theme.tooltipBackgroundColor = applicationWindow().palette.toolTipBase
        Kirigami.Theme.tooltipHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.tooltipFocusColor = applicationWindow().palette.highlight

        Kirigami.Theme.complementaryTextColor = applicationWindow().palette.windowText
        Kirigami.Theme.complementaryBackgroundColor = applicationWindow().palette.window
        Kirigami.Theme.complementaryHoverColor = applicationWindow().palette.highlight
        Kirigami.Theme.complementaryFocusColor = applicationWindow().palette.highlight
    }

    Component.onCompleted: {
        root.syncDarkTheme()
    }
}
