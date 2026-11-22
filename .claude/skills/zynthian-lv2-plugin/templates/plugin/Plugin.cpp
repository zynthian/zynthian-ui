/*
 * @@NAME@@ - DSP
 * @@DESCRIPTION@@
 *
 * Copyright (C) @@YEAR@@ @@MAKER@@
 * License: @@LICENSE@@
 */

#include "DistrhoPlugin.hpp"
#include "ParamDefs.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

START_NAMESPACE_DISTRHO

class @@CLASS@@Plugin : public Plugin
{
public:
    @@CLASS@@Plugin()
        : Plugin(kParamCount, 0, 0)  // parameters, programs, states
    {
        for (uint32_t i = 0; i < kParamCount; ++i)
            fValues[i] = kParams[i].def;
        for (uint32_t m = 0; m < kMeterCount; ++m)
            fMeterPeak[m] = 0.0f;
        sampleRateChanged(getSampleRate());
    }

protected:
    // ----------------------------------------------------------------------------------------------------------------
    // Information

    const char* getLabel() const override { return "@@SYMBOL@@"; }
    const char* getDescription() const override { return "@@DESCRIPTION@@"; }
    const char* getMaker() const override { return "@@MAKER@@"; }
    const char* getHomePage() const override { return "@@HOMEPAGE@@"; }
    const char* getLicense() const override { return "@@LICENSE@@"; }
    uint32_t getVersion() const override { return d_version(@@VERSION@@); }

    // ----------------------------------------------------------------------------------------------------------------
    // Ports, parameters and groups (from ParamDefs.hpp)

    void initPortGroup(const uint32_t groupId, PortGroup& portGroup) override
    {
        if (groupId < kGroupCount)
        {
            portGroup.name = kGroups[groupId].name;
            portGroup.symbol = kGroups[groupId].symbol;
        }
    }

    void initParameter(const uint32_t index, Parameter& parameter) override
    {
        if (index >= kParamCount)
            return;
        const ParamDef& p(kParams[index]);
        if (p.designation != kParameterDesignationNull)
            parameter.initDesignation(p.designation);  // bypass: LV2 port "lv2_enabled", inverted by DPF
        parameter.hints = p.hints;
        parameter.name = p.name;
        parameter.symbol = p.symbol;
        parameter.unit = p.unit;
        parameter.ranges.min = p.min;
        parameter.ranges.max = p.max;
        parameter.ranges.def = p.def;
        parameter.groupId = p.group >= 0 ? static_cast<uint32_t>(p.group) : kPortGroupNone;
        if (p.enumCount > 0)
        {
            ParameterEnumerationValue* const values = new ParameterEnumerationValue[p.enumCount];
            for (uint32_t i = 0; i < p.enumCount; ++i)
            {
                values[i].label = p.enumLabels[i];
                values[i].value = p.min + i;
            }
            parameter.enumValues.count = p.enumCount;
            parameter.enumValues.restrictedMode = true;
            parameter.enumValues.values = values;
        }
    }

    float getParameterValue(const uint32_t index) const override
    {
        return index < kParamCount ? fValues[index] : 0.0f;
    }

    void setParameterValue(const uint32_t index, const float value) override
    {
        if (index < kParamCount && (kParams[index].hints & kParameterIsOutput) == 0)
            fValues[index] = value;
    }

    // ----------------------------------------------------------------------------------------------------------------
    // Processing

    void sampleRateChanged(const double sampleRate) override
    {
        // Precompute everything that depends on the sample rate here (not in run)
        fMeterDecayPerSample = std::exp(-1.0f / (0.3f * static_cast<float>(sampleRate)));  // ~300 ms decay
        fBypassStep = 1.0f / (0.01f * static_cast<float>(sampleRate));  // 10 ms bypass crossfade
    }

    void activate() override
    {
        for (uint32_t m = 0; m < kMeterCount; ++m)
            fMeterPeak[m] = 0.0f;
        fBypassMix = isBypassed() ? 1.0f : 0.0f;
    }

    bool isBypassed() const
    {
        return kBypassParam < kParamCount && fValues[kBypassParam < kParamCount ? kBypassParam : 0] > 0.5f;
    }

    // TODO: replace this demo DSP (passthrough + output meters) with the algorithm in SPEC.md.
    // RT-safe only: no allocation, locks, I/O or logging here.
    void run(const float** const inputs, float** const outputs, const uint32_t frames@@RUN_MIDI_ARGS@@) override
    {
@@RUN_MIDI_BODY@@
#if DISTRHO_PLUGIN_NUM_OUTPUTS > 0
        // Per sample, reading all the inputs first: hosts may pass the same buffer as input and output.
        // Bypass (audio effects): crossfade wet -> dry in 10 ms, no clicks. When fully bypassed (fBypassMix == 1)
        // you may skip the DSP to save CPU, and reset its state (delay lines...) when un-bypassing.
        const float bypassTarget = isBypassed() ? 1.0f : 0.0f;
        for (uint32_t i = 0; i < frames; ++i)
        {
            if (fBypassMix != bypassTarget)
                fBypassMix = bypassTarget > fBypassMix ? std::min(bypassTarget, fBypassMix + fBypassStep)
                                                       : std::max(bypassTarget, fBypassMix - fBypassStep);
# if DISTRHO_PLUGIN_NUM_INPUTS > 0
            float dry[DISTRHO_PLUGIN_NUM_INPUTS];
            for (uint32_t c = 0; c < DISTRHO_PLUGIN_NUM_INPUTS; ++c)
                dry[c] = inputs[c][i];
            for (uint32_t c = 0; c < DISTRHO_PLUGIN_NUM_OUTPUTS; ++c)
            {
                const float in = dry[c % DISTRHO_PLUGIN_NUM_INPUTS];
                const float wet = in;  // TODO: the processed sample
                outputs[c][i] = wet + (in - wet) * fBypassMix;
            }
# else
            for (uint32_t c = 0; c < DISTRHO_PLUGIN_NUM_OUTPUTS; ++c)
                outputs[c][i] = 0.0f;  // TODO: the generated sample
# endif
        }

        // Demo meters: peak level (dB) of the audio outputs, held with a decay so that a host
        // polling the output ports (zynthian widget: ~30 times/s) doesn't miss the peaks.
        const float decay = std::pow(fMeterDecayPerSample, static_cast<float>(frames));
        for (uint32_t m = 0; m < kMeterCount; ++m)
        {
            const float* const out = outputs[m % DISTRHO_PLUGIN_NUM_OUTPUTS];
            float peak = 0.0f;
            for (uint32_t i = 0; i < frames; ++i)
                peak = std::max(peak, std::fabs(out[i]));
            fMeterPeak[m] = std::max(peak, fMeterPeak[m] * decay);
            const ParamDef& p(kParams[kMeterParams[m]]);
            const float db = 20.0f * std::log10(std::max(fMeterPeak[m], 1e-9f));
            fValues[kMeterParams[m]] = std::max(p.min, std::min(p.max, db));
        }
#else
        (void)outputs;
        (void)frames;
#endif
        (void)inputs;
    }

private:
    float fValues[kParamCount];
    float fMeterPeak[kMeterCount > 0 ? kMeterCount : 1];
    float fMeterDecayPerSample = 0.0f;
    float fBypassMix = 0.0f;   // 0 = processed, 1 = dry input (bypassed)
    float fBypassStep = 0.0f;

    DISTRHO_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(@@CLASS@@Plugin)
};

Plugin* createPlugin()
{
    return new @@CLASS@@Plugin();
}

END_NAMESPACE_DISTRHO
