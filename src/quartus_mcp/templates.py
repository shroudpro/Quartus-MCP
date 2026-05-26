from __future__ import annotations

from dataclasses import dataclass


QUARTUS_BIN_ENV_VAR = "QUARTUS_BIN"
DEFAULT_PROJECT_NAME = "counter_demo"
DEFAULT_TOP_ENTITY = "counter_demo"
DEFAULT_FAMILY = "MAX II"
DEFAULT_DEVICE = "EPM1270T144C5"

LED_PINS = [80, 79, 78, 77, 76, 75, 74, 73, 144, 143, 142, 141, 140, 139, 138, 137]
CLK_PIN = 18
ENABLE_PIN = 134
RST_PIN = 61


@dataclass(frozen=True)
class CounterProjectFiles:
    qpf: str
    qsf: str
    vhdl: str
    vwf: str


def render_qpf(project_name: str, revision: str) -> str:
    return f"""QUARTUS_VERSION = "9.1"
DATE = ""

# Revisions

PROJECT_REVISION = "{revision}"
"""


def render_qsf(project_name: str, top_entity: str) -> str:
    lines = [
        f'set_global_assignment -name FAMILY "{DEFAULT_FAMILY}"',
        f"set_global_assignment -name DEVICE {DEFAULT_DEVICE}",
        f"set_global_assignment -name TOP_LEVEL_ENTITY {top_entity}",
        "set_global_assignment -name ORIGINAL_QUARTUS_VERSION 9.1",
        "set_global_assignment -name LAST_QUARTUS_VERSION 9.1",
        f"set_global_assignment -name VHDL_FILE {top_entity}.vhd",
        f"set_global_assignment -name VECTOR_WAVEFORM_FILE {top_entity}.vwf",
        f'set_global_assignment -name VECTOR_INPUT_SOURCE "{top_entity}.vwf"',
        "",
        f"set_location_assignment PIN_{CLK_PIN} -to clk",
        f"set_location_assignment PIN_{ENABLE_PIN} -to enable",
        f"set_location_assignment PIN_{RST_PIN} -to rst",
    ]
    for index, pin in enumerate(LED_PINS):
        lines.append(f"set_location_assignment PIN_{pin} -to led[{index}]")
    lines.append("")
    return "\n".join(lines)


def render_counter_vhdl(top_entity: str) -> str:
    return f"""library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity {top_entity} is
    port (
        clk    : in  std_logic;
        rst    : in  std_logic;
        enable : in  std_logic;
        led    : out std_logic_vector(15 downto 0)
    );
end entity;

architecture rtl of {top_entity} is
    signal count : unsigned(15 downto 0) := (others => '0');
begin
    process(clk, rst)
    begin
        if rst = '1' then
            count <= (others => '0');
        elsif rising_edge(clk) then
            if enable = '1' then
                count <= count + 1;
            end if;
        end if;
    end process;

    led <= std_logic_vector(count);
end architecture;
"""


def _signal(name: str, direction: str, signal_type: str = "SINGLE_BIT", width: int = 1, parent: str = "") -> str:
    lsb = 0 if signal_type == "BUS" else -1
    return f"""SIGNAL("{name}")
{{
\tVALUE_TYPE = NINE_LEVEL_BIT;
\tSIGNAL_TYPE = {signal_type};
\tWIDTH = {width};
\tLSB_INDEX = {lsb};
\tDIRECTION = {direction};
\tPARENT = "{parent}";
}}
"""


def _constant_transition(name: str, level: str, duration_ns: int) -> str:
    return f"""TRANSITION_LIST("{name}")
{{
\tNODE
\t{{
\t\tREPEAT = 1;
\t\tLEVEL {level} FOR {float(duration_ns):.1f};
\t}}
}}
"""


def _display_line(channel: str, tree_index: int, tree_level: int = 0, parent: int | None = None, children: list[int] | None = None) -> str:
    extra = ""
    if children:
        extra += f"\tCHILDREN = {', '.join(str(child) for child in children)};\n"
    if parent is not None:
        extra += f"\tPARENT = {parent};\n"
    return f"""DISPLAY_LINE
{{
\tCHANNEL = "{channel}";
\tEXPAND_STATUS = COLLAPSED;
\tRADIX = Binary;
\tTREE_INDEX = {tree_index};
\tTREE_LEVEL = {tree_level};
{extra}}}
"""


def render_vwf(top_entity: str, simulation_time_ns: int = 50000, grid_period_ns: int = 100) -> str:
    half_period = grid_period_ns / 2
    repeats = max(1, simulation_time_ns // grid_period_ns)
    signal_blocks = [
        _signal("clk", "INPUT"),
        _signal("rst", "INPUT"),
        _signal("enable", "INPUT"),
        _signal("led", "OUTPUT", "BUS", 16),
    ]
    signal_blocks.extend(_signal(f"led[{index}]", "OUTPUT", parent="led") for index in range(15, -1, -1))

    transition_blocks = [
        f"""TRANSITION_LIST("clk")
{{
\tNODE
\t{{
\t\tREPEAT = 1;
\t\tNODE
\t\t{{
\t\t\tREPEAT = {repeats};
\t\t\tLEVEL 0 FOR {half_period:.1f};
\t\t\tLEVEL 1 FOR {half_period:.1f};
\t\t}}
\t}}
}}
""",
        f"""TRANSITION_LIST("rst")
{{
\tNODE
\t{{
\t\tREPEAT = 1;
\t\tLEVEL 1 FOR 200.0;
\t\tLEVEL 0 FOR {max(0.0, float(simulation_time_ns) - 200.0):.1f};
\t}}
}}
""",
        f"""TRANSITION_LIST("enable")
{{
\tNODE
\t{{
\t\tREPEAT = 1;
\t\tLEVEL 0 FOR 200.0;
\t\tLEVEL 1 FOR {max(0.0, float(simulation_time_ns) - 200.0):.1f};
\t}}
}}
""",
    ]
    transition_blocks.extend(_constant_transition(f"led[{index}]", "X", simulation_time_ns) for index in range(15, -1, -1))

    display_blocks = [
        _display_line("clk", 0),
        _display_line("rst", 1),
        _display_line("enable", 2),
        _display_line("led", 3, children=list(range(4, 20))),
    ]
    display_blocks.extend(_display_line(f"led[{index}]", 19 - index, tree_level=1, parent=3) for index in range(15, -1, -1))

    return f"""/*
Generated for Quartus II 9.1 Vector Waveform simulation.
*/

HEADER
{{
\tVERSION = 1;
\tTIME_UNIT = ns;
\tSIMULATION_TIME = {float(simulation_time_ns):.1f};
\tGRID_PHASE = 0.0;
\tGRID_PERIOD = {float(grid_period_ns):.1f};
\tGRID_DUTY_CYCLE = 50;
}}

{''.join(signal_blocks)}
{''.join(transition_blocks)}
{''.join(display_blocks)}
TIME_BAR
{{
\tTIME = 0;
\tMASTER = TRUE;
}}
;
"""


def render_counter_project_files(project_name: str, top_entity: str, simulation_time_ns: int, grid_period_ns: int) -> CounterProjectFiles:
    return CounterProjectFiles(
        qpf=render_qpf(project_name, top_entity),
        qsf=render_qsf(project_name, top_entity),
        vhdl=render_counter_vhdl(top_entity),
        vwf=render_vwf(top_entity, simulation_time_ns=simulation_time_ns, grid_period_ns=grid_period_ns),
    )
