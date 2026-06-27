# K1/K1Max 4-corner independent load cell probe for mainline Klipper
#
# Copyright (C) 2026
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Drop this file into your Klipper extras directory
# (e.g. ~/klipper/klippy/extras/) alongside the standard Klipper files.
#
# ── What this does ────────────────────────────────────────────────────────────
# Uses all 4 HX711 sensors on the K1 leveling MCU independently instead of
# wiring them in parallel.  At each probe point the closest corner sensor is
# selected automatically, giving the strongest signal and best accuracy.
#
# ── Hardware requirement ──────────────────────────────────────────────────────
# Flash the leveling MCU with standard Klipper MCU firmware (klipper.bin).
# The stock wiring already has each HX711 on its own CLK/DOUT pin pair,
# so no re-soldering is needed.
#
# ── Minimal printer.cfg ───────────────────────────────────────────────────────
#
#   [k1_load_cell_probe]
#   sensor_type: hx711
#   # Pins listed in corner order: front-left, front-right, back-right, back-left
#   corner_dout_pins: leveling_mcu:PA0, leveling_mcu:PA1, leveling_mcu:PA3, leveling_mcu:PA4
#   corner_sclk_pins: leveling_mcu:PA2, leveling_mcu:PA5, leveling_mcu:PA6, leveling_mcu:PA7
#   z_offset: 0.0
#   speed: 2.0
#   samples: 3
#
#   [stepper_z]
#   endstop_pin: probe:z_virtual_endstop
#
# ── Calibration ───────────────────────────────────────────────────────────────
# Calibrate each corner in turn (see Klipper load_cell docs for TARE /
# CALIBRATE commands).  After ACCEPT, SAVE_CONFIG writes calibration into
# a [k1_load_cell_probe <label>] subsection which this module reads back
# automatically on the next restart.
#
#   LOAD_CELL_CALIBRATE LOAD_CELL=front_left
#   TARE
#   # place a known weight on the bed near that corner, then:
#   CALIBRATE GRAMS=1000
#   ACCEPT
#   SAVE_CONFIG
#
# Repeat for front_right, back_right, back_left.
#
# ── Corner layout (looking down at the bed) ───────────────────────────────────
#   back_left (3) ──── back_right (2)
#        |                   |
#   front_left (0) ── front_right (1)
#
# Corner positions are inferred automatically from [bed_mesh] mesh_min/max.

import math
import logging
from . import hx71x, load_cell, trigger_analog, probe, manual_probe

FRAC_GRAMS_CONV = 32768.0
NUM_CORNERS = 4
CORNER_LABELS = ['front_left', 'front_right', 'back_right', 'back_left']


# ── Config wrapper ─────────────────────────────────────────────────────────────

class _CornerConfig:
    """Wraps the [k1_load_cell_probe] config, overriding per-corner values.

    Each corner needs different dout/sclk pins and its own calibration values.
    Everything else (sample_rate, gain, trigger_force …) is shared and falls
    through to the base config unchanged.
    """
    def __init__(self, base, idx, dout_pin, sclk_pin,
                 counts_per_gram, reference_tare_counts):
        self._base = base
        self._name = '%s %s' % (base.get_name(), CORNER_LABELS[idx])
        # String overrides (pin names)
        self._str_ov = {'dout_pin': dout_pin, 'sclk_pin': sclk_pin}
        # Always override calibration keys even when value is None, so that
        # the comma-separated list form in the base section is never misread
        # by LoadCell as a single-sensor value.
        self._float_ov = {'counts_per_gram': counts_per_gram}
        self._int_ov = {
            'reference_tare_counts': (
                int(reference_tare_counts)
                if reference_tare_counts is not None else None)
        }

    # ── Config interface ──────────────────────────────────────────────────────

    def get_name(self):
        return self._name

    def error(self, msg):
        return self._base.error(msg)

    def get_printer(self):
        return self._base.get_printer()

    def get(self, name, default=None):
        if name in self._str_ov:
            return self._str_ov[name]
        return self._base.get(name, default)

    def getfloat(self, name, default=None, minval=None, maxval=None,
                 above=None, below=None):
        if name in self._float_ov:
            return self._float_ov[name]
        return self._base.getfloat(name, default, minval=minval,
                                    maxval=maxval, above=above, below=below)

    def getint(self, name, default=None, minval=None, maxval=None):
        if name in self._int_ov:
            return self._int_ov[name]
        return self._base.getint(name, default, minval=minval, maxval=maxval)

    def getboolean(self, name, default=None):
        return self._base.getboolean(name, default)

    def getchoice(self, name, choices, default=None):
        return self._base.getchoice(name, choices, default)

    def getfloatlist(self, name, default=None, sep=',', count=None):
        return self._base.getfloatlist(name, default, sep=sep, count=count)

    def get_prefix_sections(self, prefix):
        return self._base.get_prefix_sections(prefix)

    def getsection(self, section):
        return self._base.getsection(section)

    def has_section(self, section):
        return self._base.has_section(section)


# ── Per-corner sensor stack ────────────────────────────────────────────────────

class _K1CornerSensor:
    """One bed corner: HX711 → LoadCell → MCU trigger_analog.

    All MCU OID allocation and config callbacks are registered here during
    Klipper's config phase so the MCU firmware is properly programmed at
    startup.
    """
    def __init__(self, base_config, idx, dout_pin, sclk_pin,
                 counts_per_gram, reference_tare_counts, sensor_class):
        self._printer = base_config.get_printer()
        self._idx = idx

        cfg = _CornerConfig(base_config, idx, dout_pin, sclk_pin,
                            counts_per_gram, reference_tare_counts)

        # Sensor (HX711 chip)
        self._sensor = sensor_class(cfg)

        # Host-side load cell wrapper (handles calibration, unit conversion,
        # and the LOAD_CELL_* GCode commands for this corner)
        self._load_cell = load_cell.LoadCell(cfg, self._sensor)

        # MCU-side trigger_analog: SOS filter + threshold detection.
        # _build_config() runs during MCU config phase and calls
        # sensor.setup_trigger_analog() automatically.
        mcu = self._sensor.get_mcu()
        self._mcu_trigger = trigger_analog.MCU_trigger_analog(self._sensor)
        cq = self._mcu_trigger.get_dispatch().get_command_queue()
        sos = trigger_analog.MCU_SosFilter(mcu, cq, 4)
        self._mcu_trigger.setup_sos_filter(sos)

        # Tell this corner's trigger which Z steppers to halt on contact
        probe.LookupZSteppers(
            base_config, self._mcu_trigger.get_dispatch().add_stepper)

    # ── Public interface ──────────────────────────────────────────────────────

    def is_calibrated(self):
        return self._load_cell.is_calibrated()

    def get_load_cell(self):
        return self._load_cell

    def get_mcu_trigger(self):
        return self._mcu_trigger

    def label(self):
        return CORNER_LABELS[self._idx]

    def tare_and_arm(self, trigger_force_g, safety_limit_g, tare_n):
        """Collect a baseline, tare the sensor, and arm the MCU trigger.

        Must be called immediately before each probing move while the
        toolhead is stationary at the probe XY position.
        """
        lc = self._load_cell
        if not lc.is_calibrated():
            raise self._printer.command_error(
                "K1 load cell corner %d (%s) is not calibrated.\n"
                "Run: LOAD_CELL_CALIBRATE LOAD_CELL=%s"
                % (self._idx, CORNER_LABELS[self._idx],
                   CORNER_LABELS[self._idx]))

        # Collect tare baseline (blocks until tare_n samples arrive)
        collector = lc.get_collector()
        samples, errors = collector.collect_min(tare_n)
        if errors:
            raise self._printer.command_error(
                "Corner %d (%s) sensor errors during tare: "
                "%d errors, %d overflows"
                % (self._idx, CORNER_LABELS[self._idx],
                   errors[0], errors[1]))
        tare_counts = float(sum(s[2] for s in samples)) / len(samples)
        lc.tare(tare_counts)

        # Safety window: stop homing if raw counts stray too far from tare
        cpg = lc.get_counts_per_gram()
        ref = lc.get_reference_tare_counts()
        safety_c = int(cpg * safety_limit_g)
        s_min, s_max = lc.get_sensor().get_range()
        self._mcu_trigger.set_raw_range(
            max(s_min + 1, int(ref - safety_c)),
            min(s_max - 1, int(ref + safety_c)))

        # SOS filter: shift by tare offset, scale raw counts → fractional grams
        sos = self._mcu_trigger.get_sos_filter()
        sos.set_offset_scale(int(-tare_counts), (1.0 / cpg) * FRAC_GRAMS_CONV)

        # Trigger threshold in fractional gram units
        self._mcu_trigger.set_trigger(
            "abs_ge", int(trigger_force_g * FRAC_GRAMS_CONV))


# ── Inner probe session ────────────────────────────────────────────────────────

class _K1ProbeSession:
    """Executes one tap (tare → probe move) per run_probe() call.

    SampleAveragingHelper wraps this and handles multi-sample logic,
    tolerance checking, and retracts between samples.
    """
    def __init__(self, printer, k1_probe):
        self._printer = printer
        self._k1 = k1_probe
        self._result = None

    def end_probe_session(self):
        self._result = None

    def run_probe(self, gcmd):
        toolhead = self._printer.lookup_object('toolhead')
        curpos = toolhead.get_position()

        # Select the corner sensor closest to the current XY position
        corner = self._k1._select_corner(curpos[0], curpos[1])

        # Tare and arm while stationary
        corner.tare_and_arm(
            self._k1._trigger_force,
            self._k1._safety_limit,
            self._k1._tare_n)

        # Descend until the MCU trigger fires
        probe_pos = list(curpos)
        probe_pos[2] = self._k1._z_min
        speed = self._k1._param_helper.get_probe_params(gcmd)['probe_speed']
        phoming = self._printer.lookup_object('homing')
        epos = phoming.probing_move(corner.get_mcu_trigger(), probe_pos, speed)

        offsets = self._k1._offsets.get_offsets()
        self._result = manual_probe.create_probe_result(epos, offsets)

    def pull_probed_results(self):
        res = [self._result]
        self._result = None
        return res


# ── Main probe object ──────────────────────────────────────────────────────────

class K1LoadCellProbe:
    """4-corner independent load cell probe for Creality K1/K1Max.

    Replaces the standard [probe] object and provides:
      • probe:z_virtual_endstop for G28 Z homing
      • PROBE, PROBE_ACCURACY, PROBE_CALIBRATE commands
      • Full BED_MESH_CALIBRATE support
      • Per-corner calibration via LOAD_CELL_CALIBRATE
    """
    def __init__(self, config):
        self._printer = config.get_printer()

        # Resolve sensor class (hx711, hx717, …)
        sensor_types = {}
        sensor_types.update(hx71x.HX71X_SENSOR_TYPES)
        sensor_class = config.getchoice('sensor_type', sensor_types)

        # Parse comma-separated pin lists (must have exactly 4 entries each)
        dout_pins = [p.strip()
                     for p in config.get('corner_dout_pins').split(',')]
        sclk_pins = [p.strip()
                     for p in config.get('corner_sclk_pins').split(',')]
        for key, lst in [('corner_dout_pins', dout_pins),
                          ('corner_sclk_pins', sclk_pins)]:
            if len(lst) != NUM_CORNERS:
                raise config.error(
                    "%s: '%s' must have exactly %d comma-separated values"
                    % (config.get_name(), key, NUM_CORNERS))

        # Per-corner calibration.  Values come from either:
        #   (a) [k1_load_cell_probe <label>] subsections written by SAVE_CONFIG
        #       after running LOAD_CELL_CALIBRATE for each corner, or
        #   (b) left as None (corner reports "not calibrated" until calibrated)
        cpg_list = [None] * NUM_CORNERS   # counts_per_gram
        rtc_list = [None] * NUM_CORNERS   # reference_tare_counts
        for i, label in enumerate(CORNER_LABELS):
            sub_name = '%s %s' % (config.get_name(), label)
            if config.has_section(sub_name):
                sub = config.getsection(sub_name)
                cpg_list[i] = sub.getfloat('counts_per_gram',
                                            default=None,
                                            minval=load_cell.MIN_COUNTS_PER_GRAM)
                rtc_list[i] = sub.getint('reference_tare_counts', default=None)

        # Probe behaviour config
        self._trigger_force = config.getfloat(
            'trigger_force', 75.0, minval=10., maxval=250.)
        self._safety_limit = config.getfloat(
            'force_safety_limit', 2000., minval=100., maxval=5000.)
        self._tare_time = config.getfloat(
            'tare_time', 4. / 60., minval=0.01, maxval=1.0)
        self._z_min = probe.lookup_minimum_z(config)

        # Corner XY positions: set at klippy:ready from bed_mesh mesh_min/max
        self._corner_xy = None
        self._tare_n = 2   # updated at klippy:ready once SPS is known

        # ── Build 4 corner stacks during config phase ─────────────────────────
        # MCU OID allocation and config callbacks must happen here, before the
        # MCU connects.
        self._corners = []
        for i in range(NUM_CORNERS):
            self._corners.append(
                _K1CornerSensor(config, i,
                                dout_pins[i], sclk_pins[i],
                                cpg_list[i], rtc_list[i],
                                sensor_class))

        # ── Standard Klipper probe integration ────────────────────────────────
        self._param_helper = probe.ProbeParameterHelper(config)
        self._offsets = probe.ProbeOffsetsHelper(config)
        self._cmd_helper = probe.ProbeCommandHelper(config, self)
        # SampleAveragingHelper handles multi-sample, tolerance, and retract
        self._avg_helper = probe.SampleAveragingHelper(
            config, self._param_helper, self._new_session)
        # Register probe:z_virtual_endstop so stepper_z endstop_pin works
        probe.HomingViaProbeHelper(config, self._offsets.get_offsets()[2])
        self._printer.add_object('probe', self)
        self._printer.register_event_handler(
            "klippy:ready", self._handle_ready)

    def _handle_ready(self):
        # Determine corner XY positions from bed_mesh limits
        bed_mesh = self._printer.lookup_object('bed_mesh', None)
        if bed_mesh is not None:
            min_x, min_y = bed_mesh.bmc.mesh_min
            max_x, max_y = bed_mesh.bmc.mesh_max
        else:
            # Fallback: use toolhead kinematic axis limits
            toolhead = self._printer.lookup_object('toolhead')
            kin_status = toolhead.get_kinematics().get_status(
                self._printer.get_reactor().monotonic())
            rng = kin_status.get('axis_minimum', [0, 0, 0]), \
                  kin_status.get('axis_maximum', [300, 300, 300])
            min_x, min_y = rng[0][0], rng[0][1]
            max_x, max_y = rng[1][0], rng[1][1]
            logging.warning(
                "k1_load_cell_probe: [bed_mesh] not found. "
                "Corner positions will be approximate. "
                "Configure [bed_mesh] for best accuracy.")

        # Corner order: front-left, front-right, back-right, back-left
        self._corner_xy = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
        ]

        # Tare sample count: enough samples to span ~4 AC power cycles
        sps = (self._corners[0]
               .get_load_cell().sensor.get_samples_per_second())
        self._tare_n = max(2, int(math.ceil(self._tare_time * sps)))

        cal_status = [
            '%s: %s' % (c.label(), 'OK' if c.is_calibrated() else 'NOT CALIBRATED')
            for c in self._corners
        ]
        logging.info(
            "k1_load_cell_probe ready | corners=%s | tare_n=%d | %s"
            % (self._corner_xy, self._tare_n, ', '.join(cal_status)))

    def _select_corner(self, x, y):
        if self._corner_xy is None:
            raise self._printer.command_error(
                "k1_load_cell_probe: printer not ready. "
                "Ensure [bed_mesh] is configured.")
        idx = min(range(NUM_CORNERS),
                  key=lambda i: math.hypot(
                      x - self._corner_xy[i][0],
                      y - self._corner_xy[i][1]))
        logging.debug(
            "k1_load_cell_probe: (%.1f, %.1f) → corner %d (%s)"
            % (x, y, idx, CORNER_LABELS[idx]))
        return self._corners[idx]

    def _new_session(self, gcmd):
        return _K1ProbeSession(self._printer, self)

    # ── Klipper probe interface ───────────────────────────────────────────────

    def get_offsets(self, gcmd=None):
        return self._offsets.get_offsets(gcmd)

    def get_probe_params(self, gcmd=None):
        return self._param_helper.get_probe_params(gcmd)

    def start_probe_session(self, gcmd):
        return self._avg_helper.start_probe_session(gcmd)

    def get_status(self, eventtime):
        return self._cmd_helper.get_status(eventtime)


# ── Config loading ─────────────────────────────────────────────────────────────

def load_config(config):
    return K1LoadCellProbe(config)

def load_config_prefix(config):
    # Handles [k1_load_cell_probe <label>] subsections that SAVE_CONFIG
    # creates when LOAD_CELL_CALIBRATE / ACCEPT is run for each corner.
    # The parent K1LoadCellProbe reads these via config.getsection().
    # This function just satisfies Klipper's config system so the sections
    # don't produce "unknown section" warnings.
    return _K1CalibrationSection(config)

class _K1CalibrationSection:
    """Minimal printer object for per-corner calibration subsections."""
    def __init__(self, config):
        # Acknowledge these keys so Klipper doesn't warn about them
        config.getfloat('counts_per_gram', default=None,
                        minval=load_cell.MIN_COUNTS_PER_GRAM)
        config.getint('reference_tare_counts', default=None)

    def get_status(self, eventtime):
        return {}
