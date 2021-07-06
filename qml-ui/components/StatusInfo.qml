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
import org.kde.kirigami 2.4 as Kirigami


Item {
	id: root
	implicitWidth: Kirigami.Units.gridUnit * 10


	Connections {
		target: zynthian.status_information
		onStatus_changed: {
			let signalA = Math.max(0, 1 + zynthian.status_information.peakA / zynthian.status_information.rangedB);
			lowSignalARect.width = Math.min(signalA, zynthian.status_information.high) * root.width;
			mediumSignalARect.width = Math.min(signalA, zynthian.status_information.over) * root.width;
			highSignalARect.width = Math.min(signalA, 1) * root.width;

			signalA = Math.max(0, 1 + zynthian.status_information.holdA / zynthian.status_information.rangedB);
			let holdAX = Math.floor(Math.min(signalA, 1) * root.width);
			holdSignalARect.x = holdAX;
			if (holdAX === 0) {
				holdSignalARect.opacity = 0;
			} else {
				holdSignalARect.opacity = 1;
			}

			let signalB = Math.max(0, 1 + zynthian.status_information.peakB / zynthian.status_information.rangedB);
			lowSignalBRect.width = Math.min(signalB, zynthian.status_information.high) * root.width;
			mediumSignalBRect.width = Math.min(signalB, zynthian.status_information.over) * root.width;
			highSignalBRect.width = Math.min(signalB, 1) * root.width;


			signalB = Math.max(0, 1 + zynthian.status_information.holdB / zynthian.status_information.rangedB);
			let holdBX = Math.floor(Math.min(signalB, 1) * root.width);
			holdSignalBRect.x = holdBX;
			if (holdBX === 0) {
				holdSignalBRect.opacity = 0;
			} else {
				holdSignalBRect.opacity = 1;
			}
		}
	}

	ColumnLayout {
		anchors.fill: parent

		Item {
			Layout.fillWidth: true
			Layout.fillHeight: true

			Rectangle {
				id: holdSignalARect
				anchors {
					top: parent.top
					bottom: parent.bottom
				}
				opacity: 0
				implicitWidth: Kirigami.Units.smallSpacing
				color: "#da4453"
				Behavior on x {
					XAnimator {
						duration: Kirigami.Units.shortDuration
						easing.type: Easing.InOutQuad
					}
				}
				Behavior on opacity {
					OpacityAnimator {
						duration: Kirigami.Units.longDuration
						easing.type: Easing.InOutQuad
					}
				}
			}
			Rectangle {
				id: highSignalARect
				anchors {
					top: parent.top
					bottom: parent.bottom
					left: parent.left
				}
				color: "#da4453"
			}
			Rectangle {
				id: mediumSignalARect
				anchors {
					top: parent.top
					bottom: parent.bottom
					left: parent.left
				}
				color: "#fbbb4c"
			}
			Rectangle {
				id: lowSignalARect
				anchors {
					top: parent.top
					bottom: parent.bottom
					left: parent.left
				}
				color: "#11d116"
			}
		}

		Item {
			Layout.fillWidth: true
			Layout.fillHeight: true

			Rectangle {
				id: holdSignalBRect
				anchors {
					top: parent.top
					bottom: parent.bottom
				}
				opacity: 0
				implicitWidth: Kirigami.Units.smallSpacing
				color: "#da4453"
				Behavior on x {
					XAnimator {
						duration: Kirigami.Units.shortDuration
						easing.type: Easing.InOutQuad
					}
				}
				Behavior on opacity {
					OpacityAnimator {
						duration: Kirigami.Units.longDuration
						easing.type: Easing.InOutQuad
					}
				}
			}
			Rectangle {
				id: highSignalBRect
				anchors {
					top: parent.top
					bottom: parent.bottom
					left: parent.left
				}
				color: "#da4453"
			}
			Rectangle {
				id: mediumSignalBRect
				anchors {
					top: parent.top
					bottom: parent.bottom
					left: parent.left
				}
				color: "#fbbb4c"
			}
			Rectangle {
				id: lowSignalBRect
				anchors {
					top: parent.top
					bottom: parent.bottom
					left: parent.left
				}
				color: "#11d116"
			}
		}
	}

	RowLayout {
		id: statusIconsLayout
		anchors {
			right: parent.right
			bottom: parent.bottom
		}
		height: Math.min(parent.height / 2, Kirigami.Units.iconSizes.smallMedium)
		Kirigami.Icon {
			Layout.fillHeight: true
			Layout.preferredWidth: height
			source: "dialog-warning-symbolic"
			color: "red"
			visible: zynthian.status_information.xrun
		}
		Kirigami.Icon {
			Layout.fillHeight: true
			Layout.preferredWidth: height
			source: "preferences-system-power"
			visible: zynthian.status_information.undervoltage
		}
		Kirigami.Icon {
			Layout.fillHeight: true
			Layout.preferredWidth: height
			source: "media-record-symbolic"
			visible: zynthian.status_information.audio_recorder || zynthian.status_information.midi_recorder
		}
	}
}
