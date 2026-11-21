/*
 * @@NAME@@ - native GUI (DPF / DGL, Cairo backend, X11UI)
 *
 * Generic GUI: one row per parameter. Controls: drag or scroll the bar, click toggles.
 * Outputs are drawn as meters. Replace with the GUI designed in SPEC.md.
 *
 * Copyright (C) @@YEAR@@ @@MAKER@@
 * License: @@LICENSE@@
 */

#include "DistrhoUI.hpp"
#include "ParamDefs.hpp"

#include <cmath>
#include <cstdio>

START_NAMESPACE_DISTRHO

using DGL_NAMESPACE::CairoGraphicsContext;

class @@CLASS@@UI : public UI
{
public:
    @@CLASS@@UI()
        : UI(DISTRHO_UI_DEFAULT_WIDTH, DISTRHO_UI_DEFAULT_HEIGHT),
          fDragging(-1)
    {
        for (uint32_t i = 0; i < kParamCount; ++i)
            fValues[i] = kParams[i].def;
        setGeometryConstraints(DISTRHO_UI_DEFAULT_WIDTH / 2, DISTRHO_UI_DEFAULT_HEIGHT / 2, false);
    }

protected:
    // ----------------------------------------------------------------------------------------------------------------
    // Host -> UI (inputs and outputs)

    void parameterChanged(const uint32_t index, const float value) override
    {
        if (index >= kParamCount || fValues[index] == value)
            return;
        fValues[index] = value;
        repaint();
    }

    // ----------------------------------------------------------------------------------------------------------------
    // Drawing

    void onCairoDisplay(const CairoGraphicsContext& context) override
    {
        cairo_t* const cr = context.handle;
        const double w = getWidth();
        const double rh = rowHeight();
        const double x0 = w * 0.36, x1 = w * 0.78;

        cairo_set_source_rgb(cr, 0.08, 0.09, 0.11);
        cairo_paint(cr);

        cairo_select_font_face(cr, "sans-serif", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD);
        cairo_set_font_size(cr, rh * 0.55);
        cairo_set_source_rgb(cr, 0.92, 0.92, 0.92);
        cairo_move_to(cr, kMargin, rh * 0.75);
        cairo_show_text(cr, DISTRHO_PLUGIN_NAME);

        cairo_select_font_face(cr, "sans-serif", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
        cairo_set_font_size(cr, rh * 0.42);

        char text[64];
        for (uint32_t i = 0; i < kParamCount; ++i)
        {
            const ParamDef& p(kParams[i]);
            const bool output = (p.hints & kParameterIsOutput) != 0;
            const double y = rh * (i + 1);

            cairo_set_source_rgb(cr, 0.80, 0.80, 0.80);
            cairo_move_to(cr, kMargin, y + rh * 0.65);
            cairo_show_text(cr, p.name);

            // Bar background + value
            const double by = y + rh * 0.2, bh = rh * 0.6;
            cairo_set_source_rgb(cr, 0.20, 0.21, 0.24);
            cairo_rectangle(cr, x0, by, x1 - x0, bh);
            cairo_fill(cr);
            if (output)
                cairo_set_source_rgb(cr, 0.20, 0.75, 0.35);
            else
                cairo_set_source_rgb(cr, 0.95, 0.55, 0.15);
            cairo_rectangle(cr, x0, by, (x1 - x0) * normalized(i, fValues[i]), bh);
            cairo_fill(cr);

            formatValue(i, text, sizeof(text));
            cairo_set_source_rgb(cr, 0.92, 0.92, 0.92);
            cairo_move_to(cr, x1 + kMargin, y + rh * 0.65);
            cairo_show_text(cr, text);
        }
    }

    // ----------------------------------------------------------------------------------------------------------------
    // Input

    bool onMouse(const MouseEvent& ev) override
    {
        if (ev.button != 1)
            return false;
        if (! ev.press)
        {
            if (fDragging < 0)
                return false;
            editParameter(fDragging, false);
            fDragging = -1;
            return true;
        }
        const int index = rowAt(ev.pos.getY());
        if (index < 0 || (kParams[index].hints & kParameterIsOutput) != 0)
            return false;
        const ParamDef& p(kParams[index]);
        if ((p.hints & kParameterIsBoolean) != 0)
        {
            editParameter(index, true);
            setValue(index, fValues[index] > (p.min + p.max) / 2 ? p.min : p.max);
            editParameter(index, false);
            return true;
        }
        fDragging = index;
        editParameter(index, true);
        setFromX(index, ev.pos.getX());
        return true;
    }

    bool onMotion(const MotionEvent& ev) override
    {
        if (fDragging < 0)
            return false;
        setFromX(fDragging, ev.pos.getX());
        return true;
    }

    bool onScroll(const ScrollEvent& ev) override
    {
        const int index = rowAt(ev.pos.getY());
        if (index < 0 || (kParams[index].hints & kParameterIsOutput) != 0)
            return false;
        const ParamDef& p(kParams[index]);
        const bool stepped = (p.hints & (kParameterIsInteger | kParameterIsBoolean)) != 0 || p.enumCount > 0;
        const float step = stepped ? 1.0f : (p.max - p.min) / 100.0f;
        editParameter(index, true);
        setValue(index, fValues[index] + (ev.delta.getY() > 0 ? step : -step));
        editParameter(index, false);
        return true;
    }

private:
    static constexpr double kMargin = 8.0;
    float fValues[kParamCount];
    int fDragging;

    double rowHeight() const
    {
        return std::fmin(40.0, getHeight() / static_cast<double>(kParamCount + 1));
    }

    int rowAt(const double y) const
    {
        const int row = static_cast<int>(y / rowHeight()) - 1;
        return row >= 0 && row < static_cast<int>(kParamCount) ? row : -1;
    }

    bool isLog(const uint32_t index) const
    {
        const ParamDef& p(kParams[index]);
        return (p.hints & kParameterIsLogarithmic) != 0 && p.min > 0.0f;
    }

    double normalized(const uint32_t index, const float value) const
    {
        const ParamDef& p(kParams[index]);
        double n = isLog(index) ? std::log(value / p.min) / std::log(p.max / p.min)
                                : (value - p.min) / (p.max - p.min);
        return std::fmin(1.0, std::fmax(0.0, n));
    }

    void setFromX(const uint32_t index, const double x)
    {
        const ParamDef& p(kParams[index]);
        const double w = getWidth(), x0 = w * 0.36, x1 = w * 0.78;
        const double n = std::fmin(1.0, std::fmax(0.0, (x - x0) / (x1 - x0)));
        const double v = isLog(index) ? p.min * std::pow(p.max / p.min, n) : p.min + n * (p.max - p.min);
        setValue(index, static_cast<float>(v));
    }

    void setValue(const uint32_t index, float value)
    {
        const ParamDef& p(kParams[index]);
        value = std::fmax(p.min, std::fmin(p.max, value));
        if ((p.hints & (kParameterIsInteger | kParameterIsBoolean)) != 0 || p.enumCount > 0)
            value = std::round(value);
        if (value == fValues[index])
            return;
        fValues[index] = value;
        setParameterValue(index, value);
        repaint();
    }

    void formatValue(const uint32_t index, char* const text, const size_t size) const
    {
        const ParamDef& p(kParams[index]);
        const float v = fValues[index];
        if (p.enumCount > 0)
        {
            const int e = static_cast<int>(std::round(v - p.min));
            std::snprintf(text, size, "%s", e >= 0 && e < static_cast<int>(p.enumCount) ? p.enumLabels[e] : "?");
        }
        else if ((p.hints & kParameterIsBoolean) != 0)
            std::snprintf(text, size, "%s", v > (p.min + p.max) / 2 ? "On" : "Off");
        else if ((p.hints & kParameterIsInteger) != 0)
            std::snprintf(text, size, "%d %s", static_cast<int>(std::round(v)), p.unit);
        else
            std::snprintf(text, size, "%.2f %s", v, p.unit);
    }

    DISTRHO_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(@@CLASS@@UI)
};

UI* createUI()
{
    return new @@CLASS@@UI();
}

END_NAMESPACE_DISTRHO
