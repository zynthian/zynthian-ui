/*
 * @@NAME@@ - plugin description macros (DPF)
 * See the DistrhoPluginInfo.h of the examples in dpf/examples for all the available macros.
 */

#ifndef DISTRHO_PLUGIN_INFO_H_INCLUDED
#define DISTRHO_PLUGIN_INFO_H_INCLUDED

#define DISTRHO_PLUGIN_NAME  "@@NAME@@"
#define DISTRHO_PLUGIN_URI   "@@URI@@"
#define DISTRHO_PLUGIN_BRAND_ID  @@BRAND_ID@@
#define DISTRHO_PLUGIN_UNIQUE_ID @@UNIQUE_ID@@

#define DISTRHO_PLUGIN_NUM_INPUTS   @@AUDIO_IN@@
#define DISTRHO_PLUGIN_NUM_OUTPUTS  @@AUDIO_OUT@@
#define DISTRHO_PLUGIN_IS_SYNTH     @@IS_SYNTH@@
#define DISTRHO_PLUGIN_WANT_MIDI_INPUT  @@MIDI_IN@@
#define DISTRHO_PLUGIN_WANT_MIDI_OUTPUT @@MIDI_OUT@@
#define DISTRHO_PLUGIN_IS_RT_SAFE   1

#define DISTRHO_PLUGIN_LV2_CATEGORY "@@LV2_CATEGORY@@"

// Native GUI: DGL with the Cairo backend (X11UI on Linux)
#define DISTRHO_PLUGIN_HAS_UI       1
#define DISTRHO_UI_USE_CAIRO        1
#define DISTRHO_UI_DEFAULT_WIDTH    @@UI_WIDTH@@
#define DISTRHO_UI_DEFAULT_HEIGHT   @@UI_HEIGHT@@
#define DISTRHO_UI_USER_RESIZABLE   1

#endif // DISTRHO_PLUGIN_INFO_H_INCLUDED
