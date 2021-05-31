# Author: Botao Yu
import numpy as np


def get_notes_from_pos_info(pos_info):
    notes = []
    for bar, ts, pos, tempo, insts_notes in pos_info:
        if insts_notes is None:
            continue
        for inst_id in insts_notes:
            if inst_id == 128:
                continue
            inst_notes = insts_notes[inst_id]
            for note in inst_notes:
                notes.append(note)
    return notes


def get_pitch_class_histogram(notes, normalize=True):
    weights = np.ones(len(notes))
    # Assumes that duration and velocity have equal weight
    # (pitch, duration, velocity, pos_end)
    # if use_duration:
    #     weights *= [note[1] for note in notes]  # duration
    # if use_velocity:
    #     weights *= [note[2] for note in notes]  # velocity
    histogram, _ = np.histogram([note[0] % 12 for note in notes], bins=np.arange(13), weights=weights,
                                density=normalize)
    if normalize:
        histogram /= (histogram.sum() + (histogram.sum() == 0))
    return histogram


def get_pitch_shift(pos_info, key_profile, use_duration=True):
    notes = get_notes_from_pos_info(pos_info)
    if len(notes) == 0:
        return 0
    histogram = get_pitch_class_histogram(notes)
    key_candidate = np.dot(key_profile, histogram)
    key_temp = np.where(key_candidate == max(key_candidate))
    try:
        major_index = key_temp[0][0]
        minor_index = key_temp[0][1]
    except IndexError:
        print(len(notes))
        print(notes)
        print(histogram)
        print(key_candidate)
        print(key_temp)
        raise
    major_count = histogram[major_index]
    minor_count = histogram[minor_index % 12]
    if major_count < minor_count:
        key_number = minor_index
    else:
        key_number = major_index
    real_key = key_number
    # transpose to C major or A minor
    if real_key <= 11:
        trans = 0 - real_key
    else:
        trans = 21 - real_key
    pitch_shift = trans
    return pitch_shift
