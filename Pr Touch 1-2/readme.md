# K1 Load Cell Probe (`k1_load_cell_probe`)

> **Warning:** **Work in Progress (WIP)** — Experimental and not yet ready for production use.

A mainline Klipper and Kalico port of Creality's proprietary `PR-Touch` bed-leveling system.

---

### Overview

`k1_load_cell_probe` enables multi-channel **HX711** load cell support on standard Klipper, allowing Creality K1-series printers running mainline firmware to utilize the factory 4-corner bed load cells for probing and Z-homing through corner aggregation.

* **Mainline Compatible:** Replaces Creality's closed-source `prtouch_v2` module with standard Klipper probe architecture.
* **Sensor Aggregation:** Combines real-time readings from all 4 bed load cells.
* **Firmware Requirement:** Requires flashing the bed MCU (`leveling_mcu`) with standard Klipper firmware.

---

### Configuration

Add the probe module and virtual endstop to your `printer.cfg`:

```ini
[k1_load_cell_probe]
sensor_type: hx711
corner_dout_pins: leveling_mcu:PA0, leveling_mcu:PA1, leveling_mcu:PA3, leveling_mcu:PA4
corner_sclk_pins: leveling_mcu:PA2, leveling_mcu:PA5, leveling_mcu:PA6, leveling_mcu:PA7
z_offset: 0.0
speed: 2.0
samples: 3

[stepper_z]
endstop_pin: probe:z_virtual_endstop

```

---

### Pin Mapping Reference

The physical GPIOs on the `leveling_mcu` are identical to stock Creality firmware, though the corner index order is arranged differently:

| Sensor / Corner | Stock `[prtouch_v2]` | `[k1_load_cell_probe]` |
| --- | --- | --- |
| **Sensor 0** | `clk`: PA5, `sdo`: PA1 | `sclk`: PA2, `dout`: PA0 |
| **Sensor 1** | `clk`: PA2, `sdo`: PA0 | `sclk`: PA5, `dout`: PA1 |
| **Sensor 2** | `clk`: PA6, `sdo`: PA3 | `sclk`: PA6, `dout`: PA3 |
| **Sensor 3** | `clk`: PA7, `sdo`: PA4 | `sclk`: PA7, `dout`: PA4 |

* The 4 data pins (**PA0, PA1, PA3, PA4**) and 4 clock pins (**PA2, PA5, PA6, PA7**) on `leveling_mcu` interface the same physical hardware.
* Stock `pres0` and `pres1` are swapped in index order compared to the pin list in `[k1_load_cell_probe]` (`PA0/PA2` vs `PA1/PA5`).
