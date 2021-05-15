import os
import sys
import io
import zipfile
import miditoolkit
import random
import time
import math
import signal
import pickle
import hashlib
from itertools import product
from multiprocessing import Pool, Lock, Manager
from utils.magenta_chord_recognition import _CHORDS, _PITCH_CLASS_NAMES, NO_CHORD

pos_resolution = 16  # per beat (quarter note)
bar_max = 256
velocity_quant = 4
tempo_quant = 12  # 2 ** (1 / 12)
min_tempo = 16
max_tempo = 256
duration_max = 8  # 2 ** 8 * beat
max_ts_denominator = 6  # x/1 x/2 x/4 ... x/64
max_notes_per_bar = 2  # 1/64 ... 128/64
beat_note_factor = 4  # In midi format a note is always 4 beats
deduplicate = True
filter_symbolic = False
filter_symbolic_ppl = 16
trunc_pos = 2 ** 16  # approx 30 minutes (1024 measures)
sample_len_max = 1000  # window length max
sample_overlap_rate = 4
ts_filter = False
encoding = 'OCTmidi'  # OCTmidi CP REMI

data_zip = None
output_file = None

ts_dict = dict()
ts_list = list()
for i in range(0, max_ts_denominator + 1):  # 1 ~ 64
    for j in range(1, ((2 ** i) * max_notes_per_bar) + 1):
        ts_dict[(j, 2 ** i)] = len(ts_dict)
        ts_list.append((j, 2 ** i))

dur_enc = list()
dur_dec = list()
for i in range(duration_max):
    for j in range(pos_resolution):
        dur_dec.append(len(dur_enc))
        for k in range(2 ** i):
            dur_enc.append(len(dur_dec) - 1)

chord_dict = dict()
chord_list = list()
for i in range(len(_CHORDS)):
    if i > 0:
        root, kind = _CHORDS[i]
        chord = '%s:%s' % (_PITCH_CLASS_NAMES[root], kind)
    else:
        chord = _CHORDS[i]
    chord_dict[chord] = i
    chord_list.append(chord)


def use_compound_word():
    return encoding in ['OCTmidi', 'CP']


def use_tree_encoding():
    return encoding in ['CP', 'REMI']


# (0 Measure, 1 Pos, 2 Program, 3 Pitch, 4 Duration, 5 Velocity, 6 TimeSig, 7 Tempo)
# (Measure, TimeSig)
# (Pos, Tempo)
# Percussion: Program=128 Pitch=[128,255]

def adaptor(e):
    if use_tree_encoding():
        prev_bar = None
        prev_pos = None
        prev_prog = None
        new_e = []
        for i in e:
            if prev_bar != i[0]:
                prev_bar = i[0]
                prev_pos = None
                new_e.append((i[0], None, None, None, None, None, i[6], None))
            if prev_pos != i[1]:
                prev_pos = i[1]
                prev_prog = None
                new_e.append((None, i[1], None, None, None, None, None, i[7]))
            if prev_prog != i[2]:
                prev_prog = i[2]
                new_e.append((None, None, i[2], None, None, None, None, None))
            if True:
                new_e.append((None, None, None, i[3], i[4], i[5], None, None))
        if not use_compound_word():
            split_e = []
            for i in new_e:
                for j, k in enumerate(i):
                    if k is not None:
                        split_e.append(tuple(k if _ == j else None for _ in range(8)))
            return split_e
        else:
            return new_e
    else:
        return e


def enc_time_sig(x):
    assert x in ts_dict, 'unsupported time signature: ' + str(x)
    return ts_dict[x]


def dec_time_sig(x):
    return ts_list[x]


def enc_dur(x):
    return dur_enc[x] if x < len(dur_enc) else dur_enc[-1]


def dec_dur(x):
    return dur_dec[x] if x < len(dur_dec) else dur_dec[-1]


def enc_vel(x):
    return x // velocity_quant


def dec_vel(x):
    return (x * velocity_quant) + (velocity_quant // 2)


def enc_tempo(x):
    x = max(x, min_tempo)
    x = min(x, max_tempo)
    x = x / min_tempo
    e = round(math.log2(x) * tempo_quant)
    return e


def dec_tempo(x):
    return 2 ** (x / tempo_quant) * min_tempo


def enc_chord(x):
    assert x in chord_dict, f'unsupported chord: {x}'
    return chord_dict[x]


def dec_chord(x):
    assert x >= 0, f'pitch {x} not chord'
    assert x < len(chord_list), f'unvalid pitch {x}'
    return chord_list[x]


def time_signature_reduce(numerator, denominator):
    # reduction (when denominator is too large)
    while denominator > 2 ** max_ts_denominator and denominator % 2 == 0 and numerator % 2 == 0:
        denominator //= 2
        numerator //= 2
    # decomposition (when length of a bar exceed max_notes_per_bar)
    while numerator > max_notes_per_bar * denominator:
        for i in range(2, numerator + 1):
            if numerator % i == 0:
                numerator //= i
                break
    return numerator, denominator


class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def writer(output_str_list):
    with open(output_file, 'a') as f:
        for output_str in output_str_list:
            f.write(output_str + '\n')


def gen_dictionary(file_name):
    num = 0
    with open(file_name, 'w') as f:
        for i in range(bar_max):
            print('<0-{}>'.format(i), num, file=f)
        for i in range(beat_note_factor * max_notes_per_bar * pos_resolution):
            print('<1-{}>'.format(i), num, file=f)
        for i in range(129):
            print('<2-{}>'.format(i), num, file=f)  # 128 for percussion
        for i in range(256):
            print('<3-{}>'.format(i), num, file=f)  # 128~255 for percussion
        for i in range(duration_max * pos_resolution):
            print('<4-{}>'.format(i), num, file=f)
        for i in range(enc_vel(127) + 1):
            print('<5-{}>'.format(i), num, file=f)
        for i in range(len(ts_list)):
            print('<6-{}>'.format(i), num, file=f)
        for i in range(enc_tempo(max_tempo) + 1):
            print('<7-{}>'.format(i), num, file=f)
        for i in range(len(chord_list)):
            print('<8-{}>'.format(i), num, file=f)


def midi_to_encoding(midi_obj):
    def time_to_pos(t):
        return round(t * pos_resolution / midi_obj.ticks_per_beat)

    notes_start_pos = []
    max_pos = 0
    for instru in midi_obj.instruments:
        for note in instru.notes:
            pos = time_to_pos(note.start)
            notes_start_pos.append(pos)
            if pos > max_pos:
                max_pos = pos
    if len(notes_start_pos) == 0:
        return list()
    max_pos = min(max_pos + 1, trunc_pos)
    pos_to_info = [[None, None, None, None, None] for _ in range(max_pos)]  # (Measure, TimeSig, Pos, Tempo, Chord)
    time_signature_changes = midi_obj.time_signature_changes
    ts_pos = [time_to_pos(item.time) for item in time_signature_changes]
    tempo_changes = midi_obj.tempo_changes
    tempo_pos = [time_to_pos(item.time) for item in tempo_changes]

    tot = len(time_signature_changes)
    for i in range(tot):
        start = ts_pos[i]
        end = ts_pos[i + 1] if i + 1 < tot else max_pos
        end = min(end, max_pos)
        for j in range(start, end):
            ts = time_signature_reduce(time_signature_changes[i].numerator, time_signature_changes[i].denominator)
            pos_to_info[j][1] = enc_time_sig(ts)
        if end == max_pos:
            break

    tot = len(tempo_changes)
    for i in range(tot):
        start = tempo_pos[i]
        end = tempo_pos[i + 1] if i + 1 < tot else max_pos
        end = min(end, max_pos)
        for j in range(start, end):
            pos_to_info[j][3] = enc_tempo(tempo_changes[i].tempo)
        if end == max_pos:
            break

    for j in range(max_pos):
        if pos_to_info[j][1] is None:
            pos_to_info[j][1] = enc_time_sig(time_signature_reduce(4, 4))  # midi default time signature
        if pos_to_info[j][3] is None:
            pos_to_info[j][3] = enc_tempo(120.0)  # midi default tempo (BPM)

    for marker in midi_obj.markers:
        pos = time_to_pos(time_to_pos(marker.time))
        if pos >= max_pos:
            continue
        try:
            chord = enc_chord(marker.text)
        except:
            continue
        pos_to_info[j][4] = chord

    last = enc_chord(NO_CHORD)
    for j in range(max_pos):
        if pos_to_info[j][4] is None:
            pos_to_info[j][4] = last
        else:
            last = pos_to_info[j][4]

    cnt = 0
    bar = 0
    measure_length = None
    for j in range(len(pos_to_info)):
        ts = dec_time_sig(pos_to_info[j][1])
        if cnt == 0:
            measure_length = ts[0] * beat_note_factor * pos_resolution // ts[1]
        pos_to_info[j][0] = bar
        pos_to_info[j][2] = cnt
        cnt += 1
        if cnt >= measure_length:
            assert cnt == measure_length, 'invalid time signature change: pos = {}'.format(j)
            cnt -= measure_length
            bar += 1

    encoding = []
    start_distribution = [0] * pos_resolution
    for inst in midi_obj.instruments:
        for note in inst.notes:
            pos = time_to_pos(note.start)
            if pos >= trunc_pos:
                continue
            start_distribution[pos % pos_resolution] += 1
            bar, time_sig, pos, tempo, chord = pos_to_info[pos]
            encoding.append((bar,
                             pos,
                             128 if inst.is_drum else inst.program,
                             note.pitch + 128 if inst.is_drum else note.pitch,
                             enc_dur(time_to_pos(note.end) - time_to_pos(note.start)),
                             enc_vel(note.velocity),
                             time_sig,
                             tempo,
                             chord
                             ))
    if len(encoding) == 0:
        return list()

    tot = sum(start_distribution)
    start_ppl = 2 ** sum((0 if x == 0 else -(x / tot) * math.log2((x / tot)) for x in start_distribution))
    # filter unaligned music
    if filter_symbolic:
        assert start_ppl <= filter_symbolic_ppl, 'filtered out by the symbolic filter: ppl = {:.2f}'.format(start_ppl)
    encoding.sort()
    return encoding


def encoding_to_midi(encoding):
    # TODO: filter out non-valid notes and error handling
    bar_to_timesig = [list() for _ in range(max(map(lambda x: x[0], encoding)) + 1)]
    for i in encoding:
        bar_to_timesig[i[0]].append(i[6])
    bar_to_timesig = [max(set(i), key=i.count) if len(i) > 0 else None for i in bar_to_timesig]
    for i in range(len(bar_to_timesig)):
        if bar_to_timesig[i] is None:
            bar_to_timesig[i] = enc_time_sig(time_signature_reduce(4, 4)) if i == 0 else bar_to_timesig[i - 1]
    bar_to_pos = [None] * len(bar_to_timesig)
    cur_pos = 0
    for i in range(len(bar_to_pos)):
        bar_to_pos[i] = cur_pos
        ts = dec_time_sig(bar_to_timesig[i])
        measure_length = ts[0] * beat_note_factor * pos_resolution // ts[1]
        cur_pos += measure_length
    pos_to_tempo = [list() for _ in range(cur_pos + max(map(lambda x: x[1], encoding)))]
    for i in encoding:
        pos_to_tempo[bar_to_pos[i[0]] + i[1]].append(i[7])
    pos_to_tempo = [round(sum(i) / len(i)) if len(i) > 0 else None for i in pos_to_tempo]
    for i in range(len(pos_to_tempo)):
        if pos_to_tempo[i] is None:
            pos_to_tempo[i] = enc_tempo(120.0) if i == 0 else pos_to_tempo[i - 1]
    midi_obj = miditoolkit.midi.parser.MidiFile()

    def get_tick(bar, pos):
        return (bar_to_pos[bar] + pos) * midi_obj.ticks_per_beat // pos_resolution

    midi_obj.instruments = [
        miditoolkit.containers.Instrument(program=(0 if i == 128 else i), is_drum=(i == 128), name=str(i)) for i in
        range(128 + 1)]
    for i in encoding:
        start = get_tick(i[0], i[1])
        program = i[2]
        pitch = (i[3] - 128 if program == 128 else i[3])
        duration = get_tick(0, dec_dur(i[4]))
        end = start + duration
        velocity = dec_vel(i[5])
        midi_obj.instruments[program].notes.append(
            miditoolkit.containers.Note(start=start, end=end, pitch=pitch, velocity=velocity))
    midi_obj.instruments = [i for i in midi_obj.instruments if len(i.notes) > 0]
    cur_ts = None
    for i in range(len(bar_to_timesig)):
        new_ts = bar_to_timesig[i]
        if new_ts != cur_ts:
            numerator, denominator = dec_time_sig(new_ts)
            midi_obj.time_signature_changes.append(
                miditoolkit.containers.TimeSignature(numerator=numerator, denominator=denominator, time=get_tick(i, 0)))
            cur_ts = new_ts
    cur_tp = None
    for i in range(len(pos_to_tempo)):
        new_tp = pos_to_tempo[i]
        if new_tp != cur_tp:
            tempo = dec_tempo(new_tp)
            midi_obj.tempo_changes.append(miditoolkit.containers.TempoChange(tempo=tempo, time=get_tick(0, i)))
            cur_tp = new_tp
    return midi_obj


def get_hash(encoding):
    midi_tuple = tuple((i[2], i[3]) for i in encoding)  # add i[4] and i[5] for stricter match
    midi_hash = hashlib.md5(str(midi_tuple).encode('ascii')).hexdigest()
    return midi_hash


def process(file_name):
    # try_times = 10
    # midi_file = None
    # for _ in range(try_times):
    # try:
    #     # lock_file.acquire()
    #     # with data_zip.open(file_name) as f:
    #     #     midi_file = io.BytesIO(f.read())  # this may fail due to unknown bug
    # except BaseException as e:
    #     try_times -= 1
    #     time.sleep(1)
    #     if try_times == 0:
    #         print('ERROR(READ): ' + file_name + ' ' + str(e) + '\n', end='')
    #         return None
    # finally:
    #     lock_file.release()
    try:
        # with timeout(seconds=600):
        #     midi_obj = miditoolkit.midi.parser.MidiFile(file=midi_file)
        midi_obj = miditoolkit.midi.parser.MidiFile(file_name)
        # check abnormal values in parse result
        assert all(0 <= j.start < 2 ** 31 and 0 <= j.end < 2 ** 31 for i in midi_obj.instruments for j in
                   i.notes), 'bad note time'
        assert all(0 < j.numerator < 2 ** 31 and 0 < j.denominator < 2 ** 31 for j in
                   midi_obj.time_signature_changes), 'bad time signature value'
        assert 0 < midi_obj.ticks_per_beat < 2 ** 31, 'bad ticks per beat'
    except BaseException as e:
        print('ERROR(PARSE): ' + file_name + ' ' + str(e) + '\n', end='')
        return None
    midi_notes_count = sum(len(inst.notes) for inst in midi_obj.instruments)
    if midi_notes_count == 0:
        print('ERROR(BLANK): ' + file_name + '\n', end='')
        return None
    try:
        enc = midi_to_encoding(midi_obj)
        if len(enc) == 0:
            print('ERROR(BLANK): ' + file_name + '\n', end='')
            return None
        if ts_filter:
            allowed_ts = enc_time_sig(time_signature_reduce(4, 4))
            if not all(i[6] == allowed_ts for i in enc):
                print('ERROR(TSFILT): ' + file_name + '\n', end='')
                return None
        if deduplicate:
            duplicated = False
            dup_file_name = ''
            midi_hash = '0' * 32
            try:
                midi_hash = get_hash(enc)
            except:
                pass
            lock_set.acquire()
            if midi_hash in midi_dict:
                dup_file_name = midi_dict[midi_hash]
                duplicated = True
            else:
                midi_dict[midi_hash] = file_name
            lock_set.release()
            if duplicated:
                print('ERROR(DUPLICATED): ' + midi_hash + ' ' + file_name + ' == ' + dup_file_name + '\n', end='')
                return None
        output_str_list = []
        sample_step = max(round(sample_len_max / sample_overlap_rate), 1)
        enc = adaptor(enc)
        for p in range(0 - random.randint(0, sample_len_max - 1), len(enc), sample_step):
            L = max(p, 0)
            R = min(p + sample_len_max, len(enc)) - 1
            bar_index_list = [enc[i][0] for i in range(L, R + 1) if enc[i][0] is not None]
            bar_index_min = 0
            bar_index_max = 0
            if len(bar_index_list) > 0:
                bar_index_min = min(bar_index_list)
                bar_index_max = max(bar_index_list)
            offset_lower_bound = -bar_index_min
            offset_upper_bound = bar_max - 1 - bar_index_max
            bar_index_offset = random.randint(offset_lower_bound,
                                              offset_upper_bound) if offset_lower_bound <= offset_upper_bound else offset_lower_bound  # to make bar index distribute in [0, bar_max)
            e_segment = []
            for i in enc[L: R + 1]:
                if i[0] is None or i[0] + bar_index_offset < bar_max:
                    e_segment.append(i)
                else:
                    break
            output_words = (['<s>'] * 9) + [
                ('<{}-{}>'.format(j, k if j > 0 else k + bar_index_offset) if k is not None else '<unk>') for i in
                e_segment for j, k in enumerate(i)] + (['</s>'] * 9)
            if not use_compound_word():
                output_words = [word for word in output_words if word != '<unk>']
            output_str_list.append(' '.join(output_words))
        if not all(len(i.split()) > 16 for i in output_str_list):
            print('ERROR(ENCODE): ' + file_name + ' ' + str(enc) + '\n', end='')
            return False
        try:
            lock_write.acquire()
            writer(output_str_list)
        except BaseException as e:
            print('ERROR(WRITE): ' + file_name + ' ' + str(e) + '\n', end='')
            return False
        finally:
            lock_write.release()
        print('SUCCESS: ' + file_name + '\n', end='')
        return True
    except BaseException as e:
        print('ERROR(PROCESS): ' + file_name + ' ' + str(e) + '\n', end='')
        return False
    print('ERROR(GENERAL): ' + file_name + '\n', end='')
    return False


def process_with_catch(file_name):
    try:
        return process(file_name)
    except:
        print('ERROR(UNCAUGHT): ' + file_name + '\n', end='')
        return False


def str_to_encoding(s):
    encoding = [int(i[3: -1]) for i in s.split() if 's' not in i]
    assert len(encoding) % 8 == 0
    encoding = [tuple(encoding[i + j] for j in range(8)) for i in range(0, len(encoding), 8)]
    return encoding


def encoding_to_str(e):
    bar_index_offset = 0
    p = 0
    return (' '.join(
        (['<s>'] * 8) + ['<{}-{}>'.format(j, k if j > 0 else k + bar_index_offset) for i in e[p: p + sample_len_max] if
                         i[0] + bar_index_offset < bar_max for j, k in enumerate(i)] + (['</s>'] * 8)))


if __name__ == '__main__':
    # lock_file = Lock()
    lock_write = Lock()
    lock_set = Lock()
    manager = Manager()
    midi_dict = manager.dict()
    # data_path = input('Dataset zip path: ')
    prefix = '.'
    # # prefix = input('Octuplemidi output path: ')
    # if os.path.exists(prefix):
    #     print('Output path {} already exists!'.format(prefix))
    #     sys.exit(0)
    # encoding = input('Encoding: ')
    # assert encoding in ['OCTmidi', 'CP', 'REMI'], 'Encoding not supported'
    # os.system('mkdir -p {}'.format(prefix))
    # data_zip = zipfile.ZipFile(data_path, 'r')
    # file_list = [n for n in data_zip.namelist() if n[-4:].lower() == '.mid' or n[-5:].lower() == '.midi']
    file_list = ['test2.mid']
    random.shuffle(file_list)
    gen_dictionary('{}/dict.txt'.format(prefix))
    ok_cnt = 0
    all_cnt = 0
    output_file = '{}/midi.txt'.format(prefix)
    process_with_catch(file_list[0])
    # for sp in ['train', 'valid', 'test']:
    #     total_file_cnt = len(file_list)
    #     file_list_split = []
    #     if sp == 'train':  # 98%
    #         file_list_split = file_list[: 98 * total_file_cnt // 100]
    #     if sp == 'valid':  # 1%
    #         file_list_split = file_list[98 * total_file_cnt // 100: 99 * total_file_cnt // 100]
    #     if sp == 'test':  # 1%
    #         file_list_split = file_list[99 * total_file_cnt // 100:]
    #     output_file = '{}/midi_{}.txt'.format(prefix, sp)
    #     with Pool(24) as p:
    #         result = list(p.imap_unordered(process_with_catch, file_list_split))
    #         all_cnt += sum((1 if i is not None else 0 for i in result))
    #         ok_cnt += sum((1 if i is True else 0 for i in result))
    #     output_file = None
    # print('{}/{} ({:.2f}%) midi files successfully processed'.format(ok_cnt, all_cnt, ok_cnt / all_cnt * 100))
