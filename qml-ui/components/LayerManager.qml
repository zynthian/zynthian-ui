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

//NOTE: this is due to a bug in Kirigami.AbstractCard from Buster's version

QQC2.StackView {
	id: layersStack
	z: 99
	anchors {
		fill: parent
	}
	//placeholder as initial item
	initialItem: columnViewLayout

	function clear () {
		//don't let it kill the main page row
		var d = layersStack.depth;
		for (var i = 1; i < d; ++i) {
			pop();
		}
	}

	popEnter: Transition {
		OpacityAnimator {
			from: 0
			to: 1
			duration: Kirigami.Units.longDuration
			easing.type: Easing.InOutCubic
		}
	}
	popExit: Transition {
		ParallelAnimation {
			OpacityAnimator {
				from: 1
				to: 0
				duration: Kirigami.Units.longDuration
				easing.type: Easing.InOutCubic
			}
			YAnimator {
				from: 0
				to: height/2
				duration: Kirigami.Units.longDuration
				easing.type: Easing.InCubic
			}
		}
	}

	pushEnter: Transition {
		ParallelAnimation {
			//NOTE: It's a PropertyAnimation instead of an Animator because with an animator the item will be visible for an instant before starting to fade
			PropertyAnimation {
				property: "opacity"
				from: 0
				to: 1
				duration: Kirigami.Units.longDuration
				easing.type: Easing.InOutCubic
			}
			YAnimator {
				from: height/2
				to: 0
				duration: Kirigami.Units.longDuration
				easing.type: Easing.OutCubic
			}
		}
	}


	pushExit: Transition {
		OpacityAnimator {
			from: 1
			to: 0
			duration: Kirigami.Units.longDuration
			easing.type: Easing.InOutCubic
		}
	}

	replaceEnter: Transition {
		ParallelAnimation {
			OpacityAnimator {
				from: 0
				to: 1
				duration: Kirigami.Units.longDuration
				easing.type: Easing.InOutCubic
			}
			YAnimator {
				from: height/2
				to: 0
				duration: Kirigami.Units.longDuration
				easing.type: Easing.OutCubic
			}
		}
	}

	replaceExit: Transition {
		ParallelAnimation {
			OpacityAnimator {
				from: 1
				to: 0
				duration: Kirigami.Units.longDuration
				easing.type: Easing.InCubic
			}
			YAnimator {
				from: 0
				to: -height/2
				duration: Kirigami.Units.longDuration
				easing.type: Easing.InOutCubic
			}
		}
	}
}
