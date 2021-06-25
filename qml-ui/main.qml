/**
 *  SPDX-FileCopyrightText: 2021 Marco Martin <mart@kde.org>
 *
 *  SPDX-License-Identifier: LGPL-2.0-or-later
 */

import QtQuick 2.1
import QtQuick.Window 2.1
import org.kde.kirigami 2.6 as Kirigami

Kirigami.ApplicationWindow {
    id: root

    width: screen.width
    height: screen.height

    pageStack.defaultColumnWidth: root.width
    pageStack.initialPage: [mainPage, layersPage, controlPage]

    // FIXME: this stuff with a newer Kirigami should be done with a PageRouter?
    function ensureVisible(page) {
        switch (page) {
        case mainPage:
            pageStack.currentIndex = 0;
            break;
        case layersPage:
            if (pageStack.depth < 2) {
                pageStack.push(layersPage)
            }
            pageStack.currentIndex = 1;
            break;
        case banksPage:
            if (pageStack.depth < 3) {
                pageStack.push(banksPage)
            }
            pageStack.currentIndex = 2;
            break;
        case presetsPage:
            if (pageStack.depth < 4) {
                pageStack.push(presetsPage)
            }
            pageStack.currentIndex = 3;
            break;
        default:
        case controlPage:
            if (pageStack.depth < 5) {
                pageStack.push(controlPage)
            }
            pageStack.currentIndex = 4;
            break;
        }
    }

    function makeLastVisible(page) {
        ensureVisible(page);
        pageStack.pop(page);
    }

    MainPage {
        id: mainPage
    }
    LayersPage {
        id: layersPage
    }
    BanksPage {
        id: banksPage
    }
    PresetsPage {
        id: presetsPage
    }
    ControlPage {
        id: controlPage
    }
}

