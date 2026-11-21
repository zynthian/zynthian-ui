# @@NAME@@: specification

Living document: each decision made in the chat is written here before it's implemented.
Status of each section: TODO / AGREED / DONE (implemented and tested on a zynthian).

## Identity — @@IDENTITY_STATUS@@
- Name: @@NAME@@ · symbol: `@@SYMBOL@@` · URI: `@@URI@@`
- Maker: @@MAKER@@ · license: @@LICENSE@@ · LV2 category: @@LV2_CATEGORY@@
- Purpose: @@DESCRIPTION@@

## I/O — @@IO_STATUS@@
@@IO@@

## Controls (LV2 input ports) — TODO
Pages = port groups, 4 controls per page in zynthian. Symbols are stable API.

| Page | Symbol | Name | Range | Default | Unit | Type | Designation / notes |
|---|---|---|---|---|---|---|---|
@@CONTROLS_TABLE@@

## Outputs (LV2 output ports → widget monitors, ~30 Hz) — TODO

| Symbol | Name | Range | Unit | Meaning / how it's computed |
|---|---|---|---|---|
@@OUTPUTS_TABLE@@

## DSP — TODO
Algorithm, formulas, smoothing, latency, CPU budget.

## State & presets — TODO
None yet.

## Zynthian widget — TODO
What it shows, layout, colours, knob/switch handling (if any).

## Native GUI (X11, Cairo) — TODO
Layout, size, controls, meters.

## Help page — TODO

## Open questions
-
