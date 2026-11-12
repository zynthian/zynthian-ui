
ctrls = [
    # Column 1 - Oscillator 1
    ['Osc1 Waveform', 17, 0],
    ['Osc1 Pulsewidth', 18, 0],
    ['Osc1 Wave Select', 19, 0],
    ['Osc1 Semitone', 20, 0],
    ['Osc1 Key Tracking', 21, 0],

    # Column 1 - Oscillator 2
    ['Osc2 Waveform', 22, 0],
    ['Osc2 Pulsewidth', 23, 0],
    ['Osc2 Wave Select', 24, 0],
    ['Osc2 Semitone', 25, 0],
    ['Osc2 Detune', 26, 0],
    ['Osc2 FM Amount', 27, 0],
    ['Osc2 Osc Sync', 28, 0],
    ['Osc2 Filter Env', 29, 0],
    ['Osc2 Key Tracking', 31, 0],

    # Column 1 - Oscillator Global
    ['Oscillator Balance', 33, 0],
    ['Subosc Volume', 34, 0],
    ['Subosc Shape', 35, 0],
    ['Main Volume', 36, 0],
    ['Noise Volume', 37, 0],
    ['Ring Mod Volume', 38, 0],
    ['Noise Color', 39, 0],

    # Column 2 - Filter 1
    ['Filter1 Cutoff', 40, 0],
    ['Filter1 Resonance', 42, 0],
    ['Filter1 Env Amount', 44, 0],
    ['Filter1 Key Tracking', 46, 0],
    ['Filter1 Mode', 51, 0],

    # Column 2 - Filter 2
    ['Filter2 Cutoff', 41, 0],
    ['Filter2 Resonance', 43, 0],
    ['Filter2 Env Amount', 45, 0],
    ['Filter2 Key Tracking', 47, 0],
    ['Filter2 Mode', 52, 0],

    # Column 2 - Filter Global
    ['Filter Balance', 48, 0],
    ['Filter Routing', 53, 0],
    ['Saturation Curve', 49, 0],
    ['FM > Filter Env', 30, 0],

    # Column 2 - Filter Envelope
    ['Filter Env Attack', 54, 0],
    ['Filter Env Decay', 55, 0],
    ['Filter Env Sustain', 56, 0],
    ['Filter Env Sustain Time', 57, 0],
    ['Filter Env Release', 58, 0],

    # Column 3 - Amp Envelope
    ['Amp Env Attack', 59, 0],
    ['Amp Env Decay', 60, 0],
    ['Amp Env Sustain', 61, 0],
    ['Amp Env Sustain Time', 62, 0],
    ['Amp Env Release', 63, 0],

    # Column 3 - Voice / Pitch
    ['Portamento Time', 5, 0],
    ['Transpose', 93, 0],
    ['Keyboard Mode', 94, 0],
    ['Unison Mode', 97, 0],
    ['Unison Detune', 98, 0],
    ['Unison Spread', 99, 0],
    ['Unison LFO Phase', 109, 0],

    # Column 3 - Global Mixer
    ['Part Volume', 7, 0],
    ['Part Balance', 8, 0],
    ['Part Pan', 10, 0],
    ['Patch Volume', 91, 0],
    ['Input Mode', 101, 0],
    ['Input Select', 102, 0],

    # Column 4 - LFO Settings
    ['LFO1 Rate', 67, 0],
    ['LFO1 Shape', 68, 0],
    ['LFO1 Envelope Mode', 69, 0],
    ['LFO1 LFO Mode', 70, 0],
    ['LFO1 Symmetry', 71, 0],
    ['LFO1 Key Tracking', 72, 0],
    ['LFO1 Key Trigger', 73, 0],

    ['LFO2 Rate', 79, 0],
    ['LFO2 Shape', 80, 0],
    ['LFO2 Envelope Mode', 81, 0],
    ['LFO2 LFO Mode', 82, 0],
    ['LFO2 Symmetry', 83, 0],
    ['LFO2 Key Tracking', 84, 0],
    ['LFO2 Key Trigger', 85, 0],

    # Column 4 - LFO Routing
    ['LFO1 > Osc1', 74, 0],
    ['LFO1 > Osc2', 75, 0],
    ['LFO1 > Pulsewidth', 76, 0],
    ['LFO1 > Resonance', 77, 0],
    ['LFO1 > Filter Gain', 78, 0],
    ['LFO2 > Osc Shape', 86, 0],
    ['LFO2 > FM Amount', 87, 0],
    ['LFO2 > Filter1 Cutoff', 88, 0],
    ['LFO2 > Filter2 Cutoff', 89, 0],
    ['LFO2 > Pan', 90, 0],

    # Column 5 - Chorus
    ['Chorus Mix', 105, 0],
    ['Chorus Rate', 106, 0],
    ['Chorus Depth', 107, 0],
    ['Chorus Delay', 108, 0],
    ['Chorus Feedback', 109, 0],
    ['Chorus LFO Shape', 110, 0],

    # Column 5 - Delay
    ['Delay Time', 114, 0],
    ['Delay Feedback', 115, 0],
    ['Delay Rate', 116, 0],
    ['Delay Depth', 117, 0],
    ['Delay LFO Shape', 118, 0],
    ['Delay Color', 119, 0],

    # Column 5 - Reverb
    ['Reverb Decay Time', 116, 0],
    ['Reverb Room Size', 117, 0],
    ['Reverb Damping', 118, 0],

    # Column 5 - Effects Global
    ['Delay/Reverb Mode', 112, 0],
    ['Effect Send', 113, 0]
]

ctrl_screens = [
    ['Global Mixer (1)', ['Part Volume', 'Part Balance', 'Part Pan', 'Patch Volume']],
    ['Global Mixer (2)', ['Input Mode', 'Input Select']],

    ['Osc1 Settings', ['Osc1 Waveform', 'Osc1 Pulsewidth', 'Osc1 Wave Select', 'Osc1 Semitone']],
    ['Osc1 Key Tracking', ['Osc1 Key Tracking']],

    ['Osc2 Settings (1)', ['Osc2 Waveform', 'Osc2 Pulsewidth', 'Osc2 Wave Select', 'Osc2 Semitone']],
    ['Osc2 Settings (2)', ['Osc2 Detune', 'Osc2 FM Amount', 'Osc2 Osc Sync', 'Osc2 Filter Env']],
    ['Osc2 Key Tracking', ['Osc2 Key Tracking']],

    ['Osc Global (1)', ['Oscillator Balance', 'Subosc Volume', 'Subosc Shape', 'Main Volume']],
    ['Osc Global (2)', ['Noise Volume', 'Ring Mod Volume', 'Noise Color']],

    ['Filter1 Settings', ['Filter1 Cutoff', 'Filter1 Resonance', 'Filter1 Env Amount', 'Filter1 Mode']],
    ['Filter1 Key Tracking', ['Filter1 Key Tracking']],

    ['Filter2 Settins', ['Filter2 Cutoff', 'Filter2 Resonance', 'Filter2 Env Amount', 'Filter2 Mode']],
    ['Filter2 Key Tracking', ['Filter2 Key Tracking']],

    ['Filter Global', ['Filter Balance', 'Filter Routing', 'Saturation Curve', 'FM > Filter Env']],

    ['Filter Env (1)', ['Filter Env Attack', 'Filter Env Decay', 'Filter Env Sustain', 'Filter Env Sustain Time']],
    ['Filter Env (2)', ['Filter Env Release']],

    ['Amp Env (1)', ['Amp Env Attack', 'Amp Env Decay', 'Amp Env Sustain', 'Amp Env Sustain Time']],
    ['Amp Env (2)', ['Amp Env Release']],

    ['Voice Pitch (1)', ['Portamento Time', 'Transpose', 'Keyboard Mode', 'Unison Mode']],
    ['Voice Pitch (2)', ['Unison Detune', 'Unison Spread', 'Unison LFO Phase']],

    ['LFO1 (1)', ['LFO1 Rate', 'LFO1 Shape', 'LFO1 Envelope Mode', 'LFO1 LFO Mode']],
    ['LFO1 (2)', ['LFO1 Symmetry', 'LFO1 Key Tracking', 'LFO1 Key Trigger']],

    ['LFO2 (1)', ['LFO2 Rate', 'LFO2 Shape', 'LFO2 Envelope Mode', 'LFO2 LFO Mode']],
    ['LFO2 (2)', ['LFO2 Symmetry', 'LFO2 Key Tracking', 'LFO2 Key Trigger']],

    ['LFO Routing (1)', ['LFO1 > Osc1', 'LFO1 > Osc2', 'LFO1 > Pulsewidth', 'LFO1 > Resonance']],
    ['LFO Routing (2)', ['LFO1 > Filter Gain', 'LFO2 > Osc Shape', 'LFO2 > FM Amount', 'LFO2 > Filter1 Cutoff']],
    ['LFO Routing (3)', ['LFO2 > Filter2 Cutoff', 'LFO2 > Pan']],

    ['FX Chorus (1)', ['Chorus Mix', 'Chorus Rate', 'Chorus Depth', 'Chorus Delay']],
    ['FX Chorus (2)', ['Chorus Feedback', 'Chorus LFO Shape']],
    ['FX Delay (1)', ['Delay Time', 'Delay Feedback', 'Delay Rate', 'Delay Depth']],
    ['FX Delay (2)', ['Delay LFO Shape', 'Delay Color']],
    ['FX Reverb', ['Reverb Decay Time', 'Reverb Room Size', 'Reverb Damping']],
    ['FX Global', ['Delay/Reverb Mode', 'Effect Send']]
]
