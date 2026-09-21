Short answer — copy these Python extras into your Klipper “extras” folder, add the matching sections to your printer.cfg, flash the Creality leveling MCU with Klipper firmware, then restart Klipper and calibrate. Below are step‑by‑step instructions and example config snippets tailored for the files you showed.

1) Prepare the Klipper extras
- On the Pi (or host running Klipper) clone or download the repo, then copy the extras into your Klippy extras directory. Example (adjust paths to your system and where you saved the repo):
  - git clone https://github.com/Mart7Mcfl7/K1maXburst ~/K1maXburst
  - mkdir -p ~/klipper/klippy/extras/prtouch_custom
  - cp ~/K1maXburst/"Pr Touch 1-2"/*.py ~/klipper/klippy/extras/prtouch_custom/
Notes:
  - Avoid leaving spaces in the extras directory name if you prefer (I used prtouch_custom above).
  - You can also symlink instead of copying (useful when testing changes).

2) Flash the leveling MCU
- The k1_load_cell_probe module expects the leveling MCU to run the Klipper MCU firmware (klipper.bin). You must build/flash Klipper firmware for that MCU (the repository header explicitly says that).
- Typical steps:
  - In your klipper repo run: make menuconfig — configure for the leveling MCU (chip, clock, interface).
  - make
  - The produced firmware (klipper.bin / firmware.hex, depending on MCU) must be flashed to the leveling MCU using the method Creality uses for the K1/K1C (SD card update or dfu/serial tooling depending on board).
- Important: identify which serial/device is the leveling MCU and use the right board target in menuconfig. If your printer.cfg already has an [mcu leveling_mcu] section, use that name/port.

3) Add sections to printer.cfg
- Add a section to enable the k1_load_cell_probe. Example minimal snippet (edit pin names to match your leveling MCU / printer):
  [k1_load_cell_probe]
  sensor_type: hx711
  # Pins listed in corner order: front-left, front-right, back-right, back-left
  corner_dout_pins: leveling_mcu:PA0, leveling_mcu:PA1, leveling_mcu:PA3, leveling_mcu:PA4
  corner_sclk_pins: leveling_mcu:PA2, leveling_mcu:PA5, leveling_mcu:PA6, leveling_mcu:PA7
  z_offset: 0.0
  speed: 2.0
  samples: 3
- Make sure you already have an [mcu leveling_mcu] section that points to the leveling MCU (serial: path or host/port), for example:
  [mcu leveling_mcu]
  serial: /dev/serial/by-id/usb-…  # replace with correct id for your leveling MCU
Notes:
  - The pin names (PA0, PA1, …) must match the MCU pin naming used in Klipper for that particular MCU; confirm them in your board/pin map.
  - The example pins above come from the file header; they may differ on K1C — verify.

4) (Optional) Install/enable prtouch wrapper
- The repo includes prtouch wrappers (prtouch.py and prtouch_v2_wrapper.py). To use the Creality prtouch logic you will typically add a section such as:
  [prtouch]
  pr_version: 2   # or 1 depending on your hardware/firmware
  # then add any pres/step swap pin names and other options required by the wrapper
- The prtouch module is large and has many config options (pins, tri_* parameters). Start with only the options required by the wrapper (pres pins, step pins) and consult the wrapper source for the exact option names (they are read from the config in prtouch_v2_wrapper.py).

5) Restart Klipper and check logs
- Restart the Klipper service so it loads extras:
  sudo service klipper restart
  or
  sudo systemctl restart klipper
- Check klippy.log (or the Klipper service logs) for errors: missing pins, invalid sections, or import failures. Typical problems:
  - Wrong pin names → "parse_pin" errors
  - MCU not present → errors about missing [mcu leveling_mcu] or cannot open serial
  - Python exceptions in modules → traceback in klippy.log

6) Calibrate the load cells
- For k1_load_cell_probe follow the header’s calibration workflow:
  - Use LOAD_CELL_CALIBRATE LOAD_CELL=<corner_label> to calibrate each corner in turn (corner_label is front_left, front_right, back_right, back_left).
  - Run TARE, place known weight close to the corner, CALIBRATE GRAMS=<value>, ACCEPT, then SAVE_CONFIG.
  - The module will read the saved per‑corner calibration on next restart.

7) Testing and safety
- Test probe operation carefully (small Z moves first).
- Use the module’s commands in the header/PRTouch wrapper (e.g., READ_PRES, TEST_PRTH) for diagnostics.
- If anything behaves unexpectedly, revert to your backup printer.cfg and klipper firmware. Always back up the original files before making changes.

Troubleshooting pointers specific to K1C
- Confirm whether K1C uses the same “leveling MCU” naming and pins as K1/K1Max. Creality variants sometimes differ in MCU type/name and pin naming.
- If you are unsure which serial corresponds to the leveling MCU, check dmesg or /dev/serial/by-id after connecting the printer, or inspect existing stock Creality Klipper configs/community K1C configs to identify the correct MCU and pins.
- If you get pin parsing errors referencing the pin like "PA0" or "PB3", the board variant in menuconfig or the MCU you compiled for may not match the real board.

If you want, I can:
- produce a ready-to-paste printer.cfg snippet tuned to your current printer.cfg (paste your printer.cfg or the current [mcu] entries and I’ll suggest exact pin/serial lines), or
- give exact commands for building/flashing firmware if you tell me which MCU chip is on your leveling board (STM32F0/STM32F1/nRF52/…).

Which would you like me to do next?
