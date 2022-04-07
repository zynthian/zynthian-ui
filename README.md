# Zynthian User Interface

[Zynthian](http://zynthian.org) is an Open Synth Platform based in Raspberry Pi, Linux (Raspbian) and Free Software Synthesizers (mostly).

The [ZynthianOS SD-image](https://os.zynthian.org/zynthianos-last-stable.zip) includes all the software you need for building a ZynthianBox, including a good amount of sound libraries and presets. This repository contains the software for the Engine Manager & User Interface.

![Image of Zynthian Box Design](http://zynthian.org/img/github/zynthian_v4_alzado_planta_nomargin.png)

The list of supported synth engines is quite long and includes, among others:

+ [ZynAddSubFX](https://sourceforge.net/projects/zynaddsubfx/) (Additive/Substractive/Pad Polyphonic Synthesizer with FXs)
+ [FluidSynth](http://www.fluidsynth.org/) (SF2 Soundfont engine)
+ [setBfree](https://github.com/pantherb/setBfree) (Hammond B3 emulation)
+ [Linuxsampler](https://www.linuxsampler.org/) (SFZ/GIG Soundfont engine)
+ [Sfizz](https://sfz.tools/sfizz/) (SFZ Soundfont engine)
+ [Pianoteq](https://www.modartt.com/pianoteq) (Non Free! Trial version included)
+ [Aeolus](https://kokkinizita.linuxaudio.org/linuxaudio/aeolus/) (Pipe Organ simulator)
+ [Dexed](https://asb2m10.github.io/dexed/) (DX7 emulator)
+ [OB-Xd](https://www.discodsp.com/obxd/https://asb2m10.github.io/dexed/) (Oberheim OB-X emulator)
+ [TAL NoizeMaker](https://tal-software.com/products/tal-noisemaker) (Virtual Analog Synthesizer)
+ [MOD-HOST + MOD-UI](https://github.com/moddevices) (Plugin Host & Web GUI by [ModDevices](http://moddevices.com))
+ [And many more ...](http://wiki.zynthian.org/index.php/Zynthian_Supported_Synth_Engines)

![Image of Zynthian Software Architecture](http://zynthian.org/img/github/sourcecode_scheme.png)

A [Zynthian Box](https://wiki.zynthian.org/index.php/Zynthian_Wiki_Home) is a hardware device that runs the zynthian's software stack. Although it's not a closed hardware specification, there is a (more or less) cannonical recomendation:

+ Raspberry Pi 3/4
+ Supported Soundcard (ZynADAC, HifiBerry, etc.)
+ Spported Display (Zynscreen, PiScreen, PiTFT, Waveshare, HDMI, etc.)
+ Zynthian controllers (4 rotary encoders + switches)
+ GPIO expander (MCP23017) => Highly recommended. You could need it because the RBPi GPIOs are busy
+ MIDI IN/THRU/OUT ports => It uses RBPi's UART (optional)

![Image of Zynthian Hardware Architecture](http://zynthian.org/img/github/zynthian_hardware_scheme_v4.png)

You can learn more about the Zynthian Project in any of our sites: 

+ [website](https://zynthian.org)
+ [wiki](https://wiki.zynthian.org)
+ [blog](https://blog.zynthian.org)
+ [forum](https://discourse.zynthian.org) => Join the conversation!!

You can buy official kits in the zynthian shop:

+ [shop](https://shop.zynthian.org)
