# Author: Botao Yu
import miditoolkit

from . import const
from . import enc_basic_utils
from . import cut_utils

REMI_CUT_METHOD = ('successive', 'cut')

INST_TYPE_MAPPING = {
    (0, 8): 2,  # Piano
    (8, 16): 13,  # Chromatic Percussion
    (16, 24): 7,  # Organ
    (24, 32): 3,  # Guitar
    (32, 40): 1,  # Bass
    (40, 48): 5,  # String
    (48, 56): 6,  # Ensemble
    (56, 64): 9,  # Brass
    (64, 72): 8,  # Reed
    (72, 80): 10,  # Pipe
    (80, 88): 11,  # Synth Lead
    (88, 96): 12,  # Synth Pad
    (96, 104): 15,  # Synth Effect
    (104, 112): 4,  # Ethnic
    (112, 120): 14,  # Percussive
    (120, 128): 16,  # Sound Effects
    (128, 129): 0,  # Percussion
}


def convert_remigen_token_to_token_str(token):
    return enc_basic_utils.convert_basic_token_to_token_str(token)


def convert_remigen_token_list_to_token_str_list(token_list):
    return enc_basic_utils.convert_basic_token_list_to_token_str_list(token_list)


def convert_remigen_token_lists_to_token_str_lists(token_lists):
    return enc_basic_utils.convert_token_lists_to_token_str_lists(token_lists)


def convert_remigen_token_str_to_token(token_str):
    return enc_basic_utils.convert_basic_token_str_to_token(token_str)


def convert_remigen_token_str_list_to_token_list(token_str_list):
    return enc_basic_utils.convert_basic_token_str_list_to_token_list(token_str_list)


def convert_pos_info_to_remigen_token_lists(pos_info_id,

                                            max_encoding_length=None,
                                            max_bar=None,

                                            cut_method='successive',

                                            max_bar_num=None,
                                            remove_bar_idx=False,
                                            remove_empty_bars=False,

                                            ignore_insts=False,
                                            ignore_ts=False,
                                            only_one_ts_at_beginning=False
                                            ):
    # bar, ts, pos, pitch, duration

    encoding = []

    one_ts = None
    start_to_have_note = False

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

        cur_local_pos = now_local_pos

        if cur_bar != now_bar:
            if cur_bar is not None:
                encoding.append((const.BAR_ABBR, 1))  # bar
            cur_bar = now_bar

            if now_ts is not None and cur_ts != now_ts:
                cur_ts = now_ts
                assert cur_ts is not None

                if only_one_ts_at_beginning:
                    if one_ts is None:
                        one_ts = cur_ts
                    else:
                        if start_to_have_note and not remove_empty_bars:
                            assert one_ts == cur_ts, (one_ts, cur_ts)

            if not ignore_ts and not only_one_ts_at_beginning:
                encoding.append((const.TS_ABBR, cur_ts))  # ts

        add_pos = False
        if now_insts_notes is not None:
            add_pos = True
        if now_tempo is not None and cur_tempo != now_tempo:
            cur_tempo = now_tempo
            # add_pos = True

        if add_pos:
            encoding.append((const.POS_ABBR, cur_local_pos))  # local pos
            encoding.append((const.TEMPO_ABBR, cur_tempo))  # tempo

        if now_insts_notes is not None:
            cur_insts_notes = now_insts_notes

            def get_type_group_id(x):
                for r in INST_TYPE_MAPPING:
                    if x in range(*r):
                        return INST_TYPE_MAPPING[r], x
                raise ValueError(x)
            insts_ids = sorted(list(cur_insts_notes.keys()), key=get_type_group_id)

            if ignore_insts:
                inst_notes = []
                for inst_id in insts_ids:
                    inst_notes.extend(cur_insts_notes[inst_id])
                inst_notes = sorted(inst_notes)
                for pitch, duration, velocity in inst_notes:
                    encoding.append((const.PITCH_ABBR, pitch))  # pitch
                    encoding.append((const.DURATION_ABBR, duration))  # duration
                    encoding.append((const.VELOCITY_ABBR, velocity))  # velocity
            else:
                for inst_id in insts_ids:
                    encoding.append((const.INST_ABBR, inst_id))  # inst
                    inst_notes = sorted(cur_insts_notes[inst_id])
                    for pitch, duration, velocity in inst_notes:
                        encoding.append((const.PITCH_ABBR, pitch))  # pitch
                        encoding.append((const.DURATION_ABBR, duration))  # duration
                        encoding.append((const.VELOCITY_ABBR, velocity))  # velocity

    encoding.append((const.BAR_ABBR, 1))  # bar

    if remove_empty_bars:
        encoding = do_remove_empty_bars(encoding, ignore_ts=ignore_ts or only_one_ts_at_beginning)

    if only_one_ts_at_beginning:
        encoding.insert(0, (const.TS_ABBR, cur_ts))

    token_lists = cut_remi_full_token_list(encoding,
                                           max_encoding_length=max_encoding_length,
                                           max_bar=max_bar,
                                           cut_method=cut_method,
                                           max_bar_num=max_bar_num,
                                           remove_bar_idx=remove_bar_idx,
                                           )

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


def do_remove_empty_bars(encoding, ignore_ts=False):
    len_encoding = len(encoding)
    valid_start = None
    valid_end = len_encoding
    for idx in range(len_encoding):
        tag_abbr = encoding[idx][0]
        if tag_abbr == (const.POS_ABBR if ignore_ts else const.TS_ABBR):
            valid_start = idx
        elif tag_abbr in (const.INST_ABBR,
                          const.PITCH_ABBR, const.DURATION_ABBR, const.VELOCITY_ABBR):
            break
    for idx in range(len_encoding - 1, -1, -1):
        tag_abbr = encoding[idx][0]
        if tag_abbr in (const.VELOCITY_ABBR, const.DURATION_ABBR, const.PITCH_ABBR,
                        const.INST_ABBR):
            break
        elif tag_abbr == const.BAR_ABBR:
            valid_end = idx + 1

    assert valid_start is not None
    assert valid_start < valid_end
    # print(valid_start, valid_end)
    # input()

    encoding = encoding[valid_start: valid_end]

    return encoding


def fix_remigen_token_list(token_list):
    token_list = token_list[:]
    return token_list


def generate_midi_obj_from_remigen_token_list(token_list,
                                              vocab_manager,
                                              ticks_per_beat=const.DEFAULT_TICKS_PER_BEAT,
                                              ts=const.DEFAULT_TS,
                                              tempo=const.DEFAULT_TEMPO,
                                              inst_id=const.DEFAULT_INST_ID,
                                              velocity=const.DEFAULT_VELOCITY,
                                              ):  # Todo: 增加TS
    # Bar, Pos, Pitch, Duration

    beat_note_factor = vocab_manager.beat_note_factor
    pos_resolution = vocab_manager.pos_resolution

    cur_bar_id = 0
    cur_ts_id = None
    cur_local_pos = None
    cur_ts_pos_per_bar = beat_note_factor * pos_resolution * ts[0] // ts[1]
    cur_global_bar_pos = 0
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

    cur_inst = midi_obj.instruments[inst_id]

    for item in token_list:  # Todo: 对错误的结果顺序做处理
        try:
            item_type, item_value = item
        except ValueError:
            print(item)
            raise
        if item_type == const.BAR_ABBR:
            cur_bar_id += 1
            cur_local_pos = None
            cur_global_bar_pos += cur_ts_pos_per_bar
            cur_global_pos = cur_global_bar_pos
        elif item_type == const.TS_ABBR:
            if cur_ts_id != item_value:
                cur_ts_id = item_value
                cur_ts = vocab_manager.convert_id_to_ts(cur_ts_id)
                cur_ts_pos_per_bar = beat_note_factor * pos_resolution * cur_ts[0] // cur_ts[1]
                midi_obj.time_signature_changes.append(
                    miditoolkit.containers.TimeSignature(numerator=cur_ts[0], denominator=cur_ts[1],
                                                         time=vocab_manager.pos_to_time(cur_global_bar_pos,
                                                                                        ticks_per_beat,
                                                                                        pos_resolution=pos_resolution))
                )
        elif item_type == const.POS_ABBR:
            if cur_local_pos != item_value:
                cur_local_pos = item_value
                cur_global_pos = cur_global_bar_pos + cur_local_pos
        elif item_type == const.TEMPO_ABBR:
            if cur_tempo_id != item_value:
                cur_tempo_id = item_value
                cur_tempo = vocab_manager.convert_id_to_tempo(cur_tempo_id)
                midi_obj.tempo_changes.append(
                    miditoolkit.containers.TempoChange(cur_tempo,
                                                       time=vocab_manager.pos_to_time(cur_global_pos,
                                                                                      ticks_per_beat,
                                                                                      pos_resolution=pos_resolution))
                )
        elif item_type == const.INST_ABBR:
            cur_inst = midi_obj.instruments[item_value]
        elif item_type == const.PITCH_ABBR:
            cur_pitch = vocab_manager.convert_id_to_pitch(item_value)
        elif item_type == const.DURATION_ABBR:
            cur_duration = vocab_manager.convert_id_to_dur(item_value)
        elif item_type == const.VELOCITY_ABBR:
            cur_velocity = vocab_manager.convert_id_to_vel(item_value)

            start_pos = cur_global_pos
            end_pos = start_pos + cur_duration
            start_time = vocab_manager.pos_to_time(start_pos, ticks_per_beat, pos_resolution=pos_resolution)
            end_time = vocab_manager.pos_to_time(end_pos, ticks_per_beat, pos_resolution=pos_resolution)
            max_tick = max(end_time, max_tick)
            cur_inst.notes.append(
                miditoolkit.containers.Note(start=start_time, end=end_time, pitch=cur_pitch, velocity=cur_velocity)
            )
        else:
            raise ValueError("Unknown encoding type: %s" % item_type)

    midi_obj.max_tick = max_tick

    midi_obj.instruments = [i for i in midi_obj.instruments if len(i.notes) > 0]

    return midi_obj
