def do_sort_insts_based_on_id(insts):
    return sorted(insts)


def do_sort_insts_based_6tracks_customization1(insts):
    keys = {
        0: 5,  # Piano
        25: 4,  # Guitar
        32: 3,  # Bass
        48: 6,  # String Ensemble 1
        80: 1,  # Synth Lead 1
        128: 2,  # Percussion
    }
    return sorted(insts, key=lambda x: keys[x])


inst_sorting_dict = {
    'id': do_sort_insts_based_on_id,
    '6tracks_cst1': do_sort_insts_based_6tracks_customization1
}


def get_inst_sorting_method(i):
    if i is None:
        return inst_sorting_dict['id']
    if isinstance(i, str):
        return inst_sorting_dict[i]
    return i

