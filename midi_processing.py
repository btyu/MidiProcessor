import os
import math
import inspect
import miditoolkit

import data_utils
import remi_utils
import ts1_utils


class MidiProcessor(object):
    # === ENCODING ===
    ENCODINGS = ('REMI', 'TS1')
    # REMI: REMI
    # TS1: 只编码Bar(no idx)、position、duration、pitch信息

    # === Abbreviation ===
    BAR_ABBR = 'b'
    POS_ABBR = 'o'
    TS_ABBR = 's'
    TEMPO_ABBR = 't'
    INST_ABBR = 'i'
    PITCH_ABBR = 'p'
    DURATION_ABBR = 'd'
    VELOCITY_ABBR = 'v'

    # === Process ===
    CUT_METHODS = ('successive', 'first')

    def __init__(self,
                 encoding_method,
                 pos_resolution=16,
                 trunc_pos=None,
                 max_ts_denominator_power=6,
                 max_notes_per_bar=2,
                 tempo_quant=12,
                 min_tempo=16,
                 max_tempo=256,
                 velocity_quant=4,
                 max_duration=8,
                 max_bar_num=256,
                 ):
        # ===== Check =====
        MidiProcessor.check_encoding_method(encoding_method)

        # ===== Authorized =====
        self.encoding_method = encoding_method

        self.pos_resolution = pos_resolution  # per beat (quarter note)
        self.trunc_pos = trunc_pos  # 2 ** 16  # approx 30 minutes (1024 measures)

        self.max_ts_denominator_power = max_ts_denominator_power  # x/1 x/2 x/4 ... x/64
        self.max_notes_per_bar = max_notes_per_bar  # max number of whole notes within a bar

        self.tempo_quant = tempo_quant  # 2 ** (1 / 12)
        self.min_tempo = min_tempo
        self.max_tempo = max_tempo

        self.velocity_quant = velocity_quant

        self.max_duration = max_duration  # 2 ** 8 * beat

        self.beat_note_factor = 4  # In midi format a note is always 4 beats

        self.max_bar_num = max_bar_num

        # ===== Unauthorized =====
        # self.deduplicate = True
        # self.filter_symbolic = False
        # self.filter_symbolic_ppl = 16
        # self.sample_len_max = 1000  # window length max
        # self.sample_overlap_rate = 4
        # self.ts_filter = False

        # ===== Generating Vocabs =====
        self.ts_dict, self.ts_list = self.generate_ts_vocab(self.max_ts_denominator_power, self.max_notes_per_bar)
        self.dur_enc, self.dur_dec = self.generate_duration_vocab(self.max_duration, self.pos_resolution)

        self.vocab = self.generate_vocab()

    # ===== Encoding Method =====
    # Finished
    @staticmethod
    def check_encoding_method(encoding_method):
        assert encoding_method in MidiProcessor.ENCODINGS, "Encoding method %s not in the supported: %s" % \
                                                           (encoding_method, ', '.join(MidiProcessor.ENCODINGS))

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
            MidiProcessor.check_encoding_method(encoding_method)
        return encoding_method

    # Finished
    @staticmethod
    def __raise_encoding_method_error(encoding_method):
        raise ValueError("Encoding method %s is not supported." % encoding_method)

    # ===== Vocab =====
    def vocab_to_str_list(self):
        return ['%s-%d' % (item[0], item[1]) for item in self.vocab]

    def dump_vocab(self, file_path, fairseq_dict=False):
        vocab_str_list = self.vocab_to_str_list()
        dir_name = os.path.dirname(file_path)
        os.makedirs(dir_name, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            for word in vocab_str_list:
                if fairseq_dict:
                    line = '%s 1\n' % word
                else:
                    line = '%s\n' % word
                f.write(line)

    @property
    def max_ts_denominator(self):
        return 2 ** self.max_ts_denominator_power

    def generate_vocab(self):
        vocab = []

        for bar_idx in range(self.max_bar_num):
            vocab.append((MidiProcessor.BAR_ABBR, bar_idx))

        for idx in range(self.beat_note_factor * self.max_notes_per_bar * self.pos_resolution):
            vocab.append((MidiProcessor.POS_ABBR, idx))

        for idx in range(129):
            vocab.append((MidiProcessor.INST_ABBR, idx))

        for idx in range(256):
            vocab.append((MidiProcessor.PITCH_ABBR, idx))

        for idx in range(len(self.dur_dec)):
            vocab.append((MidiProcessor.DURATION_ABBR, idx))

        for idx in range(self.convert_vel_to_id(127) + 1):
            vocab.append((MidiProcessor.VELOCITY_ABBR, idx))

        for idx in range(len(self.ts_list)):
            vocab.append((MidiProcessor.TS_ABBR, idx))

        for idx in range(self.convert_tempo_to_id(self.max_tempo) + 1):
            vocab.append((MidiProcessor.TEMPO_ABBR, idx))

        return vocab

    @staticmethod
    def generate_ts_vocab(max_ts_denominator_power, max_notes_per_bar):
        ts_dict = dict()
        ts_list = list()
        for i in range(0, max_ts_denominator_power + 1):  # 1 ~ 64
            for j in range(1, ((2 ** i) * max_notes_per_bar) + 1):
                ts_dict[(j, 2 ** i)] = len(ts_dict)
                ts_list.append((j, 2 ** i))
        return ts_dict, ts_list

    @staticmethod
    def generate_duration_vocab(max_duration, pos_resolution):
        dur_enc = list()
        dur_dec = list()
        for i in range(max_duration):
            for j in range(pos_resolution):
                dur_dec.append(len(dur_enc))
                for k in range(2 ** i):
                    dur_enc.append(len(dur_dec) - 1)
        return dur_enc, dur_dec

    def convert_ts_to_id(self, x):
        return self.ts_dict[x]

    def convert_id_to_ts(self, x):
        return self.ts_list[x]

    def convert_tempo_to_id(self, x):
        x = max(x, self.min_tempo)
        x = min(x, self.max_tempo)
        x = x / self.min_tempo
        e = round(math.log2(x) * self.tempo_quant)
        return e

    def convert_id_to_tempo(self, x):
        return 2 ** (x / self.tempo_quant) * self.min_tempo

    def convert_pitch_to_id(self, x, is_drum=False):
        if is_drum:
            return x + 128
        return x

    def convert_id_to_pitch(self, x):
        if x >= 128:
            x = x - 128
        return x

    def convert_vel_to_id(self, x):
        return x // self.velocity_quant

    def convert_id_to_vel(self, x):
        return (x * self.velocity_quant) + (self.velocity_quant // 2)

    def convert_dur_to_id(self, x):
        return self.dur_enc[x] if x < len(self.dur_enc) else self.dur_enc[-1]

    def convert_id_to_dur(self, x):
        return self.dur_dec[x] if x < len(self.dur_dec) else self.dur_dec[-1]

    # Finished
    @staticmethod
    def load_midi(file_path):
        """
        Open and check MIDI file, return MIDI object by miditoolkit.
        :param file_path:
        :return:
        """
        midi_obj = miditoolkit.midi.parser.MidiFile(file_path)

        # check abnormal values in parse result
        max_time_length = 2 ** 31
        assert all(0 <= j.start < max_time_length
                   and 0 <= j.end < max_time_length
                   for i in midi_obj.instruments for j in i.notes), 'Bad note time'
        assert all(0 < j.numerator < max_time_length and 0 < j.denominator < max_time_length for j in
                   midi_obj.time_signature_changes), 'Bad time signature value'
        assert 0 < midi_obj.ticks_per_beat < max_time_length, 'Bad ticks per beat'

        midi_notes_count = sum(len(inst.notes) for inst in midi_obj.instruments)
        assert midi_notes_count > 0, 'Blank note.'

        return midi_obj

    def encode_file(self, file_path,
                    encoding_method=None,
                    max_encoding_length=None,
                    max_bar=None,
                    cut_method='successive',
                    max_bar_num=None,
                    remove_bar_idx=False,
                    tracks=None,
                    save_path=None):
        encoding_method = self.get_encoding_method(encoding_method)

        midi_obj = MidiProcessor.load_midi(file_path)

        pos_info = self.collect_pos_info(midi_obj, tracks=tracks)

        if max_bar_num is None:
            max_bar_num = self.max_bar_num

        token_lists = None
        if encoding_method == 'REMI':  # Todo: REMI encoding结构修改
            token_lists = self.pos_info_to_remi_encoding(pos_info,
                                                         max_encoding_length=max_encoding_length,
                                                         max_bar=max_bar,
                                                         cut_method=cut_method, )
        elif encoding_method == 'TS1':
            token_lists = ts1_utils.convert_pos_info_to_ts1_token_lists(
                pos_info,
                MidiProcessor.BAR_ABBR,
                MidiProcessor.POS_ABBR,
                MidiProcessor.PITCH_ABBR,
                MidiProcessor.DURATION_ABBR,
                max_encoding_length=max_encoding_length,
                max_bar=max_bar,
                cut_method=cut_method,
                max_bar_num=max_bar_num,
                remove_bar_idx=remove_bar_idx,
            )
        else:
            MidiProcessor.__raise_encoding_method_error(encoding_method)

        if save_path is not None:
            try:
                self.dump_token_lists(token_lists, save_path, encoding_method=encoding_method)
            except IOError:
                print("Wrong! Saving failed: \nMIDI: %s\nSave Path: %s" % file_path, save_path)

        return token_lists

    def time_to_pos(self, t, ticks_per_beat):
        return round(t * self.pos_resolution / ticks_per_beat)

    def pos_to_time(self, pos, ticks_per_beat, pos_resolution=None):
        if pos_resolution is None:
            pos_resolution = self.pos_resolution
        return pos * ticks_per_beat // self.pos_resolution

    def collect_pos_info(self, midi_obj, tracks=None):
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
        max_pos = max_pos + 1
        if self.trunc_pos is not None:
            max_pos = min(max_pos, self.trunc_pos)

        pos_to_info = [
            [None, None, None, None, None]  # (bar, ts, local_pos, tempo, insts_notes)
            for _ in range(max_pos)
        ]

        ts_changes = midi_obj.time_signature_changes
        for ts_change in ts_changes:
            pos = self.time_to_pos(ts_change.time, midi_obj.ticks_per_beat)
            if pos >= max_pos:
                continue
            ts_numerator = ts_change.numerator
            ts_denominator = ts_change.denominator
            reduced_ts = self._time_signature_reduce(ts_numerator, ts_denominator)
            pos_to_info[pos][1] = self.convert_ts_to_id(reduced_ts)

        tempo_changes = midi_obj.tempo_changes
        for tempo_change in tempo_changes:
            pos = self.time_to_pos(tempo_change.time, midi_obj.ticks_per_beat)
            if pos >= max_pos:
                continue
            tempo = tempo_change.tempo
            pos_to_info[pos][3] = self.convert_tempo_to_id(tempo)

        insts = midi_obj.instruments
        for inst_idx, inst in enumerate(insts):
            if tracks is not None and inst_idx not in tracks:
                continue
            inst_id = 128 if inst.is_drum else inst.program
            notes = inst.notes
            for note in notes:
                pitch = note.pitch
                pitch = self.convert_pitch_to_id(pitch, is_drum=inst.is_drum)
                velocity = note.velocity
                velocity = self.convert_vel_to_id(velocity)
                start_time = note.start
                end_time = note.end
                pos_start = self.time_to_pos(start_time, midi_obj.ticks_per_beat)
                pos_end = self.time_to_pos(end_time, midi_obj.ticks_per_beat)
                duration = pos_end - pos_start
                duration = self.convert_dur_to_id(duration)

                if pos_to_info[pos_start][4] is None:
                    pos_to_info[pos_start][4] = dict()
                if inst_id not in pos_to_info[pos_start][4]:
                    pos_to_info[pos_start][4][inst_id] = []
                pos_to_info[pos_start][4][inst_id].append((pitch, duration, velocity, pos_end))

        cnt = 0
        bar = 0
        measure_length = None
        ts = (4, 4)  # default MIDI time signature
        for j in range(max_pos):
            now_ts_id = pos_to_info[j][1]
            if now_ts_id is not None:
                now_ts = self.convert_id_to_ts(now_ts_id)
                if now_ts != ts:
                    ts = now_ts
            if cnt == 0:
                measure_length = ts[0] * self.beat_note_factor * self.pos_resolution // ts[1]
            pos_to_info[j][0] = bar
            pos_to_info[j][2] = cnt
            cnt += 1
            if cnt >= measure_length:
                assert cnt == measure_length, 'invalid time signature change: pos = {}'.format(j)
                cnt = 0
                bar += 1

        return pos_to_info

    def _time_signature_reduce(self, numerator, denominator):
        # reduction (when denominator is too large)
        while denominator > self.max_ts_denominator and denominator % 2 == 0 and numerator % 2 == 0:
            denominator //= 2
            numerator //= 2
        # decomposition (when length of a bar exceed max_notes_per_bar)
        while numerator > self.max_notes_per_bar * denominator:
            for i in range(2, numerator + 1):
                if numerator % i == 0:
                    numerator //= i
                    break
        return numerator, denominator

    def pos_info_to_remi_encoding(self, pos_to_info,
                                  max_encoding_length=None, max_bar=None,
                                  cut_method='successive', ):
        encoding = []

        max_pos = len(pos_to_info)
        cur_bar = None
        cur_ts = self.convert_ts_to_id((4, 4))  # default MIDI time signature
        cur_tempo = self.convert_tempo_to_id(120.0)  # default MIDI tempo (BPM)
        for pos in range(max_pos):
            now_bar, now_ts, now_local_pos, now_tempo, now_insts_notes = pos_to_info[pos]

            cur_local_pos = now_local_pos

            if now_ts is not None and now_ts != cur_ts:
                cur_ts = now_ts
            if now_tempo is not None and now_tempo != cur_tempo:
                cur_tempo = now_tempo

            if cur_bar != now_bar:
                cur_bar = now_bar
                encoding.append((MidiProcessor.BAR_ABBR, cur_bar))  # bar
                encoding.append((MidiProcessor.TS_ABBR, cur_ts))  # ts

            if now_insts_notes is not None:
                cur_insts_notes = now_insts_notes
                encoding.append((MidiProcessor.POS_ABBR, cur_local_pos))  # local pos
                encoding.append((MidiProcessor.TEMPO_ABBR, cur_tempo))  # tempo
                insts_ids = sorted(list(cur_insts_notes.keys()))
                for inst_id in insts_ids:
                    encoding.append((MidiProcessor.INST_ABBR, inst_id))
                    inst_notes = sorted(cur_insts_notes[inst_id])
                    for pitch, duration, velocity, pos_end in inst_notes:
                        encoding.append((MidiProcessor.PITCH_ABBR, pitch))  # pitch
                        encoding.append((MidiProcessor.DURATION_ABBR, duration))  # duration
                        encoding.append((MidiProcessor.VELOCITY_ABBR, velocity))  # velocity

        return self._remi_encoding_cut(encoding,
                                       max_encoding_length=max_encoding_length, max_bar=max_bar,
                                       cut_method=cut_method)

    def _remi_encoding_cut(self, remi_encoding, max_encoding_length=None, max_bar=None,
                           cut_method='successive'):
        len_encoding = len(remi_encoding)

        direct_returns = max_encoding_length is None and max_bar is None, \
                         max_encoding_length is not None and len_encoding <= max_encoding_length and max_bar is None

        if any(direct_returns):
            return [remi_encoding[:]]

        assert cut_method in MidiProcessor.CUT_METHODS, "Cut method \"%s\" not in the supported: %s" % \
                                                        (cut_method, ', '.join(MidiProcessor.CUT_METHODS))

        def get_remi_bar_offset(encoding):
            for idx, item in enumerate(encoding):
                if item[0] == MidiProcessor.BAR_ABBR:
                    return idx, item[1]
            return None, None

        authorize_right = lambda x, y: x[y][0] == MidiProcessor.BAR_ABBR

        def authorize_bar(encoding, start, pos, offset, max_bar):
            if pos < len(encoding) and encoding[pos][0] == MidiProcessor.BAR_ABBR:
                return encoding[pos][1] - offset <= max_bar
            pos -= 1
            while pos >= start:
                if encoding[pos][0] == MidiProcessor.BAR_ABBR:
                    return encoding[pos][1] - offset < max_bar
                pos -= 1
            raise ValueError("No authorized bar in the encoding range.")

        if cut_method == 'successive':
            return self.__encoding_successive_cut(
                remi_encoding,
                max_length=max_encoding_length,
                max_bar=max_bar,
                get_offset=get_remi_bar_offset,
                authorize_right=authorize_right,
                authorize_bar=authorize_bar,
                len_encoding=len_encoding,
            )
        elif cut_method == 'first':
            return self.__encoding_successive_cut(
                remi_encoding,
                max_length=max_encoding_length,
                max_bar=max_bar,
                get_offset=get_remi_bar_offset,
                authorize_right=authorize_right,
                authorize_bar=authorize_bar,
                len_encoding=max_encoding_length,
            )
        else:
            raise ValueError("Cut method \"%s\" not currently supported." % cut_method)

    def __encoding_successive_cut(self, encoding, max_length=None, max_bar=None,
                                  get_offset=None,
                                  authorize_right=None,
                                  authorize_bar=None,
                                  len_encoding=None):
        assert inspect.isfunction(get_offset)
        assert inspect.isfunction(authorize_right)
        assert inspect.isfunction(authorize_bar)
        if len_encoding is None:
            len_encoding = len(encoding)
        if max_length is None:
            max_length = len_encoding
        assert max_length > 0

        encodings = []

        start = 0
        while start < len_encoding:
            end = min(start + max_length, len_encoding)
            first_bar_idx, bar_offset = get_offset(encoding[start: end])
            assert first_bar_idx == 0
            have_bar = False
            while True:
                assert end > start, "No authorized right position for the cut. " + \
                                    ("However, there is a bar in the range." if have_bar
                                     else "And there is no bar in the range.")
                if end == len_encoding or authorize_right(encoding, end):
                    have_bar = True
                    if max_bar is None:
                        break
                    else:
                        if authorize_bar(encoding, start, end, bar_offset, max_bar):
                            break
                end -= 1
            encodings.append(self.__remi_ensure_bar_num(encoding[start: end], bar_offset))
            start = end

        return encodings

    def __remi_ensure_bar_num(self, encoding, offset):
        new_encoding = []
        for item in encoding:
            if item[0] == MidiProcessor.BAR_ABBR:
                bar_idx = item[1]
                bar_idx -= offset
                if bar_idx >= self.max_bar_num:
                    bar_idx = self.max_bar_num - 1
                new_encoding.append((MidiProcessor.BAR_ABBR, bar_idx))
            else:
                new_encoding.append(item)
        return new_encoding

    def remi_encoding_to_midi_obj(self, encoding,
                                  ticks_per_beat=480,
                                  pos_resolution=None,
                                  beat_note_factor=None,
                                  ):
        if pos_resolution is None:
            pos_resolution = self.pos_resolution
        if beat_note_factor is None:
            beat_note_factor = self.beat_note_factor

        cur_bar_id = None
        cur_ts_id = None
        cur_local_pos = None
        cur_ts_pos_per_bar = beat_note_factor * pos_resolution
        cur_tempo_id = None
        cur_global_bar_pos = None
        cur_global_pos = None

        cur_inst = None
        cur_pitch = None
        cur_duration = None
        cur_velocity = None

        max_tick = 0

        midi_obj = miditoolkit.midi.parser.MidiFile(ticks_per_beat=ticks_per_beat)
        midi_obj.instruments = [
            miditoolkit.containers.Instrument(program=(0 if i == 128 else i), is_drum=(i == 128), name=str(i))
            for i in range(128 + 1)
        ]

        for item in encoding:
            try:
                item_type, item_value = item
            except ValueError:
                print(item)
                raise
            if item_type == MidiProcessor.BAR_ABBR:
                if cur_bar_id != item_value:
                    cur_bar_id = item_value
                    cur_local_pos = None
                    if cur_global_bar_pos is None:
                        cur_global_bar_pos = 0
                    else:
                        cur_global_bar_pos += cur_ts_pos_per_bar
                    cur_global_pos = cur_global_bar_pos
            elif item_type == MidiProcessor.TS_ABBR:
                if cur_ts_id != item_value:
                    cur_ts_id = item_value
                    cur_ts_numerator, cur_ts_denominator = self.convert_id_to_ts(cur_ts_id)
                    midi_obj.time_signature_changes.append(
                        miditoolkit.containers.TimeSignature(numerator=cur_ts_numerator,
                                                             denominator=cur_ts_denominator,
                                                             time=self.pos_to_time(cur_global_pos,
                                                                                   ticks_per_beat=ticks_per_beat))
                    )
                    cur_ts_pos_per_bar = cur_ts_numerator * beat_note_factor * pos_resolution // cur_ts_denominator
            elif item_type == MidiProcessor.POS_ABBR:
                if cur_local_pos != item_value:
                    cur_local_pos = item_value
                    cur_global_pos = cur_global_bar_pos + cur_local_pos
            elif item_type == MidiProcessor.TEMPO_ABBR:
                if cur_tempo_id != item_value:
                    cur_tempo_id = item_value
                    cur_tempo = self.convert_id_to_tempo(cur_tempo_id)
                    midi_obj.tempo_changes.append(
                        miditoolkit.containers.TempoChange(tempo=cur_tempo,
                                                           time=self.pos_to_time(cur_global_pos,
                                                                                 ticks_per_beat=ticks_per_beat))
                    )
            elif item_type == MidiProcessor.INST_ABBR:
                cur_inst = midi_obj.instruments[item_value]
            elif item_type == MidiProcessor.PITCH_ABBR:
                cur_pitch = self.convert_id_to_pitch(item_value)
            elif item_type == MidiProcessor.DURATION_ABBR:
                cur_duration = self.convert_id_to_dur(item_value)
            elif item_type == MidiProcessor.VELOCITY_ABBR:
                cur_velocity = self.convert_id_to_vel(item_value)

                start_pos = cur_global_pos
                end_pos = start_pos + cur_duration
                start_time = self.pos_to_time(start_pos, ticks_per_beat, pos_resolution=pos_resolution)
                end_time = self.pos_to_time(end_pos, ticks_per_beat, pos_resolution=pos_resolution)
                max_tick = max(end_time, max_tick)
                cur_inst.notes.append(
                    miditoolkit.containers.Note(start=start_time, end=end_time, pitch=cur_pitch, velocity=cur_velocity)
                )
            else:
                raise ValueError("Unknown encoding type: %d" % item_type)

        midi_obj.max_tick = max_tick

        midi_obj.instruments = [i for i in midi_obj.instruments if len(i.notes) > 0]

        return midi_obj

    def load_encoding_str(self, file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            line = f.readlines(1)
        line = line[0]
        line = line.strip()
        line = line.split(' ')
        encodings = []
        for item in line:
            try:
                t, value = item.split('-')
            except:
                print(item)
                raise
            encodings.append((t, int(value)))
        return encodings

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
            return remi_utils.convert_remi_token_lists_to_token_str_lists(token_lists)
        elif encoding_method == 'TS1':
            return ts1_utils.convert_ts1_token_lists_to_token_str_lists(token_lists)
        else:
            MidiProcessor.__raise_encoding_method_error(encoding_method)

    # Finished
    def dump_token_lists(self, token_lists, file_path, encoding_method=None):
        """
        将一个文件的encoding token_lists转换成str并存为文件
        :param token_lists:
        :param file_path:
        :param encoding_method:
        :return:
        """
        encoding_method = self.get_encoding_method(encoding_method)
        token_str_lists = self.convert_token_lists_to_token_str_lists(token_lists, encoding_method=encoding_method)
        data_utils.dump_lists(token_str_lists, file_path)

    # Finished
    def convert_token_str_to_token(self, token_str, encoding_method=None):
        """
        将单个token的str转换为encoding元组
        :param token_str: 单个token的str
        :param encoding_method: encoding方法
        :return:
        """
        encoding_method = self.get_encoding_method(encoding_method)
        # 调用各encoding方式对应方法
        if encoding_method == 'REMI':
            return remi_utils.convert_remi_token_str_to_token(token_str)
        else:
            MidiProcessor.__raise_encoding_method_error(encoding_method)

    # Todo
    def convert_token_str_list_to_token_list(self, token_str_list, encoding_method=None):
        """

        :param token_str_list:
        :param encoding_method:
        :return:
        """
        encoding_method = self.get_encoding_method(encoding_method)
        if encoding_method == 'REMI':
            pass

    # Todo
    def load_encoding_lists_from_str_lists(self, file_name, keep_full_dim=False, ):
        pass
