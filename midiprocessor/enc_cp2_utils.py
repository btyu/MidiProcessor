# Author: Botao Yu
import miditoolkit

from . import const
from . import enc_basic_utils
from . import cut_utils
from . import common_funcs
from .inst_sorting import get_inst_sorting_method
from .note_sorting import get_note_sorting_method


def convert_remigen_token_to_token_str(token):
    return enc_basic_utils.convert_basic_token_to_token_str(token)


def convert_remigen_token_list_to_token_str_list(token_list):
    return enc_basic_utils.convert_basic_token_list_to_token_str_list(token_list)


def convert_token_lists_to_token_str_lists(token_lists):
    return enc_basic_utils.convert_token_lists_to_token_str_lists(token_lists)


def convert_remigen_token_str_to_token(token_str):
    return enc_basic_utils.convert_basic_token_str_to_token(token_str)


def convert_token_str_list_to_token_list(token_str_list):
    return enc_basic_utils.convert_basic_token_str_list_to_token_list(token_str_list)


def do_remove_empty_bars(encoding, group_len):
    start_idx = 0
    num_encoding = len(encoding)
    idx = 0
    while idx < num_encoding:
        if encoding[idx] == (const.FAMILY_ABBR, 1) and encoding[idx + 1] == (const.BAR_ABBR, 0):
            start_idx = idx
        elif encoding[idx] == (const.FAMILY_ABBR, 2):
            break
        idx += group_len
    idx = num_encoding - group_len
    end_idx = 0
    while idx >= 0:
        if encoding[idx] == (const.FAMILY_ABBR, 1) and encoding[idx + 1] == (const.BAR_ABBR, 1):
            end_idx = idx
        elif encoding[idx] in ((const.FAMILY_ABBR, 4), (const.FAMILY_ABBR, 3), (const.FAMILY_ABBR, 2)):
            break
        idx -= group_len
    end_idx = end_idx + group_len
    if end_idx == num_encoding:
        end_idx = None
    return encoding[start_idx: end_idx]


def convert_pos_info_id_to_token_lists(
    pos_info_id,
    remove_empty_bars=False,
    ignore_inst=False,
    add_bos_eos=True,
    sort_insts=None,
    sort_notes=None,
    **kwargs
):
    common_funcs.print_redundant_parameters(kwargs)

    encoding = []

    inst_offset = -1 if ignore_inst else 0

    max_pos = len(pos_info_id)
    cur_bar = None
    cur_ts = None
    cur_tempo = None
    for pos in range(max_pos):
        now_bar, now_ts, now_local_pos, now_tempo, now_insts_notes = pos_info_id[pos]
        # bar: every pos
        # ts: only at pos where it changes, otherwise None
        # local_pos: every pos
        # tempo: only at pos where it changes, otherwise None
        # insts_notes: only at pos where the note starts, otherwise None

        if now_ts is not None:
            cur_ts = now_ts

        cur_local_pos = now_local_pos

        if now_tempo is not None:
            cur_tempo = now_tempo

        if now_bar != cur_bar:
            if cur_bar is not None:
                encoding.extend(
                    [
                        (const.FAMILY_ABBR, 1),
                        (const.BAR_ABBR, 1),
                    ] + [(const.SPECIAL_ABBR, 0)] * (8 + inst_offset)
                )
            encoding.extend(
                [
                    (const.FAMILY_ABBR, 1),
                    (const.BAR_ABBR, 0),
                    (const.TS_ABBR, cur_ts)
                ] + [(const.SPECIAL_ABBR, 0)] * (7 + inst_offset)
            )
            cur_bar = now_bar

        if now_insts_notes is not None:
            encoding.extend(
                [
                    (const.FAMILY_ABBR, 2),
                    (const.SPECIAL_ABBR, 0),
                    (const.SPECIAL_ABBR, 0),
                    (const.TEMPO_ABBR, cur_tempo),
                    (const.POS_ABBR, cur_local_pos),
                ] + [(const.SPECIAL_ABBR, 0)] * (5 + inst_offset)
            )

            cur_insts_notes = now_insts_notes
            cur_insts = list(cur_insts_notes.keys())
            if not ignore_inst:
                sort_insts = get_inst_sorting_method(sort_insts)
                cur_insts = sort_insts(cur_insts)
            for inst in cur_insts:
                if not ignore_inst:
                    encoding.extend(
                        [
                            (const.FAMILY_ABBR, 3),
                        ] + [(const.SPECIAL_ABBR, 0)] * 4 +
                        [(const.INST_ABBR, inst)] +
                        [(const.SPECIAL_ABBR, 0)] * 4
                    )
                notes = cur_insts_notes[inst]
                sort_notes = get_note_sorting_method(sort_notes)
                notes = sort_notes(notes)
                for pitch, dur, vel in notes:
                    encoding.extend(
                        [(const.FAMILY_ABBR, 4)] + [(const.SPECIAL_ABBR, 0)] * (5 + inst_offset) +
                        [
                            (const.PITCH_NAME_ABBR, pitch % 12),
                            (const.PITCH_OCTAVE_ABBR, pitch // 12),
                            (const.DURATION_ABBR, dur),
                            (const.VELOCITY_ABBR, vel)
                        ]
                    )
    encoding.extend(
        [
            (const.FAMILY_ABBR, 1),
            (const.BAR_ABBR, 1),
        ] + [(const.SPECIAL_ABBR, 0)] * (8 + inst_offset)
    )

    if remove_empty_bars:
        encoding = do_remove_empty_bars(encoding, 10 + inst_offset)

    if add_bos_eos:
        bos = [(const.FAMILY_ABBR, 0)] + [(const.SPECIAL_ABBR, 0)] * (9 + inst_offset)
        eos = [(const.FAMILY_ABBR, 5)] + [(const.SPECIAL_ABBR, 0)] * (9 + inst_offset)
        encoding = bos + encoding + eos

    token_lists = [encoding]

    return token_lists


def remigen_check_cut_method(cut_method):
    assert cut_method in REMI_CUT_METHOD, "Cut method \"%s\" not in the supported: %s" % \
                                          (cut_method, ', '.join(REMI_CUT_METHOD))


def cut_remi_full_token_list(encoding,
                             max_encoding_length=None,
                             max_bar=None,
                             cut_method='successive',
                             max_bar_num=None,
                             remove_bar_idx=False,
                             ):
    len_encoding = len(encoding)

    direct_returns = (
        max_encoding_length is None and max_bar is None,
        max_encoding_length is not None and len_encoding <= max_encoding_length and max_bar is None,
        cut_method is None,
    )

    if any(direct_returns):
        # if remove_bar_idx:
        #     pass
        #     encoding = cut_utils.do_remove_bar_idx(encoding)
        # else:
        #     encoding = cut_utils.ensure_bar_idx(encoding, 0, const.BAR_ABBR,
        #                                         max_bar_num=max_bar_num)
        return [encoding]

    raise NotImplementedError

    remigen_check_cut_method(cut_method)

    def get_bar_offset(token_list):  # 获取第一个bar的下标
        for idx, item in enumerate(token_list):
            if item[0] == const.BAR_ABBR:
                return idx, item[1]
        return None, None

    def authorize_right(token_list, idx):  # 右边
        return token_list[idx][0] == const.BAR_ABBR

    def authorize_bar(encoding, start, pos, offset, max_bar):
        if pos < len(encoding) and encoding[pos][0] == const.BAR_ABBR:
            return encoding[pos][1] - offset <= max_bar
        pos -= 1
        while pos >= start:
            if encoding[pos][0] == const.BAR_ABBR:
                return encoding[pos][1] - offset < max_bar
            pos -= 1
        raise ValueError("No authorized bar in the encoding range.")

    if cut_method == 'successive':
        encodings = cut_utils.encoding_successive_cut(
            encoding,
            const.BAR_ABBR,
            max_length=max_encoding_length,
            max_bar=max_bar,
            get_bar_offset=get_bar_offset,
            authorize_right=authorize_right,
            authorize_bar=authorize_bar,
            len_encoding=len_encoding,
            max_bar_num=max_bar_num,
        )
    elif cut_method == 'first':
        encodings = cut_utils.encoding_successive_cut(
            encoding,
            const.BAR_ABBR,
            max_length=max_encoding_length,
            max_bar=max_bar,
            get_bar_offset=get_bar_offset,
            authorize_right=authorize_right,
            authorize_bar=authorize_bar,
            len_encoding=max_encoding_length,
            max_bar_num=max_bar_num,
        )
    else:
        raise ValueError("Cut method \"%s\" is not currently supported." % cut_method)

    if remove_bar_idx:
        encodings = [cut_utils.do_remove_bar_idx(encoding) for encoding in encodings]

    return encodings


def fix_remigen_token_list(token_list):
    token_list = token_list[:]
    return token_list


def generate_midi_obj_from_remigen_token_list(
    token_list,
    vocab_manager,
    ticks_per_beat=const.DEFAULT_TICKS_PER_BEAT,
    ts=const.DEFAULT_TS,
    tempo=const.DEFAULT_TEMPO,
    inst_id=const.DEFAULT_INST_ID,
    velocity=const.DEFAULT_VELOCITY,
):
    # Bar, Pos, Pitch, Duration

    beat_note_factor = vocab_manager.beat_note_factor
    pos_resolution = vocab_manager.pos_resolution

    cur_bar_id = 0
    cur_ts_id = None
    cur_local_pos = None
    cur_ts_pos_per_bar = beat_note_factor * pos_resolution * ts[0] // ts[1]
    cur_global_bar_pos = None
    cur_global_pos = None

    cur_pitch = None
    cur_duration = None
    cur_velocity = velocity
    cur_tempo_id = None

    max_tick = 0

    midi_obj = miditoolkit.midi.parser.MidiFile(ticks_per_beat=ticks_per_beat)
    midi_obj.instruments = [
        miditoolkit.containers.Instrument(program=(0 if i == 128 else i), is_drum=(i == 128), name=str(i))
        for i in range(128 + 1)
    ]

    cur_inst_id = inst_id
    cur_inst = midi_obj.instruments[inst_id]

    len_token_list = len(token_list)
    assert len_token_list % 10 == 0
    seq_len = len_token_list // 10

    for idx in range(seq_len):
        super_token = token_list[idx * 10: (idx + 1) * 10]
        family_token = super_token[0]
        if family_token in (('f', 0), ('f', 5)):
            continue
        if family_token == ('f', 1):
            now_bar_token, now_ts_token = super_token[1: 3]
            if now_bar_token == ('b', 0):
                cur_bar_id += 1
                cur_local_pos = None
                if cur_global_bar_pos is None:
                    cur_global_bar_pos = 0
                else:
                    cur_global_bar_pos += cur_ts_pos_per_bar
                cur_global_pos = cur_global_bar_pos

                now_ts_id = now_ts_token[1]
                if now_ts_id != cur_ts_id:
                    cur_ts_id = now_ts_id
                    cur_ts = vocab_manager.convert_id_to_ts(cur_ts_id)
                    cur_ts_pos_per_bar = beat_note_factor * pos_resolution * cur_ts[0] // cur_ts[1]
                    midi_obj.time_signature_changes.append(
                        miditoolkit.containers.TimeSignature(
                            numerator=cur_ts[0], denominator=cur_ts[1],
                            time=vocab_manager.pos_to_time(cur_global_bar_pos, ticks_per_beat,
                                                           pos_resolution=pos_resolution)
                        )
                    )
        elif family_token == ('f', 2):
            now_tempo_token, now_pos_token = super_token[3: 5]
            now_tempo_id = now_tempo_token[1]
            now_pos_id = now_pos_token[1]
            if now_pos_id != cur_local_pos:
                cur_local_pos = now_pos_id
                cur_global_pos = cur_global_bar_pos + cur_local_pos

                if cur_tempo_id != now_tempo_id:
                    cur_tempo_id = now_tempo_id
                    cur_tempo = vocab_manager.convert_id_to_tempo(cur_tempo_id)
                    midi_obj.tempo_changes.append(
                        miditoolkit.containers.TempoChange(
                            cur_tempo,
                            time=vocab_manager.pos_to_time(cur_global_pos, ticks_per_beat,
                                                           pos_resolution=pos_resolution))
                    )
        elif family_token == ('f', 3):
            now_inst_token = super_token[5]
            now_inst_id = now_inst_token[1]
            cur_inst_id = now_inst_id
            cur_inst = midi_obj.instruments[cur_inst_id]
        elif family_token == ('f', 4):
            cur_name_token, cur_octave_token, cur_duration_token, cur_velocity_token = super_token[6: 11]
            cur_name_id = cur_name_token[1]
            cur_octave_id = cur_octave_token[1]
            cur_duration_id = cur_duration_token[1]
            cur_velocity_id = cur_velocity_token[1]
            cur_pitch_id = cur_name_id + cur_octave_id * 12
            cur_pitch = vocab_manager.convert_id_to_pitch(cur_pitch_id)
            cur_duration = vocab_manager.convert_id_to_dur(cur_duration_id, min_pos=None)
            if cur_duration == 0:
                cur_duration = int(8 * ticks_per_beat / 480)
            cur_velocity = vocab_manager.convert_id_to_vel(cur_velocity_id)
            start_pos = cur_global_pos
            end_pos = start_pos + cur_duration
            start_time = vocab_manager.pos_to_time(start_pos, ticks_per_beat, pos_resolution=pos_resolution)
            end_time = vocab_manager.pos_to_time(end_pos, ticks_per_beat, pos_resolution=pos_resolution)
            max_tick = max(end_time, max_tick)
            cur_inst.notes.append(
                miditoolkit.containers.Note(start=start_time, end=end_time, pitch=cur_pitch, velocity=cur_velocity)
            )
        else:
            raise ValueError(family_token)

    midi_obj.max_tick = max_tick

    midi_obj.instruments = [i for i in midi_obj.instruments if len(i.notes) > 0]

    return midi_obj
