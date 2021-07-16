# Author: Botao Yu


# === Abbreviation ===
BAR_ABBR = 'b'
POS_ABBR = 'o'
TS_ABBR = 's'
TEMPO_ABBR = 't'
INST_ABBR = 'i'
PITCH_ABBR = 'p'
DURATION_ABBR = 'd'
VELOCITY_ABBR = 'v'

# === Encoding ===
ENCODINGS = ('REMI', 'TS1')
# REMI: REMI
# TS1: 只编码Bar(no idx)、position、duration、pitch信息

# === Cut Methods ===
CUT_METHODS = ('successive', 'first')

# === Defaults ===
DEFAULT_TICKS_PER_BEAT = 480
DEFAULT_TS = (4, 4)
DEFAULT_TEMPO = 120.0
DEFAULT_INST_ID = 0
DEFAULT_VELOCITY = 96
