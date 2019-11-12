# Zynthian User Interface

[Zynthian](http://zynthian.org) is an Open Synth Platform based in Raspberry Pi, Linux (Raspbian) and some Open Software Synthesizers.

![Image of Zynthian Box Design](http://zynthian.org/img/github/zynthian_v3_backside.jpg)

Zynthian is a multi-engine platform and at the present time can run the next Synth Engines:

+ [ZynAddSubFX](https://sourceforge.net/projects/zynaddsubfx/) (Advanced Synthesizer)
+ [FluidSynth](http://www.fluidsynth.org/) (Sampler engine)
+ [setBfree](https://github.com/pantherb/setBfree) (Hammond B3 emulation)
+ [Linuxsampler](https://www.linuxsampler.org/) (Advanced Sampler engine)
+ [MOD-HOST + MOD-UI](https://github.com/moddevices) (Plugin Host & Web GUI by [ModDevices](http://moddevices.com))
+ [And more ...](http://wiki.zynthian.org/index.php/Zynthian_Supported_Synth_Engines)

![Image of Zynthian Software Architecture](http://zynthian.org/img/github/zynthian_software_amidi_scheme.png)

The [Zynthian Distribution](http://blog.zynthian.org/index.php/2015/11/22/building-a-zynthian-box/) includes a good amount of sound libraries and presets, but can be extended by the user.

A [Zynthian Box](http://blog.zynthian.org/index.php/2015/11/22/building-a-zynthian-box/) is a hardware device that complains the [Zynthian Hardware Specification](http://blog.zynthian.org/index.php/2015/11/22/building-a-zynthian-box/):

+ Raspberry Pi 2/3
+ HifiBerry DAC+ or other soundcard compatible with RBPi
+ PiTFT touchscreen or other screen compatible with RBPi
+ 4 rotary encoders + switches (Zynthian controller modules)
+ GPIO expander (MCP23008) => you need it because the RBPi GPIOs are not enough
+ MIDI-IN using RBPi UART (optional)

![Image of Zynthian Hardware Architecture](http://zynthian.org/img/github/zynthian_hardware_scheme_v2.png)

This repository contains the specific software used by a Zynthian Box. It includes the "User Interface software" and some "setup scripts".

A standard Zynthian Box get updated from this repository by default, but can be configured to get updated from other repositories.

You can learn more about the Zynthian Project reading [the blog](http://blog.zynthian.org) or visiting [the website](http://zynthian.org). Also, you can join the conversation in [the forum](https://discourse.zynthian.org).
