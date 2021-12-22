import os
import typing
import pickle
from . import midi_utils
from copy import deepcopy

from . import const
from .vocab_manager import VocabManager
from . import data_utils
from . import enc_remi_utils
from . import enc_remigen_utils
from . import enc_ts1_utils
from . import enc_tg1_utils
from . import keys_normalization


file_dir = os.path.dirname(__file__)


class MidiEncoder(object):
    def __init__(self,
                 encoding_method,
                 key_profile_file=None,
                 ):
        # ===== Check =====
        MidiEncoder.check_encoding_method(encoding_method)

        # ===== Authorized =====
        self.encoding_method = encoding_method

        self.vm = VocabManager()

        self.key_profile = None
        if key_profile_file is None:
            key_profile_file = os.path.join(file_dir, const.KEY_PROFILE)
        self.load_key_profile(key_profile_file)

        # ===== Unauthorized =====
        # self.deduplicate = True
        # self.filter_symbolic = False
        # self.filter_symbolic_ppl = 16
        # self.sample_len_max = 1000  # window length max
        # self.sample_overlap_rate = 4
        # self.ts_filter = False

    # ==== Key Profile =====
    def load_key_profile(self, key_profile_file):
        with open(key_profile_file, 'rb') as f:
            self.key_profile = pickle.load(f)

    # ===== Encoding Method =====
    # Finished
    @staticmethod
    def check_encoding_method(encoding_method):
        assert encoding_method in const.ENCODINGS, "Encoding method %s not in the supported: %s" % \
                                                   (encoding_method, ', '.join(const.ENCODINGS))

    # Finished
    def get_encoding_method(self, encoding_method=None):
        """
        供各方法调用的获取encoding_method的方法
        :param encoding_method:
        :return:
        """
        if encoding_method is None:
            encoding_method = self.encoding_method
        else:
            MidiEncoder.check_encoding_method(encoding_method)
        return encoding_method

    # Finished
    @staticmethod
    def __raise_encoding_method_error(encoding_method):
        raise ValueError("Encoding method %s is not supported." % encoding_method)

    # ===== Basic Functions ===
    def time_to_pos(self, *args, **kwargs):
        return self.vm.time_to_pos(*args, **kwargs)

    def collect_pos_info(self, midi_obj, trunc_pos=None, tracks=None):
        if tracks is not None:
            from collections.abc import Iterable
            assert isinstance(tracks, (int, Iterable))
            if isinstance(tracks, str):
                tracks = int(tracks)
            if isinstance(tracks, int):
                if tracks < 0:
                    tracks = len(midi_obj.instruments) + tracks
                tracks = (tracks,)

        max_pos = 0
        for inst in midi_obj.instruments:
            for note in inst.notes:
                pos = self.time_to_pos(note.start, midi_obj.ticks_per_beat)
                max_pos = max(max_pos, pos)
        max_pos = max_pos + 1  # 最大global position
        if trunc_pos is not None:
            max_pos = min(max_pos, trunc_pos)

        pos_info = [
            [None, None, None, None, None]  # (bar, ts, local_pos, tempo, insts_notes)
            for _ in range(max_pos)
        ]
        pos_info: typing.List
        # bar: every pos
        # ts: only at pos where it changes, otherwise None
        # local_pos: every pos
        # tempo: only at pos where it changes, otherwise None
        # insts_notes: only at pos where the note starts, otherwise None

        ts_changes = midi_obj.time_signature_changes
        zero_pos_ts_change = False
        for ts_change in ts_changes:
            pos = self.time_to_pos(ts_change.time, midi_obj.ticks_per_beat)
            if pos >= max_pos:
                continue
            if pos == 0:
                zero_pos_ts_change = True
            ts_numerator = ts_change.numerator
            ts_denominator = ts_change.denominator
            ts_numerator, ts_denominator = self.vm.reduce_time_signature(ts_numerator, ts_denominator)
            pos_info[pos][1] = (ts_numerator, ts_denominator)
        if not zero_pos_ts_change:
            pos_info[0][1] = const.DEFAULT_TS

        tempo_changes = midi_obj.tempo_changes
        zero_pos_tempo_change = False
        for tempo_change in tempo_changes:
            pos = self.time_to_pos(tempo_change.time, midi_obj.ticks_per_beat)
            if pos >= max_pos:
                continue
            if pos == 0:
                zero_pos_tempo_change = True
            pos_info[pos][3] = tempo_change.tempo
        if not zero_pos_tempo_change:
            pos_info[0][3] = const.DEFAULT_TEMPO

        insts = midi_obj.instruments
        for inst_idx, inst in enumerate(insts):
            if tracks is not None and inst_idx not in tracks:
                continue
            inst_id = 128 if inst.is_drum else inst.program
            notes = inst.notes
            for note in notes:
                pitch = note.pitch
                velocity = note.velocity
                start_time = note.start
                end_time = note.end
                pos_start = self.time_to_pos(start_time, midi_obj.ticks_per_beat)
                pos_end = self.time_to_pos(end_time, midi_obj.ticks_per_beat)
                duration = pos_end - pos_start
                duration = max(1, duration)

                if pos_info[pos_start][4] is None:
                    pos_info[pos_start][4] = dict()
                if inst_id not in pos_info[pos_start][4]:
                    pos_info[pos_start][4][inst_id] = []
                pos_info[pos_start][4][inst_id].append([pitch, duration, velocity])

        cnt = 0
        bar = 0
        measure_length = None
        ts = const.DEFAULT_TS  # default MIDI time signature
        for j in range(max_pos):
            now_ts = pos_info[j][1]
            if now_ts is not None:
                if now_ts != ts:
                    ts = now_ts
            if cnt == 0:
                measure_length = ts[0] * self.vm.beat_note_factor * self.vm.pos_resolution // ts[1]
            pos_info[j][0] = bar
            pos_info[j][2] = cnt
            cnt += 1
            if cnt >= measure_length:
                assert cnt == measure_length, 'invalid time signature change: pos = {}'.format(j)
                cnt = 0
                bar += 1

        return pos_info

    def convert_pos_info_to_pos_info_id(self, pos_info):
        pos_info_id = deepcopy(pos_info)
        # (bar, ts, local_pos, tempo, insts_notes)

        for idx, item in enumerate(pos_info_id):
            bar, ts, local_pos, tempo, insts_notes = item
            if ts is not None:
                ts_id = self.vm.convert_ts_to_id(ts)
                item[1] = ts_id
            if tempo is not None:
                tempo_id = self.vm.convert_tempo_to_id(tempo)
                item[3] = tempo_id
            if insts_notes is not None:
                # (pitch, duration, velocity, pos_end)
                for inst_id in insts_notes:
                    inst_notes = insts_notes[inst_id]
                    for inst_note in inst_notes:
                        pitch, duration, velocity = inst_note
                        pitch_id = self.vm.convert_pitch_to_id(pitch, is_drum=inst_id == 128)
                        duration_id = self.vm.convert_dur_to_id(duration)
                        velocity_id = self.vm.convert_vel_to_id(velocity)
                        inst_note[0] = pitch_id
                        inst_note[1] = duration_id
                        inst_note[2] = velocity_id
        return pos_info_id

    def encode_file(self,
                    file_path,

                    max_encoding_length=None,
                    max_bar=None,
                    trunc_pos=None,

                    cut_method='successive',
                    remove_bar_idx=False,
                    normalize_keys=False,
                    remove_empty_bars=False,
                    tracks=None,
                    save_path=None,
                    midi_obj=None):
        encoding_method = self.encoding_method

        if midi_obj is None:
            midi_obj = midi_utils.load_midi(file_path)

        pos_info = self.collect_pos_info(midi_obj, trunc_pos=trunc_pos, tracks=tracks)

        if normalize_keys:
            pos_info = self.normalize_pitch(pos_info)

        pos_info_id = self.convert_pos_info_to_pos_info_id(pos_info)

        token_lists = None
        if encoding_method == 'REMI':  # Todo: REMI encoding参考原版重写
            token_lists = enc_remi_utils.convert_pos_info_to_remi_token_lists(
                pos_info_id,
                max_encoding_length=max_encoding_length,
                max_bar=max_bar,
                cut_method=cut_method,
                max_bar_num=self.vm.max_bar_num,
                remove_bar_idx=remove_bar_idx,
                remove_empty_bars=remove_empty_bars,
            )
        elif encoding_method == 'REMIGEN':
            token_lists = enc_remigen_utils.convert_pos_info_to_remigen_token_lists(
                pos_info_id,
                max_encoding_length=max_encoding_length,
                max_bar=max_bar,
                cut_method=cut_method,
                max_bar_num=self.vm.max_bar_num,
                remove_bar_idx=remove_bar_idx,
                remove_empty_bars=remove_empty_bars,
            )
        elif encoding_method == 'TS1':
            token_lists = enc_ts1_utils.convert_pos_info_to_ts1_token_lists(
                pos_info_id,
                max_encoding_length=max_encoding_length,
                max_bar=max_bar,
                cut_method=cut_method,
                max_bar_num=self.vm.max_bar_num,
                remove_bar_idx=remove_bar_idx,
                remove_empty_bars=remove_empty_bars,
            )
        elif encoding_method == 'TG1':
            token_lists = enc_tg1_utils.convert_pos_info_to_tg1_token_lists(
                pos_info_id,
                max_encoding_length=max_encoding_length,
                max_bar=max_bar,
                cut_method=cut_method,
                max_bar_num=self.vm.max_bar_num,
                remove_bar_idx=remove_bar_idx,
                remove_empty_bars=remove_empty_bars,
            )
        else:
            MidiEncoder.__raise_encoding_method_error(encoding_method)

        if save_path is not None:
            try:
                self.dump_token_lists(token_lists, save_path)
            except IOError:
                print("Wrong! Saving failed: \nMIDI: %s\nSave Path: %s" % file_path, save_path)

        return token_lists

    def normalize_pitch(self, pos_info):
        assert self.key_profile is not None, "Please load key_profile first, using load_key_profile method."
        pitch_shift, _, _ = keys_normalization.get_pitch_shift(pos_info, self.key_profile,
                                                               normalize=True, use_duration=True, use_velocity=True,
                                                               ensure_valid_range=True)
        for bar, ts, pos, tempo, insts_notes in pos_info:
            if insts_notes is None:
                continue
            for inst_id in insts_notes:
                if inst_id == 128:
                    continue
                inst_notes = insts_notes[inst_id]
                for note_idx, (pitch, duration, velocity) in enumerate(inst_notes):
                    # inst_notes[note_idx] = (pitch + pitch_shift, duration, velocity)
                    inst_notes[note_idx][0] = pitch + pitch_shift
        return pos_info

    # def pos_info_to_remi_encoding(self, pos_to_info,
    #                               max_encoding_length=None, max_bar=None,
    #                               cut_method='successive', ):
    #     encoding = []
    #
    #     max_pos = len(pos_to_info)
    #     cur_bar = None
    #     cur_ts = self.convert_ts_to_id((4, 4))  # default MIDI time signature
    #     cur_tempo = self.convert_tempo_to_id(120.0)  # default MIDI tempo (BPM)
    #     for pos in range(max_pos):
    #         now_bar, now_ts, now_local_pos, now_tempo, now_insts_notes = pos_to_info[pos]
    #
    #         cur_local_pos = now_local_pos
    #
    #         if now_ts is not None and now_ts != cur_ts:
    #             cur_ts = now_ts
    #         if now_tempo is not None and now_tempo != cur_tempo:
    #             cur_tempo = now_tempo
    #
    #         if cur_bar != now_bar:
    #             cur_bar = now_bar
    #             encoding.append((const.BAR_ABBR, cur_bar))  # bar
    #             encoding.append((const.TS_ABBR, cur_ts))  # ts
    #
    #         if now_insts_notes is not None:
    #             cur_insts_notes = now_insts_notes
    #             encoding.append((const.POS_ABBR, cur_local_pos))  # local pos
    #             encoding.append((const.TEMPO_ABBR, cur_tempo))  # tempo
    #             insts_ids = sorted(list(cur_insts_notes.keys()))
    #             for inst_id in insts_ids:
    #                 encoding.append((const.INST_ABBR, inst_id))
    #                 inst_notes = sorted(cur_insts_notes[inst_id])
    #                 for pitch, duration, velocity, pos_end in inst_notes:
    #                     encoding.append((const.PITCH_ABBR, pitch))  # pitch
    #                     encoding.append((const.DURATION_ABBR, duration))  # duration
    #                     encoding.append((const.VELOCITY_ABBR, velocity))  # velocity
    #
    #     return self._remi_encoding_cut(encoding,
    #                                    max_encoding_length=max_encoding_length, max_bar=max_bar,
    #                                    cut_method=cut_method)
    #
    # def _remi_encoding_cut(self, remi_encoding, max_encoding_length=None, max_bar=None,
    #                        cut_method='successive'):
    #     len_encoding = len(remi_encoding)
    #
    #     direct_returns = max_encoding_length is None and max_bar is None, \
    #                      max_encoding_length is not None and len_encoding <= max_encoding_length and max_bar is None
    #
    #     if any(direct_returns):
    #         return [remi_encoding[:]]
    #
    #     assert cut_method in const.CUT_METHODS, "Cut method \"%s\" not in the supported: %s" % \
    #                                                   (cut_method, ', '.join(const.CUT_METHODS))
    #
    #     def get_remi_bar_offset(encoding):
    #         for idx, item in enumerate(encoding):
    #             if item[0] == const.BAR_ABBR:
    #                 return idx, item[1]
    #         return None, None
    #
    #     authorize_right = lambda x, y: x[y][0] == const.BAR_ABBR
    #
    #     def authorize_bar(encoding, start, pos, offset, max_bar):
    #         if pos < len(encoding) and encoding[pos][0] == const.BAR_ABBR:
    #             return encoding[pos][1] - offset <= max_bar
    #         pos -= 1
    #         while pos >= start:
    #             if encoding[pos][0] == const.BAR_ABBR:
    #                 return encoding[pos][1] - offset < max_bar
    #             pos -= 1
    #         raise ValueError("No authorized bar in the encoding range.")
    #
    #     if cut_method == 'successive':
    #         return self.__encoding_successive_cut(
    #             remi_encoding,
    #             max_length=max_encoding_length,
    #             max_bar=max_bar,
    #             get_offset=get_remi_bar_offset,
    #             authorize_right=authorize_right,
    #             authorize_bar=authorize_bar,
    #             len_encoding=len_encoding,
    #         )
    #     elif cut_method == 'first':
    #         return self.__encoding_successive_cut(
    #             remi_encoding,
    #             max_length=max_encoding_length,
    #             max_bar=max_bar,
    #             get_offset=get_remi_bar_offset,
    #             authorize_right=authorize_right,
    #             authorize_bar=authorize_bar,
    #             len_encoding=max_encoding_length,
    #         )
    #     else:
    #         raise ValueError("Cut method \"%s\" not currently supported." % cut_method)

    # def __encoding_successive_cut(self, encoding, max_length=None, max_bar=None,
    #                               get_offset=None,
    #                               authorize_right=None,
    #                               authorize_bar=None,
    #                               len_encoding=None):
    #     assert inspect.isfunction(get_offset)
    #     assert inspect.isfunction(authorize_right)
    #     assert inspect.isfunction(authorize_bar)
    #     if len_encoding is None:
    #         len_encoding = len(encoding)
    #     if max_length is None:
    #         max_length = len_encoding
    #     assert max_length > 0
    #
    #     encodings = []
    #
    #     start = 0
    #     while start < len_encoding:
    #         end = min(start + max_length, len_encoding)
    #         first_bar_idx, bar_offset = get_offset(encoding[start: end])
    #         assert first_bar_idx == 0
    #         have_bar = False
    #         while True:
    #             assert end > start, "No authorized right position for the cut. " + \
    #                                 ("However, there is a bar in the range." if have_bar
    #                                  else "And there is no bar in the range.")
    #             if end == len_encoding or authorize_right(encoding, end):
    #                 have_bar = True
    #                 if max_bar is None:
    #                     break
    #                 else:
    #                     if authorize_bar(encoding, start, end, bar_offset, max_bar):
    #                         break
    #             end -= 1
    #         encodings.append(self.__remi_ensure_bar_num(encoding[start: end], bar_offset))
    #         start = end
    #
    #     return encodings

    # def __remi_ensure_bar_num(self, encoding, offset):
    #     new_encoding = []
    #     for item in encoding:
    #         if item[0] == const.BAR_ABBR:
    #             bar_idx = item[1]
    #             bar_idx -= offset
    #             if bar_idx >= self.max_bar_num:
    #                 bar_idx = self.max_bar_num - 1
    #             new_encoding.append((const.BAR_ABBR, bar_idx))
    #         else:
    #             new_encoding.append(item)
    #     return new_encoding

    # def remi_encoding_to_midi_obj(self, encoding,
    #                               ticks_per_beat=480,
    #                               pos_resolution=None,
    #                               beat_note_factor=None,
    #                               ):
    #     if pos_resolution is None:
    #         pos_resolution = self.pos_resolution
    #     if beat_note_factor is None:
    #         beat_note_factor = self.beat_note_factor
    #
    #     cur_bar_id = None
    #     cur_ts_id = None
    #     cur_local_pos = None
    #     cur_ts_pos_per_bar = beat_note_factor * pos_resolution
    #     cur_tempo_id = None
    #     cur_global_bar_pos = None
    #     cur_global_pos = None
    #
    #     cur_inst = None
    #     cur_pitch = None
    #     cur_duration = None
    #     cur_velocity = None
    #
    #     max_tick = 0
    #
    #     midi_obj = miditoolkit.midi.parser.MidiFile(ticks_per_beat=ticks_per_beat)
    #     midi_obj.instruments = [
    #         miditoolkit.containers.Instrument(program=(0 if i == 128 else i), is_drum=(i == 128), name=str(i))
    #         for i in range(128 + 1)
    #     ]
    #
    #     for item in encoding:
    #         try:
    #             item_type, item_value = item
    #         except ValueError:
    #             print(item)
    #             raise
    #         if item_type == const.BAR_ABBR:
    #             if cur_bar_id != item_value:
    #                 cur_bar_id = item_value
    #                 cur_local_pos = None
    #                 if cur_global_bar_pos is None:
    #                     cur_global_bar_pos = 0
    #                 else:
    #                     cur_global_bar_pos += cur_ts_pos_per_bar
    #                 cur_global_pos = cur_global_bar_pos
    #         elif item_type == const.TS_ABBR:
    #             if cur_ts_id != item_value:
    #                 cur_ts_id = item_value
    #                 cur_ts_numerator, cur_ts_denominator = self.convert_id_to_ts(cur_ts_id)
    #                 midi_obj.time_signature_changes.append(
    #                     miditoolkit.containers.TimeSignature(numerator=cur_ts_numerator,
    #                                                          denominator=cur_ts_denominator,
    #                                                          time=self.pos_to_time(cur_global_pos,
    #                                                                                ticks_per_beat=ticks_per_beat))
    #                 )
    #                 cur_ts_pos_per_bar = cur_ts_numerator * beat_note_factor * pos_resolution // cur_ts_denominator
    #         elif item_type == const.POS_ABBR:
    #             if cur_local_pos != item_value:
    #                 cur_local_pos = item_value
    #                 cur_global_pos = cur_global_bar_pos + cur_local_pos
    #         elif item_type == const.TEMPO_ABBR:
    #             if cur_tempo_id != item_value:
    #                 cur_tempo_id = item_value
    #                 cur_tempo = self.convert_id_to_tempo(cur_tempo_id)
    #                 midi_obj.tempo_changes.append(
    #                     miditoolkit.containers.TempoChange(tempo=cur_tempo,
    #                                                        time=self.pos_to_time(cur_global_pos,
    #                                                                              ticks_per_beat=ticks_per_beat))
    #                 )
    #         elif item_type == const.INST_ABBR:
    #             cur_inst = midi_obj.instruments[item_value]
    #         elif item_type == const.PITCH_ABBR:
    #             cur_pitch = self.convert_id_to_pitch(item_value)
    #         elif item_type == const.DURATION_ABBR:
    #             cur_duration = self.convert_id_to_dur(item_value)
    #         elif item_type == const.VELOCITY_ABBR:
    #             cur_velocity = self.convert_id_to_vel(item_value)
    #
    #             start_pos = cur_global_pos
    #             end_pos = start_pos + cur_duration
    #             start_time = self.pos_to_time(start_pos, ticks_per_beat, pos_resolution=pos_resolution)
    #             end_time = self.pos_to_time(end_pos, ticks_per_beat, pos_resolution=pos_resolution)
    #             max_tick = max(end_time, max_tick)
    #             cur_inst.notes.append(
    #                 miditoolkit.containers.Note(start=start_time, end=end_time, pitch=cur_pitch, velocity=cur_velocity)
    #             )
    #         else:
    #             raise ValueError("Unknown encoding type: %d" % item_type)
    #
    #     midi_obj.max_tick = max_tick
    #
    #     midi_obj.instruments = [i for i in midi_obj.instruments if len(i.notes) > 0]
    #
    #     return midi_obj

    # def load_encoding_str(self, file_name):
    #     with open(file_name, 'r', encoding='utf-8') as f:
    #         line = f.readlines(1)
    #     line = line[0]
    #     line = line.strip()
    #     line = line.split(' ')
    #     encodings = []
    #     for item in line:
    #         try:
    #             t, value = item.split('-')
    #         except:
    #             print(item)
    #             raise
    #         encodings.append((t, int(value)))
    #     return encodings

    # Finished
    # encoding_method check
    def convert_token_lists_to_token_str_lists(self, token_lists, encoding_method=None):
        """
        将一个文件的encoding token_lists（二层列表）转换为str lists
        :param token_lists:
        :param encoding_method:
        :return:
        """
        encoding_method = self.get_encoding_method(encoding_method)
        if encoding_method == 'REMI':
            return enc_remi_utils.convert_remi_token_lists_to_token_str_lists(token_lists)
        elif encoding_method == 'TS1':
            return enc_ts1_utils.convert_ts1_token_lists_to_token_str_lists(token_lists)
        else:
            MidiEncoder.__raise_encoding_method_error(encoding_method)

    # Finished
    def dump_token_lists(self, token_lists, file_path):
        """
        将一个文件的encoding token_lists转换成str并存为文件
        :param token_lists:
        :param file_path:
        :return:
        """
        token_str_lists = self.convert_token_lists_to_token_str_lists(token_lists, encoding_method=self.encoding_method)
        data_utils.dump_lists(token_str_lists, file_path)
